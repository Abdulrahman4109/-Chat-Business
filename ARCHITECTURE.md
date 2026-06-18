# Financial Chat Assistant — Architecture Guide

> **A full-stack financial goal calculator** — users describe their finances in plain text (Arabic/English), the system extracts numbers via a two-LLM pipeline, computes a goal timeline, and persists conversations locally + to Mujarrad cloud.

---

## The Complete Message Journey (Start to Finish)

When a user sends a message like "اريد شراء عربة 800000 وعندي ادخار 300000 ودخلي 50000 ومصروفي 10000", here is the full step-by-step journey:

### Step 1: Receive the message (`main.py` — `/chat` endpoint)

```
POST /chat  { message: "اريد شراء عربة 800000..." }
```

- Request arrives at `POST /chat` in `main.py`
- Input validated against `ChatRequest` model (text 1-8000 chars)
- New conversation_id created if not provided

### Step 2: Extract raw numbers (`nlp.py` — extract_numbers)

```
"اريد شراء عربة 800000 وعندي ادخار 300000 ودخلي 50000 ومصروفي 10000"
                              ↓
                    [800000, 300000, 50000, 10000]
```

- Regex pattern matching: `\d+(?:,\d{3})*(?:\.\d+)?`
- Supports Arabic-Indic digits (٠-٩, ۰-۹), converts to Western
- spaCy optional: if available, extracts additional `like_num` tokens
- Output: `token_numbers` list ordered by appearance in text

### Step 3: LLM #1 — Segment the text (`openai_service.py` — segment_with_llm)

```
Input: raw user message

Sent to GPT-4o-mini with SEGMENTER_PROMPT:
  "Split the following financial text into separate segments..."

Response: {"segments": ["اريد شراء عربة 800000", "ادخار 300000", "دخلي 50000", "مصروفي 10000"]}
```

- Model: GPT-4o-mini, temperature=0, timeout=10s
- **Fallback**: if LLM fails (no API key, connection error, etc.), uses `segmenter.segment_text()` — a Regex-based algorithm that splits on conjunctions (و، ،, .) with max 5 segments

### Step 4: Save raw segments (`storage.py` — save_segment_node)

```
Each segment saved as a node in Mujarrad "example" space:
  seg-{conv_id}-0 → {"text": "اريد شراء عربة 800000", "status": "raw"}
  seg-{conv_id}-1 → {"text": "ادخار 300000", "status": "raw"}
  ...
```

- Async, best-effort
- Does not block the pipeline on failure — only logs the error

### Step 5: LLM #2 — Extract financial data (`openai_service.py` — extract)

```
Inputs:
  1. Original message
  2. Token numbers [800000, 300000, 50000, 10000]
  3. Segments from LLM #1

Sent to GPT-4o-mini with EXTRACTION_PROMPT:
  "Extract financial information from the following text..."

Response (JSON):
{
  "goal_price": 800000,
  "monthly_income": 50000,
  "monthly_expenses": 10000,
  "current_savings": 300000,
  "segments": [
    {"text": "اريد شراء عربة 800000", "classification": "goal"},
    {"text": "ادخار 300000", "classification": "savings"},
    ...
  ]
}
```

