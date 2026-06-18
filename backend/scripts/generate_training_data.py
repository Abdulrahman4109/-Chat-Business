"""Generate fine-tuning dataset for financial extraction model.

Output: backend/scripts/finetune_data.jsonl — ready for OpenAI fine-tuning.

Usage:
  python scripts/generate_training_data.py

To upload & fine-tune (requires OpenAI API key):
  export OPENAI_API_KEY=sk-...
  python scripts/generate_training_data.py --upload
"""

import json
import os
import sys
import argparse
from itertools import product

SYSTEM_MSG = (
    "Extract financial data from text segments. "
    "Each segment is numbered [index]. "
    "Normalize ALL time values to monthly equivalents: "
    "hourly x171.43, daily x30, weekly x4.2857, bi-weekly x2.1429, "
    "every-10-days x3, semi-monthly x2, quarterly /3, semi-annually /6, "
    "yearly /12, biennially /24. "
    "Monthly or no-unit means keep as-is. "
    "Return JSON: {\"extractions\": [{\"segment_index\": 0, \"field\": \"...\", \"value\": 0.0}]}"
)


def make(segments, extractions):
    user = "Segments:\n" + "\n".join(f"[{i}] {s}" for i, s in enumerate(segments))
    assistant = json.dumps({"extractions": extractions}, ensure_ascii=False)
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def n(value):
    return round(value)


MULTIPLIERS = {
    "hourly": 171.43,
    "daily": 30,
    "weekly": 4.2857,
    "bi_weekly": 2.1429,
    "every_10_days": 3,
    "semi_monthly": 2,
    "monthly": 1,
    "quarterly": 1 / 3,
    "semi_annual": 1 / 6,
    "yearly": 1 / 12,
    "biennial": 1 / 24,
}

TIME_LABELS = {
    "hourly": {
        "en": ["{v} per hour", "{v}/hour", "hourly rate {v}"],
        "ar": ["{v} في الساعة", "{v} بالساعة", "مرتب {v} في الساعة"],
    },
    "daily": {
        "en": ["{v} per day", "{v} daily", "{v}/day"],
        "ar": ["{v} في اليوم", "{v} يومياً", "مرتب {v} يوميا"],
    },
    "weekly": {
        "en": ["{v} per week", "{v} weekly", "{v}/week"],
        "ar": ["{v} اسبوعيا", "{v} اسبوعي", "{v} في الاسبوع"],
    },
    "bi_weekly": {
        "en": ["{v} bi-weekly", "{v} every 2 weeks", "{v} per two weeks"],
        "ar": ["{v} كل اسبوعين", "{v} كل 14 يوم"],
    },
    "every_10_days": {
        "en": ["{v} every 10 days", "{v} per 10 days"],
        "ar": ["{v} كل 10 ايام", "{v} عشرة ايام"],
    },
    "semi_monthly": {
        "en": ["{v} semi-monthly", "{v} twice monthly", "semi-monthly pay {v}"],
        "ar": ["{v} نصف شهري", "{v} مرتين بالشهر"],
    },
    "monthly": {
        "en": ["{v} per month", "{v} monthly", "monthly salary {v}"],
        "ar": ["{v} شهريا", "{v} في الشهر", "مرتب {v} شهري"],
    },
    "quarterly": {
        "en": ["{v} quarterly", "{v} every 3 months", "{v} per quarter"],
        "ar": ["{v} كل 3 شهور", "{v} ربع سنوي", "مرتب {v} كل 3 شهور"],
    },
    "semi_annual": {
        "en": ["{v} semi-annually", "{v} every 6 months"],
        "ar": ["{v} كل 6 شهور", "{v} نصف سنوي"],
    },
    "yearly": {
        "en": ["{v} per year", "{v} yearly", "{v} annually", "{v}/year"],
        "ar": ["{v} سنوي", "{v} سنويا", "{v} في السنة", "راتب {v} سنوي"],
    },
    "biennial": {
        "en": ["{v} every 2 years", "{v} biennially"],
        "ar": ["{v} كل سنتين"],
    },
}

