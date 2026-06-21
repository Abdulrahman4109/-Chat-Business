# Financial Chat Assistant — Project Memory

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, uvicorn (port 8000) |
| Frontend | React 19, Vite (port 5173, proxy → 8001) |
| AI | gpt-4o-mini via OpenRouter |
| Storage | Local JSON (`~/.mujarrad-chat/history.json`) + Mujarrad API |

## Key API Endpoints (`backend/app/main.py`)

| Route | Method | Input | Output |
|-------|--------|-------|--------|
| `/health` | GET | — | `{"status": "ok"}` |
| `/analyze` | POST | `{message}` | `{data: FinancialData, token_numbers}` |
| `/calculate` | POST | `{data: FinancialData}` | `CalculationResult` |
| `/chat` | POST | `{message, user_id, conversation_id?}` | `{conversation_id, assistant_message, extracted_data, calculation}` |
| `/history` | GET | `?user_id=` | `list[ChatRecord]` |
| `/mujarrad/status` | GET | — | `{connected, space, segments_space, api}` |

## Pydantic Models (`backend/app/models.py`)

| Model | Key Fields |
|-------|-----------|
| `ChatRequest` | `message: str` (1-8000), `user_id: str` (default="default-user"), `conversation_id: str\|None` |
| `FinancialData` | `goal_price, monthly_income, monthly_expenses, current_savings=None, extra_income=None, current_debts=None, goals: list[dict]=[], all_numbers: list[float]=[], assumptions: list[str]=[]` — all floats non-negative; None means unmentioned (hidden from UI) |
| `CalculationResult` | `net_monthly_savings, remaining, months, duration_display, is_achievable, suggestions: list[str]` |
| `ChatMessage` | `id, role, content, created_at, extracted_data?, calculation?` |
| `ChatRecord` | `id, user_id, conversation_id, user_message, assistant_message, extracted_data, calculation, created_at` |
| `ChatResponse` | `conversation_id, assistant_message, extracted_data, calculation` |

## Extraction Pipeline (`/chat` flow)

1. **`nlp.extract_numbers(message)`** — regex + spaCy → `list[float]`
2. **LLM #1 — `segment_with_llm(message)`**:
   - GPT with `SEGMENTER_PROMPT` → `{"segments": [...]}`
   - Falls back to `segmenter.segment_text()` regex splitter if unavailable
3. **LLM #2 — `extract(message, token_numbers, segments)`**:
   - Time normalization: `extract_time_unit()` + `normalize_value()`
   - 11 time units × Arabic/English variants (25+), computed multipliers (`كل 2 شهر` → `__MULT_0.5__`)
   - Fallback: `heuristic_extract()` — numbers only, no field classification
   - `_aggregate_segment_extractions()` merges per-segment results into FinancialData
4. **`calculator.calculate_goal(data)`**:
   - `net_savings = income + extra - expenses`
   - `effective_savings = max(savings - debts, 0)`
   - `months = ceil(max(goal - effective_savings, 0) / net_savings)`
5. **`_store_async()`** (background, after response):
   - Save raw segments (parallel asyncio.gather)
   - Update classified segments (parallel asyncio.gather)
   - Save chat record → local JSON + Mujarrad POST

## Heuristics (`backend/app/heuristics.py`)

Pure number-extraction fallback — no keyword classification:
- `normalize_text()` — Arabic-Indic digits (٠-٩, ۰-۹) → Western digits
- `extract_number_mentions()` — regex pattern for all number formats
- `heuristic_extract()` — extracts numbers to `all_numbers` only (LLM is sole classifier)
- `apply_intelligent_defaults()` — None→0 for calculator, builds `goals` list

## Calculator (`backend/app/calculator.py`)

- `calculate_goal(data)` → `CalculationResult`
- No goal → unachievable; remaining=0 → "already funded"; net_savings≤0 → unachievable
- `effective_savings = max((savings or 0) - (debts or 0), 0)` — debts reduce available capital
- `format_duration(months)` → "5 months" / "1 year" / "2 years and 3 months"
- `build_suggestions()` → max 3: reserve suggestion, >12mo optimization, >60% expense review, multi-goal prioritization

## NLP (`backend/app/nlp.py`)

- `extract_numbers(text)` — two-pass: regex patterns + spaCy `like_num`, deduplicated
- spaCy model `en_core_web_sm` loaded lazily (optional, not in requirements.txt)

## Config (`backend/app/config.py`)

| Field | Default | Notes |
|-------|---------|-------|
| `openai_api_key` | `""` | OpenRouter (`sk-or-v1-...`) or OpenAI (`sk-...`) |
| `openai_base_url` | `https://openrouter.ai/api/v1` | Empty string = direct OpenAI |
| `openai_model` | `gpt-4o-mini` | Shared for both LLM calls |
| `mujarrad_public_key` | `""` | Mujarrad API public key |
| `mujarrad_secret_key` | `""` | Mujarrad API secret key |
| `mujarrad_api_base` | `https://www.mujarrad.com/api` | Mujarrad API base URL |
| `mujarrad_space_url` | `https://.../spaces/chat` | Chat records space |
| `mujarrad_segments_space_url` | `https://.../spaces/example` | Segment nodes space |
| `cors_origins` | `localhost:5173,...` | Comma-separated allowed origins |

