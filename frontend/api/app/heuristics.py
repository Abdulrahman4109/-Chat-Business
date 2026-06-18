import re
from dataclasses import dataclass
from .models import FinancialData


ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


@dataclass(frozen=True)
class NumberMention:
    value: float
    start: int
    end: int


def normalize_text(text: str) -> str:
    return text.translate(ARABIC_DIGITS)


def extract_number_mentions(text: str) -> list[NumberMention]:
    normalized = normalize_text(text)
    mentions = []
    pattern = r"(?:[$€£])?\s*\d+(?:,\d{3})*(?:\.\d+)?[kKmM]?"
    for match in re.finditer(pattern, normalized):
        value = normalize_number(match.group())
        if value is not None:
            mentions.append(NumberMention(value=value, start=match.start(), end=match.end()))
    return mentions


def normalize_number(raw: str) -> float | None:
    cleaned = raw.translate(ARABIC_DIGITS).replace(",", "").replace(" ", "").strip().lower()
    multiplier = 1
    if cleaned.endswith("k"):
        multiplier = 1_000
        cleaned = cleaned[:-1]
    elif cleaned.endswith("m"):
        multiplier = 1_000_000
        cleaned = cleaned[:-1]
    cleaned = re.sub(r"^[^\d.]+|[^\d.]+$", "", cleaned)
    if not cleaned:
        return None
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None


def heuristic_extract(message: str, token_numbers: list[float]) -> FinancialData:
    text = normalize_text(message)
    mentions = extract_number_mentions(text)
    data = FinancialData(all_numbers=_dedupe_numbers([*[m.value for m in mentions], *token_numbers]))
    return apply_intelligent_defaults(data)


def apply_intelligent_defaults(data: FinancialData) -> FinancialData:
    normalized = data.model_copy(deep=True)
    if normalized.current_savings is None:
        normalized.current_savings = 0
    if normalized.extra_income is None:
        normalized.extra_income = 0
    if normalized.monthly_expenses is None:
        normalized.monthly_expenses = 0
    if normalized.goal_price is not None and not normalized.goals:
        normalized.goals = [{"name": "primary goal", "goal_price": normalized.goal_price}]
    normalized.assumptions = _dedupe_strings(normalized.assumptions)
    return normalized


def _dedupe_numbers(values: list[float]) -> list[float]:
    result = []
    seen = set()
    for value in values:
        key = round(float(value), 4)
        if key not in seen:
            seen.add(key)
            result.append(float(value))
    return result


def _dedupe_strings(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
