# Architecture Guide

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
│    → FinancialData (classified, time-normalized│
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

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI routes (`/chat`, `/analyze`, `/calculate`, `/history`, `/health`) |
| `app/models.py` | Pydantic models (FinancialData, CalculationResult, ChatRecord) |
| `app/config.py` | Settings from .env (pydantic-settings) |
| `app/openai_service.py` | Two-LLM pipeline + time unit normalization |
| `app/heuristics.py` | Fallback number extraction (no field classification) |
| `app/calculator.py` | Goal timeline math with debts support |
| `app/nlp.py` | Number extraction (regex + optional spaCy) |
| `app/segmenter.py` | Arabic-aware regex text segmenter |
| `app/storage.py` | Local JSON + Mujarrad API client |

See `documents/02-backend-api.md` for API endpoints, `documents/03-ai-pipeline.md` for pipeline details, `documents/04-storage.md` for storage.
