# ChatBusiness — Financial Chat Assistant

A bilingual (Arabic/English) conversational AI that extracts financial data from free text, normalizes any time unit to monthly, calculates goal timelines, and stores conversations.

## Features

- Extract income, expenses, savings, debts, and goals from casual sentences
- Normalize ANY time unit to monthly (hourly, daily, weekly, biweekly, quarterly, yearly, `كل 2 شهر`, etc.)
- Arabic + English mixed in the same message (handles `ادخار20000`, `800000ولدي`, Arabic-Indic digits)
- Debts reduce effective savings in calculation
- Unmentioned fields skip display (no zero placeholders)
- Cancel button to abort mistaken sends
- Conversation history with sidebar grouped by conversation
- Background storage (local JSON + Mujarrad API) — never blocks response

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, uvicorn (port 8000) |
| Frontend | React 19, Vite, Lucide icons (port 5173) |
| AI | gpt-4o-mini via OpenRouter |
| NLP | Regex + optional spaCy (`en_core_web_sm`) |
| Storage | Local JSON (`~/.mujarrad-chat/`) + Mujarrad API |

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenRouter key (`sk-or-v1-...`) or OpenAI key (`sk-...`) |
| `MUJARRAD_PUBLIC_KEY` | Public key from Mujarrad CLI |
| `MUJARRAD_SECRET_KEY` | Secret key from Mujarrad CLI |

To generate Mujarrad keys:

```bash
npm install -g mujarrad-cli
mujarrad auth login
mujarrad sdk keygen
```

Then run:

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

spaCy is optional (regex-only extraction works fine without it):

```bash
.venv\Scripts\python -m spacy download en_core_web_sm
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite proxy forwards `/chat`, `/history`, etc. to `localhost:8001` — run the backend on port **8001** for dev, or update `vite.config.js` to match your backend port.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /chat` | Full pipeline — extract → calculate → respond → store (background) |
| `GET /history?user_id=xxx` | Fetch conversation history |
| `POST /analyze` | Run financial extraction (no save) |
| `POST /calculate` | Compute goal timeline from structured data |
| `GET /mujarrad/status` | Check Mujarrad API connection |
| `GET /health` | Server health check |

## Mujarrad Spaces

- **Chat history** → [`chat` space](https://www.mujarrad.com/spaces/chat)
- **Financial segments** → [`example` space](https://www.mujarrad.com/spaces/example)

## Tests

```bash
cd backend
.venv\Scripts\python -m pytest tests -v
```
