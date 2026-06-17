# Financial Chat Assistant — Architecture Guide

## Overview

A financial chat application that helps users analyze their financial goals and calculate the timeline to achieve them. The user enters plain text (Arabic or English) describing their income, expenses, savings, and goal. The system extracts numbers, classifies them into financial fields, and computes the goal timeline.

---

## 1. Data Pipeline — End to End

```
     User
       │
       ▼  types: "اريد شراء عربة 800000 وعندي ادخار 300000..."
       │
┌──────┴──────────────────────────────────────────────────────┐
│ ❶  Number Extraction  (NLP)                                │
│    extract_numbers(message) → list[float]                   │
│    Tools: regex, spaCy (en_core_web_sm)                    │
│    Output: [800000, 300000, 50000, 10000, 4000, 2000]      │
└─────────────────────────────────────────────────────────────┘
       │
       ▼  token_numbers
       │
┌──────┴──────────────────────────────────────────────────────┐
│ ❷  Financial Data Extraction                               │
│    OpenAIExtractionService.extract(message, numbers)        │
│                                                             │
│    ┌─────────────────┐       ┌──────────────────┐          │
│    │   AI Path        │       │  Heuristic Path   │          │
│    │  OpenAI GPT-4o   │       │  heuristic_extract│          │
│    │ (if key exists)  │       │  (always runs)    │          │
│    └────────┬────────┘       └────────┬─────────┘          │
│             │                         │                     │
│             └──────────┬──────────────┘                     │
│                        ▼                                    │
│               merge_extractions(AI, heuristic)              │
│                        │                                    │
│                        ▼                                    │
│               FinancialData                                  │
│               {goal_price, monthly_income,                  │
│                monthly_expenses, current_savings,           │
│                extra_income, goals, all_numbers}            │
└─────────────────────────────────────────────────────────────┘
       │
       ▼  extracted
       │
┌──────┴──────────────────────────────────────────────────────┐
│ ❸  Timeline Calculation                                    │
│    calculate_goal(data) → CalculationResult                 │
│                                                             │
│    net = income + extra - expenses                          │
│    remaining = max(goal - savings, 0)                       │
│    months = ceil(remaining / net)                           │
│                                                             │
│    Output: {net_monthly_savings, remaining, months,         │
│             duration_display, is_achievable,                │
│             suggestions}                                    │
└─────────────────────────────────────────────────────────────┘
       │
       ▼  calculation
       │
┌──────┴──────────────────────────────────────────────────────┐
│ ❹  Response Builder                                        │
│    build_assistant_response(calc) → str                    │
│                                                             │
│    • Not achievable → explanation message                   │
│    • Already funded → "Your goal is already funded"        │
│    • Achievable → duration + net savings + remaining       │
└─────────────────────────────────────────────────────────────┘
       │
       ▼  assistant_text
       │
┌──────┴──────────────────────────────────────────────────────┐
│ ❺  Storage                                                 │
│    MujarradStorage.save_chat_record(record)                 │
│                                                             │
│    • Local: ~/.mujarrad-chat/history.json (JSON file)      │
│    • Cloud: Mujarrad API (async POST, best-effort)         │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────┴──────────────────────────────────────────────────────┐
│ ❻  Frontend Display                                        │
│    React + Vite → Dark-themed UI                           │
│    • Message bubble (Message component)                    │
│    • Analysis grid (Metric component)                      │
│    • Result panel (Goal, Income, Expenses, Savings...)     │
│    • Sidebar (conversation history)                        │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
     User sees the response
```

---

## 2. Tools & Libraries per Stage

### Stage ❶ — Number Extraction (NLP)
| Tool | Usage |
|------|-------|
| `re` (regex) | Pattern `(?:[$€£])?\s*\d+(?:,\d{3})*(?:\.\d+)?[kKmM]?` to capture numbers |
| `spaCy` (`en_core_web_sm`) | `token.like_num` to detect textual numbers (e.g. "five hundred") |
| `normalize_text()` | Converts Arabic-Indic digits (٠-٩, ۰-۹) to Western digits |
| **File**: `backend/app/nlp.py` | |

### Stage ❷ — Financial Data Extraction

