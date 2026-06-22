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


SEGMENTER_PROMPT = """Split the message into segments at natural boundaries. Each segment = one complete financial thought.

Split at sentence endings (.!?؟) and topical shifts. Keep numbers attached to their context. Max 12 segments.

Return ONLY valid JSON: {"segments": ["...", "..."]}
"""

TIME_UNITS = {
    "hourly": 171.43, "per hour": 171.43, "بالساعة": 171.43, "كل ساعة": 171.43,
    "daily": 30, "per day": 30, "يومياً": 30, "في اليوم": 30, "في يوم": 30, "يومي": 30, "يومية": 30, "يوميا": 30, "كل يوم": 30,
    "weekly": 4.2857, "per week": 4.2857, "اسبوعياً": 4.2857, "في الاسبوع": 4.2857, "في الأسبوع": 4.2857, "كل اسبوع": 4.2857, "كل أسبوع": 4.2857, "أسبوعياً": 4.2857, "اسبوعي": 4.2857, "اسبوع": 4.2857, "اسبوعيه": 4.2857, "أسبوعي": 4.2857,
    "biweekly": 2.1429, "bi-weekly": 2.1429, "كل اسبوعين": 2.1429, "كل أسبوعين": 2.1429, "كل 14 يوم": 2.1429, "15 يوم": 2.1429, "اسبوعين": 2.1429,
    "tendays": 3, "كل 10 ايام": 3, "كل 10 أيام": 3, "عشرة ايام": 3, "عشرة أيام": 3,
    "monthly": 1, "per month": 1, "شهرياً": 1, "في الشهر": 1, "شهري": 1, "شهر": 1, "شهرية": 1, "شهريه": 1, "شهريا": 1, "كل شهر": 1, "شهري": 1,
    "semimonthly": 2, "semi-monthly": 2, "نصف شهري": 2, "مرتين بالشهر": 2,
    "quarterly": 1/3, "كل 3 شهور": 1/3, "كل ٣ شهور": 1/3, "ربع سنوي": 1/3, "ربع سنة": 1/3,
    "semiannually": 1/6, "semi-annually": 1/6, "كل 6 شهور": 1/6, "كل ٦ شهور": 1/6, "نصف سنوي": 1/6, "نصف سنة": 1/6,
    "yearly": 1/12, "per year": 1/12, "annually": 1/12, "سنوياً": 1/12, "في السنة": 1/12, "كل سنة": 1/12, "سنوي": 1/12, "سنويه": 1/12, "سنوية": 1/12, "سنة": 1/12, "سنويا": 1/12, "كل عام": 1/12,
    "biennially": 1/24, "كل سنتين": 1/24, "سنتين": 1/24, "كل عامين": 1/24,
}

# General regex patterns for time units not in the dictionary (e.g. "every 2 months", "each week")
_TIME_GENERAL_PATTERNS = [
    (r'كل\s+(\d+)\s+(شهر|شهور|سنة|سنين|ايام|اسابيع|يوم|اسبوع)', lambda m: int(m.group(1))),
    (r'(\d+)\s+(شهر|شهور|سنة|سنين|ايام|اسابيع|يوم|اسبوع)\s+(\w+)', lambda m: int(m.group(1))),
    (r'every\s+(\d+)\s+(month|year|week|day)', lambda m: int(m.group(1))),
    (r'(\d+)\s+(months|years|weeks|days)\s+(per|every|each)', lambda m: int(m.group(1))),
    (r'per\s+(month|year|week|day|hour)', lambda m: 1),
    (r'each\s+(month|year|week|day)', lambda m: 1),
]

# Regex patterns for time unit extraction (longer/more specific first)
_TIME_PATTERNS = sorted(TIME_UNITS.keys(), key=len, reverse=True)


def _canonical_unit(pattern: str) -> str:
    m = TIME_UNITS[pattern]
    if m == 1/12: return "yearly"
    if m == 1/24: return "biennially"
    if m == 1/3: return "quarterly"
    if m == 1/6: return "semiannually"
    if m == 2: return "semimonthly"
    if m == 2.1429: return "biweekly"
    if m == 3: return "tendays"
    if m == 30: return "daily"
    if m == 171.43: return "hourly"
    if m == 4.2857: return "weekly"
    if m == 1: return "monthly"
    return pattern


