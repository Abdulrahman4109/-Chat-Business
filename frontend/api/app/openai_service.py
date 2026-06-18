import json
import re
from openai import AsyncOpenAI
from .config import get_settings
from .heuristics import heuristic_extract
from .models import FinancialData
from .nlp import extract_entities
from .segmenter import segment_text


def _parse_json_from_text(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        text = text[brace_start : brace_end + 1]
    return json.loads(text)


SEGMENTER_PROMPT = """Split the message into meaningful segments at natural boundaries.

Each segment should be one complete thought. Split at sentence endings (.!?؟) and major topical shifts. Keep numbers attached to their context.

Return at most 12 segments.

Examples:
Input: "I want a car worth 600000. I have 200000 saved. My salary is 10000 and expenses are 4000."
Output: ["I want a car worth 600000.", "I have 200000 saved.", "My salary is 10000 and expenses are 4000."]

Input: "اريد شراء عربة 800000ولدي ادخار20000 مرتب 50000 اسبوعي"
Output: ["اريد شراء عربة 800000", "ولدي ادخار20000", "مرتب 50000 اسبوعي"]

Return ONLY valid JSON: {"segments": ["...", "..."]}
"""

EXTRACTION_PROMPT = """You are a precise financial data extraction engine. Analyze each text segment independently.

For each segment that contains financial information, extract ALL numeric values and classify each into the correct field. CRITICAL: Normalize ALL time units to MONTHLY equivalent before returning the value.

Precise time normalization (standard month = 30 days):
| Input | Conversion | Formula |
|-------|-----------|---------|
| per hour / hourly / بالساعة | × 171.43 | 40h/week × 30/7 days |
| per day / daily / يومياً / في اليوم | × 30 | 30 days/month |
| per week / weekly / اسبوعياً / في الاسبوع / أسبوعياً / كل اسبوع | × 4.2857 | 30 ÷ 7 |
| per 2 weeks / bi-weekly / كل اسبوعين / كل 14 يوم / 15 يوم | × 2.1429 | 30 ÷ 14 |
| per 10 days / كل 10 ايام / عشرة ايام | × 3 | 30 ÷ 10 |
| per month / monthly / شهرياً / في الشهر | as is | — |
| semi-monthly / twice monthly / نصف شهري / مرتين بالشهر / كل 15 يوم | × 2 | 2× per month |
| per 3 months / quarterly / كل 3 شهور / ربع سنوي | ÷ 3 | 3 months |
| per 6 months / semi-annually / كل 6 شهور / نصف سنوي | ÷ 6 | 6 months |
| per year / yearly / annually / سنوياً / في السنة / كل سنة | ÷ 12 | 12 months |
| per 2 years / biennially / كل سنتين | ÷ 24 | 24 months |
If NO time unit mentioned → assume monthly, keep as is

CRITICAL: The conversion table at the top applies to EVERY field equally — monthly_income, monthly_expenses, AND extra_income. ALWAYS normalize to monthly. DO NOT copy example values — COMPUTE using the table multiplier. If input differs from examples, calculate fresh: value × multiplier from table. When NO time unit is mentioned, keep the value as-is (already monthly).

Examples (format reference, do NOT copy values):
=== monthly_income ===
- "مرتب 10000" -> 10000
- "5000 salary" -> 5000
- "مرتب 100 في الساعة" -> 17143
- "50 per hour" -> 8572
- "100 per day" -> 3000
- "مرتب 50000 اسبوعي" -> 214286
- "4,000 per week" -> 17143
- "راتب 30000 كل اسبوعين" -> 64286
- "مرتب 100000 كل 10 ايام" -> 300000
- "quarterly salary 90000" -> 30000
- "مرتب 600000 سنوي" -> 50000
- "120000 per year" -> 10000

=== monthly_expenses ===
- "مصاريف 10000" -> 10000
- "rent 2000" -> 2000
- "ايجار 900 اسبوعي" -> 3857
- "rent 500 per week" -> 2143
- "900 per week expenses" -> 3857
- "30 per day expenses" -> 900
- "bills 12000 quarterly" -> 4000
- "مصاريف 60000 سنوي" -> 5000
- "insurance 12000 per year" -> 1000

=== extra_income ===
- "حوافز 4000" -> 4000
- "اضافي 2000" -> 2000
- "bonus 1500" -> 1500
- "بونص 1000 اسبوعي" -> 4286
- "100 per week bonus" -> 429
- "overtime 20 per hour" -> 3429
- "freelance 300 per day" -> 9000
- "عمولة 60000 سنوي" -> 5000
- "side hustle 12000 per year" -> 1000

=== current_savings (static — do NOT normalize) ===
- "عندي 20000 في البنك" -> 20000
- "savings 10000" -> 10000

=== goal_price (static — do NOT normalize) ===
- "اريد شراء عربة 800000" -> 800000
- "i want a car worth 600000" -> 600000

=== comprehensive English example ===
Input: "I want to buy a car worth 800,000. I have 20,000 in savings. My income is 4,000 per week, with weekly expenses of 900. I also receive 4,000 in bonuses and have an additional income of 2,000."
Computation: income=4000×4.2857=17143, expenses=900×4.2857=3857, bonuses=4000, extra=2000+4000=6000
Output: [{"segment_index":0,"field":"goal_price","value":800000},{"segment_index":1,"field":"current_savings","value":20000},{"segment_index":2,"field":"monthly_income","value":17143},{"segment_index":2,"field":"monthly_expenses","value":3857},{"segment_index":3,"field":"extra_income","value":6000}]

Fields:
- "goal_price": target cost, purchase price, goal amount, what the user wants to buy or save for
- "monthly_income": salary, wage, base recurring income from primary job (ALWAYS normalized to monthly)
- "monthly_expenses": spending, rent, bills, costs, outgoings (ALWAYS normalized to monthly)
- "current_savings": amount ALREADY saved, bank balance, cash on hand (NOT recurring, keep as-is)
- "extra_income": bonuses, commissions, overtime, side income, freelance, part-time, tips (ALWAYS normalized to monthly)

Numbers may use comma separators (e.g. 4,000 = 4000, 800,000 = 800000). Strip commas before computing multiplication.

Return ONLY valid JSON with this exact shape:
{
  "extractions": [
    {"segment_index": 0, "field": "monthly_income", "value": 5000.0}
  ]
}

Rules:
- Segment with NO financial data -> omit from extractions entirely
- One segment may produce MULTIPLE extractions for different fields
- Convert shorthand: 5k = 5000, 2m = 2000000
- NEVER classify base salary/wage as extra_income
- NEVER classify bonuses/commission as monthly_income
- "salary", "wage", "base pay", "earn" -> monthly_income
- "bonuses", "commission", "side", "freelance", "overtime", "tips" -> extra_income
- "want", "buy", "goal", "target", "save for" with amount -> goal_price
- "saved", "savings", "already have", "bank", "cash" -> current_savings
- "spend", "expenses", "rent", "bills", "cost" -> monthly_expenses
- Arabic hints: راتب/مرتب = monthly_income, مصاريف/ايجار/فواتير = monthly_expenses,
  مدخرات/عندي/معايا = current_savings, بونص/اضافي/حوافز = extra_income,
  عايز/هدف/سعر = goal_price

A "NER financial entities detected" section may be appended below. These are automated hints from spaCy — use them to guide classification but always verify against the segment text. MONEY = currency amount, CARDINAL = plain number, DATE = time/period reference, PERCENT = percentage."""


class OpenAIExtractionService:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openai_model
        if settings.openai_api_key:
            client_kwargs = {"api_key": settings.openai_api_key}
            if settings.openai_base_url:
                client_kwargs["base_url"] = settings.openai_base_url
            self.client = AsyncOpenAI(**client_kwargs)
        else:
            self.client = None

    async def segment_with_llm(self, message: str) -> list[str]:
        if self.client is None:
            return segment_text(message)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SEGMENTER_PROMPT},
                    {"role": "user", "content": message},
                ],
                timeout=10,
            )
            content = response.choices[0].message.content or "{}"
            parsed = _parse_json_from_text(content)
            segments = parsed.get("segments", [])
            if segments and isinstance(segments, list):
                return segments
        except Exception:
            pass

        return segment_text(message)

    async def extract(
        self, message: str, token_numbers: list[float], segments: list[str] | None = None
    ) -> FinancialData:
        if segments is None:
            segments = segment_text(message)
        fallback = heuristic_extract(message, token_numbers)

        if self.client is None:
            fallback.assumptions.append("OPENAI_API_KEY not configured; used deterministic extraction.")
            return fallback

        if not segments:
            fallback.assumptions.append("No segments to analyze; used deterministic extraction.")
            return fallback

        try:
            entities = extract_entities(message)
            segment_data = await self._extract_from_segments(segments, token_numbers, entities)
        except Exception as e:
            fallback.assumptions.append(f"Segment extraction failed; used deterministic extraction. ({e})")
            return fallback

        return segment_data

    async def _extract_from_segments(
        self, segments: list[str], token_numbers: list[float], entities: list[dict] | None = None
    ) -> FinancialData:
        segments_text = "\n".join(f"[{i}] {seg}" for i, seg in enumerate(segments))

        entities_text = ""
        if entities:
            entities_text = "\n\nNER financial entities detected in text:\n" + "\n".join(
                f'- {e["label"]}: "{e["text"]}"' for e in entities
            )

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": f"Segments:\n{segments_text}{entities_text}"},
            ],
            timeout=10,
        )

        content = response.choices[0].message.content or "{}"
        parsed = _parse_json_from_text(content)
        extractions = parsed.get("extractions", [])

        return _aggregate_segment_extractions(extractions, token_numbers, segments)


