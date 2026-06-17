# Financial Chat Assistant — Project Memory

## Stack
- **Backend**: Python FastAPI (port 8000, uvicorn)
- **Frontend**: React 19 + Vite (port 5173, proxy → 8001)
- **AI**: gpt-4o-mini via OpenRouter (OpenAI-compatible)
- **Storage**: Local JSON (`~/.mujarrad-chat/history.json`) + Mujarrad API sync
- **Deploy**: Vercel (Mangum handler in `backend/api/index.py`)

## Key API Endpoints (`backend/app/main.py`)

| Route | Method | Input | Output |
|-------|--------|-------|--------|
| `/health` | GET | — | `{"status": "ok"}` |
| `/analyze` | POST | `{message}` | `{data: FinancialData, token_numbers}` |
| `/calculate` | POST | `{data: FinancialData}` | `CalculationResult` |
| `/chat` | POST | `{message, user_id, conversation_id?}` | `{conversation_id, assistant_message, extracted_data, calculation}` |
| `/history` | GET | `?user_id=` | `list[ChatRecord]` |
| `/mujarrad/status` | GET | — | `{connected, space, api}` |

## Pydantic Models (`backend/app/models.py`)

| Model | Key Fields |
|-------|-----------|
| `ChatRequest` | `message: str` (1-8000), `user_id: str` (default="default-user"), `conversation_id: str\|None` |
| `FinancialData` | `goal_price, monthly_income, monthly_expenses, current_savings=0, extra_income=0, goals: list[dict]=[], all_numbers: list[float]=[], assumptions: list[str]=[]` — all floats validated non-negative |
| `CalculationResult` | `net_monthly_savings, remaining, months, duration_display, is_achievable, suggestions: list[str]` |
| `ChatMessage` | `id, role, content, created_at, extracted_data?, calculation?` |
| `ChatRecord` | `id, user_id, conversation_id, user_message, assistant_message, extracted_data, calculation, created_at` |
| `ChatResponse` | `conversation_id, assistant_message, extracted_data, calculation` |

## Extraction Pipeline (`/chat` flow)

1. **`nlp.extract_numbers(message)`** — regex + spaCy tokenizer → `list[float]`
2. **`openai_service.OpenAIExtractionService.extract(message, token_numbers)`**:
   - First runs `heuristics.heuristic_extract()` for fallback
   - If API key set: calls GPT with `response_format={"type": "json_object"}`, temperature=0
   - Merges AI + heuristic via `merge_extractions()`
3. **`calculator.calculate_goal(data)`**:
   - `net_monthly_savings = income + extra - expenses`
   - `remaining = max(goal - savings, 0)`
   - `raw_months = remaining / net_savings` → `ceil()`
4. **`storage.MujarradStorage.save_chat_record(record)`** — saves locally then async POSTs to Mujarrad

## Heuristics (`backend/app/heuristics.py`)

- `normalize_text()` — translates Arabic-Indic digits (٠-٩, ۰-۹) to Western digits
- `extract_number_mentions()` — regex `(?:[$€£])?\s*\d+(?:,\d{3})*(?:\.\d+)?[kKmM]?`
- `heuristic_extract()` — scores each number mention against 6 field keyword lists (context window ±42 chars), picks best field based on proximity. Falls back to largest unclassified number if goal language detected
- `merge_extractions()` — goal_price from AI, rest = `max(primary, fallback)`
- `apply_intelligent_defaults()` — fills None→0, creates `goals` list from `goal_price`

## Calculator (`backend/app/calculator.py`)

- `calculate_goal(data)` → `CalculationResult`
- If no goal_price → unachievable
- If remaining==0 → months=0, "already funded"
- If net_savings≤0 → unachievable
- `format_duration(months)` → "5 months", "1 year", "2 years and 3 months"
- `build_suggestions()` → max 3: keep reserves, if >12mo suggest income/expense fix, if expenses>60% review costs, if multiple goals prioritize

## NLP (`backend/app/nlp.py`)

- `extract_numbers(text)` — two-pass: regex patterns + spaCy `like_num` tokens, dedup'd
- SpaCy model `en_core_web_sm` loaded lazily (optional dep, not in requirements.txt)

## Config (`backend/app/config.py`)

| Field | Default |
|-------|---------|
| `openai_api_key` | `""` |
| `openai_base_url` | `https://openrouter.ai/api/v1` |
| `openai_model` | `gpt-4o-mini` |
| `mujarrad_public_key` | `""` |
| `mujarrad_secret_key` | `""` |
| `mujarrad_api_base` | `https://www.mujarrad.com/api` |
| `mujarrad_space_url` | `https://www.mujarrad.com/spaces/chat` |
| `cors_origins` | `"http://localhost:5173,http://127.0.0.1:5173,https://chat-business.vercel.app"` |

Properties: `cors_origin_list` (splits by comma), `mujarrad_space_slug` (last URL segment → "chat")

## Storage (`backend/app/storage.py`)

