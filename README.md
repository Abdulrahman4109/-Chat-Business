# ChatBusiness — Financial Chat Assistant

A smart financial chat app that extracts numbers from natural language (Arabic/English), calculates goal timelines, and stores conversations via Mujarrad API.

## Features

- Extract income, expenses, savings, and financial goals from any sentence
- Calculate time required to reach a financial goal (months/years)
- Supports Arabic and English text
- Save conversations locally (`~/.mujarrad-chat/history.json`) and to Mujarrad cloud
- Sidebar history sorted by most recent

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python FastAPI (port 8000) |
| Frontend | React + Vite (port 5173) |
| AI | gpt-4o-mini (OpenAI-compatible) |
| NLP | spaCy + Regex |
| Storage | Local JSON + Mujarrad API |

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Create `backend/.env` with the following keys:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | API key |
| `MUJARRAD_PUBLIC_KEY` | Public key from Mujarrad CLI |
| `MUJARRAD_SECRET_KEY` | Secret key from Mujarrad CLI |

To generate these keys, first install the Mujarrad CLI:

```bash
npm install -g mujarrad-cli
# or run directly without installing:
npx mujarrad-cli sdk keygen
```

This outputs a public key and secret key pair. Add them to `.env`.

Then:

```bash
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /chat` | Send a message and get AI response with financial analysis |
| `GET /history?user_id=xxx` | Fetch conversation history for a user |
| `POST /analyze` | Run financial analysis on text |
| `POST /calculate` | Calculate goal timeline |
| `GET /mujarrad/status` | Check Mujarrad API connection status |
| `GET /health` | Server health check |

## Mujarrad Spaces

- **Chat history** → [`chat` space](https://www.mujarrad.com/spaces/chat)
- **Financial segments** (extracted data nodes) → [`example` space](https://www.mujarrad.com/spaces/example)

## Tests

```bash
cd backend
.venv\Scripts\python -m pytest tests -v
```
