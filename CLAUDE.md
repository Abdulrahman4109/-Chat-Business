# Financial Chat Assistant — Project Memory

## Stack
- Backend: Python FastAPI (port 8000)
- Frontend: React + Vite (port 5173)
- AI: OpenRouter (gpt-4o-mini) — OpenAI-compatible
- Storage: Local JSON (`~/.mujarrad-chat/history.json`) + Mujarrad API

## Key Files

| File | Purpose |
|------|---------|
| `backend/.env` | API keys (OpenRouter + Mujarrad) |
| `backend/app/main.py` | FastAPI routes: `/chat`, `/history`, `/analyze`, `/calculate`, `/health`, `/mujarrad/status` |
| `backend/app/storage.py` | `MujarradStorage`: saves to local JSON + syncs to `POST /api/spaces/{slug}/nodes` |
| `backend/app/config.py` | `Settings`: reads `.env`, extracts space slug from `MUJARRAD_SPACE_URL` |
| `backend/app/models.py` | Pydantic models: `ChatRecord`, `FinancialData`, `CalculationResult`, etc. |
| `backend/app/openai_service.py` | OpenAI/OpenRouter client with `base_url` support |
| `backend/app/heuristics.py` | Rule-based Arabic/English financial extraction (fallback when no AI key) |
| `backend/app/calculator.py` | Goal timeline calculator |
| `backend/app/nlp.py` | Number extraction (spaCy + regex) |
| `backend/schema.json` | Mujarrad data model schema definition |
| `frontend/src/main.jsx` | React app: chat UI + sidebar history (like ChatGPT) |
| `frontend/src/styles.css` | Dark theme styles |

## Mujarrad API
- **Space slug**: `chat` (from `MUJARRAD_SPACE_URL`)
- **Auth headers**: `X-API-Key` + `X-API-Secret`
- **Endpoints**: `POST/GET /api/spaces/{slug}/nodes`
- **Web UI**: `https://www.mujarrad.com/spaces/chat`

## Storage Flow
1. Chat message → backend → save to `~/.mujarrad-chat/history.json` (always)
2. Backend → async POST to Mujarrad API (if reachable)
3. History: load from local first, then try Mujarrad API for fresher data
4. Sidebar sorted by most recent conversation

## Tests
- `backend/tests/`: 45 tests (calculator, heuristics, models, nlp)
- Run: `cd backend && .venv\Scripts\python -m pytest tests -v`
