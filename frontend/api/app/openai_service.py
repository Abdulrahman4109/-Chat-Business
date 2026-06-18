import json
from openai import AsyncOpenAI
from .config import get_settings
from .heuristics import heuristic_extract, merge_extractions
from .models import FinancialData


SYSTEM_PROMPT = """You are a financial data extraction engine.
Return ONLY valid JSON. No markdown, no comments, no extra text.

Extract every numeric financial value from the user's text and classify values into:
- goal_price: total target cost or goal amount (e.g. "car worth X", "buy X", "goal of X", "need X")
- monthly_income: recurring monthly income or salary (DO NOT include bonuses, commissions, overtime, or side income here)
- monthly_expenses: recurring monthly expenses, spending, rent, bills, debts, or costs
- current_savings: current saved amount, cash, bank balance, or amount already available (NEVER add goal_price to savings)
- extra_income: SUM of ALL recurring extra monthly incomes (bonuses + commissions + overtime + side income + freelancing + additional income)

Rules:
- Never fail and never return text outside JSON.
- Never say missing and never return an error.
- Extract what is available even in mixed Arabic and English.
- Use null only when goal_price or monthly_income is not mentioned anywhere.
- Return monthly_expenses as 0 when expenses are absent.
- Use 0 for current_savings or extra_income when absent.
- Convert shorthand like 5k to 5000.
- Do not perform timeline math.
- DO NOT count salaries, wages, or base income as extra_income.
- DO NOT count bonuses, commissions, or side income as monthly_income.
- DO NOT add goal_price to current_savings — they are separate.
- "I have X savings" or "X saved" means X is current_savings.
- "I earn X salary" means X is monthly_income.
- "X bonuses", "X commission", "X extra" means X is extra_income. ALWAYS include bonuses in extra_income.
- "want a car worth X", "buy X car", "goal of X" means X is goal_price.

JSON shape:
{
  "goal_price": number|null,
  "monthly_income": number|null,
  "monthly_expenses": number,
  "current_savings": number,
  "extra_income": number
}
"""


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

    async def extract(self, message: str, token_numbers: list[float]) -> FinancialData:
        fallback = heuristic_extract(message, token_numbers)
        if self.client is None:
            fallback.assumptions.append("OPENAI_API_KEY is not configured; used deterministic bilingual extraction.")
            return fallback

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ],
                timeout=8,
                max_retries=0,
            )
            content = response.choices[0].message.content or "{}"
        except Exception as e:
            fallback.assumptions.append(f"AI extraction failed; used deterministic extraction. ({e})")
            return fallback

        try:
            parsed = json.loads(content)
            data = FinancialData.model_validate(parsed)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            fallback.assumptions.append(f"AI response was not valid JSON; used deterministic extraction. ({e})")
            return fallback
        data.all_numbers = _dedupe_numbers([*data.all_numbers, *token_numbers])
        return merge_extractions(data, fallback)


def _dedupe_numbers(values: list[float]) -> list[float]:
    result = []
    seen = set()
    for value in values:
        key = round(float(value), 4)
        if key not in seen:
            seen.add(key)
            result.append(float(value))
    return result