- Model: GPT-4o-mini, temperature=0, timeout=10s
- **Fallback**: if LLM fails, uses `heuristic_extract()` — extracts numbers only (no classification, just all_numbers)
- Uses `_parse_json_from_text()` to extract JSON from any response format (even with Markdown or extra text)
- **Does not use** `response_format={"type":"json_object"}` (removed because OpenRouter didn't support it reliably)

### Step 6: Aggregate segments and update (`openai_service.py` — _aggregate_segment_extractions)

```
After LLM #2 extraction:
  - Sums duplicate fields (e.g., "income 50000" and "extra income 6000")
  - Updates segment nodes in Mujarrad "example" with classifications (goal, income, savings, ...)
```

### Step 7: Calculate (`calculator.py` — calculate_goal)

```
Extracted data:
  goal_price = 800000
  current_savings = 300000
  monthly_income = 50000
  monthly_expenses = 10000

Calculations:
  net_monthly_savings = 50000 - 10000 = 40000
  remaining = 800000 - 300000 = 500000
  months = ceil(500000 / 40000) = 13 months

Result:
  net_monthly_savings: 40000
  remaining: 500000
  months: 13
  duration_display: "1 year and 1 month"
  is_achievable: true
  suggestions: ["Keep an emergency fund", ...]
```

- No `goal_price` → unachievable
- `remaining` = 0 → "already funded"
- `net_savings` ≤ 0 → unachievable
- Builds suggestions (reduce expenses if >60%, increase income if >12 months)

### Step 8: Store (`storage.py` — save_chat_record)

```
ChatRecord {
  id: uuid,
  user_id: "user-123",
  conversation_id: "conv-456",
  user_message: "اريد شراء عربة 800000...",
  assistant_message: "You need 13 months to reach your goal...",
  extracted_data: { goal_price: 800000, ... },
  calculation: { months: 13, ... },
  created_at: "2026-06-19T..."
}

1. Saved to local file ~/.mujarrad-chat/history.json (sync, immediate)
2. Sent to Mujarrad POST /api/spaces/chat/nodes (async)
   slug: chat-{uuid}
```

### Step 9: Respond to frontend (`main.py`)

```
Response: {
  conversation_id: "conv-456",
  assistant_message: "To reach your goal of buying the car (800,000)...
     Remaining: 500,000
     Monthly savings: 40,000
     Duration: 13 months
     ✅ Achievable!",
  extracted_data: { ... },
  calculation: { months: 13, duration_display: "1 year and 1 month", ... }
}
```

### Step 10: Display (React — main.jsx)

- Chat bubble showing the response
- Analysis grid displaying extracted numbers (goal, income, expenses, savings)
- Result panel showing timeline, monthly savings, and suggestions

---

## Changes Summary (Before vs After)

| Before | After |
|--------|-------|
| Single LLM extracts everything directly | Two LLMs: Segmenter (LLM#1) + Extractor (LLM#2) |
| `response_format="json_object"` | `_parse_json_from_text()` — handles any response format |
| `merge_extractions()` merges heuristic + LLM | LLM is sole classifier, no merging |
| `FIELD_KEYWORDS` and `_classify_mention()` for classification | Removed entirely — LLM classifies without keyword rules |
| OpenRouter API by default | Direct OpenAI API by default |
| Timeouts 5s / 8s | Timeouts 10s / 10s |
| History fetch without pagination | Full pagination (all pages) |
| No OPTIONS handler | Catch-all OPTIONS handler for CORS |

---

## Two-LLM Pipeline Details

### LLM #1 — Segmenter

```
Purpose: Split financial text into logical segments

Input: "اريد شراء عربة 800000 وعندي ادخار 300000 ودخلي 50000 ومصروفي 10000"
Output: {"segments": ["اريد شراء عربة 800000", "ادخار 300000", "دخلي 50000", "مصروفي 10000"]}

Model: GPT-4o-mini
Temperature: 0
Timeout: 10s
Fallback: segmenter.segment_text() (Regex)
File: openai_service.py — segment_with_llm()
```

**Why a separate LLM for segmentation?**
- Arabic text is often connected without clear delimiters
- Conjunctions (و) may link different information: "دخلي 50000 ومصروفي 10000"
- LLM understands context and splits more accurately than Regex

### LLM #2 — Extractor

```
Purpose: Extract and classify financial data from text and segments

Inputs:
  - Original message
  - Token numbers [800000, 300000, 50000, 10000]
  - Segments from LLM #1 ["اريد شراء عربة 800000", ...]

Output: FinancialData {
  goal_price: 800000,
  monthly_income: 50000,
  monthly_expenses: 10000,
  current_savings: 300000,
  segments: [{text, classification}, ...],
  assumptions: [...]
}

Model: GPT-4o-mini
Temperature: 0
Timeout: 10s
Fallback: heuristic_extract() (numbers only, no classification)
File: openai_service.py — extract()
```

**Why a second LLM for extraction?**
- Segmentation and extraction are distinct tasks
- LLM #2 benefits from pre-classified segments from LLM #1
- Each LLM can fail independently — if #1 fails, #2 works on raw text
- If #2 fails, `heuristic_extract()` ensures the user always gets a response

### Segment Storage in Mujarrad

```
"example" space in Mujarrad:
  Node: seg-{conv}-{idx}
  Before extraction: {text: "...", status: "raw"}
  After extraction:  {text: "...", status: "classified", classification: "goal"}
  Update: async, best-effort
```

---

## Data Pipeline Diagram (6 Stages)

```
User Input: "اريد شراء عربة 800000 وعندي ادخار 300000..."
       │
       ▼
┌────────────────────────────────────────────────┐
│ 1  NLP — Number Extraction (nlp.py)           │
│    extract_numbers(message) → [800000,300000]  │
│    regex + spaCy (optional)                   │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 2  LLM #1 — Segmenter (openai_service.py)     │
│    segment_with_llm(message) → {"segments":[]} │
│    Falls back to segmenter.segment_text()      │
│    RAW segments saved to Mujarrad "example"    │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 3  LLM #2 — Extractor (openai_service.py)     │
│    extract(message, numbers, segments)         │
│    → FinancialData (classified fields)        │
│    Falls back to heuristic_extract() (numbers  │
│    only, no classification) if no API key     │
│    Updates segment nodes with classifications │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 4  Calculator (calculator.py)                 │
│    calculate_goal(data) → CalculationResult    │
│    net = income + extra − expenses            │
│    rem = max(goal − savings, 0)               │
│    mos = ceil(rem / net)                      │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 5  Storage (storage.py) — MujarradStorage     │
│    save_chat_record() → local JSON + cloud    │
│    get_history() → paginated fetch (all pages)│
│    slug: chat-{record.id} (unique per msg)    │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 6  Frontend (main.jsx) — React 19 + Vite      │
│    Chat bubbles, analysis grid, result panel,  │
│    sidebar with history grouped by conversation│
└────────────────────┬──────────────────────────┘
                     │
                     ▼
              User sees the reply
```

---

## Project Structure

```
chat/
├── ARCHITECTURE.md
├── CLAUDE.md
├── README.md
├── .gitignore
│
├── backend/
│   ├── .env                       # API keys (gitignored)
│   ├── requirements.txt           # fastapi, openai, pydantic, httpx
│   ├── vercel.json                # Vercel routing (separate deploy)
│   ├── api/index.py               # Mangum handler
│   ├── app/
│   │   ├── main.py                # FastAPI app + 6 routes
│   │   ├── models.py              # Pydantic models
│   │   ├── config.py              # Settings via pydantic-settings
│   │   ├── nlp.py                 # Number extraction (regex + optional spaCy)
│   │   ├── segmenter.py           # Regex-based text segmentation
│   │   ├── heuristics.py          # Number-only extraction fallback
│   │   ├── openai_service.py      # Two-LLM pipeline (segmenter + extractor)
│   │   ├── calculator.py          # Goal timeline calculation
│   │   ├── storage.py             # Local JSON + Mujarrad cloud
│   │   └── schema.json            # Mujarrad node schema
│   ├── tests/                     # 76 pytest tests
│   │   ├── test_calculator.py     # 10
│   │   ├── test_heuristics.py     # 10
│   │   ├── test_models.py         # 8
│   │   ├── test_nlp.py           # 10
│   │   ├── test_openai_service.py # 15
│   │   └── test_segmenter.py     # 9
│   └── scripts/                   # Fine-tuning utilities
│       ├── generate_training_data.py
│       ├── HOW_TO_FINETUNE.md
│       └── finetune_data.jsonl
│
├── frontend/
│   ├── package.json               # react, lucide-react, vite
│   ├── vite.config.js             # Proxy → localhost:8001
│   ├── vercel.json                # Unified deployment routing
│   ├── index.html
│   ├── src/
│   │   ├── main.jsx               # React (App, Message, Metric)
│   │   └── styles.css             # Dark theme CSS
│   └── api/                       # Backend duplicate (for unified deploy)
│
└── documents/                     # Detailed docs
    ├── 00-overview.md
    ├── 01-architecture.md
    ├── 02-backend-api.md
    ├── 03-ai-pipeline.md
    ├── 04-storage.md
    ├── 05-frontend.md
    ├── 06-deployment.md
    ├── 07-development.md
    └── 08-training-data.md
```

---

## Pydantic Models

```python
ChatRequest
  message: str (1-8000)
  user_id: str (default: "default-user")
  conversation_id: str | None

FinancialData
  goal_price: float | None
  monthly_income: float | None
  monthly_expenses: float | None
  current_savings: float (default 0)
  extra_income: float (default 0)
  goals: list[dict] = []
  all_numbers: list[float] = []
  assumptions: list[str] = []
  segments: list[dict] = []          # from LLM #2

CalculationResult
  net_monthly_savings: float
  remaining: float
  months: int | None
  raw_months: float | None
  duration_display: str
  is_achievable: bool
  suggestions: list[str]
```

---

## Heuristics (Fallback Only)

When no `OPENAI_API_KEY` is configured, `heuristic_extract()` runs:

```
extract_numbers() → all_numbers: [50000, 3000, 1500, 10000]
                         │
                         ▼
              No field classification
              (goal_price=null, income=null, etc.)
```

- `normalize_text()` — Arabic-Indic → Western digits
- `extract_number_mentions()` — regex for number patterns
- `heuristic_extract()` — numbers only, no field classification
- `apply_intelligent_defaults()` — None→0, goals list from goal_price

---

## Storage Flow

```
save_chat_record(record)
  └─ Local: ~/.mujarrad-chat/history.json (always, sync)
  └─ Cloud: POST /api/spaces/chat/nodes (async, best-effort)
            slug: chat-{record.id} (unique UUID per message)

get_history(user_id)
  └─ Load local file
  └─ Fetch from Mujarrad (paginated, all pages, size=50)
  └─ If remote succeeds: save remote data locally, return it
  └─ Fallback: return local data
```

---

## API Endpoints

| Route | Method | Input | Output |
|-------|--------|-------|--------|
| `/health` | GET | — | `{"status": "ok"}` |
| `/analyze` | POST | `{message}` | `{data: FinancialData, token_numbers}` |
| `/calculate` | POST | `{data: FinancialData}` | `CalculationResult` |
| `/chat` | POST | `{message, user_id, conversation_id?}` | `ChatResponse` |
| `/history` | GET | `?user_id=` | `list[ChatRecord]` |
| `/mujarrad/status` | GET | — | connection status |
| All paths | OPTIONS | — | `200` (CORS preflight fix) |

---

## Config (pydantic-settings)

| Key | Default | Notes |
|-----|---------|-------|
| `OPENAI_API_KEY` | `""` | Falls back to heuristic |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | |
| `OPENAI_MODEL` | `gpt-4o-mini` | |
| `MUJARRAD_PUBLIC_KEY` | `""` | Generate via `npx mujarrad-cli sdk keygen` |
| `MUJARRAD_SECRET_KEY` | `""` | Generate via `npx mujarrad-cli sdk keygen` |
| `MUJARRAD_API_BASE` | `https://www.mujarrad.com/api` | |
| `MUJARRAD_SPACE_URL` | `https://www.mujarrad.com/spaces/chat` | |
| `CORS_ORIGINS` | localhost:5173, chat-business.vercel.app | |

---

## Run Commands

### Backend
```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
.venv\Scripts\python -m pytest tests -v
```

### Frontend
```powershell
cd frontend
npm run dev       # localhost:5173, proxy → localhost:8001
npm run build
```
