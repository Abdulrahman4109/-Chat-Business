# Architecture

## Project Structure

```
chat/
├── backend/                          # Python FastAPI (port 8000)
│   ├── app/
│   │   ├── main.py                   # Routes: /chat, /history, /analyze, /calculate, /diagram
│   │   ├── models.py                 # Pydantic schemas (request/response)
│   │   ├── config.py                 # Environment settings
│   │   ├── heuristics.py             # Text normalization, number extraction
│   │   ├── calculator.py             # Goal timeline math
│   │   ├── nlp.py                    # Regex + spaCy number extraction
│   │   ├── storage.py                # Local JSON + remote API storage
│   │   ├── openai_service.py         # Legacy extraction (used by /analyze)
│   │   ├── diagram_generator.py      # Draw.io XML generation
│   │   ├── segmenter.py              # Text splitting
│   │   ├── financial_agent/          # Guided conversation pipeline
│   │   └── system_builder/           # Separate system builder feature
│   └── tests/                        # 96 tests
├── frontend/                         # React 19 + Vite (port 5173)
│   └── src/
│       ├── main.jsx                  # App, Message, Metric components
│       └── styles.css                # Dark theme
└── documents/                        # System documentation
```

## Request Flow

```
User → POST /chat { message, user_id, conversation_id? }
         │
         ▼
   1. normalize_text()
      - Arabic/Persian digits → Western digits
      - Detach numbers from adjacent text
         │
         ▼
   2. FinancialAgentPipeline.run_orchestrator()
         │
         ├── process_input()      ← First message: extract all fields
         ├── check_completeness() ← Any fields missing?
         │   ├── Yes → generate_question() → response with question_type="yesno"
         │   └── No  → calculate_goal()    → response with calculation
         │
         ▼
   3. _store_chat_record_async()  ← Background save (never blocks)
         │
         ▼
      Response → Frontend
```

## Data Flow Diagram

```
┌──────────┐    POST /chat     ┌─────────────────────┐
│  React    │ ────────────────→ │    FastAPI App      │
│  Frontend │ ←──────────────── │    (main.py)        │
└──────────┘    JSON response   └─────────┬───────────┘
                                          │
                     ┌────────────────────┼────────────────────┐
                     ▼                    ▼                    ▼
              ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
              │  LLM Calls   │    │  Calculator  │    │   Storage    │
              │ (extraction) │    │  (timeline)  │    │  (async)     │
              └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
                     │                   │                   │
                     ▼                   ▼                   ▼
              ┌──────────────────────────────────────────────────┐
              │              FinancialAgentState                 │
              │  goal, income, expenses, savings, debts, extra   │
              │  is_complete, result, messages                   │
              └──────────────────────────────────────────────────┘
```

## Key Design Decisions

- **None ≠ 0**: Unmentioned fields stay `None` — UI hides them, calculator treats as 0
- **Background storage**: Remote API failures never slow the user response
- **Conversational extraction**: Ask for missing data instead of requiring it all at once
- **Time-unit normalization**: All values normalized to monthly; if no unit specified, assume monthly
