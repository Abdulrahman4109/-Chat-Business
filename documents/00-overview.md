# Financial Chat Assistant — System Overview

## What is this?

A bilingual (Arabic/English) conversational AI that transforms casual financial chat into a structured goal-timeline projection.

You type something like:

> *"I want to buy a car worth 800,000. I have 20,000 in savings. My income is 4,000 per week, with weekly expenses of 900. I also receive 4,000 in bonuses and have an additional income of 2,000."*

The system understands the meaning (not just keywords), normalizes all time units to monthly, and replies with:

> *"At your current pace, it will take 3 years and 5 months. Net monthly savings: 19,286. Remaining amount: 780,000."*

## How It Works (Step by Step)

### 1. Number Extraction (`nlp.py`)
Pulls every number out of the raw message — handles attached Arabic text (`ادخار20000`), currency symbols (`$4,000`), shorthand (`5k`), Arabic-Indic digits (`١٢٣`), and comma formatting (`800,000`).

### 2. LLM #1 — Semantic Segmentation (`openai_service.py:segment_with_llm`)
Sends the message to GPT-4o-mini to split it into atomic "thought units":

> `"I want a car worth 800,000 and my salary is 4,000 per week"`
> → `["I want a car worth 800,000", "my salary is 4,000 per week"]`

The LLM understands that Arabic `و` joins separate financial facts. If GPT is unavailable, a regex fallback in `segmenter.py` handles the splitting without intelligence.

### 3. LLM #2 — Financial Classification (`openai_service.py:extract`)
The same GPT model classifies each segment into the correct financial field:

- `"I want a car worth 800,000"` → **goal_price = 800,000**
- `"my salary is 4,000 per week"` → **monthly_income = 17,143** (weekly → monthly)

Time unit normalization happens inside `extract_time_unit` + `normalize_value`: weekly ×4.2857, daily ×30, yearly ÷12, `كل 2 شهر` → ×0.5, etc.

If GPT fails, `heuristic_extract()` returns raw numbers without field classification.

### 4. Calculation (`calculator.py`)
```
net_monthly_savings = (income + extra) - expenses
remaining = max(goal - savings, 0)
months = ceil(remaining / net_monthly_savings)
```
Debts reduce effective savings: `effective_savings = max(savings - debts, 0)`.

### 5. Response (`build_assistant_response`)
Builds a natural-language reply with the timeline, net savings, and up to 3 suggestions.

### 6. Background Storage (`_store_async`)
All storage (local JSON + Mujarrad API) runs as an `asyncio.create_task` after the response is sent — the user never waits for disk or network writes. Raw segments are saved first (parallel), then classified segments are updated (parallel), then the chat record is saved.

## Frontend

A dark-themed React 19 + Vite SPA with:

- **Chat bubbles** showing text + metric grid + result panel
- **Metric cards** that return `null` for unmentioned fields — if you didn't mention debts, no "Debt" card appears (not even a 0)
- **Net Savings row** appears only when `current_debts` exists
- **Cancel button** with `AbortController` to abort a mistaken send
- **History sidebar** grouped by conversation, restored on click
- **Vite proxy** routes `/chat`, `/history`, etc. → `localhost:8001`

## Architecture Diagram

```
User → React (Vite :5173)
         ↓ POST /chat
      FastAPI (uvicorn :8000)
         ↓
     1. extract_numbers()          — regex + spaCy
     2. LLM #1: segment_with_llm() — GPT splits into segments
        ↳ Fallback: segmenter.segment_text()
     3. LLM #2: extract()          — GPT classifies + normalizes time
        ↳ Fallback: heuristic_extract() (numbers only)
     4. calculate_goal()           — timeline math + debts support
     5. _store_async (background)  — raw segs → classified → chat
         ↓
      Response → Frontend
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, uvicorn (port 8000) |
| AI | gpt-4o-mini via OpenRouter |
| Frontend | React 19, Vite, Lucide icons (port 5173) |
| Storage | Local JSON (`~/.mujarrad-chat/`) + Mujarrad REST API |

## Key Design Principles

- **Semantic understanding, not keywords** — "عايز أشتري", "هدفى", "نفسي في", "save for", "need" all map to `goal_price`. No keyword lists, no regex patterns for each field.
- **Time-unit agnostic** — hourly, daily, weekly, biweekly, monthly, quarterly, yearly, biennially, plus all Arabic variants including computed multipliers (`كل 2 شهر` → ×0.5). Every unit normalizes to a standard month.
- **Background storage** — Mujarrad can be slow or down; it never slows the user's response.
- **None ≠ 0** — unmentioned fields stay `None` and are hidden from the UI. The user sees only what they actually said.
