# Backend API

## Routes

### GET `/health`

**Response:** `{"status": "ok"}`

---

### POST `/analyze`

Extract financial data without saving.

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | User input (1-8000 chars) |

**Response:**
```json
{
  "data": {
    "goal_price": 800000,
    "monthly_income": 17143,
    "monthly_expenses": 3857,
    "current_savings": 20000,
    "extra_income": 6000,
    "current_debts": null,
    "goals": [{"name": "primary goal", "goal_price": 800000}],
    "all_numbers": [4000, 20000, ...],
    "assumptions": [],
    "segments": [...]
  },
  "token_numbers": [4000, 20000, 800000, ...]
}
```

Note: Fields not mentioned by the user appear as `null` (e.g. `current_debts`) and are hidden from the frontend.

---

### POST `/calculate`

Compute timeline from structured FinancialData.

| Field | Type | Description |
|-------|------|-------------|
| `data` | FinancialData | Pre-extracted financial data |

**Response:**
```json
{
  "net_monthly_savings": 19286,
  "remaining": 780000,
  "months": 41,
  "raw_months": 40.44,
  "duration_display": "3 years and 5 months",
  "is_achievable": true,
  "suggestions": [
    "Keep at least 19,286 per month reserved for this goal."
  ]
}
```

---

### POST `/chat` (main endpoint)

Full pipeline: extract → calculate → save → respond.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | yes | User message (1-8000 chars) |
| `user_id` | string | no | Default: "default-user" |
| `conversation_id` | string | no | New UUID generated if not provided |

**Response:**
```json
{
  "conversation_id": "uuid",
  "assistant_message": {
    "id": "uuid",
    "role": "assistant",
    "content": "At your current pace, it will take 3 years and 5 months...",
    "created_at": "2026-06-18T21:00:00+00:00",
    "extracted_data": { ... },
    "calculation": { ... }
  },
  "extracted_data": { ... },
  "calculation": { ... }
}
```

---

### GET `/history`

Fetch conversation history for a user.

| Query | Type | Default | Description |
|-------|------|---------|-------------|
| `user_id` | string | "default-user" | User identifier |

**Response:** `list[ChatRecord]`

---

### GET `/mujarrad/status`

Check Mujarrad API connectivity.

**Response:**
```json
{
  "connected": true,
  "space": "chat",
  "segments_space": "example",
  "api": "https://www.mujarrad.com/api"
}
```

---

## Pydantic Models

### FinancialData
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `goal_price` | float? | null | Target amount |
| `monthly_income` | float? | null | Base salary (monthly) |
| `monthly_expenses` | float? | null | Monthly spending |
| `current_savings` | float? | null | Already saved (null = unmentioned) |
| `extra_income` | float? | null | Bonuses, side income (null = unmentioned) |
| `current_debts` | float? | null | Outstanding debts (null = unmentioned) |
| `goals` | list | [] | Goal descriptors |
| `all_numbers` | list[float] | [] | All detected numbers |
| `assumptions` | list[str] | [] | Processing notes |
| `segments` | list[dict] | [] | Per-segment classifications |

### CalculationResult
| Field | Type | Description |
|-------|------|-------------|
| `net_monthly_savings` | float | income + extra - expenses |
| `remaining`| float | goal - savings (min 0) |
| `months` | int? | Months to goal (null = unachievable) |
| `raw_months` | float? | Exact months before ceiling |
| `duration_display` | str | "5 months", "1 year", "2 years and 3 months" |
| `is_achievable` | bool | Can the goal be reached? |
| `suggestions` | list[str] | Up to 3 suggestions |

### ChatRecord
| Field | Type | Description |
|-------|------|-------------|
| `id` | string | UUID |
| `user_id` | string | Who sent this |
| `conversation_id` | string | Groups messages into conversations |
| `user_message` | ChatMessage | Original user input |
| `assistant_message` | ChatMessage | AI response + data |
| `extracted_data` | FinancialData | Parsed numbers |
| `calculation` | CalculationResult | Timeline result |
| `created_at` | string | ISO datetime |
