# Financial Chat Assistant

A conversational AI that extracts financial goals from free text, asks for missing information, calculates goal timelines, and generates visual roadmaps.

## Features

- Extract goal, income, expenses, savings, debts, and extra income from natural language
- Ask for missing data with yes/no questions instead of failing or guessing
- Normalize any time unit to monthly (weekly, daily, yearly, etc.)
- Calculate goal timeline with optimization suggestions
- Generate interactive financial roadmap diagrams (draw.io)
- Background storage (local JSON + remote API) — never blocks response
- Language detection — asks questions in the user's language
- Conversation history grouped by session

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, uvicorn (port 8000) |
| Frontend | React 19, Vite, Lucide icons (port 5173, proxy → 8001) |
| AI | gpt-4o-mini via OpenRouter or direct OpenAI |
| Storage | Local JSON (`~/.mujarrad-chat/`) + Mujarrad API |

## Setup

### 1. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenRouter (`sk-or-v1-...`) or OpenAI (`sk-...`) |
| `OPENAI_BASE_URL` | No | Default: `https://openrouter.ai/api/v1` (empty = direct OpenAI) |
| `OPENAI_MODEL` | No | Default: `gpt-4o-mini` |
| `MUJARRAD_PUBLIC_KEY` | No | Mujarrad API public key |
| `MUJARRAD_SECRET_KEY` | No | Mujarrad API secret key |
| `MUJARRAD_SPACE_URL` | No | Chat history space |
| `MUJARRAD_GRAPH_SPACE_URL` | No | Diagram storage space |

Run:

```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite proxy forwards requests to `localhost:8001` — run the backend on port **8001** or update `vite.config.js`.

## Usage

1. **Start**: Send a goal message like "I want to buy a car for 800,000, I earn 15,000 a month"
2. **Follow-up**: Answer yes/no questions for any missing information (expenses, savings, debts, extra income)
3. **Result**: View the timeline, breakdown, and optimization suggestions
4. **Visualize**: Click "View Financial Plan" to open an interactive draw.io roadmap

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Guided extraction → calculation → respond |
| `/analyze` | POST | Legacy one-shot extraction |
| `/calculate` | POST | Pure timeline math from existing data |
| `/diagram` | POST | Generate draw.io roadmap XML |
| `/diagram/save` | POST | Save edited diagram |
| `/diagram/load` | GET | Load saved diagram |
| `/history` | GET | Past conversations for a user |
| `/health` | GET | Liveness check |
| `/mujarrad/status` | GET | Storage connection status |

## Storage Spaces

| Slug | Content | URL |
|------|---------|-----|
| `chat` | Conversation history | `.../spaces/chat` |
| `graph` | Diagram XML | `.../spaces/graph` |

## Tests

```powershell
cd backend
.venv\Scripts\python -m pytest tests -v
```

96 tests across 7 test files.

## Documentation

See `documents/` directory for detailed reference:

- `00-overview.md` — Quick intro
- `01-architecture.md` — Project structure, request lifecycle
- `02-backend-api.md` — All endpoints, request/response schemas
- `03-ai-pipeline.md` — Extraction, normalization, calculation
- `04-storage.md` — Local + remote storage
- `05-frontend.md` — React components, state flow
- `06-financial-agent.md` — State machine, prompts
- `07-diagram.md` — Draw.io integration