def extract_time_unit(text: str, raw_value: float | None = None) -> str:
    text_lower = text.strip().rstrip('.,!?;:،؛.\n\r').lower()
    val_str = f"{raw_value:.0f}" if raw_value is not None and raw_value == int(raw_value) else str(raw_value) if raw_value is not None else None
    if not val_str:
        return ""
    val_pattern = r'(?<!\d)' + re.escape(val_str) + r'(?!\d)'
    if not re.search(val_pattern, text_lower):
        return ""
    # 1) NUMBER + time unit (allow 1 word between)
    for pattern in _TIME_PATTERNS:
        m = re.search(val_pattern + r'(?:\s+\S+){0,1}\s*' + re.escape(pattern) + r'(?:\s|$)', text_lower)
        if m:
            return _canonical_unit(pattern)
    # 2) TIME UNIT + NUMBER (allow 1 word between)
    for pattern in _TIME_PATTERNS:
        m = re.search(re.escape(pattern) + r'(?:\s+\S+){0,1}\s*' + val_pattern + r'(?:\s|$)', text_lower)
        if m:
            return _canonical_unit(pattern)
    # 3) General patterns like "كل 3 شهور", "every 2 months"
    for pat_re, multiplier_fn in _TIME_GENERAL_PATTERNS:
        m = re.search(pat_re, text_lower)
        if m:
            span = m.span()
            base = m.group(0)
            before = text_lower[:span[0]]
            after = text_lower[span[1]:]
            if re.search(val_pattern, before[-len(val_str)-15:]) or re.search(val_pattern, after[:len(val_str)+15]):
                count = multiplier_fn(m)
                if 'شهر' in base or 'شهور' in base or 'month' in base:
                    return f"__MULT_{1/count}__"
                if 'سن' in base or 'year' in base:
                    return f"__MULT_{1/(12*count)}__"
                if 'اسبوع' in base or 'week' in base:
                    weekly_mult = TIME_UNITS.get('weekly', 4.2857)
                    return f"__MULT_{weekly_mult/count}__"
                if 'يوم' in base or 'day' in base:
                    daily_mult = TIME_UNITS.get('daily', 30)
                    return f"__MULT_{daily_mult/count}__"
                return f"__MULT_{1/count}__"
    return ""


def normalize_value(raw_value: float, time_unit: str) -> float:
    unit = (time_unit or "").strip().lower()
    if not unit:
        return raw_value
    # Handle computed multipliers from general patterns (e.g. "__MULT_0.5__")
    if unit.startswith("__mult_"):
        try:
            multiplier = float(unit.split("__mult_")[1].rstrip("_"))
            return round(raw_value * multiplier, 2)
        except (ValueError, IndexError):
            return raw_value
    multiplier = TIME_UNITS.get(unit)
    if multiplier is not None:
        return round(raw_value * multiplier, 2)
    return raw_value


