# Pipeline Stages — Financial Goal Calculator

A theoretical description of the request processing stages in the Financial Goal Calculator mode, from receiving the user's message to returning the final result.

---

## Overview

```
User Message
      │
      ▼
┌─────────────────┐
│  Normalization  │  ← Convert non-Western digits + detach text from numbers
└────────┬────────┘
         ▼
┌─────────────────┐
│    Heuristics   │  ← Regex number extraction + field classification
└────────┬────────┘
         ▼
┌─────────────────┐
│  LLM Extraction │  ← Extract remaining fields via AI
└────────┬────────┘
         ▼
┌─────────────────┐
│  State Machine  │  ← Dialogue management: question → answer → update
└────────┬────────┘
         ▼
┌─────────────────┐
│   Calculation   │  ← Math formula + optimization suggestions
└────────┬────────┘
         ▼
┌─────────────────┐
│     Output      │  ← Response + background storage
└─────────────────┘
```

Each stage consumes the output of the preceding stage. If all fields are satisfied at an early stage, subsequent unnecessary stages are skipped.

---

## Stage 1 — Normalization

**Input**: Raw user text (string)

**Processing** — `normalize_text()` in `heuristics.py`:

1. **Convert non-Western digits** to 0-9:
   - Arabic-Indic (٠١٢٣٤٥٦٧٨٩) → 0123456789
   - Persian (۰۱۲۳۴۵۶۷۸۹) → 0123456789
   - Any other numeral system is converted to its Western equivalent

2. **Separate text from attached digits**:
   - Insert a space between non-Latin characters and adjacent digits
   - Example: "بـ50000" → "بـ 50000"
   - Ensures regex patterns work correctly in the next stage

**Output**: Normalized string

**Purpose**: Unify different numeral formats (Arabic/Persian/Western, attached/detached) before processing. Without this stage, regex and the LLM would fail to extract numbers entered in non-Western scripts.

---

## Stage 2 — Heuristic Extraction

**Input**: Normalized text + list of required fields

**Processing** — `heuristic_classify()` in `heuristics.py`:

 1. **Extract all numbers** from text via `extract_number_mentions()` — handles integers, decimals, currencies, suffixes, and thousands separators

 2. **Classify numbers into fields** by matching regex patterns:
   - `goal_price`
   - `monthly_income`
   - `monthly_expenses`
   - `current_savings`
   - `current_debts`
   - `extra_income`

 3. **Early completeness check** via `is_ready_for_calculation()`:
   - If all six fields are found with non-null values → skip the LLM stage entirely
   - If any field is missing → proceed to the LLM stage

**Output**: `FinancialData` object (some fields may be null) + preliminary completeness flag

**Purpose**: Fast extraction with zero API cost and latency. Regex runs locally in milliseconds. It fully covers ~40-60% of simple cases.

---

## Stage 3 — LLM Extraction

**Input**: Normalized text + incomplete `FinancialData` object

**Processing** — `process_input()` → LLM call with `PROCESS_INPUT_PROMPT`:

 1. **Build the prompt** with field definitions in both Arabic and English

2. **Send to the LLM** via the model chain (`chain_call()`):
   - Primary model: gpt-4o-mini via OpenRouter
   - Fallback model: openrouter/free
   - If all fail: heuristic values only are used

 3. **Normalize time units** to monthly equivalents (weekly, daily, yearly — or assume monthly if unspecified)

4. **Merge results**: LLM results merge with heuristic results (they do not replace them)

**Output**: Updated `FinancialData` object (more non-null fields)

**Purpose**: Extract fields that heuristic regex failed to capture due to linguistic complexity. The LLM understands context and implications that regex cannot.

---

## Stage 4 — State Machine

**Input**: `FinancialData` object + `FinancialAgentState` (session state)

**Processing** — `FinancialAgentPipeline` methods in `financial_agent/pipeline.py`:

### 4.1 — Completeness Check (`check_completeness`)
- Iterate over all six fields
- If any field is null → dialogue is incomplete
- If all are non-null → dialogue is complete