def _aggregate_segment_extractions(
    extractions: list[dict], all_numbers: list[float], segments: list[str]
) -> FinancialData:
    enriched = list(all_numbers)
    for ext in extractions:
        v = ext.get("value")
        if v is not None:
            try:
                enriched.append(float(v))
            except (ValueError, TypeError):
                pass
    data = FinancialData(all_numbers=_dedupe_numbers(enriched))
    goals = []
    seg_map: dict[int, list[dict]] = {}

    for ext in extractions:
        field = ext.get("field")
        value = ext.get("value")
        seg_idx = ext.get("segment_index")
        if field is None or value is None or seg_idx is None:
            continue

        try:
            value = float(value)
        except (ValueError, TypeError):
            continue

        if seg_idx not in seg_map:
            seg_map[seg_idx] = []
        seg_map[seg_idx].append({"field": field, "value": value})

        if field == "goal_price":
            goals.append({"name": "primary goal", "goal_price": value})
            if data.goal_price is None or value > data.goal_price:
                data.goal_price = value
        elif field in ("monthly_income", "monthly_expenses", "current_savings", "extra_income"):
            current = getattr(data, field) or 0
            setattr(data, field, current + value)

    if goals:
        data.goals = goals

    for i, seg_text in enumerate(segments):
        classifications = seg_map.get(i, [])
        data.segments.append({
            "text": seg_text,
            "classifications": classifications,
        })

    return data


def _dedupe_numbers(values: list[float]) -> list[float]:
    result = []
    seen = set()
    for value in values:
        key = round(float(value), 4)
        if key not in seen:
            seen.add(key)
            result.append(float(value))
    return result
