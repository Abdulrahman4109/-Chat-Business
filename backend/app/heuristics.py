import re
from dataclasses import dataclass
from .models import FinancialData


ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

FIELD_KEYWORDS = {
    "extra_income": [
        "extra",
        "side",
        "freelance",
        "bonus",
        "sometimes get",
        "additional",
        "اضافي",
        "إضافي",
        "زيادة",
        "فريلانس",
        "مكافأة",
        "باخد",
        "بآخد",
        "اخد",
    ],
    "current_savings": [
        "saved",
        "savings",
        "save",
        "have",
        "with me",
        "already",
        "bank",
        "cash",
        "عندي",
        "معايا",
        "مدخر",
        "مدخرات",
        "محوش",
        "موفر",
    ],
    "monthly_expenses": [
        "spend",
        "expenses",
        "expense",
        "rent",
        "bills",
        "costs",
        "pay",
        "بصرف",
        "اصرف",
        "مصروف",
        "مصاريف",
        "ايجار",
        "إيجار",
        "فواتير",
    ],
    "monthly_income": [
        "earn",
        "salary",
        "income",
        "make",
        "monthly income",
        "per month",
        "بقبض",
        "قبضي",
        "قبض",
        "بدخل",
        "دخلي",
        "دخل",
        "راتب",
        "مرتب",
        "شهري",
    ],
    "goal_price": [
        "want to buy",
        "buy",
        "goal",
        "target",
        "price",
        "عايز",
        "عاوز",
        "أشتري",
        "اشتري",
        "اشترى",
        "هدف",
        "سعر",
        "تمن",
        "ثمن",
        "عربية",
        "سيارة",
        "سياره",
    ],
}


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
    field_matches: dict[str, tuple[NumberMention, int]] = {}

    for mention in mentions:
        classified = _classify_mention(text, mention)
        if classified is None:
            continue
        field, score = classified
        current = field_matches.get(field)
        if current is None or score > current[1]:
            field_matches[field] = (mention, score)

    for field, (mention, _) in field_matches.items():
        setattr(data, field, mention.value)

    if data.goal_price is None and mentions and _has_goal_language(text):
        used = {match[0] for match in field_matches.values()}
        candidates = [mention for mention in mentions if mention not in used] or mentions
        largest = max(candidates, key=lambda item: item.value)
        data.goal_price = largest.value
        data.goals = [{"name": "primary goal", "goal_price": largest.value}]

    return apply_intelligent_defaults(data)


def merge_extractions(primary: FinancialData, fallback: FinancialData) -> FinancialData:
    merged = primary.model_copy(deep=True)
    for field in ("goal_price", "monthly_income", "monthly_expenses", "current_savings", "extra_income"):
        if getattr(merged, field) is None:
            setattr(merged, field, getattr(fallback, field))
    if not merged.goals:
        merged.goals = fallback.goals
    merged.all_numbers = _dedupe_numbers([*merged.all_numbers, *fallback.all_numbers])
    merged.assumptions = _dedupe_strings([*merged.assumptions, *fallback.assumptions])
    return apply_intelligent_defaults(merged)


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


def _classify_mention(text: str, mention: NumberMention) -> tuple[str, int] | None:
    best_field = None
    lowered = text.lower()
    best_score = 0
    context_start = max(0, mention.start - 42)
    context_end = min(len(lowered), mention.end + 42)
    context = lowered[context_start:context_end]
    mention_start = mention.start - context_start
    mention_end = mention.end - context_start

    for field, keywords in FIELD_KEYWORDS.items():
        score = _score_context(context, keywords, mention_start, mention_end)
        if score > best_score:
            best_score = score
            best_field = field
    if best_field is None:
        return None
    return best_field, best_score


def _score_context(context: str, keywords: list[str], mention_start: int, mention_end: int) -> int:
    score = 0
    for keyword in keywords:
        lowered_keyword = keyword.lower()
        search_from = 0
        while True:
            index = context.find(lowered_keyword, search_from)
            if index == -1:
                break
            keyword_end = index + len(lowered_keyword)
            if keyword_end <= mention_start:
                distance = mention_start - keyword_end
            elif index >= mention_end:
                distance = index - mention_end
            else:
                distance = 0
            if distance <= 36:
                score = max(score, 80 - distance + (10 if " " in lowered_keyword else 0))
            search_from = index + 1
    return score


def _has_goal_language(text: str) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in FIELD_KEYWORDS["goal_price"])


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