# Base values to vary (keeps model from memorizing one number per unit)
INCOME_VALUES = [3000, 5000, 8000, 10000, 12000, 15000, 20000, 25000, 40000, 50000, 60000, 75000, 100000]
EXPENSES_VALUES = [200, 500, 800, 1000, 1500, 2000, 3000, 5000, 7000, 8000, 10000, 12000, 15000]
EXTRA_VALUES = [200, 500, 1000, 1500, 2000, 3000, 4000, 5000, 8000, 10000]
SAVINGS_VALUES = [5000, 10000, 15000, 20000, 30000, 50000, 75000, 100000, 150000, 200000]
GOAL_VALUES = [100000, 150000, 200000, 250000, 300000, 400000, 500000, 600000, 750000, 800000, 1000000]

cases = []


# ==============================
# 1) SINGLE FIELD — GOAL (static)
# ==============================
def gen_goal():
    ar_templates = [
        "اريد شراء {v}",
        "عايز سيارة ب {v}",
        "هدف {v}",
        "بدي شقة ب {v}",
        "اريد عربية {v}",
        "هدفي جمع {v}",
        "بكفي {v}",
    ]
    en_templates = [
        "i want to buy {v}",
        "i need {v}",
        "goal {v}",
        "target {v}",
        "want a car for {v}",
        "save for {v}",
        "worth {v}",
    ]
    for v in GOAL_VALUES[:5]:
        cases.append(make([ar_templates[0].replace("{v}", str(v))], [{"segment_index": 0, "field": "goal_price", "value": v}]))
        cases.append(make([en_templates[0].replace("{v}", str(v))], [{"segment_index": 0, "field": "goal_price", "value": v}]))


# ==============================
# 2) SINGLE FIELD — SAVINGS (static)
# ==============================
def gen_savings():
    ar_templates = [
        "عندي {v} في البنك",
        "ادخار {v}",
        "مدخرات {v}",
        "معايا {v}",
        "عندي مدخرات {v}",
    ]
    en_templates = [
        "i have {v} saved",
        "savings {v}",
        "saved {v}",
        "have {v} in the bank",
        "cash {v}",
        "i already have {v}",
    ]
    for v in SAVINGS_VALUES[:5]:
        cases.append(make([ar_templates[0].replace("{v}", str(v))], [{"segment_index": 0, "field": "current_savings", "value": v}]))
        cases.append(make([en_templates[0].replace("{v}", str(v))], [{"segment_index": 0, "field": "current_savings", "value": v}]))


# ==============================
# 3) COMBINATORIAL: income / expenses / extra × time × lang
# ==============================
def gen_field_time(field, values, ar_field_keyword, en_field_templates):
    for unit, mult in MULTIPLIERS.items():
        labels = TIME_LABELS[unit]
        for v in values[:3]:
            monthly = n(v * mult)
            # English
            for tmpl in labels["en"][:1]:
                text = tmpl.replace("{v}", str(v))
                if en_field_templates:
                    text = en_field_templates[0].replace("{v}", text)
                cases.append(make([text], [{"segment_index": 0, "field": field, "value": monthly}]))
            # Arabic
            for tmpl in labels["ar"][:1]:
                text = tmpl.replace("{v}", str(v))
                if ar_field_keyword:
                    text = f"{ar_field_keyword} {text}"
                cases.append(make([text], [{"segment_index": 0, "field": field, "value": monthly}]))


def gen_all_combinatorial():
    gen_field_time("monthly_income", INCOME_VALUES, "مرتب", ["{v} salary", "{v} wage", "earn {v}", "{v}"])
    gen_field_time("monthly_expenses", EXPENSES_VALUES, "مصاريف", ["{v} expenses", "{v} rent", "spend {v}", "{v} bills", "{v} cost"])
    gen_field_time("extra_income", EXTRA_VALUES, "حوافز", ["{v} bonus", "{v} commission", "{v} freelance", "extra {v}", "side income {v}"])