EXTRACTION_PROMPT = """You are a financial data extraction engine. Classify each number into the correct field.

Fields by meaning:
- goal_price: target amount user wants to reach (هدف, عاوز, شراء)
- monthly_income: the MAIN salary/income only (مرتب, راتب, قبض, أجر أساسي)
- monthly_expenses: regular spending (مصاريف, إيجار, فواتير)
- current_savings: one-time ASSETS the user OWNS (cash, عقار, سيارة, أسهم, شيكات, أوراق قبض, ودائع, أرض, any physical or financial asset the user already has)
- extra_income: ANY extra money beyond the main salary (حوافز, مكافآت, اضافي, إضافي, بدل, علاوة, عمولة, commission, overtime, bonus, extra income, secondary income, side income)
- current_debts: amounts the user OWES (قروض, أوراق دفع, ديون)

IMPORTANT: حوافز, مكافآت, اضافي, بدل, علاوة ALL go to extra_income, regardless of time words.

time_unit: set when a word tells you the FREQUENCY (how often): يومي, اسبوعي, شهرياً, سنوياً, في الاسبوع, في الشهر, كل شهر, كل سنة, per week, etc.
Do NOT set time_unit when the word just describes a TYPE (e.g. "مرتب شهري" = standard salary, not a frequency).
The same word can be TYPE in one context and FREQUENCY in another — think about the meaning.

Examples:
{"segment_index": 0, "field": "monthly_income", "raw_value": 4000.0, "time_unit": ""}       ← "مرتب شهري 40000" (شهري describes type of salary)
{"segment_index": 0, "field": "monthly_income", "raw_value": 4000.0, "time_unit": "weekly"}← "مرتب 4000 في الاسبوع" (في الاسبوع = frequency)
{"segment_index": 0, "field": "monthly_income", "raw_value": 3000.0, "time_unit": "weekly"} ← "قبض اسبوعي 3000" (weekly salary = frequency)
{"segment_index": 0, "field": "monthly_expenses", "raw_value": 100.0, "time_unit": "daily"}← "مصاريف يومية 100" (daily = frequency)
{"segment_index": 0, "field": "monthly_expenses", "raw_value": 6000.0, "time_unit": ""}     ← "مصاريف شهرية 6000" (general expense type)
{"segment_index": 0, "field": "extra_income", "raw_value": 4000.0, "time_unit": "weekly"}   ← "اسبوعي حوافز 4000" (weekly = frequency)
{"segment_index": 0, "field": "extra_income", "raw_value": 2000.0, "time_unit": ""}         ← "اضافي 2000" (no time word)
{"segment_index": 0, "field": "current_savings", "raw_value": 1000000.0, "time_unit": ""}   ← "عقار بقيمة 1000000"
{"segment_index": 0, "field": "current_savings", "raw_value": 30000.0, "time_unit": ""}     ← "اسهم بقيمة 30000"
{"segment_index": 0, "field": "current_debts", "raw_value": 9000.0, "time_unit": ""}        ← "اوراق دفع بقيمة 9000"

Return ONLY valid JSON: {"extractions": [...]}"""


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
            segments = await self.segment_with_llm(message)
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
        v = ext.get("raw_value") or ext.get("value")
        if v is not None:
            try:
                enriched.append(float(v))
            except (ValueError, TypeError):
                pass
    data = FinancialData(all_numbers=_dedupe_numbers(enriched))
    goals = []
    seg_map: dict[int, list[dict]] = {}

    # Resolve conflicts: same raw_value in competing fields (income/savings/extra)
    # Keep only the highest-priority assignment (extra_income > current_savings > monthly_income)
    # Only conflicts apply between these 3 fields, not with expenses/debts/goal
    conflict_fields = {"monthly_income", "current_savings", "extra_income"}
    field_priority = {"extra_income": 0, "current_savings": 1, "monthly_income": 2}
    seen_values: dict[tuple, dict] = {}
    resolved = []
    for ext in extractions:
        field = ext.get("field")
        raw_value = ext.get("raw_value") or ext.get("value")
        seg_idx = ext.get("segment_index")
        if field is None or raw_value is None or seg_idx is None:
            resolved.append(ext)
            continue
        try:
            raw_value = float(raw_value)
        except (ValueError, TypeError):
            resolved.append(ext)
            continue
        if field not in conflict_fields:
            resolved.append(ext)
            continue
        key = (round(raw_value, 2), seg_idx)
        if key not in seen_values:
            seen_values[key] = {"field": field, "raw_value": raw_value, "seg_idx": seg_idx, "ext": ext}
        elif field_priority.get(field, 99) < field_priority.get(seen_values[key]["field"], 99):
            seen_values[key] = {"field": field, "raw_value": raw_value, "seg_idx": seg_idx, "ext": ext}
    resolved.extend(v["ext"] for v in seen_values.values())

    # Apply resolved extractions
    for ext in resolved:
        field = ext.get("field")
        raw_value = ext.get("raw_value") or ext.get("value")
        seg_idx = ext.get("segment_index")
        if field is None or raw_value is None or seg_idx is None:
            continue

        try:
            raw_value = float(raw_value)
        except (ValueError, TypeError):
            continue

        seg_text = segments[seg_idx] if seg_idx < len(segments) else ""
        time_unit = ext.get("time_unit", "") or extract_time_unit(seg_text, raw_value)

        if field == "extra_income" and not time_unit:
            time_unit = "monthly"

        if field == "monthly_expenses" and not time_unit:
            time_unit = "monthly"

        value = normalize_value(raw_value, time_unit)

        if seg_idx not in seg_map:
            seg_map[seg_idx] = []
        seg_map[seg_idx].append({"field": field, "raw_value": raw_value, "time_unit": time_unit, "value": value})

        if field == "goal_price":
            goals.append({"name": "primary goal", "goal_price": value})
            if data.goal_price is None or value > data.goal_price:
                data.goal_price = value
        elif field in ("monthly_income", "monthly_expenses", "current_savings", "extra_income", "current_debts"):
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
