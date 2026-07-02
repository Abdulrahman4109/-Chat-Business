# Financial Chat Assistant — Project Memory

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, uvicorn (port 8000) |
| Frontend | React 19, Vite (port 5173, proxy → 8001) |
| AI | gpt-4o-mini via OpenRouter or direct OpenAI |
| Storage | Local JSON (`~/.mujarrad-chat/history.json`) + Mujarrad API |

## Project Structure

```
chat/
├── backend/
│   ├── .env
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                       # All routes
│   │   ├── models.py                     # Pydantic schemas
│   │   ├── config.py                     # Environment settings
│   │   ├── heuristics.py                 # Text normalization & defaults
│   │   ├── calculator.py                 # Goal timeline math
│   │   ├── nlp.py                        # Regex + optional spaCy extraction
│   │   ├── openai_service.py             # Legacy extraction (used by /analyze)
│   │   ├── segmenter.py                  # Text splitting
│   │   ├── llm_chain.py                  # Model fallback chain (OpenRouter)
│   │   ├── diagram_generator.py          # Draw.io XML generation
│   │   ├── storage.py                    # Local + remote persistence
│   │   ├── financial_agent/              # Guided conversation state machine
│   │   │   ├── models.py
│   │   │   ├── pipeline.py
│   │   │   └── prompts.py
│   ├── scripts/                          # Training data generation
│   └── tests/                            # 169 tests
├── frontend/
│   ├── package.json                      # React 19, Vite, lucide-react
│   ├── index.html
│   ├── vite.config.js                    # Proxy to 8001
│   └── src/
│       ├── main.jsx                      # App, Message, Metric components
│       └── styles.css                    # Dark theme
└── documents/                            # 11 markdown docs
```

## Core Endpoints (`main.py`)

| Route | Method | Purpose |
|-------|--------|---------|
| `/chat` | POST | Conversational extraction → guided questions → calculation |
| `/analyze` | POST | One-shot LLM extraction (legacy) |
| `/calculate` | POST | Pure timeline math on existing data |
| `/diagram` | POST | Generate draw.io roadmap XML |
| `/diagram/save` | POST | Persist edited diagram |
| `/diagram/load` | GET | Load saved diagram |
| `/history` | GET | Past conversations for a user |
| `/health` | GET | Liveness check |
| `/mujarrad/status` | GET | Storage connection status |

## `/chat` Pipeline

1. **Normalize**: `heuristics.normalize_text()` — converts non-Western digits (Arabic-Indic, Persian, etc.) to 0-9; inserts spaces between letters and attached digits
2. **Regex**: `heuristic_classify()` extracts and classifies numbers into fields (helper step)
3. **LLM**: Extracts all remaining fields via `chain_call()` with `PROCESS_INPUT_PROMPT` — normalizes time units to monthly equivalents
4. **Completeness check**: all fields (goal, income, expenses, savings, debts, extra) must be non-null
5. **If incomplete**: return `question_type: "yesno"` with field name; user answers Yes/No with optional value
6. **If complete**: calculate timeline via `calculator.calculate_goal()`
7. **Store**: background `asyncio.create_task` saves ChatRecord to local JSON + remote API (never blocks response)

### Calculation Formula
```
net_savings = (income + extra) - expenses
effective_savings = max((savings or 0) - (debts or 0), 0)
remaining = max(goal - effective_savings, 0)
months = ceil(remaining / net_savings)  if net_savings > 0
```

### Question Order
monthly_expenses → current_savings → current_debts → extra_income

Questions are asked in the user's detected language (Arabic detected by Unicode block, otherwise English).

### Response Fields
| Field | When Present |
|-------|-------------|
| `extracted_data` | Always (shows current state) |
| `calculation` | Only when `is_complete: true` |
| `question_type` | "yesno" when more info needed |
| `question_field` | Which field is being asked about |
| `is_complete` | True only when all fields collected and calculated |

## Key Models

### FinancialData
All floats nullable. `null` = unmentioned (hidden in UI). `0` = explicitly stated as zero.

