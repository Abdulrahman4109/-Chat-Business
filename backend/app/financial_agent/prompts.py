PROCESS_INPUT_PROMPT = """You are a financial data extraction engine. Classify each number from the user's message into the correct field.

User message: {message}

Fields by meaning:
- goal: target amount the user wants to reach (هدف, عاوز, شراء, price, target, goal)
- monthly_income: the MAIN salary/income only (مرتب, راتب, قبض, أجر أساسي, salary, income)
- monthly_expenses: regular monthly spending (مصاريف, إيجار, فواتير, expenses, spending)
- current_savings: assets the user OWNS (مدخرات, عقار, سيارة, أسهم, ودائع, savings, saved, have)
- current_debts: amounts the user OWES (ديون, قروض, loans, debts)
- extra_income: ANY extra money beyond main salary (حوافز, مكافآت, اضافي, بدل, bonus, extra income, commission, overtime, side income)

IMPORTANT: حوافز, مكافآت, اضافي, بدل ALL go to extra_income — NOT monthly_income.

Time unit rules:
- If the user mentions a specific time unit (يومي, اسبوعي, في الاسبوع, في الشهر, سنوياً, per week, per year, daily, yearly) → normalize to monthly equivalent:
  - weekly/اسبوعي → × 4.2857
  - daily/يومي → × 30
  - yearly/سنوي → ÷ 12
- If NO time unit is mentioned → assume the value is ALREADY monthly (use as-is)
- Also: if the word just describes the TYPE (like "مرتب شهري" standard salary) → use as-is (monthly)

Examples:
"عاوز عربية بـ 40000 ومرتبي 6500 في الشهر ومصروفي 4200 وعندي 8000 مدخرات وعندي حوافز 500 في الاسبوع"
→ goal=40000, monthly_income=6500, monthly_expenses=4200, current_savings=8000, extra_income=2000 (500 weekly × 4.2857)

"مرتبي 8000 ومصروفاتي 3000 وعندي سيارة بـ 50000 وعليا دين 10000"
→ monthly_income=8000, monthly_expenses=3000, current_savings=50000, current_debts=10000

Return ONLY valid JSON:
{{
  "goal": null,
  "goal_description": "",
  "monthly_income": null,
  "monthly_expenses": null,
  "current_savings": null,
  "current_debts": null,
  "extra_income": null
}}"""

UPDATE_DATA_PROMPT = """You are a financial data updater. Extract the value from the user's answer and normalize it to a monthly amount.

Current data:
{data_json}

Field being asked about: {field}
User answer: {answer}

Rules:
- If user says No / لا / none / nothing → set value to 0
- If user says Yes / نعم / أيوه → look for a number in the answer
- If user says Yes but no number → set value to 0
- If a time unit is specified (weekly, daily, yearly, في الاسبوع, يومي, سنوي, etc.):
  - weekly / اسبوعي / في الاسبوع → × 4.2857
  - daily / يومي / في اليوم → × 30
  - yearly / سنوي / في السنة → ÷ 12
  - biweekly / كل أسبوعين → × 2.1429
- If NO time unit is mentioned → the value is ALREADY monthly (use as-is)

Examples:
"Yes, 500 weekly" / "ايوه 500 في الاسبوع" → value = 2142.85 (500 × 4.2857)
"Yes, 200" / "ايوه 200" → value = 200 (no time unit, assume monthly)
"No" / "لا" → value = 0

Return ONLY valid JSON:
{{
  "value": 0.0
}}"""
