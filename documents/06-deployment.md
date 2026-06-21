# Deployment

## Running the Backend

```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

## Running the Frontend

```powershell
cd frontend
npm run dev
```

## Building the Frontend for Production

```powershell
cd frontend
npm run build
```

Output: `frontend/dist/` — deploy to any static host.

Set `VITE_API_BASE_URL` to the backend URL (or omit for same-origin).

## CORS Configuration

The deployed frontend URL can be added to `cors_origins` in `.env`:

```
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://your-domain.com
```

## Environment Variables

Set in `backend/.env`:

| Variable | Example | Notes |
|----------|---------|-------|
| `OPENAI_API_KEY` | `sk-or-v1-...` | OpenRouter API key |
| `MUJARRAD_PUBLIC_KEY` | `pk_live_...` | Mujarrad API public key |
| `MUJARRAD_SECRET_KEY` | `sk_live_...` | Mujarrad API secret key |
| `MUJARRAD_SPACE_URL` | `https://.../spaces/chat` | Chat records space |

Optional overrides via Settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `openai_base_url` | `https://openrouter.ai/api/v1` | OpenAI-compatible API base |
| `openai_model` | `gpt-4o-mini` | Model to use |
| `mujarrad_api_base` | `https://www.mujarrad.com/api` | Mujarrad API base |
| `mujarrad_segments_space_url` | `https://.../spaces/example` | Segment nodes space |
| `cors_origins` | localhost:5173 | Comma-separated CORS origins |
