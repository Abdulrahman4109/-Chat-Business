# AI Pipeline

Two-stage extraction pipeline: fast regex heuristic first, LLM fallback when heuristic can't classify all fields.

## Stage 1: Text Normalization

`heuristics.normalize_text()` runs on every input:
1. **Digit conversion**: Arabic-Indic (٠-٩), Persian (۰-۹) → 0-9
2. **Detach numbers**: Insert space between non-Latin text and adjacent digits

No modification to: `k`/`m` suffixes, thousands separators, decimal points, currency symbols.

## Stage 2: Hybrid Extraction

### Heuristic First (`heuristic_classify`)
Regex patterns match financial keywords in Arabic + English (see `heuristics.py` patterns):
- Goal: عاوز/عايز/اريد/نفسي + object + ب/تمن/سعر/قيمة/ثمن
- Income: مرتب/راتب/قبض/أجر/دخل/salary
- Expenses: مصاريف/إيجار/فواتير/expenses
- Savings: معايا/عندي/معي/مدخرات/savings/have
- Debts: ديون/قروض/عليا/debts/loans
- Extra: حوافز/مكافآت/اضافي/commission/bonus

Each pattern finds the closest number + time unit multiplier (weekly×4.2857, daily×30, yearly÷12, biweekly×2.1429).

### LLM Fallback
If `is_ready_for_calculation()` returns False after heuristic, calls LLM with `PROCESS_INPUT_PROMPT`:
- Defines each field by meaning (not name)
- Time unit normalization rules
- Returns JSON with all fields nullable

## Stage 3: State Machine (`/chat` pipeline)

1. **New message** → if heuristic detects financial data → reset all fields → `process_input` (heuristic → LLM). Non-financial messages (e.g. "hello") don't reset state
2. **Answer to question** → `update_data` — extract value from Yes/No answer
3. **Check completeness** — all 6 fields must be non-None
4. **If incomplete** → `generate_question` — pick next unanswered field, set question type:
   - `ask_value` for income (direct number input)
   - `yesno` for expenses/savings/debts/extra
   - `restore_context` when previous session detected
5. **If complete** → `calculate_goal()` → result

### Language Detection
`_detect_language()` checks Unicode block of conversation messages. Questions, labels, and result formatting switch between English and Arabic accordingly.

## Stage 4: Calculation

```python
net_savings = (income + extra) - expenses
effective_savings = max((savings or 0) - (debts or 0), 0)
remaining = max(goal - effective_savings, 0)
months = ceil(remaining / net_savings) if net_savings > 0
```

### Edge Cases
| Condition | Result |
|-----------|--------|
| No goal | Unachievable, suggest target |
| Remaining ≤ 0 | "Already funded" (months = 0) |
| Net savings ≤ 0 | Unachievable, suggest expense reduction |
| Debts present | Reduce effective savings |

### Suggestions (max 3)
1. Reserve net savings monthly
2. If >12 months: small increase helps
3. If expenses >60% of income: review fixed costs
4. If multiple goals: prioritize one at a time

**Output**: Bilingual (`format_duration` / `format_duration_ar`) with years, months, days.

## Stage 5: Background Storage

`asyncio.create_task` — never blocks the response. Saves ChatRecord to local JSON + remote Mujarrad API.