# ==============================
# 4) MULTI-FIELD SAME SEGMENT
# ==============================
def gen_multi():
    multi = [
        (["مرتب 10000 ومصاريف 5000"], [{"segment_index": 0, "field": "monthly_income", "value": 10000}, {"segment_index": 0, "field": "monthly_expenses", "value": 5000}]),
        (["salary 7000 expenses 2000"], [{"segment_index": 0, "field": "monthly_income", "value": 7000}, {"segment_index": 0, "field": "monthly_expenses", "value": 2000}]),
        (["حوافز 4000 مرتب 30000"], [{"segment_index": 0, "field": "extra_income", "value": 4000}, {"segment_index": 0, "field": "monthly_income", "value": 30000}]),
        (["راتب 15000 مصاريف 4000"], [{"segment_index": 0, "field": "monthly_income", "value": 15000}, {"segment_index": 0, "field": "monthly_expenses", "value": 4000}]),
        (["salary 12000 rent 3000 bonus 1000"], [{"segment_index": 0, "field": "monthly_income", "value": 12000}, {"segment_index": 0, "field": "monthly_expenses", "value": 3000}, {"segment_index": 0, "field": "extra_income", "value": 1000}]),
        (["مرتب 20000 ومصاريف 8000 وبونص 2000"], [{"segment_index": 0, "field": "monthly_income", "value": 20000}, {"segment_index": 0, "field": "monthly_expenses", "value": 8000}, {"segment_index": 0, "field": "extra_income", "value": 2000}]),
        (["5000 per week salary 2000 monthly expenses"], [{"segment_index": 0, "field": "monthly_income", "value": n(5000 * 4.2857)}, {"segment_index": 0, "field": "monthly_expenses", "value": 2000}]),
        (["مرتب 30000 اسبوعي ومصاريف 12000 شهري وبونص 3000"], [{"segment_index": 0, "field": "monthly_income", "value": n(30000 * 4.2857)}, {"segment_index": 0, "field": "monthly_expenses", "value": 12000}, {"segment_index": 0, "field": "extra_income", "value": 3000}]),
        (["earn 100 per day spend 50 per day"], [{"segment_index": 0, "field": "monthly_income", "value": n(100 * 30)}, {"segment_index": 0, "field": "monthly_expenses", "value": n(50 * 30)}]),
        (["مرتب 100 في الساعة ومصروف 2000 شهريا"], [{"segment_index": 0, "field": "monthly_income", "value": n(100 * 171.43)}, {"segment_index": 0, "field": "monthly_expenses", "value": 2000}]),
        (["rent 500 per week food 300 per week"], [{"segment_index": 0, "field": "monthly_expenses", "value": n(800 * 4.2857)}]),
        (["راتب 50000 سنوي وايجار 12000 سنوي"], [{"segment_index": 0, "field": "monthly_income", "value": n(50000 / 12)}, {"segment_index": 0, "field": "monthly_expenses", "value": n(12000 / 12)}]),
    ]
    for s, ex in multi:
        cases.append(make(s, ex))


# ==============================
# 5) ARABIC ATTACHED NUMBERS
# ==============================
def gen_attached():
    attached = [
        (["اريد شراء عربة 800000", "ولدي ادخار20000"], [{"segment_index": 0, "field": "goal_price", "value": 800000}, {"segment_index": 1, "field": "current_savings", "value": 20000}]),
        (["مرتب 50000", "ادخار20000"], [{"segment_index": 0, "field": "monthly_income", "value": 50000}, {"segment_index": 1, "field": "current_savings", "value": 20000}]),
        (["عايز سيارة 300000", "ادخار50000"], [{"segment_index": 0, "field": "goal_price", "value": 300000}, {"segment_index": 1, "field": "current_savings", "value": 50000}]),
        (["مرتب 10000", "مصاريف8000"], [{"segment_index": 0, "field": "monthly_income", "value": 10000}, {"segment_index": 1, "field": "monthly_expenses", "value": 8000}]),
        (["مرتب 4000 في الاسبوع", "مصاريف900اسبوعي"], [{"segment_index": 0, "field": "monthly_income", "value": n(4000 * 4.2857)}, {"segment_index": 1, "field": "monthly_expenses", "value": n(900 * 4.2857)}]),
        (["عندي 20000", "مرتب50000اسبوعي"], [{"segment_index": 0, "field": "current_savings", "value": 20000}, {"segment_index": 1, "field": "monthly_income", "value": n(50000 * 4.2857)}]),
        (["مرتب 100 في الساعة", "حوافز4000"], [{"segment_index": 0, "field": "monthly_income", "value": n(100 * 171.43)}, {"segment_index": 1, "field": "extra_income", "value": 4000}]),
        (["بونص 2000", "موقع1000فيالساعة"], [{"segment_index": 0, "field": "extra_income", "value": 2000}, {"segment_index": 1, "field": "extra_income", "value": n(1000 * 171.43)}]),
    ]
    for s, ex in attached:
        cases.append(make(s, ex))


