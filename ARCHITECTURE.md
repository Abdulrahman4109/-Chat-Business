# Architecture Guide

A complete reference to the system's structure, data flow, components, and design decisions.

---

## Data Pipeline Diagram (Guided `/chat`)

```
User Input: "I want to buy a car worth 800,000, I earn 15,000..."
       │
       ▼
┌────────────────────────────────────────────────┐
│ 1  Normalize (heuristics.py)                  │
│    normalize_text(message)                     │
│    ├─ Any non-Western digits → 0-9            │
│    └─ Insert space between text + digits       │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 2  Guided Pipeline (financial_agent/)          │
│    First message:                              │
│      process_input() → LLM extracts all fields │
│    Follow-up:                                  │
│      update_data() → LLM extracts value        │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 3  Completeness Check                         │
│    check_completeness(state)                   │
│    ├─ If missing fields → generate_question()  │
│    │     Response: question_type="yesno"       │
│    │     Waits for user Yes/No + value          │
│    └─ If all filled → proceed to calculator    │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 4  Calculator (calculator.py)                  │
│    calculate_goal(data) → CalculationResult    │
│    net = income + extra − expenses             │
│    eff_savings = max(savings − debts, 0)       │
│    rem = max(goal − eff_savings, 0)            │
│    mos = ceil(rem / net)                       │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 5  Background Storage (never blocks response)  │
│    asyncio.create_task(save_chat_record)       │
│    ├─ Local JSON (~/.mujarrad-chat/history)    │
│    └─ Remote Mujarrad API (best-effort)        │
└────────────────────────────────────────────────┘
```

---

## Project Structure

```
chat/
├── CLAUDE.md                  ← Auto-updated project memory
├── ARCHITECTURE.md            ← This file
├── README.md                  ← Quick start guide
├── .gitignore
│
├── backend/
│   ├── .env                   ← API keys (gitignored)
│   ├── requirements.txt       ← Python dependencies
│   │
│   ├── app/
│   │   ├── main.py            ← FastAPI: all 11+ HTTP routes
│   │   ├── models.py          ← Pydantic data models
│   │   ├── config.py          ← pydantic-settings from .env
│   │   ├── openai_service.py  ← Legacy extraction (used by /analyze)
│   │   ├── heuristics.py      ← Text normalization & defaults
│   │   ├── calculator.py      ← Goal timeline math
│   │   ├── nlp.py             ← Regex + optional spaCy number extraction
│   │   ├── segmenter.py       ← Text splitting
│   │   ├── storage.py         ← Local JSON + Mujarrad API client
│   │   ├── diagram_generator.py ← Draw.io XML generation
│   │   ├── financial_agent/   ← Guided conversation state machine
│   │   │   ├── models.py      ← FinancialAgentState
│   │   │   ├── pipeline.py    ← Pipeline (process→check→question→calculate)
│   │   │   └── prompts.py     ← LLM prompts for extraction
│   │   └── system_builder/    ← Separate system design feature
│   │
│   ├── scripts/               ← Training data generation
│   │
│   └── tests/                 ← 96 tests total
│       ├── test_calculator.py        (10)
│       ├── test_financial_agent.py   (11)
│       ├── test_heuristics.py        (24)
│       ├── test_models.py            (10)
│       ├── test_nlp.py               (9)
│       ├── test_openai_service.py    (19)
│       └── test_segmenter.py         (13)
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js         ← Proxy /* → localhost:8001
│   ├── index.html
│   └── src/
│       ├── main.jsx           ← React app (App, Message, Metric)
│       ├── system-builder/    ← System builder UI
│       └── styles.css         ← Dark theme
│
└── documents/                 ← Detailed documentation
    ├── 00-overview.md
    ├── 01-architecture.md
    ├── 02-backend-api.md
    ├── 03-ai-pipeline.md
    ├── 04-storage.md
    ├── 05-frontend.md
    ├── 06-financial-agent.md
    └── 07-diagram.md
```

---

## Request Lifecycle (`/chat`)

| # | Step | Component | What Happens |
|---|------|-----------|-------------|
| 1 | Normalize | `heuristics.py` | Convert non-Western digits, separate attached numbers |
| 2 | Process Input | `financial_agent/pipeline.py` | LLM extracts all fields → normalizes time units to monthly |
| 3 | Check Completeness | `financial_agent/pipeline.py` | All 6 fields non-null? |
| 4a | If incomplete | `financial_agent/pipeline.py` | Generate yes/no question → respond immediately |
| 4b | If complete | `calculator.py` | Calculate timeline, suggestions |
| 5 | Build Response | `main.py` | Assemble JSON with/extracted_data, calculation, question_type |
| 6 | Background Storage | `main.py` | `_store_chat_record_async()` — never blocks response |