#### Heuristic Path (always runs)
| Tool | Usage |
|------|-------|
| `re` | Extract `NumberMention` for each number (value + position) |
| `FIELD_KEYWORDS` | 6 keyword lists for the 6 financial fields |
| `_score_context()` | Score each number against each field based on nearby keywords (±42 chars) |
| `_classify_mention()` | Pick the best field per number (highest score + field priority on tie) |
| `merge_extractions()` | Merge AI + heuristic results, preferring values present in `all_numbers` |
| `apply_intelligent_defaults()` | Fill nulls (None → 0), create `goals` from `goal_price` |
| **File**: `backend/app/heuristics.py` | |

**Keyword System:**

| Field | Arabic Keywords (examples) | English Keywords (examples) |
|-------|---------------------------|-----------------------------|
| `goal_price` | اريد, أريد, شراء, عربة, سيارة, عايز, اشتري, هدف | want to buy, goal, target, car, save for |
| `monthly_income` | راتب, مرتب, شهري, دخلي, قبض | salary, income, earn, take home |
| `monthly_expenses` | مصاريف, مصروف, ايجار, فواتير | expenses, spend, rent, bills |
| `current_savings` | ادخار, مدخرات, عندي, معايا, لدى, لدي | savings, saved, have, bank |
| `extra_income` | حوافز, اضافي, مكافأة, فريلانس | bonus, extra, freelance, side |

#### AI Path (if OpenAI key is configured)
| Tool | Usage |
|------|-------|
| `openai` (AsyncOpenAI) | `gpt-4o-mini` via OpenRouter |
| `response_format={"type": "json_object"}` | Force GPT to return valid JSON |
| `temperature=0` | Stable, deterministic results |
| `timeout=8, max_retries=0` | Prevent long timeouts (especially for Vercel) |
| **File**: `backend/app/openai_service.py` | |

### Stage ❸ — Timeline Calculation
| Tool | Usage |
|------|-------|
| `math.ceil()` | Round months up (a partial month counts as a full month) |
| `format_duration()` | Convert months to text: "11 months", "2 years and 3 months" |
| `build_suggestions()` | Generate up to 3 tips (reserve savings, income/expense optimization, priorities) |
| **File**: `backend/app/calculator.py` | |

### Stage ❹ — Response Builder
| Tool | Usage |
|------|-------|
| 3 text templates | • Not achievable • Already funded • Achievable with duration |
| **File**: `backend/app/main.py` (`build_assistant_response()`) | |

### Stage ❺ — Storage
| Tool | Usage |
|------|-------|
| `json` (local) | Read/write `~/.mujarrad-chat/history.json` |
| `httpx.AsyncClient` (cloud) | POST/GET `https://www.mujarrad.com/api/spaces/{slug}/nodes` |
| **File**: `backend/app/storage.py` | |

### Stage ❻ — Frontend
| Tool | Usage |
|------|-------|
| `React 19` | Build components (App, Message, Metric) |
| `Vite` | Build & dev server with proxy → backend (localhost:8001) |
| `lucide-react` | Icons (Send, Menu, X) |
| **File**: `frontend/src/main.jsx` | |

### Infrastructure
| Tool | Usage |
|------|-------|
| `FastAPI` (Python) | API server (routes: /health, /analyze, /calculate, /chat, /history) |
| `Pydantic` | Data models with validation |
| `pydantic-settings` | Environment config (.env → Settings) |
| `Mangum` | Vercel Serverless adapter |
| `Uvicorn` | Local dev server (`uvicorn app.main:app --reload --port 8000`) |

---

## 3. Project Structure