# ==============================
# 6) FULL COMPLEX MESSAGES (multi-segment)
# ==============================
def gen_full():
    full = [
        # Arabic classic
        (["اريد شراء عربة 800000", "ولدي ادخار20000 مرتب 5000 اسبوعي مصاريف 10000"], [{"segment_index": 0, "field": "goal_price", "value": 800000}, {"segment_index": 1, "field": "current_savings", "value": 20000}, {"segment_index": 1, "field": "monthly_income", "value": n(5000 * 4.2857)}, {"segment_index": 1, "field": "monthly_expenses", "value": 10000}]),
        # Arabic with extras
        (["اريد شراء عربة 800000", "ولدي ادخار20000 مرتب 5000 اسبوعي مصاريف 10000 حوافز 4000 اضافي 2000"], [{"segment_index": 0, "field": "goal_price", "value": 800000}, {"segment_index": 1, "field": "current_savings", "value": 20000}, {"segment_index": 1, "field": "monthly_income", "value": n(5000 * 4.2857)}, {"segment_index": 1, "field": "monthly_expenses", "value": 10000}, {"segment_index": 1, "field": "extra_income", "value": 6000}]),
        # Arabic weekly expenses + hourly income
        (["اريد شراء عربة 600000", "ولدي ادخار50000 مرتب 100 في الساعة مصاريف 900 اسبوعي حوافز 3000"], [{"segment_index": 0, "field": "goal_price", "value": 600000}, {"segment_index": 1, "field": "current_savings", "value": 50000}, {"segment_index": 1, "field": "monthly_income", "value": n(100 * 171.43)}, {"segment_index": 1, "field": "monthly_expenses", "value": n(900 * 4.2857)}, {"segment_index": 1, "field": "extra_income", "value": 3000}]),
        # Arabic yearly
        (["هدف 500000", "عندي 100000", "مرتب 120000 سنوي مصاريف 36000 سنوي"], [{"segment_index": 0, "field": "goal_price", "value": 500000}, {"segment_index": 1, "field": "current_savings", "value": 100000}, {"segment_index": 2, "field": "monthly_income", "value": n(120000 / 12)}, {"segment_index": 2, "field": "monthly_expenses", "value": n(36000 / 12)}]),
        # English classic
        (["i want a car worth 600000", "i have 20000 saved salary 5000 per week expenses 2000 bonus 500"], [{"segment_index": 0, "field": "goal_price", "value": 600000}, {"segment_index": 1, "field": "current_savings", "value": 20000}, {"segment_index": 1, "field": "monthly_income", "value": n(5000 * 4.2857)}, {"segment_index": 1, "field": "monthly_expenses", "value": 2000}, {"segment_index": 1, "field": "extra_income", "value": 500}]),
        # English comma-separated (the user's failing case)
        (["I want to buy a car worth 800,000", "I have 20,000 in savings", "My income is 4,000 per week, with weekly expenses of 900", "I also receive 4,000 in bonuses and have an additional income of 2,000"], [{"segment_index": 0, "field": "goal_price", "value": 800000}, {"segment_index": 1, "field": "current_savings", "value": 20000}, {"segment_index": 2, "field": "monthly_income", "value": n(4000 * 4.2857)}, {"segment_index": 2, "field": "monthly_expenses", "value": n(900 * 4.2857)}, {"segment_index": 3, "field": "extra_income", "value": 6000}]),
        # English hourly
        (["want to buy a house for 450000", "i have 50000 saved i earn 25 per hour full time expenses 1500"], [{"segment_index": 0, "field": "goal_price", "value": 450000}, {"segment_index": 1, "field": "current_savings", "value": 50000}, {"segment_index": 1, "field": "monthly_income", "value": n(25 * 171.43)}, {"segment_index": 1, "field": "monthly_expenses", "value": 1500}]),
        # English daily income, weekly expenses
        (["goal 300000", "saved 10000", "earn 200 per day expenses 1000 per week"], [{"segment_index": 0, "field": "goal_price", "value": 300000}, {"segment_index": 1, "field": "current_savings", "value": 10000}, {"segment_index": 2, "field": "monthly_income", "value": n(200 * 30)}, {"segment_index": 2, "field": "monthly_expenses", "value": n(1000 * 4.2857)}]),
        # Arabic multiple time units in one
        (["عايز شقة 700000", "ادخار 150000", "مرتب 30000 سنوي ومصروف 2000 شهري"], [{"segment_index": 0, "field": "goal_price", "value": 700000}, {"segment_index": 1, "field": "current_savings", "value": 150000}, {"segment_index": 2, "field": "monthly_income", "value": n(30000 / 12)}, {"segment_index": 2, "field": "monthly_expenses", "value": 2000}]),
        # English quarterly + semi-annual
        (["need 500000 for business", "have 50000", "quarterly income 60000 expenses 1000 per month side 5000 per quarter"], [{"segment_index": 0, "field": "goal_price", "value": 500000}, {"segment_index": 1, "field": "current_savings", "value": 50000}, {"segment_index": 2, "field": "monthly_income", "value": n(60000 / 3)}, {"segment_index": 2, "field": "monthly_expenses", "value": 1000}, {"segment_index": 2, "field": "extra_income", "value": n(5000 / 3)}]),
        # Arabic bi-weekly
        ((["اريد شراء سيارة بأربعمائة الف", "عندي 50000", "مرتب 10000 كل اسبوعين ومصاريف 2000"]), [{"segment_index": 0, "field": "goal_price", "value": 400000}, {"segment_index": 1, "field": "current_savings", "value": 50000}, {"segment_index": 2, "field": "monthly_income", "value": n(10000 * 2.1429)}, {"segment_index": 2, "field": "monthly_expenses", "value": 2000}]),
        # English every 10 days
        ((["save for 750000", "saved 25000", "earn 8000 every 10 days spend 2000 per month"]), [{"segment_index": 0, "field": "goal_price", "value": 750000}, {"segment_index": 1, "field": "current_savings", "value": 25000}, {"segment_index": 2, "field": "monthly_income", "value": n(8000 * 3)}, {"segment_index": 2, "field": "monthly_expenses", "value": 2000}]),
        # Arabic semi-annual
        ((["هدف 1,000,000", "ادخار 100,000", "راتب 50000 كل 6 شهور ومصاريف 15000 شهريا"]), [{"segment_index": 0, "field": "goal_price", "value": 1000000}, {"segment_index": 1, "field": "current_savings", "value": 100000}, {"segment_index": 2, "field": "monthly_income", "value": n(50000 / 6)}, {"segment_index": 2, "field": "monthly_expenses", "value": 15000}]),
        # English biennial
        ((["buy house 900000", "savings 200000", "earn 100000 every 2 years plus 3000 monthly bonus spend 2500 per month"]), [{"segment_index": 0, "field": "goal_price", "value": 900000}, {"segment_index": 1, "field": "current_savings", "value": 200000}, {"segment_index": 2, "field": "monthly_income", "value": n(100000 / 24)}, {"segment_index": 2, "field": "extra_income", "value": 3000}, {"segment_index": 2, "field": "monthly_expenses", "value": 2500}]),
    ]
    for s, ex in full:
        cases.append(make(s, ex))