### 4.2 — Question Generation (`generate_question`) [if incomplete]
- Identify the first missing field in order:
  1. `monthly_income` — ask directly (ask_value)
  2. `monthly_expenses` — ask Yes/No (yesno)
  3. `current_savings` — ask Yes/No (yesno)
  4. `current_debts` — ask Yes/No (yesno)
  5. `extra_income` — ask Yes/No (yesno)
- Build the question text in the user's detected language (Arabic or English)
- Store `question_type` and `question_field` in the session state

### 4.3 — Data Update (`update_data`) [on user answer]
- If question type is `yesno`:
  - "No" or negation → set value to 0
  - "Yes" with a number → extract the number (with time unit normalization)
  - "Yes" without a number → set an estimated value
- If question type is `ask_value`:
  - Extract the number directly from the answer
- If question type is `restore_context` (previous session):
  - "Yes" → restore all values from the previous session
  - "No" → start a new session

### 4.4 — Routing
- If all fields are complete → proceed to the calculation stage
- If a field is still missing → generate a new question for the next field

**Output**: Either a new question (with `is_complete: false`) or complete data for calculation

**Purpose**: Collect missing information interactively. Instead of overwhelming the user by asking for everything at once, the process is broken into small, natural steps.

---

## Stage 5 — Calculation

**Input**: Complete `FinancialData` object

**Processing** — `calculate_goal()` in `calculator.py`:

### 5.1 — Core Formulas

```
net_monthly_savings = (income + extra_income) - expenses
effective_savings   = max(savings - debts, 0)
remaining           = max(goal - effective_savings, 0)
months              = ceil(remaining / net_monthly_savings)   (if net_savings > 0)
```

### 5.2 — Edge Cases
- **No goal** (`goal` is null or 0) → result: unachievable
- **Remaining ≤ 0** (savings already cover the goal) → `months = 0`, message: "already funded"
- **Net savings ≤ 0** (expenses ≥ income) → unachievable, suggestion to reduce expenses
- **Income is null** → unachievable (cannot calculate without income)

### 5.3 — Duration Formatting (`format_duration`)
- Convert months to a bilingual display string (e.g. "3 years and 5 months" / "٣ سنوات و ٥ أشهر")

### 5.4 — Suggestion Generation (`build_suggestions`)
Maximum 3 suggestions from the following pool:
- If `months > 0`: suggest setting aside a monthly reserve
- If `months > 12`: suggest ways to shorten the timeline
- If `expenses > 0.6 × income`: suggest reviewing expenses
- If multiple goals exist: suggest consolidating goals

**Output**: `CalculationResult` object (months, duration_display, is_achievable, suggestions)

**Purpose**: Transform the extracted financial data into an understandable, actionable result.

---

## Stage 6 — Output & Storage

**Input**: `FinancialData` object + `CalculationResult`

**Processing** — `handle_message()` in `main.py`:

### 6.1 — Build Response
- `assistant_message`: response text in the appropriate language (Arabic/English)
- `extracted_data`: all extracted financial fields
- `calculation`: calculation result (if complete)
- `is_complete`: true/false
- `question_type` and `question_field`: (if incomplete)

### 6.2 — Background Storage
`asyncio.create_task` performs the following without blocking the response:
1. Local save: `~/.mujarrad-chat/history.json`
2. Remote save: POST to Mujarrad API (best-effort)

**Output**: JSON response to the frontend

**Purpose**: Return the result immediately while persisting records in the background. Remote storage failure does not affect the user experience.

---

## Summary

| Stage | Component | Cost | Latency | Depends on LLM? |
|-------|-----------|------|---------|-----------------|
| 1. Normalization | `heuristics.py` | Free | <1ms | No |
| 2. Heuristic Extraction | `heuristics.py` | Free | <5ms | No |
| 3. LLM Extraction | `llm_chain.py` + prompts | ~$0.001 | ~1-3s | Yes |
| 4. State Machine | `financial_agent/pipeline.py` | Free | <1ms | No |
| 5. Calculation | `calculator.py` | Free | <1ms | No |
| 6. Output & Storage | `main.py` + `storage.py` | Varies | <1ms (+ async) | No |

The only costly call is Stage 3 (LLM). All other stages are local and free. In simple cases (where the heuristic covers all fields), Stage 3 is skipped entirely, resulting in <10ms response time.
