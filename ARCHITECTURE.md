# Architecture Guide

A complete reference to the system's structure, data flow, components, and design decisions.

---

## Data Pipeline Diagram

```
User Input: "اريد شراء عربة 800000 وعندي ادخار 300000..."
       │
       ▼
┌────────────────────────────────────────────────┐
│ 1  NLP — Number Extraction (nlp.py)           │
│    extract_numbers(message) → [800000,300000]  │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 2  LLM #1 — Segmenter (openai_service.py)     │
│    segment_with_llm(message) → {"segments":[]} │
│    Falls back to segmenter.segment_text()      │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 3  LLM #2 — Extractor (openai_service.py)     │
│    extract(message, numbers, segments)         │
│    → FinancialData (classified, time-normalized)│
│    Falls back to heuristic_extract() (numbers) │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 4  Calculator (calculator.py)                 │
│    calculate_goal(data) → CalculationResult    │
│    net = income + extra − expenses             │
│    eff_savings = max(savings − debts, 0)       │
│    rem = max(goal − eff_savings, 0)            │
│    mos = ceil(rem / net)                       │
└────────────────────┬──────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│ 5  _store_async (background task, never blocks)│
│    Run after response is returned              │
│    ├─ Save raw segments (parallel gather)      │
│    ├─ Update classified segments (parallel)     │
│    └─ save_chat_record → local + Mujarrad      │
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
│   │   ├── main.py            ← FastAPI app: all 6 HTTP routes
│   │   ├── models.py          ← Pydantic data models
│   │   ├── config.py          ← pydantic-settings from .env
│   │   ├── openai_service.py  ← Two-LLM pipeline + time normalization
│   │   ├── heuristics.py      ← Fallback number extraction
│   │   ├── calculator.py      ← Goal timeline math
│   │   ├── nlp.py             ← Regex + optional spaCy number extraction
│   │   ├── segmenter.py       ← Arabic-aware regex text splitter
│   │   ├── storage.py         ← Local JSON + Mujarrad API client
│   │   └── schema.json        ← Mujarrad node schema
│   │
│   ├── scripts/
│   │   ├── generate_training_data.py  ← Dataset generator
│   │   ├── finetune_data.jsonl         ← Generated examples
│   │   └── HOW_TO_FINETUNE.md
│   │
│   └── tests/                 ← 85 tests total
│       ├── test_calculator.py        (10)
│       ├── test_heuristics.py        (24)
│       ├── test_models.py            (10)
│       ├── test_nlp.py               (9)
│       ├── test_openai_service.py    (19)
│       └── test_segmenter.py         (13)
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js         ← Proxy /api/* → localhost:8001
│   ├── index.html
│   └── src/
│       ├── main.jsx           ← React app (App, Message, Metric)
│       └── styles.css         ← Dark theme
│
└── documents/                 ← Detailed documentation
    ├── 00-overview.md
    ├── 01-architecture.md
    ├── 02-backend-api.md
    ├── 03-ai-pipeline.md
    ├── 04-storage.md
    └── 05-frontend.md
```

---

## Request Lifecycle

Every `/chat` request follows this exact path:

| # | Step | File | What Happens |
|---|------|------|-------------|
| 1 | Number Extraction | `nlp.py` | Regex + spaCy find all numbers in raw message |
| 2 | LLM Segmentation | `openai_service.py` | GPT-4o-mini splits message into semantic segments |
| 3 | Fallback Split | `segmenter.py` | Regex split if GPT is unavailable |
| 4 | LLM Extraction | `openai_service.py` | GPT classifies each segment → FinancialData |
| 5 | Time Normalization | `openai_service.py` | Any time unit → monthly equivalent |
| 6 | Aggregation | `openai_service.py` | Merge per-segment extractions, sum same fields |
| 7 | Calculator | `calculator.py` | Compute timeline, edge case handling |
| 8 | Response Builder | `main.py` | Build natural-language reply with suggestions |
| 9 | Background Storage | `main.py` | `_store_async`: raw segs → classified → chat |
| 10 | Response | `main.py` | Return JSON to frontend immediately |

