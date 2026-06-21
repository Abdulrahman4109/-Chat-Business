# Financial Chat Assistant — Project Memory

## Stack
- **Backend**: Python FastAPI (port 8000, uvicorn)
- **Frontend**: React 19 + Vite (port 5173, proxy → 8001)
- **AI**: gpt-4o-mini via OpenRouter (OpenAI-compatible API)
- **Storage**: Local JSON (`~/.mujarrad-chat/history.json`) + Mujarrad API sync

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
| `FinancialData` | `goal_price, monthly_income, monthly_expenses, current_savings=None, extra_income=None, current_debts=None, goals: list[dict]=[], all_numbers: list[float]=[], assumptions: list[str]=[]` — all floats validated non-negative; None means unmentioned and hidden from UI |
| `CalculationResult` | `net_monthly_savings, remaining, months, duration_display, is_achievable, suggestions: list[str]` |
| `ChatMessage` | `id, role, content, created_at, extracted_data?, calculation?` |
| `ChatRecord` | `id, user_id, conversation_id, user_message, assistant_message, extracted_data, calculation, created_at` |
| `ChatResponse` | `conversation_id, assistant_message, extracted_data, calculation` |

## Extraction Pipeline (`/chat` flow)

1. **`nlp.extract_numbers(message)`** — regex + spaCy tokenizer → `list[float]`
2. **`segmenter.segment_text(message)`** — regex splitter → `list[str]`
3. **LLM #1 — `OpenAIExtractionService.segment_with_llm(message)`**:
   - Calls GPT with `SEGMENTER_PROMPT` → `{"segments": [...]}`
   - Falls back to regex segmenter if LLM unavailable/fails
4. RAW segment nodes saved to Mujarrad `example` space (background, parallel with asyncio.gather)
5. **LLM #2 — `OpenAIExtractionService.extract(message, token_numbers, segments)`**:
   - Time unit normalization: `extract_time_unit()` parses time phrases, `normalize_value()` computes monthly equivalent
   - Supports hourly, daily, weekly, biweekly, every-10-days, semimonthly, monthly, quarterly, semiannually, yearly, biennially
   - Arabic variants: كل شهر, كل أسبوع, أسبوعي, يومي, سنويا, every hamza variant
   - General patterns: `كل 2 شهر` → computed multiplier `__MULT_0.5__`
   - If no API key → `heuristic_extract()` fallback (numbers only, no field classification)
6. **`_aggregate_segment_extractions()`** — sums same fields across segments, builds `segments[]` list with classifications
7. Updates segment nodes in Mujarrad with classifications (background, parallel)
8. **`calculator.calculate_goal(data)`**:
   - `net_monthly_savings = income + extra - expenses`
   - `remaining = max(goal - savings, 0)`
   - `effective_savings = max(savings - debts, 0)` when debts present
   - `raw_months = remaining / net_savings` → `ceil()`
9. **Background storage**: `asyncio.create_task(_store_async(...))` — saves locally then async POSTs to Mujarrad, parallel segment saves with `asyncio.gather`

## Heuristics (`backend/app/heuristics.py`)

- **Purpose**: Pure number-extraction fallback. No keyword classification.
- `normalize_text()` — translates Arabic-Indic digits (٠-٩, ۰-۹) to Western digits
- `extract_number_mentions()` — regex `(?:[$€£])?\s*\d+(?:,\d{3})*(?:\.\d+)?[kKmM]?`
- `heuristic_extract()` — extracts numbers into `all_numbers` only, no field classification
- `merge_extractions()` — **REMOVED** (LLM is sole classifier)
- `_classify_mention()` / `_score_context()` / `_has_goal_language()` / `FIELD_PRIORITY` — **REMOVED** (no keywords)
- `FIELD_KEYWORDS` — **REMOVED** (LLM understands fields without keywords)
- `apply_intelligent_defaults()` — fills None→0 for calculator, creates `goals` list from `goal_price`

## Calculator (`backend/app/calculator.py`)

- `calculate_goal(data)` → `CalculationResult`
- If no goal_price → unachievable
- If remaining==0 → months=0, "already funded"
- If net_savings≤0 → unachievable
- `effective_savings = max((current_savings or 0) - (current_debts or 0), 0)` — debts reduce available savings
- `format_duration(months)` → "5 months", "1 year", "2 years and 3 months"
- `build_suggestions()` → max 3: keep reserves, if >12mo suggest income/expense fix, if expenses>60% review costs, if multiple goals prioritize

## NLP (`backend/app/nlp.py`)

- `extract_numbers(text)` — two-pass: regex patterns + spaCy `like_num` tokens, dedup'd
- SpaCy model `en_core_web_sm` loaded lazily (optional dep, not in requirements.txt)

## Config (`backend/app/config.py`)

