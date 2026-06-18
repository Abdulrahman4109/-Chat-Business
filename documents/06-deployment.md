# Deployment

## Vercel Serverless Deployment

The backend is deployed on Vercel using a **Mangum** adapter that wraps the FastAPI ASGI app as a Vercel serverless function.

### Entry Point: `backend/api/index.py`

```python
from mangum import Mangum
from app.main import app

handler = Mangum(app)
```

### Configuration: `backend/vercel.json`

```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    { "src": "/api/(.*)", "dest": "api/index.py" }
  ]
}
```

**Important:** The `src` path is relative to `backend/`, so the file is `api/index.py` (not `backend/api/index.py`).

### CORS Origins (from `config.py`)

```python
cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,https://chat-business.vercel.app"
```

The deployed frontend URL (`https://chat-business.vercel.app`) is included in CORS.

---

## Environment Variables

All set in `backend/.env`:

| Variable | Example | Notes |
|----------|---------|-------|
| `OPENAI_API_KEY` | `sk-or-v1-...` | OpenRouter key (not OpenAI directly) |
| `MUJARRAD_PUBLIC_KEY` | `pk_live_...` | Mujarrad API public key |
| `MUJARRAD_SECRET_KEY` | `sk_live_...` | Mujarrad API secret key |
| `MUJARRAD_SPACE_URL` | `https://.../spaces/chat` | Chat records space |

**Optional overrides (via Settings):**

| Setting | Default | Description |
|---------|---------|-------------|
| `openai_base_url` | `https://openrouter.ai/api/v1` | OpenAI-compatible API base |
| `openai_model` | `gpt-4o-mini` | Model to use |
| `mujarrad_api_base` | `https://www.mujarrad.com/api` | Mujarrad API base |
| `mujarrad_segments_space_url` | `https://.../spaces/example` | Segment nodes space |
| `cors_origins` | See config.py | Comma-separated CORS origins |

---

## Frontend Deployment

Build for production:

```bash
cd frontend
npm run build
```

Output: `frontend/dist/` — deploy to any static host (Vercel, Netlify, etc.).

Set `VITE_API_BASE_URL` to the backend URL (or omit for same-origin).

---

## Backend-Frontend Sync

There is a `frontend/api/` directory that **mirrors** `backend/app/` for Vercel serverless deployment. When making backend changes, you must also update `frontend/api/` to keep them in sync. The Vercel function handler lives at `backend/api/index.py`.