- `MujarradStorage.__init__()` reads settings, builds headers (`X-API-Key`, `X-API-Secret`)
- `_load_local()` / `_save_local()` — reads/writes `~/.mujarrad-chat/history.json`
- `save_chat_record()` — always saves locally, tries async POST to Mujarrad (logs errors, never raises)
- `get_history()` — loads local filtered by user_id, then tries Mujarrad GET (paginated, size=50), saves remote data locally if successful, falls back to local
- `check_connection()` — GET `{base_url}/spaces/{slug}/nodes?size=1`, returns specific error for 401/ConnectError

## Frontend (`frontend/src/main.jsx`)

- **Components**: `App` (root), `Message` (bubble + analysis grid + result panel), `Metric` (label+value)
- **State**: `userId` (localStorage `financial-chat-user-id`), `conversationId`, `messages[]`, `input`, `history[]`, `loading`, `sidebarOpen`
- **History**: grouped by `conversation_id`, sorted most-recent-first, sidebar shows first user message
- **Styling**: Dark theme CSS variables (`--bg: #02000F`, `--primary: #541288`, `--accent: #A582B1`), responsive at 860px
- **API base**: `import.meta.env.VITE_API_BASE_URL || ''` (Vite proxy handles `/chat`, `/history`, etc. → `localhost:8001`)

## Mujarrad API
- **Space slug**: `chat`
- **Auth**: `X-API-Key` (public) + `X-API-Secret` (secret)
- **Endpoints**: `POST/GET /api/spaces/{slug}/nodes`
- **Payload**: `{title: "chat-{id}", nodeType: "REGULAR", nodeDetails: <ChatRecord dict>}`
- **Web UI**: `https://www.mujarrad.com/spaces/chat`

## Storage Flow
1. Chat → save to `~/.mujarrad-chat/history.json` (always, synchronous)
2. Backend → async POST to Mujarrad API (best-effort, logs errors)
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
│   │   ├── openai_service.py ← OpenAIExtractionService
│   │   ├── heuristics.py  ← Rule-based extraction (Ar/En)
│   │   ├── calculator.py  ← Goal timeline calculator
│   │   ├── nlp.py         ← Number extraction (spaCy+regex)
│   │   └── schema.json    ← Mujarrad node schema
│   ├── api/index.py       ← Vercel Mangum handler
│   ├── vercel.json
│   └── tests/             ← 41 tests (calculator, heuristics, models, nlp)
├── frontend/
│   ├── package.json       ← react, lucide-react, vite
│   ├── vite.config.js     ← proxy /chat, /history etc. → localhost:8001
│   ├── index.html
│   ├── src/
│   │   ├── main.jsx       ← React app (App, Message, Metric)
│   │   └── styles.css     ← Dark theme CSS
│   └── api/               ← Duplicate backend for Vercel deployment
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

## Tests (41 total)
| File | Tests |
|------|-------|
| `tests/test_calculator.py` | 10: goal calc, formatting, suggestions |
| `tests/test_heuristics.py` | 14: normalize, extract, classify, merge |
| `tests/test_models.py` | 8: defaults, validation, serialization |
| `tests/test_nlp.py` | 10: basic numbers, currency, Arabic digits, dedup, attached to Arabic text |
| `tests/test_openai_service.py` | 4: heuristic fallback, English/Arabic merge |

No tests for `storage.py` or `main.py` (async/API tests missing).

## Recent Fixes (June 2026)

### 1. English keywords expanded (`heuristics.py`)
Added missing English keywords: `have`, `take home`, `net salary`, `purchase`, `bonuses`, `side hustle`, `per diem`, `gig work`, `emergency fund`, `utilities`, `mortgage`, `full time`, `day job`, `afford`, etc.

### 2. Keyword scoring fix (`heuristics.py:_score_context`)
**Before**: `+5` bonus for keywords appearing **before** the number (caused "4,000 bonuses" to be classified as income because "salary" preceded it).
**After**: `+2..0` bonus for keywords appearing **≤2 chars after** the number (e.g., "4,000 bonuses" → "bonuses" wins).

### 3. Merge fix (`heuristics.py:merge_extractions`)
**Before**: `max(AI, fallback)` → wrong AI value (e.g., savings=800k) overrides correct heuristic (200k).
**After**: Prefers the value that appears in extracted `all_numbers` when AI and heuristic disagree.

### 4. JSON timeout fix (`openai_service.py`)
- Added `timeout=8, max_retries=0` to OpenAI client (prevents Vercel 10s timeout killing the function)
- Wrapped API call + `json.loads` in `try/except` → falls back to heuristic on ANY failure

### 5. Frontend resilience (`frontend/src/main.jsx`)
- Catches non-JSON responses (HTML timeout pages) instead of crashing with SyntaxError

## Notes
- `spaCy` is NOT in requirements.txt (optional import in `nlp.py`)
- Frontend deps all use `"latest"` in package.json
- Backend runs on port **8000**, Vite proxied to **8001** (not 8000!) in vite.config.js
- Deployed frontend at: `https://chat-business.vercel.app` (in CORS)
- `frontend/api/` is a duplicate of `backend/app/` for Vercel serverless; keep in sync