# ==============================
# 7) EDGE CASES
# ==============================
def gen_edge():
    edge = [
        (["مرحبا كيف حالك"], []),
        (["hello"], []),
        (["كيف يمكنني مساعدتك"], []),
        (["i need 300000 for a house"], [{"segment_index": 0, "field": "goal_price", "value": 300000}]),
        (["مدخرات 75000"], [{"segment_index": 0, "field": "current_savings", "value": 75000}]),
        (["اريد شراء عربة 800000 وموتوسيكل 50000"], [{"segment_index": 0, "field": "goal_price", "value": 800000}]),
        (["cash on hand 5000"], [{"segment_index": 0, "field": "current_savings", "value": 5000}]),
        (["عايز سيارة ب 500000"], [{"segment_index": 0, "field": "goal_price", "value": 500000}]),
        ((["save 300000 buy car 200000"]), [{"segment_index": 0, "field": "goal_price", "value": 300000}]),
        ((["i have 50000 saved i want car 250000"]), [{"segment_index": 0, "field": "goal_price", "value": 250000}, {"segment_index": 0, "field": "current_savings", "value": 50000}]),
        ((["مصاريف اليوم 50", "مرتب 2000 شهريا"]), [{"segment_index": 0, "field": "monthly_expenses", "value": n(50 * 30)}, {"segment_index": 1, "field": "monthly_income", "value": 2000}]),
        ((["مرتب 5k"]), [{"segment_index": 0, "field": "monthly_income", "value": 5000}]),
        ((["bonus 2k"]), [{"segment_index": 0, "field": "extra_income", "value": 2000}]),
        ((["savings 1.5m"]), [{"segment_index": 0, "field": "current_savings", "value": 1500000}]),
        ((["need 2.5m for a business"]), [{"segment_index": 0, "field": "goal_price", "value": 2500000}]),
        ((["basis 100 000"]), [{"segment_index": 0, "field": "monthly_income", "value": 100000}]),
        ((["مصروف 5 الاف"]), [{"segment_index": 0, "field": "monthly_expenses", "value": 5000}]),
        ((["مرتب 20 الف"]), [{"segment_index": 0, "field": "monthly_income", "value": 20000}]),
        ((["سعر السيارة 450000"]), [{"segment_index": 0, "field": "goal_price", "value": 450000}]),
        ((["ميزانية 300000"]), [{"segment_index": 0, "field": "goal_price", "value": 300000}]),
        ((["كشف راتب 8000"]), [{"segment_index": 0, "field": "monthly_income", "value": 8000}]),
        ((["net pay 5500"]), [{"segment_index": 0, "field": "monthly_income", "value": 5500}]),
        ((["take home 7000"]), [{"segment_index": 0, "field": "monthly_income", "value": 7000}]),
    ]
    for s, ex in edge:
        cases.append(make(s, ex))


