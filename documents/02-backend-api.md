# Backend API

## POST `/chat` — Main Endpoint

Conversational pipeline: extract fields → ask follow-ups → calculate → respond.

**Request:**
```json
{
  "message": "I want to buy a car worth 800,000. My salary is 16,000.",
  "user_id": "default-user",
  "conversation_id": null
}
```

**Response (complete):**
```json
{
  "conversation_id": "uuid",
  "assistant_message": {
    "role": "assistant",
    "content": "At your current pace, it will take 3 years and 5 months."
  },
  "extracted_data": { "goal_price": 800000, "monthly_income": 16000, ... },
  "calculation": { "duration_display": "3 years and 5 months", "months": 41, ... },
  "question_type": "",
  "question_field": "",
  "is_complete": true
}
```

**Response (incomplete — awaiting answer):**
```json
{
  "conversation_id": "uuid",
  "assistant_message": { "role": "assistant", "content": "Do you have any monthly expenses?" },
  "extracted_data": { "goal_price": 800000, "monthly_income": 16000 },
  "question_type": "yesno",
  "question_field": "monthly_expenses",
  "is_complete": false
}
```

**Flow:**
1. First call → LLM extracts what it can
2. Missing fields → response has `question_type: "yesno"`, `is_complete: false`
3. User answers "Yes, 1000" or "No" → call again with same `conversation_id`
4. Repeat for each missing field until `is_complete: true`

**Question order:** monthly_expenses → current_savings → current_debts → extra_income

---

## POST `/analyze` — Extraction Only

One-shot extraction without conversation. Uses legacy `OpenAIExtractionService`.

**Request:** `{ "message": "..." }`

**Response:** `{ "data": FinancialData, "token_numbers": [...] }`

---

## POST `/calculate` — Timeline Only

Pure calculation from already-extracted data.

**Request:** `{ "data": FinancialData }`

**Response:** `CalculationResult`

---

## GET `/history`

**Query:** `?user_id=default-user`

**Response:** `[ChatRecord, ...]` — All conversations for this user.

---

## POST `/diagram`

Generate a draw.io XML roadmap diagram.

**Request:** `{ "data": FinancialData, "calculation": CalculationResult }`

**Response:** `{ "xml": "<mxGraphModel>..." }`

---

## POST `/diagram/save`

Save an edited diagram.

**Request:** `{ "conversation_id": "...", "user_id": "...", "xml": "..." }`

**Response:** `{ "success": true }`

---

## GET `/diagram/load`

Load a saved diagram.

**Query:** `?conversation_id=...&user_id=default-user`

**Response:** `{ "xml": "..." }` or `{ "xml": null }`

---

## GET `/health`

**Response:** `{ "status": "ok" }`

---

## GET `/mujarrad/status`

**Response:** `{ "connected": true, "space": "chat", "segments_space": "example", "api": "..." }`

---

## Models

### ChatRequest
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `message` | string | yes | — |
| `user_id` | string | no | "default-user" |
| `conversation_id` | string? | no | null (auto-generated) |

### ChatResponse
| Field | Type | Description |
|-------|------|-------------|
| `conversation_id` | string | Conversation identifier |
| `assistant_message` | ChatMessage | Response text + optional data |
| `extracted_data` | FinancialData? | Parsed numbers (final message only) |
| `calculation` | CalculationResult? | Timeline result (final message only) |
| `question_type` | string | "yesno" if follow-up needed |
| `question_field` | string | Which field is being asked |
| `is_complete` | bool | Whether all data has been collected |

### FinancialData
All fields nullable float — `null` means unmentioned (hidden in UI).

| Field | Description |
|-------|-------------|
| `goal_price` | Target amount to reach |
| `monthly_income` | Main salary/income |
| `monthly_expenses` | Regular monthly spending |
| `current_savings` | Existing savings/assets |
| `extra_income` | Additional income (bonuses, side gigs) |
| `current_debts` | Outstanding debts/loans |
| `goals` | List of goal descriptors |
| `all_numbers` | All detected numbers |
| `assumptions` | Processing notes |
| `segments` | Per-segment classifications |

### CalculationResult
| Field | Type | Description |
|-------|------|-------------|
| `net_monthly_savings` | float | income + extra - expenses |
| `remaining` | float | goal - savings (min 0) |
| `months` | int? | Months to goal |
| `duration_display` | string | Human-readable: "3 years and 5 months" |
| `is_achievable` | bool | Can the goal be reached? |
| `suggestions` | string[] | Up to 3 optimization tips |

### ChatRecord
Stored per conversation turn.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | UUID |
| `user_id` | string | Who sent this |
| `conversation_id` | string | Groups turns into conversations |
| `user_message` | ChatMessage | Original input |
| `assistant_message` | ChatMessage | AI response |
| `extracted_data` | FinancialData | Parsed numbers |
| `calculation` | CalculationResult | Timeline result |
| `created_at` | string | ISO datetime |