| Field | Description |
|-------|-------------|
| `goal_price` | Target amount |
| `monthly_income` | Main salary |
| `monthly_expenses` | Regular spending |
| `current_savings` | Existing assets |
| `current_debts` | Amounts owed |
| `extra_income` | Bonuses, side gigs, etc. |

### CalculationResult
| Field | Type | Description |
|-------|------|-------------|
| `net_monthly_savings` | float | income + extra - expenses |
| `remaining` | float | goal - effective savings (min 0) |
| `months` | int? | Months to goal |
| `raw_months` | float? | Unrounded value |
| `duration_display` | string | "3 years and 5 months" |
| `is_achievable` | bool | Can goal be reached? |
| `suggestions` | string[] | Up to 3 optimization tips |

### ChatResponse
| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `conversation_id` | string | — | Groups messages |
| `assistant_message` | ChatMessage | — | AI response |
| `extracted_data` | FinancialData? | null | Parsed numbers |
| `calculation` | CalculationResult? | null | Timeline result |
| `question_type` | string | "" | "yesno" during follow-up |
| `question_field` | string | "" | Field being asked |
| `is_complete` | bool | True | Done collecting data |

## State Management

### Financial Agent (`financial_agent/`)
Per-conversation state stored in `guided_sessions: dict[str, FinancialAgentState]`.

| Field | Type | Notes |
|-------|------|-------|
| `session_id` | string | UUID |
| `goal, monthly_income, monthly_expenses` | float? | Required fields |
| `current_savings, current_debts, extra_income` | float? | Optional fields |
| `is_complete` | bool | Starts False |
| `latest_question` | string | Current question text |
| `question_type, question_field` | string | Current question metadata |
| `asked_fields` | list[str] | Avoid re-asking fields |
| `messages` | list[dict] | Conversation history for LLM context |
| `result` | dict? | Calculated timeline |

### Session Cleanup
States are never cleaned (in-memory dictionary). For production, use a database.

## Text Normalization (`heuristics.py`)

- `normalize_text()`: Converts all non-Western digits to 0-9; inserts space between non-Latin script characters and attached digits
- `extract_number_mentions()`: Regex for all number formats (decimals, `k`/`m` suffixes, currency prefixes, thousands separators)
- `heuristic_extract()`: Pure number extraction to `all_numbers` list (no classification — LLM is sole classifier)
- `apply_intelligent_defaults()`: Converts None→0 for calculator; builds goals list; preserves null for UI

## Prompts

### PROCESS_INPUT_PROMPT
Extracts all fields from the initial message. Defines each field by meaning with multilingual examples. Time unit normalization rules: weekly×4.2857, daily×30, yearly÷12; no unit = assume monthly.

### UPDATE_DATA_PROMPT
Extracts value from yes/no answers. Handles negation (sets 0), affirmation with value, time unit normalization.

## Calculator (`calculator.py`)

Edge cases:
- No goal → unachievable
- Remaining ≤ 0 → "already funded" (months = 0)
- Net savings ≤ 0 → unachievable with suggestions to reduce expenses
- `format_duration(months)`: "5 months", "1 year", "2 years and 3 months"
- `build_suggestions()`: max 3 from reserve, >12mo optimization, >60% expense review, multi-goal

## Storage (`storage.py`)

| Method | Purpose |
|--------|---------|
| `save_chat_record()` | Local JSON + async POST to `chat` space |
| `save_segment_node()` | Async POST to `example` space (legacy) |
| `save_diagram_node()` | Async POST to `graph` space |
| `get_diagram_node()` | GET from `graph` space |
| `get_history()` | Local first → remote (paginated, 50/size) → replace local on success |
| `check_connection()` | Health check via minimal GET |

### Slugs
| Slug | Space URL suffix | Content |
|------|-----------------|---------|
| `chat` | `/spaces/chat` | Chat history |
| `example` | `/spaces/example` | Segment nodes (legacy) |
| `graph` | `/spaces/graph` | Diagram XML |

