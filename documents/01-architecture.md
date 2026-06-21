# Architecture

A detailed breakdown of the project's directory layout, request lifecycle, and data flow.

## Project Structure

```
chat/
├── CLAUDE.md                  ← Project memory (auto-updated)
├── ARCHITECTURE.md
├── README.md
├── .gitignore
│
├── backend/                   ← Python FastAPI
│   ├── .env                   ← API keys (gitignored)
│   ├── requirements.txt       ← fastapi, openai, pydantic, httpx, mangum
│   ├── app/
│   │   ├── main.py            ← FastAPI app: all HTTP routes
│   │   ├── models.py          ← Pydantic models (ChatRequest, FinancialData with None defaults, current_debts)
│   │   ├── config.py          ← Settings from .env (pydantic-settings)
│   │   ├── openai_service.py  ← LLM extraction service + time unit normalization pipeline
│   │   ├── heuristics.py      ← Fallback: number extraction (no classification)
│   │   ├── calculator.py      ← Goal timeline math (debts reduce effective savings)
│   │   ├── nlp.py             ← Number extraction (regex + spaCy like_num)
│   │   ├── segmenter.py       ← Arabic-aware text segmenter (regex)
│   │   ├── storage.py         ← Local JSON + Mujarrad API client
│   │   └── schema.json        ← Mujarrad node schema
│   ├── scripts/
│   │   ├── generate_training_data.py  ← Fine-tuning dataset generator
│   │   ├── finetune_data.jsonl         ← Generated training examples
│   │   └── HOW_TO_FINETUNE.md
│   └── tests/                 ← 85 pytest tests
│       ├── test_calculator.py
│       ├── test_heuristics.py
│       ├── test_models.py
│       ├── test_nlp.py
│       ├── test_openai_service.py
│       └── test_segmenter.py
│
├── frontend/                  ← React + Vite
│   ├── package.json
│   ├── vite.config.js         ← Proxy /chat, /history → localhost:8001
│   ├── index.html
│   ├── src/
│   │   ├── main.jsx           ← React app (App, Message, Metric)
│   │   └── styles.css         ← Dark theme CSS
│
└── documents/                 ← Detailed docs
    ├── 00-overview.md
    ├── 01-architecture.md
    ├── 02-backend-api.md
    ├── 03-ai-pipeline.md
    ├── 04-storage.md
    └── 05-frontend.md
```

## Request Flow (Detailed)

```
User types message
       ↓
Frontend POST /chat
  { message, user_id, conversation_id? }
       ↓
Backend main.py::chat()
  1. extract_numbers(message)        ← regex + spaCy → raw numbers
  2. LLM #1: segment_with_llm()     ← GPT → segments[]
     ↳ Fallback: segmenter.segment_text() (regex)
  3. LLM #2: extract()              ← GPT → FinancialData
     a. extract_time_unit()         ← parse time phrases
     b. normalize_value()           ← compute monthly equivalent
     c. _aggregate_segment_extractions() ← merge into FinancialData
  4. calculate_goal(data)           ← calculator → CalculationResult
  5. _store_async (background)      ← after response returns:
     ├─ save RAW segments (parallel)
     ├─ update classified segments (parallel)
     └─ save chat record → local + Mujarrad
       ↓
Response → Frontend
  { conversation_id, assistant_message, extracted_data, calculation }
```

## Data Flow Diagram

```
┌──────────┐     POST /chat     ┌──────────────────┐
│  React    │ ─────────────────→ │   FastAPI App    │
│  Frontend │ ←──────────────── │  (main.py)       │
└──────────┘     JSON response  └────────┬─────────┘
                                         │
                         ┌───────────────┼───────────────┐
                         ▼               ▼               ▼
                  ┌────────────┐  ┌─────────────┐  ┌──────────┐
                  │ LLM #1     │  │ LLM #2     │  │Calculator│
                  │ Segmenter  │  │ Extractor  │  │ (math)  │
                  └─────┬──────┘  └──────┬──────┘  └────┬─────┘
                        │                │              │
                        ▼                ▼              ▼
                  ┌────────────────────────────────────────┐
                  │         MujarradStorage                │
                  │  (local .mujarrad-chat/history.json    │
                  │   + background async POST to Mujarrad) │
                  └────────────────────────────────────────┘
```