```
chat/
├── ARCHITECTURE.md          ← this file
├── CLAUDE.md                ← project memory for AI assistant
├── README.md
├── .gitignore
│
├── backend/
│   ├── .env                 ← API keys (OpenRouter, Mujarrad)
│   ├── requirements.txt     ← fastapi, openai, pydantic, httpx, mangum, spacy
│   ├── vercel.json
│   ├── api/
│   │   └── index.py         ← Mangum handler for Vercel
│   ├── tests/
│   │   ├── test_calculator.py    ← 10 tests
│   │   ├── test_heuristics.py    ← 15 tests
│   │   ├── test_models.py        ← 8 tests
│   │   ├── test_nlp.py           ← 10 tests
│   │   └── test_openai_service.py ← 4 tests
│   └── app/
│       ├── __init__.py
│       ├── main.py          ← FastAPI app, all routes
│       ├── models.py        ← Pydantic models
│       ├── config.py        ← Settings (pydantic-settings)
│       ├── nlp.py           ← Number extraction (regex + spaCy)
│       ├── heuristics.py    ← Rule-based extraction + classification + merge
│       ├── openai_service.py ← AI extraction (GPT-4o-mini)
│       ├── calculator.py    ← Goal timeline calculator
│       ├── storage.py       ← Local + cloud storage (Mujarrad)
│       └── schema.json      ← Mujarrad node schema
│
├── frontend/
│   ├── package.json         ← react, lucide-react, vite
│   ├── vite.config.js       ← Proxy /chat, /history → localhost:8001
│   ├── index.html
│   └── src/
│       ├── main.jsx         ← React (App, Message, Metric)
│       └── styles.css       ← Dark theme
│
└── api/                     ← Duplicate for Vercel deployment
```

---

## 4. Pydantic Models

```
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

## 5. How Heuristic Classification Works

```
Text: "اريد شراء عربة 800000 وعندي ادخار 300000"
                │
                ▼
    1. normalize_text() ← translate Arabic digits
    2. extract_number_mentions() ← regex
                │
                ▼
    For each number:
    ┌──────────────────────────────────────────────
    │ Take ±42 char context window around number
    │ For each of the 6 fields:
    │   Search for field keywords in context
    │   Compute score = 80 - distance + bonus
    │ Pick field with highest score
    │ (tiebreaker: goal > income > expenses
    │  > savings > extra)
    └──────────────────────────────────────────────
                │
                ▼
    If goal_price is still unset and text contains
    goal language → largest unclassified number = goal
```

### Scoring Example:
```
"اريد شراء عربة 800000"
                  ▲
    keywords:     │
    "اريد" → score 69 (11 chars before number)
    "شراء" → score 74 (6 chars before number)
    "عرب"  → score 79 (1 char before number) ← winner!
