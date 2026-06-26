# AI Pipeline

The data processing pipeline converts raw user text into structured financial data and a goal timeline.

## Stage 1: Text Normalization

All user messages pass through `heuristics.normalize_text()` before LLM processing:

1. **Digit conversion**: Non-Western digit systems (Arabic-Indic, Persian, etc.) → 0-9
2. **Text/digit separation**: Inserts spaces between non-Latin script characters and adjacent digits — e.g., text with attached numbers like `text123text456` becomes `text 123 text 456`
3. **No modification to**: `k`/`m` suffixes, thousands separators, decimal points, currency symbols

This normalization happens at both ends: before sending to the LLM and when parsing LLM responses.

---

## Stage 2: Guided Extraction (Financial Agent)

The `FinancialAgentPipeline` manages a conversation state machine:

### Initial Extraction
Sends the user's message to the LLM with a prompt that defines fields by meaning:
- **goal**: target amount (price, target, goal, purchase)
- **monthly_income**: main salary or income
- **monthly_expenses**: regular spending
- **current_savings**: assets already owned
- **current_debts**: amounts owed
- **extra_income**: additional income (bonuses, commissions, side gigs)

### Time Unit Normalization
The LLM normalizes time values to monthly equivalents:
- If a time unit is mentioned (weekly, daily, yearly) → convert to monthly (weekly ×4.2857, daily ×30, yearly ÷12)
- If no time unit — assume already monthly

### Completeness Check
After extraction, each field is checked. Required: goal, income, expenses. Optional: savings, debts, extra income. All fields must be non-null before completion.

### Follow-up Questions
When fields are missing, the system asks a yes/no question in order:
1. Expenses → 2. Savings → 3. Debts → 4. Extra Income

The user answers with "Yes, {amount}" or "No". The LLM extracts the value and normalizes time units.

### Answer Extraction
- "No" / negation → value = 0
- "Yes, {number}" with no time unit → value = {number} (assumed monthly)
- "Yes, {number} weekly/daily/yearly" → normalized to monthly

---

## Stage 3: Calculation

Formula:
```
net_savings = (income + extra) - expenses
effective_savings = max((savings or 0) - (debts or 0), 0)
remaining = max(goal - effective_savings, 0)
months = ceil(remaining / net_savings)
```

### Edge Cases

| Condition | Result |
|-----------|--------|
| No goal amount | Unachievable |
| Already have enough savings | "Already funded" (months = 0) |
| Net savings ≤ 0 | Unachievable, suggests expense reduction |
| Debts present | Debts reduce effective savings (savings - debts) |
| Goal achievable | Human-readable duration (months/years) |

### Suggestions
Up to 3 tips returned with every calculation:
1. Reserve the net savings amount monthly
2. If timeline > 12 months: small income increase or expense reduction helps
3. If expenses > 60% of income: review fixed costs
4. If multiple goals: prioritize one at a time

---

## Stage 4: Background Storage

After the response is sent, storage runs asynchronously:
1. Save `ChatRecord` (user message + assistant message + data) to local JSON
2. Save `ChatRecord` to remote API (best-effort, failures logged but ignored)

Storage never blocks the response.
