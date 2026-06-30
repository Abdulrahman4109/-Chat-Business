# Financial Agent — State Machine

The `FinancialAgentPipeline` manages a guided conversation. Each conversation has a `FinancialAgentState` that progresses through extraction, questions, answers, and final calculation.

## State (`FinancialAgentState`)

In-memory dict (`guided_sessions`) keyed by `conversation_id`. Never cleaned.

| Field | Type | Notes |
|-------|------|-------|
| `session_id` | string | UUID |
| `goal`, `monthly_income`, `monthly_expenses` | float? | Required fields |
| `current_savings`, `current_debts`, `extra_income` | float? | Optional fields |
| `is_complete` | bool | Starts False |
| `latest_question` | string | Current question text (bilingual) |
| `question_type`, `question_field` | string | "yesno" / "ask_value" / "restore_context" |
| `asked_fields` | list[str] | Avoid re-asking |
| `messages` | list[dict] | Conversation history for LLM context |
| `result` | dict? | Serialized CalculationResult |
| `previous_context` | dict? | Previous session data for restore prompt |
| `goal_description` | str | Natural language goal description |

## Pipeline Methods

### `process_input(state, message)`
1. Run `heuristic_classify(message)` — regex-based extraction
2. Check `is_ready_for_calculation()` — if all 6 fields found, skip LLM
3. If incomplete, call LLM with `PROCESS_INPUT_PROMPT` to extract remaining fields
4. Normalize time units to monthly

### `generate_question(state)`
Iterates `FIELD_ORDER` for first missing field:
```
['monthly_income', 'monthly_expenses', 'current_savings', 'current_debts', 'extra_income']
```

For each field, checks `QUESTION_TYPES` map to determine prompt style:
- `monthly_income` → `ask_value` (direct number input)
- `monthly_expenses`, `current_savings`, `current_debts`, `extra_income` → `yesno`

Questions from `FIELD_QUESTIONS` dict, bilingual (en/ar keys). Language detected by `_detect_language()` — checks Unicode block of conversation messages.

### `update_data(state, answer)`
Handles three question types:
- **`restore_context`**: "Yes" → restore previous field values from `previous_context`; "No" → continue fresh
- **`yesno`**: "No"/negation → value = 0; "Yes, {number}" → extract with time unit normalization
- **`ask_value`**: Extract number directly from answer

Uses `extract_number_mentions()` + `_extract_time_unit()` for value extraction. Negation detection via regex (لا/ليس/ما عندي/no/none/don't have).

### `check_completeness(state)`
All 6 fields must be non-None. `monthly_income`, `monthly_expenses`, `goal` are required; the rest are asked but not strictly required (still set to None if user declines).

## Orchestrator Flow

```
run_orchestrator(state, message):
  1. IF question_type is set (expecting answer):
       update_data(state, message)
  2. ELSE (new message with financial data):
       reset all financial fields → process_input(state, message)
     (non-financial messages don't reset state)
  3. check_completeness(state)
  4. IF complete:
       calculate_goal(data) → store result
       append assistant message with formatted result (bilingual)
       set is_complete = True
  5. IF incomplete:
       generate_question(state)
       append assistant message with question text + metadata
```

**Important**: When a new user message contains financial data (detected by heuristic regex), ALL financial fields are reset to None before `process_input`. This prevents stale data from a previous turn. Non-financial messages (greetings, casual chat) skip the reset.

## Session Restoration (`_restore_session` in main.py)

When a user returns to an existing `conversation_id`:
1. Fetch ChatRecords from history
2. Extract last `FinancialData` and `CalculationResult`
3. Build `previous_context` dict with all field values
4. Set `question_type = "restore_context"` to ask "Would you like to restore your previous data?"
5. If user says Yes → populate all fields from context; if No → start fresh

## Prompts

### PROCESS_INPUT_PROMPT
Single prompt defining all 6 fields by meaning with multilingual examples:
- goal: target price to BUY (عاوز/عايز/اريد + object + ب/تمن/سعر)
- monthly_income: main recurring salary (مرتب/راتب/قبض)
- monthly_expenses: regular spending (مصاريف/إيجار/فواتير)
- current_savings: money ALREADY OWNED (معايا/عندي/معي)
- extra_income: extra recurring (حوافز/مكافآت/اضافي)
- current_debts: amounts OWED (ديون/قروض/عليا)

"منهم/منها" after possession = savings toward goal. Returns JSON, all fields nullable.

No `UPDATE_DATA_PROMPT` exists — `update_data` uses regex-based extraction directly, no LLM call.
