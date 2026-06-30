# Example: Complete Walkthrough

A user wants to buy a car. Here is every step from first message to final result.

---

## User Message

> "I want to buy a car worth 800,000. I earn 15,000 a month."

---

## Step 1 — Normalize Text

**`heuristics.normalize_text()`** converts any non-Western digits to 0-9 and separates numbers attached to text. No change needed here (all Western digits).

---

## Step 2 — Heuristic Extraction

**`heuristic_classify()`** runs regex patterns:
- Goal: matches "car worth 800,000" → `goal_price = 800000`
- Income: matches "earn 15,000 a month" → `monthly_income = 15000`

Result: all_numbers=[800000, 15000], goal=800K, income=15K. Expenses, savings, debts, extra are null.

**`is_ready_for_calculation()`** → **False** (4 fields missing). Falls through to LLM.

---

## Step 3 — LLM Extraction

LLM receives `PROCESS_INPUT_PROMPT` + user message. Returns JSON:
```json
{"goal": 800000, "monthly_income": 15000, "monthly_expenses": null, "current_savings": null, "current_debts": null, "extra_income": null}
```

State after: goal=800K, income=15K. Expenses, savings, debts, extra are null.

---

## Step 4 — Generate Question (Expenses)

First missing field in `FIELD_ORDER` = `monthly_expenses`. Type = `yesno`.

**Q**: "Do you have any monthly expenses?" / "هل لديك مصاريف شهرية؟"
**Response**: `question_type: "yesno"`, `question_field: "monthly_expenses"`, `is_complete: false`

---

## Step 5 — User Answers "Yes, 4200"

**`update_data()`** — not negation, has number. `extract_number_mentions()` gets 4200, no time unit → assume monthly. Sets `monthly_expenses = 4200`.

---

## Step 6 — Generate Question (Savings)

Next missing: `current_savings`. Type = `yesno`.

**Q**: "Do you have any current savings?" / "هل لديك مدخرات حالية؟"
**A**: "Yes, 200000" → `current_savings = 200000`

---

## Step 7 — Generate Question (Debts)

Next missing: `current_debts`. Type = `yesno`.

**Q**: "Do you have any debts or loans?" / "هل لديك ديون أو قروض؟"
**A**: "Yes, 50000" → `current_debts = 50000`

---

## Step 8 — Generate Question (Extra Income)

Next missing: `extra_income`. Type = `yesno`.

**Q**: "Do you have any extra monthly income?" / "هل لديك دخل إضافي؟"
**A**: "No" → negation regex matches (لا/no/none) → `extra_income = 0`

---

## Step 9 — Completeness Check

All 6 fields non-null: goal=800K ✓, income=15K ✓, expenses=4.2K ✓, savings=200K ✓, debts=50K ✓, extra=0 ✓

**`is_complete = true`**

---

## Step 10 — Calculation

```python
net_savings = (15000 + 0) - 4200 = 10800
effective_savings = max(200000 - 50000, 0) = 150000
remaining = max(800000 - 150000, 0) = 650000
months = ceil(650000 / 10800) = 61
```

**Duration**: 5 years and 1 month. **Achievable**: Yes.

Suggestions (max 3): reserve savings monthly, reduce timeline if >12mo, review expenses if >60% of income.

---

## Step 11 — Response

**Assistant**: "At your current pace, it will take 5 years and 1 month. Net monthly savings: 10,800. Remaining: 650,000."

Frontend renders: analysis grid with all 6 fields + result panel + "View Financial Plan" button.

---

## Step 12 — Background Storage

`asyncio.create_task` saves ChatRecord to local JSON → remote Mujarrad API. Never blocks the response.

---

## Step 13 — Diagram (Optional)

User clicks "View Financial Plan". POST `/diagram` generates:

```
Row 1: [Income: +$15K] → [Expenses: -$4.2K] → [Net Savings: =$10.8K]
                                                    │
                                                    ▼
Row 2: [Savings: $200K] → [Debts: -$50K] → [Goal: $800K] → [Still Needed: $650K] → [5y 1mo ✓]
```

Purple/pink/light purple color scheme. Opens in draw.io iframe for editing and saving.

---

## Summary Table

| Step | Action | Component |
|------|--------|-----------|
| 1 | Normalize digits | `heuristics.normalize_text()` |
| 2 | Regex extraction | `heuristic_classify()` |
| 3 | LLM fallback extraction | `FinancialAgentPipeline.process_input()` |
| 4-8 | Ask → Answer → Update (4 yesno fields) | `generate_question()` / `update_data()` |
| 9 | Completeness check | `check_completeness()` |
| 10 | Calculate timeline | `calculator.calculate_goal()` |
| 11 | Send response with data + calculation | `main.py` → frontend |
| 12 | Background save | `storage.save_chat_record()` |
| 13 | Generate diagram (optional) | `diagram_generator.generate_financial_roadmap()` |
