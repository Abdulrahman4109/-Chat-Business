# Financial Agent — State Machine

The `FinancialAgentPipeline` manages the guided conversation. Each conversation has a state that progresses from extraction → question → answer → calculation.

## State (`FinancialAgentState`)

Persisted per conversation in memory (dictionary keyed by `conversation_id`):

| Field | Type | Description |
|-------|------|-------------|
| `goal` | float? | Target amount |
| `monthly_income` | float? | Main income |
| `monthly_expenses` | float? | Regular expenses |
| `current_savings` | float? | Existing savings |
| `current_debts` | float? | Outstanding debts |
| `extra_income` | float? | Additional income |
| `is_complete` | bool | All required fields collected |
| `messages` | array | Message history for LLM context |
| `result` | CalculationResult? | Final timeline |

## Pipeline Methods

### `process_input(normalized_text)`

Called on the first message of a conversation. Sends the user text to the LLM with `PROCESS_INPUT_PROMPT` which defines each field by meaning (not by name).

The LLM returns a JSON blob:
```json
{
  "goal_price": 800000,
  "monthly_income": 15000,
  "monthly_expenses": null,
  "current_savings": null,
  "current_debts": null,
  "extra_income": 0,
  "segments": [{"type": "goal", "text": "...", "numbers": [800000]}]
}
```

`null` means the user didn't mention it. `0` means explicitly zero.

After parsing, `heuristics.apply_intelligent_defaults()` ensures zero for nil values used in calculation while preserving null for UI visibility.

### `check_completeness(state)`

Returns `(all_fields: bool, missing: list)`.

Required fields: goal, income, expenses. All must be non-null.

Optional fields: savings, debts, extra_income. Also checked but not strictly required — however, the agent still asks for them to provide a complete picture.

### `generate_question(state)`

Uses a fixed order based on missing fields:
1. monthly_expenses → "Do you have any monthly expenses?"
2. current_savings → "Do you have any current savings?"
3. current_debts → "Do you have any current debts or loans?"
4. extra_income → "Do you have any additional income or bonuses?"

Returns a `ChatResponse` with `question_type: "yesno"`, `question_field: "<field_name>"`.

### `update_data(state, user_message)`

Called when the user responds to a yes/no question. Sends the response to the LLM with `UPDATE_DATA_PROMPT` which extracts the value.

The prompt handles:
- Negation ("No", "None", "I don't have") → sets value to `0`
- Affirmative with value ("Yes, 5000") → extracts the number
- Affirmative without value ("Yes" alone) → leaves as null (will re-ask)
- Time units: "500 weekly" → normalize to monthly (~2143)

### `run_orchestrator(state, user_message)`

Main entry point. Logic:
1. If first message → `process_input()`
2. If answering a question → `update_data()`
3. Always → `check_completeness()`
4. If incomplete → `generate_question()` → return with `is_complete: false`
5. If complete → `calculate_goal()` → return with `is_complete: true`

## Prompts

### PROCESS_INPUT_PROMPT
- Defines each field clearly
- Instructs the LLM to normalize time units to monthly
- Requests segments (text classification by type: goal, income, expense, etc.)
- Explicit mention: if no time unit is specified, assume monthly

### UPDATE_DATA_PROMPT
- Understands the context of the question being asked
- Normalizes time values to monthly
- Recognizes negation patterns across languages
- Returns only the field value being asked about

## Session Management

States are stored in a dictionary `_sessions: dict[str, FinancialAgentState]`.

States are never cleaned (intended for a stateless API facade — in production, use a proper database).