```

---

## 6. Calculation Formulas

```
Net monthly savings = income + extra - expenses
Remaining = max(goal - savings, 0)
Duration (months) = ceil(remaining / net_savings)
```

Example from user message:
```
Goal:        800,000
Savings:     300,000
Income:       50,000
Expenses:     10,000
Extra:         6,000
─────────────────────
Net savings:    46,000  (= 50,000 + 6,000 - 10,000)
Remaining:    500,000  (= 800,000 - 300,000)
Duration:  11 months    (= ceil(500,000 / 46,000))
```

---

## 7. Run Commands

### Backend
```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
.venv\Scripts\python -m pytest tests -v
```

### Frontend
```powershell
cd frontend
npm run dev   # localhost:5173, proxy → localhost:8001
npm run build
```

---

## 8. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User                                           │
│         types: "اريد شراء عربة 800000..."                                   │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ❶ NLP Layer (backend/app/nlp.py)                                          │
│ ┌────────────────────────────────────────────────────────────────────────┐ │
│ │ extract_numbers(message)                                              │ │
│ │ │ regex: (?:[$€£])?\s*\d+(?:,\d{3})*(?:\.\d+)?[kKmM]?               │ │
│ │ │ spaCy: token.like_num                                              │ │
│ │ └──────────────────────────┬─────────────────────────────────────────┘ │
│ │                            ▼                                           │
│ │                    token_numbers: list[float]                           │
│ │                    [800000, 300000, 50000, 10000, 4000, 2000]          │
│ └────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ❷ Extraction Layer (backend/app/openai_service.py + heuristics.py)        │
│                                                                           │
│  ┌────────────────────┐          ┌────────────────────────────────────┐   │
│  │  heuristic_extract │          │  OpenAI API (if key configured)    │   │
│  │  (always runs)     │          │  GPT-4o-mini → JSON                │   │
│  │                    │          │  timeout=8, temperature=0          │   │
│  │  Per number:       │          │  response_format={"type":"json"}   │   │
│  │  • get context     │          └──────────────┬─────────────────────┘   │
│  │  • search keywords │                         │                         │
│  │  • compute score   │                         │                         │
│  │  • pick best field │                         │                         │
│  └────────┬───────────┘          ┌──────────────┘                         │
│           │                      │                                        │
│           └──────────┬───────────┘                                        │
│                      ▼                                                     │
│           merge_extractions(AI, heuristic)                                 │
│           • goal_price from AI (or fallback if null)                       │
│           • other fields: max(AI, heuristic), prefer value in all_numbers │
│                      ▼                                                     │
│              FinancialData (all fields classified)                          │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ❸ Calculator Layer (backend/app/calculator.py)                            │
│                                                                           │
│  calculate_goal(data)                                                     │
│  │                                                                        │
│  │ net_monthly = income + extra - expenses = 50,000 + 6,000 - 10,000     │
│  │             = 46,000                                                   │
│  │                                                                        │
│  │ remaining = max(goal - savings, 0) = max(800,000 - 300,000, 0)       │
│  │           = 500,000                                                    │
│  │                                                                        │
│  │ months = ceil(500,000 / 46,000) = 11                                  │
│  │                                                                        │
│  │ duration_display = "11 months"                                         │
│  │                                                                        │
│  │ is_achievable = True (goal exists, net > 0, remaining > 0)            │
│  │                                                                        │
│  │ suggestions: ["Keep at least 46,000 per month reserved..."]            │
│  └──────────────────┬─────────────────────────────────────────────────────┘
│                     ▼                                                     │
│             CalculationResult                                             │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ❹ Response Builder (backend/app/main.py)                                  │
│                                                                           │
│  build_assistant_response(calc)                                           │
│  │                                                                        │
│  │ calc.is_achievable = True                                              │
│  │ calc.months = 11 ≠ 0                                                   │
│  │ ↓                                                                      │
│  │ "At your current pace, it will take 11 months.                         │
│  │  Net monthly savings: 46,000.                                          │
│  │  Remaining amount: 500,000.                                            │
│  │  Keep at least 46,000 per month reserved for this goal."               │
│  └──────────────────┬─────────────────────────────────────────────────────┘
│                     ▼                                                     │
│              assistant_text (str)                                          │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ❺ Storage Layer (backend/app/storage.py)                                  │
│                                                                           │
│  MujarradStorage.save_chat_record(record)                                 │
│  │                                                                        │
│  ├──► Local: ~/.mujarrad-chat/history.json (synchronous)                  │
│  │    JSON array of ChatRecord objects                                    │
│  │                                                                        │
│  └──► Cloud: POST https://www.mujarrad.com/api/spaces/chat/nodes          │
│       Headers: X-API-Key, X-API-Secret                                    │
│       (best-effort, does not block the response)                          │
│                                                                           │
│  get_history(user_id)                                                     │
│  ├──► Local (filtered by user_id)                                         │
│  └──► Cloud GET (paginated, size=50) ← updates local if successful        │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ❻ Frontend Layer (frontend/src/main.jsx)                                  │
│                                                                           │
│  ChatResponse ──► React renders                                           │
│                                                                           │
│  • Message component: chat bubble (user/assistant)                       │
│  • Metric component: display each financial field (label + value)        │
│  • Analysis Grid: organized table (Goal, Income, Expenses, Savings, Extra)│
│  • Result Panel: net_monthly_savings, remaining, months, suggestions      │
│  • Sidebar: conversation history grouped by conversation_id               │
│                                                                           │
│  API calls: fetch('/chat', POST) → ChatResponse                           │
│             fetch('/history?user_id=...', GET) → ChatRecord[]             │
│                                                                           │
│  Styling: CSS custom properties (dark theme)                              │
│  --bg: #02000F, --primary: #541288, --accent: #A582B1                    │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                              User                                         │
│         sees: "At your current pace, it will take 11 months."             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Summary

```
Complete 6-step pipeline:

  Text ──► ❶ NLP (regex + spaCy) ──► raw numbers
         ──► ❷ Extraction (heuristic ± GPT) ──► classified FinancialData
         ──► ❸ Calculator ──► CalculationResult
         ──► ❹ Response Builder ──► response text
         ──► ❺ Storage (local + cloud) ──► persisted
         ──► ❻ Frontend (React) ──► displayed to user

Each step has:
  • Dedicated file(s) in backend/app/
  • Specific libraries and tools
  • Independent, testable logic
  • Tests in backend/tests/
```
