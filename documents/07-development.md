# Development Setup

## Prerequisites

- Python 3.13+
- Node.js 20+
- npm

---

## Backend Setup

```powershell
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Set up environment
# Copy or edit .env with your API keys
```

### Run Backend

```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Server starts on `http://localhost:8000`.

### Run Tests

```powershell
cd backend

# All tests
.venv\Scripts\python -m pytest tests -v

# Specific file
.venv\Scripts\python -m pytest tests/test_calculator.py -v
```

**Test count:** 85 tests across 6 files.

---

## Frontend Setup

```powershell
cd frontend
npm install
```

### Run Frontend

```powershell
cd frontend
npm run dev
```

Server starts on `http://localhost:5173`.

**Important:** Vite proxies API calls to `localhost:8001`, not `localhost:8000`. Either:
- Run backend on port 8001
- Or update `vite.config.js` proxy target

---

## Full Dev Environment (Run Both)

**Terminal 1 — Backend:**
```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8001
```

**Terminal 2 — Frontend:**
```powershell
cd frontend
npm run dev
```

Then open `http://localhost:5173`.

---

## spaCy Model

spaCy is NOT in `requirements.txt` — it is optional:

```powershell
cd backend
.venv\Scripts\python -m spacy download en_core_web_sm
```

Without the model, the system works fine (regex-only number extraction). The model adds `like_num` token detection as additional hints.

---

## .gitignore

```
.env
.venv/
__pycache__/
*.pyc
node_modules/
dist/
.vite/
```

---

## Common Commands

### Backend
| Command | Description |
|---------|-------------|
| `uvicorn app.main:app --reload --port 8000` | Dev server |
| `python -m pytest tests -v` | Run all tests |
| `python scripts/generate_training_data.py` | Regenerate fine-tuning dataset |
| `python scripts/generate_training_data.py --upload` | Upload + start fine-tuning |

### Frontend
| Command | Description |
|---------|-------------|
| `npm run dev` | Dev server with HMR |
| `npm run build` | Production build → dist/ |