The response returns at step 10. Step 9 runs as a background task.

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
| `goals` | list | [] | All goals (largest = primary) |
| `segments` | list | [] | Per-segment classifications |

### CalculationResult (what the system computed)

| Field | Type | Meaning |
|-------|------|---------|
| `net_monthly_savings` | float | income + extra − expenses |
| `remaining` | float | goal − savings (min 0) |
| `months` | int? | null if unachievable |
| `duration_display` | str | "3 years and 5 months" |
| `is_achievable` | bool | Can the goal be reached? |

---

## Key Design Decisions

### LLM-First, Regex-Fallback
- Primary path uses GPT-4o-mini for both segmentation and classification
- Regex fallbacks handle offline/API-failure scenarios gracefully
- Heuristics provide raw numbers only (no keyword classification)

### Two LLM Calls (Not One)
- **Segmenter** (LLM #1): splits into atomic units — improves accuracy vs processing raw text
- **Extractor** (LLM #2): classifies each segment independently — each number gets its own field
- Separate prompts, separate concerns, same model

### Time Unit Agnosticism
- Any time unit normalizes to monthly via `extract_time_unit` + `normalize_value`
- Dictionary lookup for known units (25+ Arabic/English variants)
- General pattern matching for computed units (`كل N شهر` → ×1/N)
- Missing unit = assumed monthly

### Background Storage
- All I/O (local file + Mujarrad API) runs in `asyncio.create_task`
- Response returns in ~2-3s (LLM latency only), storage adds 0ms to user-perceived time
- Failures in storage are logged and never surfaced

### None ≠ 0
- Unmentioned fields default to `None`, not `0`
- Frontend `Metric` component returns `null` for None values
- Calculator converts None→0 internally via `apply_intelligent_defaults`
- User sees only fields they actually mentioned

---

## Key Files Reference

| File | Responsibility | Key Functions |
|------|---------------|---------------|
| `app/main.py` | HTTP layer, routing, response assembly | `chat()`, `analyze()`, `calculate()`, `_store_async()` |
| `app/models.py` | All Pydantic schemas | `FinancialData`, `ChatRequest`, `ChatResponse`, `CalculationResult` |
| `app/config.py` | Environment + settings | `Settings` class from pydantic-settings |
| `app/openai_service.py` | Two-LLM pipeline, time normalization | `segment_with_llm()`, `extract()`, `extract_time_unit()`, `normalize_value()` |
| `app/heuristics.py` | Offline fallback | `heuristic_extract()`, `apply_intelligent_defaults()` |
| `app/calculator.py` | Timeline math | `calculate_goal()`, `format_duration()`, `build_suggestions()` |
| `app/nlp.py` | Number detection | `extract_numbers()` — regex + spaCy |
| `app/segmenter.py` | Regex text splitting | `segment_text()` |
| `app/storage.py` | Local + remote persistence | `save_chat_record()`, `get_history()`, `save_segment_node()` |

---

## Configuration (`.env`)

| Variable | Example | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | `sk-or-v1-...` | OpenRouter API key |
| `OPENAI_BASE_URL` | `https://openrouter.ai/api/v1` | Default; empty = direct OpenAI |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model for both LLMs |
| `MUJARRAD_PUBLIC_KEY` | `pk_live_...` | Mujarrad API public key |
| `MUJARRAD_SECRET_KEY` | `sk_live_...` | Mujarrad API secret key |
| `MUJARRAD_SPACE_URL` | `https://.../spaces/chat` | Chat records space |
| `MUJARRAD_SEGMENTS_SPACE_URL` | `https://.../spaces/example` | Segment nodes space |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins |

---

## Edge Cases Handled

- **No goal**: Response says "goal amount not provided" + suggestions
- **Already funded**: Months = 0, "Your goal is already funded"
- **Negative net savings**: Unachievable, suggests expense reduction
- **Debts present**: `effective_savings = max(savings − debts, 0)`
- **Multiple goals**: Largest value becomes primary
- **No time unit**: Value assumed monthly
- **Arabic attached numbers**: `ادخار20000` → split correctly
- **Comma-formatted**: `800,000` → 800000
- **Arabic-Indic digits**: `١٢٣` → 123
- **15+ segments**: Truncated, remainder merged into last segment
