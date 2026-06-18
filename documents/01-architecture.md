# Architecture

## Project Structure

```
chat/
├── CLAUDE.md                  ← Project memory (auto-updated)
├── README.md
├── .gitignore
│
├── backend/                   ← Python FastAPI
│   ├── .env                   ← API keys (gitignored)
│   ├── requirements.txt       ← fastapi, openai, pydantic, httpx, mangum
│   ├── vercel.json            ← Vercel deployment config
│   ├── app/
│   │   ├── main.py            ← FastAPI app: all HTTP routes
│   │   ├── models.py          ← Pydantic models (ChatRequest, FinancialData, …)
│   │   ├── config.py          ← Settings from .env (pydantic-settings)
│   │   ├── openai_service.py  ← LLM extraction service (prompts + API calls)
│   │   ├── heuristics.py      ← Fallback: number extraction (no classification)
│   │   ├── calculator.py      ← Goal timeline math (net savings → months)
│   │   ├── nlp.py             ← Number extraction (regex + spaCy like_num)
│   │   ├── segmenter.py       ← Arabic-aware text segmenter (regex)
│   │   ├── storage.py         ← Local JSON + Mujarrad API client
│   │   └── schema.json        ← Mujarrad node schema
│   ├── api/index.py           ← Vercel Mangum handler
│   ├── scripts/
│   │   ├── generate_training_data.py  ← Fine-tuning dataset generator
│   │   ├── finetune_data.jsonl         ← Generated training examples
│   │   └── HOW_TO_FINETUNE.md
│   └── tests/                 ← 76 pytest tests
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
│   └── api/                   ← Duplicate backend for Vercel serverless
│
└── documents/                 ← ← You are here
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

## Request Flow (Detailed)

```
User types message
       ↓
Frontend POST /chat
  { message, user_id, conversation_id? }
       ↓
Backend main.py::chat()
  1. extract_numbers(message)        ← regex + spaCy → raw numbers
  2. segment_text(message)           ← regex splitter → list[str]
  3. save segment nodes (RAW)        ← Mujarrad "example" space
  4. OpenAIExtractionService.extract() ← LLM → FinancialData
     a. extract_entities()           ← spaCy NER (MONEY, DATE, …)
     b. LLM call with segments       ← EXTRACTION_PROMPT
     c. _aggregate_segment_extractions() ← merge into FinancialData
  5. calculate_goal(data)            ← calculator → CalculationResult
  6. update segment nodes (classified) ← Mujarrad "example" space
  7. save_chat_record(record)        ← Local JSON + Mujarrad "chat" space
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
                  │ Segmenter  │  │ LLM Service │  │ Calculator│
                  │ (regex)    │  │ (openai)    │  │ (math)   │
                  └─────┬──────┘  └──────┬──────┘  └────┬─────┘
                        │                │              │
                        ▼                ▼              ▼
                  ┌────────────────────────────────────────┐
                  │         MujarradStorage                │
                  │  (local .mujarrad-chat/history.json    │
                  │   + async POST to Mujarrad API)        │
                  └────────────────────────────────────────┘
```

## Two Storage Spaces in Mujarrad

| Space Slug | Purpose | Node Titles |
|-----------|---------|------------|
| `chat` | Full chat records | `chat-{uuid}` |
| `example` | Financial segment nodes | `seg-{conv_id}-{idx}` |

Why two spaces? Chat records contain full conversations (for history sidebar). Segment nodes contain per-sentence financial classifications (for data analysis/auditing).