| Field | Default |
|-------|---------|
| `openai_api_key` | `""` |
| `openai_base_url` | `https://openrouter.ai/api/v1` | Override with `""` for direct OpenAI API |
| `openai_model` | `gpt-4o-mini` |
| `mujarrad_public_key` | `""` |
| `mujarrad_secret_key` | `""` |
| `mujarrad_api_base` | `https://www.mujarrad.com/api` |
| `mujarrad_space_url` | `https://www.mujarrad.com/spaces/chat` |
| `mujarrad_segments_space_url` | `https://www.mujarrad.com/spaces/example` |
| `cors_origins` | `"http://localhost:5173,http://127.0.0.1:5173"` |

Properties: `cors_origin_list` (splits by comma), `mujarrad_space_slug` (last URL segment → "chat"), `mujarrad_segments_space_slug` (last URL segment → "example")

## Storage (`backend/app/storage.py`)

- `MujarradStorage.__init__()` reads settings, builds headers (`X-API-Key`, `X-API-Secret`)
- Two space slugs: `self.slug` (chat history → `chat` space), `self.segments_slug` (financial nodes → `example` space)
- `_load_local()` / `_save_local()` — reads/writes `~/.mujarrad-chat/history.json`
- `save_chat_record()` — saves to `chat` space (always local + async POST to Mujarrad)
- `save_segment_node()` / `update_segment_node()` — saves to `example` space (async POST, never raises)
- `get_history()` — loads local filtered by user_id, then tries Mujarrad GET from `chat` space (paginated, size=50), saves remote data locally if successful, falls back to local
- `check_connection()` — GET `{base_url}/spaces/{slug}/nodes?size=1`, returns specific error for 401/ConnectError

## Frontend (`frontend/src/main.jsx`)

- **Components**: `App` (root), `Message` (bubble + analysis grid + result panel), `Metric` (label+value)
- **State**: `userId` (localStorage `financial-chat-user-id`), `conversationId`, `messages[]`, `input`, `history[]`, `loading`, `sidebarOpen`, `abortRef`
- **Cancel button**: `AbortController` in `sendMessage()`, `cancelRequest()` function, button appears in typing indicator during loading
- **Metric component**: returns `null` when value is `null` or `undefined` — unmentioned fields do not display
- **Analysis grid**: conditionally shows "Net Savings" row when `current_debts` exists
- **History**: grouped by `conversation_id`, sorted most-recent-first, sidebar shows first user message
- **Styling**: Dark theme CSS variables (`--bg: #02000F`, `--primary: #541288`, `--accent: #A582B1`), responsive at 860px
- **API base**: `import.meta.env.VITE_API_BASE_URL || ''` (Vite proxy handles `/chat`, `/history`, etc. → `localhost:8001`)

## Mujarrad API
- **Chat space slug**: `chat`
- **Segments space slug**: `example`
- **Auth**: `X-API-Key` (public) + `X-API-Secret` (secret)
- **Endpoints**: `POST/GET /api/spaces/{slug}/nodes`
- **Payload**: `{title: "chat-{id}", nodeType: "REGULAR", nodeDetails: <ChatRecord dict>}` (for chat records); `{title: "seg-{conv}-{idx}", nodeType: "SEGMENT", nodeDetails: {...}}` (for segments)
- **Web UI**: `https://www.mujarrad.com/spaces/chat` (history), `https://www.mujarrad.com/spaces/example` (segments)

## Storage Flow
1. Chat → save to `~/.mujarrad-chat/history.json` (always, synchronous)
2. Backend → `asyncio.create_task(_store_async(...))` background task: POST chat record to `chat` space, segment nodes to `example` space (parallel with `asyncio.gather`), best-effort
3. History load: local first, then Mujarrad API for fresher data, save if remote succeeds
4. Sidebar sorted by most recent conversation

## Project Structure
```
chat/
├── CLAUDE.md              ← this file
├── README.md
├── backend/
│   ├── .env               ← API keys (secrets!)
│   ├── requirements.txt   ← fastapi, openai, pydantic, httpx, mangum
│   ├── app/
│   │   ├── main.py        ← FastAPI app, all routes
│   │   ├── storage.py     ← MujarradStorage (local + cloud)
│   │   ├── config.py      ← Settings (pydantic-settings)
│   │   ├── models.py      ← Pydantic models
│   │   ├── openai_service.py ← OpenAIExtractionService + time unit normalization
│   │   ├── heuristics.py  ← Rule-based number extraction (Ar/En)
│   │   ├── calculator.py  ← Goal timeline calculator (with debts support)
│   │   ├── nlp.py         ← Number extraction (spaCy+regex)
│   │   └── schema.json    ← Mujarrad node schema
│   └── tests/             ← 85 tests (calculator, heuristics, models, nlp, segmenter, openai_service)
├── frontend/
│   ├── package.json       ← react, lucide-react, vite
│   ├── vite.config.js     ← proxy /chat, /history etc. → localhost:8001
│   ├── index.html
│   ├── src/
│   │   ├── main.jsx       ← React app (App, Message, Metric) + cancel button
│   │   └── styles.css     ← Dark theme CSS + cancel button styles
└── .gitignore
```