Properties: `cors_origin_list` (splits by comma), `mujarrad_space_slug` / `mujarrad_segments_space_slug` (extracted from URL last segment).

## Storage (`backend/app/storage.py`)

- `MujarradStorage` — reads settings, builds auth headers (`X-API-Key`, `X-API-Secret`)
- Two space slugs: `slug` (chat history → `chat`), `segments_slug` (financial nodes → `example`)
- `_load_local()` / `_save_local()` — `~/.mujarrad-chat/history.json`
- `save_chat_record()` — local + async POST to `chat` space
- `save_segment_node()` / `update_segment_node()` — async POST to `example` space (best-effort, never raises)
- `get_history()` — local first, then Mujarrad GET (paginated, size=50), merge remote→local on success, fallback to local
- `check_connection()` — health check via GET `{base}/spaces/{slug}/nodes?size=1`

## Frontend (`frontend/src/main.jsx`)

- **Components**: `App` (root), `Message` (bubble + grid + result), `Metric` (label+value, null for None fields)
- **State**: `userId` (localStorage), `conversationId`, `messages[]`, `input`, `history[]`, `loading`, `sidebarOpen`, `abortRef`
- **Cancel**: `AbortController` in `sendMessage()`, button appears during loading — aborts cleanly without error message
- **Metric**: returns `null` for `null`/`undefined` — unmentioned fields invisible
- **Analysis grid**: Net Savings row conditional on `current_debts`
- **History**: grouped by `conversation_id`, most-recent-first, sidebar shows first user message
- **Styling**: Dark CSS variables (`--bg: #02000F`, `--primary: #541288`, `--accent: #A582B1`), responsive at 860px
- **API base**: `VITE_API_BASE_URL || ''` (Vite proxy → `localhost:8001`)

## Mujarrad API

| Detail | Value |
|--------|-------|
| Chat space slug | `chat` |
| Segments space slug | `example` |
| Auth | `X-API-Key` + `X-API-Secret` |
| Endpoints | `POST/GET /api/spaces/{slug}/nodes` |
| Chat payload | `{title: "chat-{id}", nodeType: "REGULAR", nodeDetails: <ChatRecord>}` |
| Segment payload | `{title: "seg-{conv}-{idx}", nodeType: "SEGMENT", nodeDetails: {...}}` |
| Web UI | `https://www.mujarrad.com/spaces/chat` / `https://www.mujarrad.com/spaces/example` |

## Project Structure

```
chat/
├── CLAUDE.md
├── ARCHITECTURE.md
├── README.md
├── .gitignore
│
├── backend/
│   ├── .env
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── config.py
│   │   ├── openai_service.py
│   │   ├── heuristics.py
│   │   ├── calculator.py
│   │   ├── nlp.py
│   │   ├── segmenter.py
│   │   ├── storage.py
│   │   └── schema.json
│   ├── scripts/
│   │   ├── generate_training_data.py
│   │   ├── finetune_data.jsonl
│   │   └── HOW_TO_FINETUNE.md
│   └── tests/                 ← 85 tests
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       └── styles.css
│
└── documents/
    ├── 00-overview.md
    ├── 01-architecture.md
    ├── 02-backend-api.md
    ├── 03-ai-pipeline.md
    ├── 04-storage.md
    └── 05-frontend.md
```

## Common Commands

### Backend
```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
.venv\Scripts\python -m pytest tests -v
```

### Frontend
```powershell
cd frontend
npm run dev      # localhost:5173, proxy → localhost:8001
npm run build    # output → dist/
```

## Tests (85 total)

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_calculator.py` | 10 | Goal calc, formatting, suggestions, edge cases |
| `tests/test_heuristics.py` | 24 | Number extraction, Arabic digits, defaults |
| `tests/test_models.py` | 10 | Defaults, validation, serialization |
| `tests/test_nlp.py` | 9 | Numbers, currency, Arabic digits, dedup, attachments |
| `tests/test_openai_service.py` | 19 | Heuristic fallback, aggregation, segments, time units |
| `tests/test_segmenter.py` | 13 | Empty input, Arabic/English splits, conjunctions, max segments |

## Notes

- spaCy is optional (not in `requirements.txt`) — regex-only number extraction works without it
- Frontend dependencies use `"latest"` in `package.json`
- Vite proxy targets `localhost:8001` (not 8000) in `vite.config.js`
- Storage tests are missing (`storage.py` and `main.py` have no tests due to async/API complexity)
