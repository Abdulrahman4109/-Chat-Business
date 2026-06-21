# Financial Chat Assistant — Overview

## What is this?

A bilingual (Arabic/English) conversational AI that extracts financial information from natural language text, calculates goal-timeline projections, and returns structured results.

**Input (free-text, any order):**

> "I want to buy a car worth 800,000. I have 20,000 in savings. My income is 4,000 per week, with weekly expenses of 900. I also receive 4,000 in bonuses and have an additional income of 2,000."

**Output (structured + timeline):**

> Goal: 800,000 | Income: 17,143 | Expenses: 3,857 | Savings: 20,000 | Extra: 6,000
>
> "At your current pace, it will take 3 years and 5 months. Net monthly savings: 19,286. Remaining amount: 780,000."

## Key Features

- **Bilingual**: Arabic + English, mixed in same message
- **Time normalization**: Any time unit → standard month (30 days)
  - Hourly ×171.43, Daily ×30, Weekly ×4.2857, Bi-weekly ×2.1429
  - Every-10-days ×3, Semi-monthly ×2, Quarterly ÷3
  - Semi-annually ÷6, Yearly ÷12, Biennially ÷24
- **Arabic attached numbers**: Handles `ادخار20000`, `مرتب50000`, `800000ولدي`
- **Comma-formatted numbers**: `4,000` → 4000, `800,000` → 800000
- **Currency symbols**: $, €, £
- **Shorthand**: 5k → 5000, 2m → 2000000
- **Arabic-Indic digits**: ١٢٣ → 123
- **No-goal fallback**: Answers basic "what are my finances" without a target
- **Conversation history**: Persistent per-user, restored from sidebar
- **Mujarrad sync**: Remote storage via Mujarrad API (nodes)
- **Cancel button**: Abort in-flight request if sent by mistake
- **None defaults**: Unmentioned fields skip display entirely (no "0" placeholders)

## System Architecture (High-Level)

```
User → React Frontend (Vite:5173)
         ↓ POST /chat
      FastAPI Backend (uvicorn:8000)
         ↓
      1. extract_numbers()         — Regex + spaCy
      2. LLM #1: segment_with_llm() — GPT splits into segments
         ↳ Fallback: segmenter.segment_text() (regex)
      3. save RAW segments          — to Mujarrad (background, parallel)
      4. LLM #2: extract()          — GPT classifies + normalizes time units
         ↳ Fallback: heuristic_extract() (numbers only)
      5. calculate_goal()           — Timeline math (with debts support)
      6. save chat record           — Local JSON + Mujarrad (background)
         ↓
      Response → Frontend → Bubble (text + metric grid + result panel)
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, uvicorn |
| AI | OpenAI gpt-4o-mini (via OpenRouter) |
| Frontend | React 19, Vite, Lucide icons |
| Storage | Local JSON (~/.mujarrad-chat/) + Mujarrad REST API |
| Deployment | Local uvicorn + static hosting |