## Common Commands

### Backend
```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
.venv\Scripts\python -m pytest tests -v
.venv\Scripts\python -m pytest tests/test_calculator.py -v
```

### Frontend
```powershell
cd frontend
npm run dev    # starts on localhost:5173, proxy → localhost:8001
npm run build
```

## Tests (85 total)
| File | Tests |
|------|-------|
| `tests/test_calculator.py` | 10: goal calc, formatting, suggestions |
| `tests/test_heuristics.py` | 24: normalize, extract, defaults, Arabic |
| `tests/test_models.py` | 10: defaults, validation, serialization |
| `tests/test_nlp.py` | 9: basic numbers, currency, Arabic digits, dedup, attached to Arabic text |
| `tests/test_openai_service.py` | 19: heuristic fallback, aggregation, segments, time normalization |
| `tests/test_segmenter.py` | 13: empty, English/Arabic split, conjunctions, max segments |

No tests for `storage.py` or `main.py` (async/API tests missing).

## Recent Changes

### 12. Cancel button + background storage parallelization
- Added `AbortController` ref + `cancelRequest()` in `main.jsx` — cancel button appears in typing indicator during loading
- Storage moved to `asyncio.create_task(_store_async(...))` so response returns immediately after LLM + calculation
- Segment saves parallelized with `asyncio.gather` (all raw segments, then all classified segments, at once)
- Chat record saved after segment operations complete

### 11. None defaults, debts support, time unit normalization pipeline
- `FinancialData.current_savings`, `extra_income`, `current_debts` default to `None` instead of `0` — unmentioned fields skip display entirely
- `Metric` component returns `null` for `null`/`undefined` values
- Analysis grid shows "Net Savings" row only when `current_debts` present
- `build_assistant_response` accepts `data` param and mentions debts breakdown only when `current_debts` exists
- **CRITICAL fix**: `segmenter.py` Arabic split patterns `(\d)` → `(\d+)`, was corrupting numbers by eating last digit (e.g. `30000 و شيك` → `3000. و شيك`)
- `extract_time_unit` uses word-boundary matching `(?<!\d)...(?!\d)` to prevent false matches inside larger numbers
- Added ~25 missing Arabic time-unit variants (hamza variants, يومي, كل يوم, كل شهر, كل عام, etc.)
- `_TIME_GENERAL_PATTERNS` correctly computes multipliers for non-1 counts (e.g. `كل 2 شهر` → `__MULT_0.5__` instead of incorrectly returning `'monthly'`)

### 10. response_format removed, timeouts increased
- Removed `response_format={"type": "json_object"}` from both LLM calls (OpenRouter didn't support it reliably)
- Added `_parse_json_from_text()` helper to extract JSON from any LLM response (handles markdown, extra text)
- Increased timeouts: segmenter 5s→10s, extractor 8s→10s
- Improved SEGMENTER_PROMPT with Arabic attached-number examples (800000ولدي, ادخار20000)
- Improved EXTRACTION_PROMPT with Arabic financial examples

### 9. Two-LLM pipeline (segmenter + extractor)
- **LLM #1** (`segment_with_llm` in `openai_service.py`): Takes raw text, returns `{"segments": [...]}` via GPT with `SEGMENTER_PROMPT`. Falls back to regex `segmenter.py` if LLM fails.
- **LLM #2** (`extract` in `openai_service.py`): Takes segments from LLM #1, extracts financial data with `EXTRACTION_PROMPT`.
- `main.py` updated: creates one `OpenAIExtractionService`, calls `segment_with_llm()` then `extract()`.

### 8. FIELD_KEYWORDS and merge_extractions removed (`heuristics.py`)
- **Removed** `FIELD_KEYWORDS` dict entirely, along with `_classify_mention`, `_score_context`, `_has_goal_language`, `FIELD_PRIORITY`
- **Removed** `merge_extractions()` function — LLM is now the sole classifier
- **Removed** 5 merge/extraction tests (76 total then)
- `heuristic_extract()` now only extracts numbers into `all_numbers` with no field classification
- Pipeline: segmenter → LLM → calculator (no heuristic merge)

### 7. Segments saved to separate Mujarrad space
Chat history → `chat` space, financial segment nodes → `example` space (`mujarrad_segments_space_url` config). Added `segments_slug` to `MujarradStorage`, updated `save_segment_node`/`update_segment_node` to target the segments space.

## Notes
- `spaCy` is NOT in requirements.txt (optional import in `nlp.py`)
- Frontend deps all use `"latest"` in package.json
- Backend runs on port **8000**, Vite proxied to **8001** (not 8000!) in vite.config.js