# ==============================
# 8) COMMA + CURRENCY VARIATIONS
# ==============================
def gen_currency():
    comma = [
        ((["مرتب 10,000"]), [{"segment_index": 0, "field": "monthly_income", "value": 10000}]),
        ((["مصاريف 5,000"]), [{"segment_index": 0, "field": "monthly_expenses", "value": 5000}]),
        ((["مدخرات 100,000"]), [{"segment_index": 0, "field": "current_savings", "value": 100000}]),
        ((["اشتري سيارة 800,000"]), [{"segment_index": 0, "field": "goal_price", "value": 800000}]),
        ((["حوافز 4,000"]), [{"segment_index": 0, "field": "extra_income", "value": 4000}]),
        ((["$5000 salary"]), [{"segment_index": 0, "field": "monthly_income", "value": 5000}]),
        ((["€3000 rent"]), [{"segment_index": 0, "field": "monthly_expenses", "value": 3000}]),
        ((["£2000 bonus"]), [{"segment_index": 0, "field": "extra_income", "value": 2000}]),
        ((["$50,000 saved"]), [{"segment_index": 0, "field": "current_savings", "value": 50000}]),
        ((["car $30,000"]), [{"segment_index": 0, "field": "goal_price", "value": 30000}]),
        ((["$3,000 per month salary"]), [{"segment_index": 0, "field": "monthly_income", "value": 3000}]),
        ((["$500 per week rent"]), [{"segment_index": 0, "field": "monthly_expenses", "value": n(500 * 4.2857)}]),
        ((["earn $25 per hour"]), [{"segment_index": 0, "field": "monthly_income", "value": n(25 * 171.43)}]),
        ((["freelance $2,000 per month"]), [{"segment_index": 0, "field": "extra_income", "value": 2000}]),
        ((["bill $200 per week"]), [{"segment_index": 0, "field": "monthly_expenses", "value": n(200 * 4.2857)}]),
        ((["bonus $5,000 per year"]), [{"segment_index": 0, "field": "extra_income", "value": n(5000 / 12)}]),
        ((["salary $4,000 per week"]), [{"segment_index": 0, "field": "monthly_income", "value": n(4000 * 4.2857)}]),
        ((["$100 per day freelance"]), [{"segment_index": 0, "field": "extra_income", "value": n(100 * 30)}]),
        ((["مرتب $2,000"]), [{"segment_index": 0, "field": "monthly_income", "value": 2000}]),
        ((["إيجار ١٠٠٠ شهريا"]), [{"segment_index": 0, "field": "monthly_expenses", "value": 1000}]),
        ((["راتب ١,٥٠٠,٠٠٠ سنوي"]), [{"segment_index": 0, "field": "monthly_income", "value": n(1500000 / 12)}]),
    ]
    for s, ex in comma:
        cases.append(make(s, ex))


