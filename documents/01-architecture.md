# Architecture

## Project Structure

```
chat/
├── backend/                          # Python FastAPI
│   ├── .env
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                   # All routes
│   │   ├── models.py                 # Pydantic schemas
│   │   ├── config.py                 # Environment settings (cached singleton)
│   │   ├── llm_chain.py              # Model fallback chain (OpenRouter → free models)
│   │   ├── heuristics.py             # Text normalization, regex classification
│   │   ├── calculator.py             # Goal timeline math + bilingual formatting
│   │   ├── nlp.py                    # Regex + optional spaCy extraction
│   │   ├── openai_service.py         # Legacy extraction (used by /analyze)
│   │   ├── segmenter.py              # Text splitting
│   │   ├── diagram_generator.py      # Draw.io roadmap XML
│   │   ├── storage.py                # Local JSON + remote Mujarrad API
│   │   ├── financial_agent/          # Guided conversation state machine
│   │   │   ├── models.py             # FinancialAgentState, GuidedChatResponse
│   │   │   ├── pipeline.py           # Orchestrator: extract → question → calculate
│   │   │   └── prompts.py            # PROCESS_INPUT_PROMPT
│   │   └── schema.json               # Mujarrad API node payload schemas
│   ├── scripts/                      # Training data generation
│   └── tests/                        # 96 tests
├── frontend/
│   ├── package.json                  # React 19, Vite, lucide-react
│   ├── vite.config.js                # Proxy all API paths → 8001
│   └── src/
│       ├── main.jsx                  # App, Message, Metric components
│       └── styles.css                # Dark theme
└── documents/                        # 9 markdown docs
```

## Pipeline

State machine with 6 fields (goal, income, expenses, savings, debts, extra). Hybrid extraction: fast regex heuristic first, LLM fallback. Bilingual Arabic/English.

## LLM Chain (`llm_chain.py`)

`chain_call()` iterates through a model chain (configurable via `openai_model_chain`):
1. Primary: `gpt-4o-mini` (OpenRouter)
2. Fallbacks: `openrouter/free`, `google/gemma-4-31b-it:free`

Each model gets up to 2 attempts. `RateLimitError` → skip immediately. All fail → return `"{}"`. No API key → return `"{}"`. Uses `AsyncOpenAI` client with `temperature=0`.

## Request Flow (`/chat`)

```
User → POST /chat { message, user_id, conversation_id? }
         │
         ▼
    1. normalize_text() — digits → 0-9, detach text/numbers
         │
         ▼
    2. _restore_session() — rebuild FinancialAgentState from history + context
         │
         ▼
    3. FinancialAgentPipeline.run_orchestrator(state, message)
         ├── First message → process_input (heuristic → LLM)
         ├── Answer → update_data (extract value)
         ├── check_completeness → generate_question (if incomplete)
         └── calculate_goal → result (if complete)
         │
         ▼
    4. asyncio.create_task: save ChatRecord + context (never blocks)
         │
         ▼
      Response → Frontend
```

## Config (`config.py`)

| Variable | Default | Notes |
|----------|---------|-------|
| `openai_api_key` | "" | `sk-or-v1-...` (OpenRouter) or `sk-...` (OpenAI) |
| `openai_base_url` | `https://openrouter.ai/api/v1` | Empty = direct OpenAI |
| `openai_model` | `gpt-4o-mini` | Primary model |
| `openai_model_chain` | `gpt-4o-mini,openrouter/free,...` | Fallback models |
| `mujarrad_*_key` | "" | API auth for storage |
| `mujarrad_*_space_url` | `/spaces/{slug}` | Spaces: chat, example, graph |
| `cors_origins` | `localhost:5173,127.0.0.1:5173` | CORS allowlist |
| `token_limit` | 4096 | Max LLM tokens |
| `max_history_messages` | 6 | Context window for state restoration |

## Key Design Decisions

- **None ≠ 0**: Unmentioned fields stay None — UI hides them; calculator treats as 0
- **Background storage**: Remote API failures never slow the response
- **Conversational extraction**: Ask for missing info instead of requiring it all at once
- **Time-unit normalization**: All values → monthly; no unit = assume monthly
- **Hybrid extraction**: Regex heuristic first (fast, no API cost), LLM fallback
- **Bilingual**: Questions in user's detected language (Arabic Unicode or English)