Response returns after step 4 or 5. Storage (step 6) runs in background after response.

---

## Data Models

### FinancialData (what the user said)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `goal_price` | float? | null | Target purchase amount |
| `monthly_income` | float? | null | Normalized to monthly |
| `monthly_expenses` | float? | null | Normalized to monthly |
| `current_savings` | float? | null | null = user didn't mention |
| `extra_income` | float? | null | Bonuses, side income |
| `current_debts` | float? | null | Outstanding debts |
| `goals` | list | [] | Goal descriptors |
| `all_numbers` | list | [] | All detected numbers |
| `assumptions` | list | [] | Processing notes |
| `segments` | list | [] | Per-segment classifications |

### CalculationResult (what the system computed)

| Field | Type | Meaning |
|-------|------|---------|
| `net_monthly_savings` | float | income + extra − expenses |
| `remaining` | float | goal − effective savings (min 0) |
| `months` | int? | null if unachievable, 0 if already funded |
| `raw_months` | float? | Unrounded value |
| `duration_display` | str | "3 years and 5 months" |
| `is_achievable` | bool | Can the goal be reached? |
| `suggestions` | list[str] | Up to 3 optimization tips |

### ChatResponse (the API response)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `conversation_id` | string | — | Groups messages |
| `assistant_message` | ChatMessage | — | AI response |
| `extracted_data` | FinancialData? | null | Parsed numbers |
| `calculation` | CalculationResult? | null | Timeline result |
| `question_type` | string | "" | "yesno" during follow-up |
| `question_field` | string | "" | Field being asked |
| `is_complete` | bool | True | Done collecting data |

---

## Storage Spaces

| Slug | Content | API Methods |
|------|---------|-------------|
| `chat` | Conversation history | `save_chat_record()`, `get_history()` |
| `example` | Segment nodes (legacy) | `save_segment_node()` |
| `graph` | Diagram XML | `save_diagram_node()`, `get_diagram_node()` |
| `roi` | ROI calculations | `save_roi_node()`, `get_roi_node()` |

All remote saves are best-effort (failures logged, never raise). Auth via `X-API-Key` + `X-API-Secret` headers.

---

## Key Design Decisions

### Single LLM Call per Turn (not two)
- The old pipeline used two LLM calls (segmenter + extractor)
- The guided pipeline uses one LLM call per turn — `process_input()` on first message, `update_data()` on follow-ups
- Simpler, faster, fewer API failures

### Conversational Extraction (not one-shot)
- Missing fields trigger yes/no questions instead of failing or guessing
- User answers with "Yes, {amount}" or "No"
- Questions asked in fixed order: expenses → savings → debts → extra income
- No re-asking already-answered fields

### LLM Understands, Regex Backs Up
- LLM classifies numbers into fields based on semantic understanding
- `heuristics.py` provides raw `all_numbers` list (no classification)
- Time unit normalization: weekly×4.2857, daily×30, yearly÷12; no unit = assume monthly

### None ≠ 0
- Unmentioned fields default to `None`, not `0`
- Frontend `Metric` component returns `null` for None values
- Calculator converts None→0 internally
- User sees only fields they actually mentioned

### Background Storage
- All I/O (local file + Mujarrad API) runs in `asyncio.create_task`
- Response returns in ~2-3s (LLM latency only), storage adds 0ms
- Failures in storage are logged and never surfaced

### Language Detection
- Language detected by Unicode block (Arabic `\u0600-\u06FF`)
- Questions asked in the user's detected language
- Fallback to English if no Arabic characters detected

---

## Endpoints

| Route | Method | Purpose |
|-------|--------|---------|
| `/chat` | POST | Guided extraction + calculation |
| `/analyze` | POST | Legacy one-shot extraction |
| `/calculate` | POST | Pure timeline math |
| `/diagram` | POST | Generate draw.io XML |
| `/diagram/save` | POST | Persist edited diagram |
| `/diagram/load` | GET | Load saved diagram |
| `/history` | GET | Past conversations |
| `/system-builder/chat` | POST | System design conversation |
| `/system-builder/roi/save` | POST | Save ROI data |
| `/health` | GET | Liveness check |
| `/mujarrad/status` | GET | Storage connection status |

---

## Edge Cases Handled

- **No goal**: Response says "goal amount not provided" + suggestions
- **Already funded**: Months = 0, "Your goal is already funded"
- **Negative net savings**: Unachievable, suggests expense reduction
- **Debts present**: `effective_savings = max(savings − debts, 0)`
- **No time unit**: Value assumed monthly
- **Arabic-Indic digits**: `١٢٣` → normalized to 123
- **Attached numbers**: `text123text` → separated to `text 123 text`
- **Comma-formatted**: `800,000` → 800000
