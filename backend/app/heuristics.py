import re
from dataclasses import dataclass
from .models import FinancialData


ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

FIELD_KEYWORDS = {
    "extra_income": [
        "extra", "side", "freelance", "bonus", "bonuses", "sometimes get", "additional",
        "overtime", "commission", "commissions", "side hustle", "part time",
        "gig", "tips", "tipping", "passive income", "passive",
        "second job", "weekend job", "evening job", "side gig", "side work",
        "extra cash", "extra money", "investment income", "rental income",
        "dividend", "interest", "cashback", "reward", "incentive",
        "per diem", "allowance", "stipend", "bonus pay", "yearly bonus",
        "annual bonus", "commission pay", "gig work",
        "اضافي", "إضافي", "زيادة", "فريلانس", "مكافأة", "حوافز",
        "باخد", "بآخد", "اخد", "اخدت",
        "شغل إضافي", "شغل جانبي", "شغل جمبي", "عمل جانبي",
        "اوفر تايم", "ساعات إضافية",
        "عمولة", "نسبة", "ارباح", "ربح", "بونص",
        "دخل إضافي", "منحة", "كسبت", "بجيب", "جاب",
        "شغل اونلاين", "مشروع", "عائد", "ايراد", "مردود",
    ],
    "current_savings": [
        "saved", "savings", "save", "with me", "already", "have",
        "bank", "cash", "balance", "in my account", "available",
        "currently have", "saved up", "put aside", "set aside",
        "saved so far", "got", "i have", "i got",
        "saving", "deposit", "fund", "funds", "emergency fund",
        "reserve", "reserves", "savings account",
        "عندي", "معايا", "لدى", "لدي", "مدخر", "مدخرات", "محوش", "موفر",
        "محوشة", "حوشت", "بحوش", "توفير",
        "ادخار", "ادخرت", "في البنك", "في حسابي",
        "حساب توفير", "رصيد", "كاش",
        "شهادات", "وديعة", "دهب", "ذهب",
        "متوفر", "موجود", "تحت الفراش", "في الخزنة",
        "فلوس", "نقود",
    ],
    "monthly_expenses": [
        "spend", "expenses", "expense", "rent", "bills", "costs", "pay",
        "spending", "monthly spend", "outgoing", "outgoings", "living cost",
        "living expenses", "cost of living", "overheads",
        "fixed costs", "variable costs", "loan", "debt", "credit",
        "mortgage", "utility", "utilities", "groceries", "food",
        "transport", "transportation", "insurance",
        "subscription", "emi", "monthly payment",
        "spending money", "i spend", "i pay",
        "monthly expenses",
        "بصرف", "اصرف", "صرفت", "يصرف", "صرف",
        "مصروف", "مصاريف", "مصروفات", "مصاريفي", "مصروفي",
        "ايجار", "إيجار", "فواتير", "فاتورة",
        "أقساط", "قسط", "دفع", "دافع", "بدفع",
        "كهربا", "مياه", "غاز", "نت", "تليفون", "محمول",
        "بنزين", "مواصلات", "أكل", "سكن",
        "علاج", "دوا", "تعليم", "مدارس", "جامعة",
        "تكاليف", "التزامات", "احتياجات", "مستلزمات",
        "ضرايب", "خلص", "بخرج",
        "سوبرماركت", "تموين", "عيش",
    ],
    "monthly_income": [
        "earn", "salary", "income", "make", "monthly income",
        "wage", "earning", "monthly salary", "my salary", "base salary",
        "take home", "net salary", "gross", "basic",
        "monthly pay", "my pay", "fixed", "wages",
        "payslip", "primary", "full time", "9 to 5", "day job",
        "fixed income", "monthly earning", "primary income",
        "main income", "job income",
        "بقبض", "قبضي", "قبض", "قبضت",
        "بدخل", "دخلي", "دخل", "دخول",
        "راتب", "مرتب", "راتبي", "مرتبي",
        "شهر", "شهري", "شهرية",
        "معاش", "مرتبات", "علاوة", "بدل",
        "أجر", "أجرة", "كسب", "مكسب", "رزق",
        "تعويض", "صافي", "إجمالي",
        "مرتب ثابت", "مستلم", "استلمت", "استلم",
        "بينزل", "نزل الراتب",
        "ايراد", "إيراد", "ارباح",
    ],
    "goal_price": [
        "want to buy", "buy", "goal", "target", "price", "worth",
        "car", "vehicle", "house", "apartment", "condo",
        "want", "need", "save for", "saving for", "planning to buy",
        "will cost", "priced at", "cost", "budget", "my goal",
        "aiming for", "save up for",
        "purchase", "looking for", "looking to buy",
        "plan to buy", "intend to buy", "save up",
        "fund", "finance", "afford",
        "my target", "budget for", "estimated cost",
        "approximate", "around",
        "اريد", "أريد", "بدي", "ابي", "أبي",
        "عايز", "عاوز", "عايزة", "عاوزة", "عايزين",
        "أشتري", "اشتري", "اشترى", "شراء", "شرا",
        "هدف", "سعر", "تمن", "ثمن",
        "عربية", "سيارة", "سياره", "عربيتي", "عربة", "عرب",
        "نفسي في", "أحلم", "حلم", "طموح",
        "مستهدف", "ناوي على", "ناوي أشتري",
        "محتاج", "أحتاج", "ضروري", "غرض",
        "شقة", "بيت", "فيلا", "أرض",
        "جهاز", "زواج", "جواز", "سفر",
        "سياحة", "دورة", "عملية",
        "موتوسيكل", "لاب توب", "موبايل", "تابلت",
        "أجيب", "عايز أوفر",
        "قيمة", "بقيمة",
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
    field_matches: dict[str, list[tuple[NumberMention, int]]] = {}

    for mention in mentions:
        classified = _classify_mention(text, mention)
        if classified is None:
            continue
        field, score = classified
        if field not in field_matches:
            field_matches[field] = []
        field_matches[field].append((mention, score))

    for field, matches in field_matches.items():
        if field == "goal_price":
            best = max(matches, key=lambda m: m[1])
            setattr(data, field, best[0].value)
        else:
            total = sum(m[0].value for m in matches)
            setattr(data, field, total)

    if data.goal_price is None and mentions and _has_goal_language(text):
        used = {match[0] for match in field_matches.values()}
        candidates = [mention for mention in mentions if mention not in used] or mentions
        largest = max(candidates, key=lambda item: item.value)
        data.goal_price = largest.value
        data.goals = [{"name": "primary goal", "goal_price": largest.value}]

    return apply_intelligent_defaults(data)


def merge_extractions(primary: FinancialData, fallback: FinancialData) -> FinancialData:
    merged = primary.model_copy(deep=True)
    numbers_set = set()
    for n in [*merged.all_numbers, *fallback.all_numbers]:
        numbers_set.add(round(float(n), 4))

    for field in ("goal_price", "monthly_income", "monthly_expenses", "current_savings", "extra_income"):
        if field == "goal_price":
            if getattr(merged, field) is None:
                setattr(merged, field, getattr(fallback, field))
        else:
            pv = getattr(merged, field) or 0
            fv = getattr(fallback, field) or 0
            if pv and fv:
                pv_in = round(float(pv), 4) in numbers_set
                fv_in = round(float(fv), 4) in numbers_set
                if pv_in and not fv_in:
                    setattr(merged, field, pv)
                elif fv_in and not pv_in:
                    setattr(merged, field, fv)
                else:
                    setattr(merged, field, max(pv, fv))
            else:
                setattr(merged, field, max(pv, fv))
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


FIELD_PRIORITY = ["goal_price", "monthly_income", "monthly_expenses", "current_savings", "extra_income"]


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
        if best_field is None:
            best_score = score
            best_field = field
        elif score > best_score or (score == best_score and FIELD_PRIORITY.index(field) < FIELD_PRIORITY.index(best_field)):
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
                if index >= mention_end:
                    bonus = 2 if distance == 0 else (1 if distance == 1 else 0)
                elif keyword_end <= mention_start and distance == 0:
                    bonus = 1
                else:
                    bonus = 0
                score = max(score, 80 - distance + bonus)
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