All remote saves are best-effort (failures logged, never raise). Auth via `X-API-Key` + `X-API-Secret` headers.

## Config (`config.py` — `.env` file)

| Variable | Default | Notes |
|----------|---------|-------|
| `openai_api_key` | "" | `sk-or-v1-...` (OpenRouter) or `sk-...` (OpenAI) |
| `openai_base_url` | `https://openrouter.ai/api/v1` | Empty = direct OpenAI |
| `openai_model` | `gpt-4o-mini` | Extraction model |
| `mujarrad_*_key` | "" | API authentication |
| `mujarrad_*_space_url` | `https://.../spaces/{slug}` | Per-space URLs |
| `cors_origins` | `localhost:5173,127.0.0.1:5173` | Comma-separated |

## Frontend (`main.jsx`)

### Components
- **App**: Root — manages state, chat flow, Yes/No buttons, diagram modal, history sidebar, mode toggle (chat)
- **Message**: Bubble with text + optional analysis grid + optional result panel + optional "View Financial Plan" button
- **Metric**: Label + formatted value row; returns null for null/undefined

### State
| Variable | Type | Purpose |
|----------|------|---------|
| `mode` | "chat" | App mode |
| `userId` | string | Persistent (localStorage) |
| `conversationId` | string? | Active conversation |
| `messages` | array | Current conversation |
| `history` | array | All past records |
| `loading` | bool | Fetch in progress |
| `pendingYesNo` | object? | Current Yes/No prompt |
| `diagramOpen` | bool | Diagram modal visibility |

### Chat Flow
1. User types message → POST `/chat`
2. If response `is_complete: false` with `question_type: "yesno"` → show Yes/No buttons
3. Yes → inline input for value; No → auto-send "No"
4. If `is_complete: true` → show result with analysis grid + calculation + diagram button

### Diagram Modal
- Embedded iframe at `https://embed.diagrams.net`
- `postMessage` protocol: draw.io sends "init" → frontend replies with "load" + XML
- Save button in draw.io triggers frontend → POST `/diagram/save`
- Only accepts messages from `*.diagrams.net`, `*.draw.io`

### Styling
- CSS variables: `--bg: #02000F`, `--primary: #541288`, `--accent: #A582B1`, `--text: #F5F5F5`
- Responsive at 860px breakpoint
- No CSS framework

## Diagram Generator (`diagram_generator.py`)

Produces `mxGraphModel` XML with two rows:
- Row 1: Income → Expenses → (Extra Income) → Net Savings
- Row 2: Current Savings → Goal → Still Needed → Timeline/Achievability

Color scheme: income (purple #8E3DFF), expenses (pink #E35CFF), assets (light purple #C9A4FF), result (based on achievability).

## Tests (169)

| File | Tests | Scope |
|------|-------|-------|
| `test_calculator.py` | 18 | Math, formatting, suggestions, edge cases |
| `test_field_classification.py` | 65 | Heuristic + LLM classification |
| `test_financial_agent.py` | 11 | Normalization, pipeline logic |
| `test_heuristics.py` | 24 | Number extraction, digit conversion, defaults |
| `test_models.py` | 10 | Defaults, validation, serialization |
| `test_nlp.py` | 9 | Numbers, currency, dedup |
| `test_openai_service.py` | 19 | Fallback, aggregation, time units |
| `test_segmenter.py` | 13 | Text splits, edge cases |

## Commands

```powershell
# Backend
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
.venv\Scripts\python -m pytest tests -v

# Frontend
cd frontend
npm run dev      # localhost:5173, proxy → 8001
npm run build    # output → dist/
```

## Notes

- `null` ≠ `0` in FinancialData — null means unmentioned (hidden in UI), 0 means explicitly zero
- spaCy is optional (`en_core_web_sm` lazy-loaded, not in requirements.txt) — regex works without it
- Vite proxy targets port 8001 (not 8000)
- Storage module has no dedicated tests due to async/API complexity
- Documents are in `documents/` directory: 00-overview through 11-how-it-works