# ==============================
# 9) ALTERNATE ARABIC PHRASINGS
# ==============================
def gen_alt_ar():
    alt = [
        ((["قيمة الهدف 500000"]), [{"segment_index": 0, "field": "goal_price", "value": 500000}]),
        ((["تكلفة السيارة 350000"]), [{"segment_index": 0, "field": "goal_price", "value": 350000}]),
        ((["المبلغ المطلوب 750000"]), [{"segment_index": 0, "field": "goal_price", "value": 750000}]),
        ((["الراتب 8000"]), [{"segment_index": 0, "field": "monthly_income", "value": 8000}]),
        ((["الدخل 15000"]), [{"segment_index": 0, "field": "monthly_income", "value": 15000}]),
        ((["المرتب 25000"]), [{"segment_index": 0, "field": "monthly_income", "value": 25000}]),
        ((["المصروفات 4000"]), [{"segment_index": 0, "field": "monthly_expenses", "value": 4000}]),
        ((["الايجار 3000"]), [{"segment_index": 0, "field": "monthly_expenses", "value": 3000}]),
        ((["الفواتير 1500"]), [{"segment_index": 0, "field": "monthly_expenses", "value": 1500}]),
        ((["المكافأة 2000"]), [{"segment_index": 0, "field": "extra_income", "value": 2000}]),
        ((["الحوافز 3500"]), [{"segment_index": 0, "field": "extra_income", "value": 3500}]),
        ((["العلاوة 1000"]), [{"segment_index": 0, "field": "extra_income", "value": 1000}]),
        ((["مدخراتي 80000"]), [{"segment_index": 0, "field": "current_savings", "value": 80000}]),
        ((["المدخرات 45000"]), [{"segment_index": 0, "field": "current_savings", "value": 45000}]),
        ((["في البنك 60000"]), [{"segment_index": 0, "field": "current_savings", "value": 60000}]),
        ((["أجره 800 في اليوم"]), [{"segment_index": 0, "field": "monthly_income", "value": n(800 * 30)}]),
        ((["مكافأة 1000 كل 3 شهور"]), [{"segment_index": 0, "field": "extra_income", "value": n(1000 / 3)}]),
        ((["مصروف السكن 5000 في الشهر"]), [{"segment_index": 0, "field": "monthly_expenses", "value": 5000}]),
        ((["مرتب 2000 في الاسبوع"]), [{"segment_index": 0, "field": "monthly_income", "value": n(2000 * 4.2857)}]),
        ((["مصروف 200 اسبوعيا"]), [{"segment_index": 0, "field": "monthly_expenses", "value": n(200 * 4.2857)}]),
        ((["بونص 50000 سنويا"]), [{"segment_index": 0, "field": "extra_income", "value": n(50000 / 12)}]),
    ]
    for s, ex in alt:
        cases.append(make(s, ex))


# ==============================
# GENERATE ALL
# ==============================
gen_goal()
gen_savings()
gen_all_combinatorial()
gen_multi()
gen_attached()
gen_full()
gen_edge()
gen_currency()
gen_alt_ar()


# ==============================
# OUTPUT
# ==============================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="finetune_data.jsonl")
    parser.add_argument("--upload", action="store_true", help="Upload to OpenAI and start fine-tune")
    args = parser.parse_args()

    output_path = os.path.join(os.path.dirname(__file__) or ".", args.output)
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")

    print(f"Generated {len(cases)} training examples → {output_path}")

    if args.upload:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("ERROR: set OPENAI_API_KEY environment variable")
            sys.exit(1)
        client = OpenAI(api_key=api_key)
        print("Uploading file...")
        with open(output_path, "rb") as f:
            file = client.files.create(file=f, purpose="fine-tune")
        print(f"File uploaded: {file.id}")
        print("Creating fine-tuning job...")
        job = client.fine_tuning.jobs.create(
            training_file=file.id,
            model="gpt-4o-mini-2024-07-18",
            hyperparameters={"n_epochs": 3},
        )
        print(f"Fine-tuning job created: {job.id}")
        print(f"Model will be: {job.fine_tuned_model}")
        print("Check status: openai_client.fine_tuning.jobs.retrieve('{job.id}')")


if __name__ == "__main__":
    main()
