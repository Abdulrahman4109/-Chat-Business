# How the System Works

A simplified step-by-step explanation of how the system processes a user's financial goal.

---

## Overview

The system receives a sentence from the user describing a financial goal, extracts numbers from it, asks for missing information one question at a time, then calculates the timeline to achieve the goal.

---

## Step 1 — User Sends a Message

The user writes a sentence describing their financial goal.

**Required**: The goal + its price. May also include monthly income.

---

## Step 2 — Text Normalization

The system receives the text and unifies number formats:

1. **Convert non-Western digits**: Arabic-Indic and Persian digits are converted to 0-9
2. **Separate text from attached digits**: If a letter is attached to a digit, a space is inserted between them

**Result**: Text ready for analysis, all numbers in a unified format.

---

## Step 3 — Extract Numbers by Regex

The system searches the text for numbers using regex patterns:

1. **Extract all numbers**:
   - Integers
   - Decimals
   - Numbers with suffixes (k, million, thousand)
   - Currencies and comma-separated numbers

2. **Classify numbers by field**:
   - Is this number the **goal** (price)?
   - Is it **monthly income** (salary)?
   - Is it **expenses**?
   - Is it **savings**?
   - Is it **debts**?
   - Is it **extra income**?

3. **Completeness check**:
   - If all six fields are found → skip the next stage
   - If any field is missing → proceed to AI

**Result**: Some fields are filled, others remain empty.

---

## Step 4 — AI Extraction

If the previous stage failed to find all fields, the system calls the AI:

1. **Build instructions for the AI**: Each field is defined in both Arabic and English with its meaning clarified

2. **Send the text to the AI**: Through a model chain (primary model, then fallback if the first fails)

3. **Normalize time units**: If the user says "weekly", multiply by 4.2857. If "yearly", divide by 12. If no unit is specified, the value is assumed to be monthly.

4. **Merge results**: AI results are added to the previous stage's results (they do not replace them)

**Result**: More fields are filled, but some may still be missing.

---

## Step 5 — AI Asks Questions

If fields are still missing, the AI asks the user one field at a time. It tracks which fields have been asked, stores answers, and decides what to ask next.

**Question order**:
1. **Monthly expenses**: "Do you have any monthly expenses?" (Yes/No + value)
2. **Current savings**: "Do you have any current savings?" (Yes/No + value)
3. **Current debts**: "Do you have any debts or loans?" (Yes/No + value)
4. **Extra income**: "Do you have any extra monthly income?" (Yes/No + value)

**For each question**:
- If the answer is "No" → set the value to 0
- If "Yes" with a number → extract the number and normalize the time unit
- If "Yes" without a number → set an estimated value

**Result**: After answering all questions, all six fields are filled.

---

## Step 6 — Calculate Timeline

When all fields are complete, the system calculates the timeline:

### Formulas

```
net_monthly_savings = (income + extra_income) - expenses
effective_savings   = max(savings - debts, 0)
remaining           = max(goal - effective_savings, 0)
months              = ceil(remaining / net_monthly_savings)
```

### Edge Cases

- **No goal**: Result is unachievable
- **Savings already cover the goal**: Duration is 0, message says "already funded"
- **Expenses ≥ income**: Unachievable, suggests reducing expenses
- **No income**: Cannot calculate

### Duration Formatting

Months are converted to a readable string:
- Less than a month → "less than a month"
- One year → "1 year"
- Two years and 3 months → "2 years and 3 months"

### Suggestions

The system provides up to 3 suggestions to improve the result:
- Setting aside a monthly reserve
- Ways to shorten the timeline (if longer than 12 months)
- Reviewing expenses (if they exceed 60% of income)
- Consolidating multiple goals

**Result**: Timeline duration + suggestions + achievability status.

---

## Step 7 — Response

The system builds the response and sends it to the frontend:

**Response contents**:
- **Response text**: A sentence explaining the result
- **Extracted data**: All financial fields (goal, income, expenses, savings, debts, extra income)
- **Calculation result**: Duration, net savings, remaining amount, suggestions
- **Completeness status**: Whether everything was calculated

**In the background**:
- Save the conversation to a local file (`~/.mujarrad-chat/history.json`)
- Save the conversation to the remote server (if it fails, the response is unaffected)

**Result**: The user sees the result immediately while storage happens in the background.



## Summary

| Step | Function | Depends on AI? |
|------|----------|----------------|
| 1. Send message | User describes the goal | No |
| 2. Text normalization | Unify number formats | No |
| 3. Regex extraction | Find and classify numbers | No |
| 4. AI extraction | Find missing fields | Yes |
| 5. AI asks questions | Ask about missing fields | Yes |
| 6. Calculation | Calculate the timeline | No |
| 7. Response and storage | Return result + save | No |

AI is used in Steps 4 and 5. However, from the user's perspective, everything is done by AI.
