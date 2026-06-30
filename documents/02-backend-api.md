# Backend API

## POST `/chat` — Main Pipeline

Conversational financial goal pipeline: extract → ask follow-ups → calculate.

**Request:**
```json
{ "message": "I want to buy a car worth 800,000. My salary is 16,000.", "user_id": "default-user", "conversation_id": null }
```

**Response (complete):** `is_complete: true` with `calculation` + `extracted_data`
**Response (incomplete):** `is_complete: false` with `question_type` + `question_field`

### Question Types
| Type | When | User Action |
|------|------|-------------|
| `yesno` | Expenses, savings, debts, extra | Yes/No + optional value |
| `ask_value` | Monthly income (first field) | Enter a number |
| `restore_context` | Previous session detected | Yes to restore, No to start fresh |

### Question Order
`monthly_income` (ask_value) → `monthly_expenses` (yesno) → `current_savings` (yesno) → `current_debts` (yesno) → `extra_income` (yesno)

Questions in user's detected language (Arabic or English).

---

## POST `/analyze` — Legacy Extraction

One-shot LLM extraction via `OpenAIExtractionService`.
**Request:** `{ "message": "..." }` **Response:** `{ "data": FinancialData, "token_numbers": [...] }`

---

## POST `/calculate` — Pure Timeline Math

**Request:** `{ "data": FinancialData }` **Response:** `CalculationResult`

---

## GET `/history` — Get Conversations

**Query:** `?user_id=default-user` **Response:** `[ChatRecord, ...]`

---

## DELETE `/history/{conversation_id}` — Delete Conversation

**Query:** `?user_id=default-user` **Response:** `{ "success": true }`

---

## POST `/diagram` — Generate Financial Roadmap

**Request:** `{ "data": FinancialData, "calculation": CalculationResult }`
**Response:** `{ "xml": "<mxGraphModel>..." }`

---

## POST `/diagram/save` — Persist Edited Diagram

**Request:** `{ "conversation_id": "...", "user_id": "...", "xml": "..." }`
**Response:** `{ "success": true }`

---

## GET `/diagram/load` — Load Saved Diagram

**Query:** `?conversation_id=...&user_id=default-user`
**Response:** `{ "xml": "..." }` or `{ "xml": null }`

---

## GET `/health` — Liveness

**Response:** `{ "status": "ok" }`

---

## GET `/mujarrad/status` — Storage Connection

**Response:** `{ "connected": true, "space": "chat", "segments_space": "example" }`

---

## Models

### ChatRequest
| Field | Type | Default | Constraint |
|-------|------|---------|-----------|
| `message` | string | — | 1-8000 chars |
| `user_id` | string | "default-user" | — |
| `conversation_id` | string? | null | auto-generated if null |

### FinancialData
All `float | None`. `null` = unmentioned (hidden in UI). `0` = explicitly zero.

| Field | Description |
|-------|-------------|
| `goal_price` | Target amount |
| `monthly_income` | Main salary |
| `monthly_expenses` | Regular spending |
| `current_savings` | Existing assets |
| `extra_income` | Bonuses, side gigs |
| `current_debts` | Outstanding debts |

### CalculationResult
| Field | Type | Description |
|-------|------|-------------|
| `net_monthly_savings` | float | income + extra - expenses |
| `remaining` | float | max(goal - effective_savings, 0) |
| `months` | int? | Months to goal |
| `raw_months` | float? | Unrounded |
| `days` | int? | Fractional days |
| `duration_display` | string | e.g. "3 years and 5 months" |
| `is_achievable` | bool | Can goal be reached? |
| `suggestions` | string[] | Up to 3 optimization tips |

### ChatResponse
| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `conversation_id` | string | — | Groups messages |
| `assistant_message` | ChatMessage | — | AI response |
| `extracted_data` | FinancialData? | null | Parsed numbers |
| `calculation` | CalculationResult? | null | Timeline result |
| `question_type` | string | "" | "yesno"/"ask_value"/"restore_context" |
| `question_field` | string | "" | Field being asked |
| `is_complete` | bool | True | Done collecting data |
