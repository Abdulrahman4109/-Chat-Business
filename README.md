# Financial Chat Assistant

Full-stack chat app that extracts financial numbers from natural language, classifies them, calculates goal timelines, and stores chat history only through `https://www.mujarrad.com/spaces/chat`.

## Stack

- Backend: FastAPI, OpenAI API, spaCy tokenization/numeric extraction
- Frontend: React + Vite
- Storage: Mujarrad Spaces endpoint only

## Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Copy `.env` with your keys (see below), then:

```bash
uvicorn app.main:app --reload --port 8000
```

**Required env vars in `backend/.env`:**
- `OPENAI_API_KEY` — OpenRouter or OpenAI key
- `MUJARRAD_PUBLIC_KEY` / `MUJARRAD_SECRET_KEY` — generate via `npx mujarrad-cli sdk keygen --name "my-app"`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend expects the backend at `http://localhost:8000` unless `VITE_API_BASE_URL` is set.

## API

- `POST /chat`
- `POST /analyze`
- `POST /calculate`
- `GET /history`

