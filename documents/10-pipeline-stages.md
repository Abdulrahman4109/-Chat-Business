# Pipeline Stages — Financial Goal Calculator

A theoretical description of the request processing stages in the Financial Goal Calculator mode, from receiving the user's message to returning the final result.

---

## Overview

```
User Message
      │
      ▼
┌─────────────────┐
│  Normalization  │  ← Convert non-Western digits + detach text from numbers
└────────┬────────┘
         ▼
┌─────────────────┐
│    Heuristics   │  ← Regex number extraction + field classification
└────────┬────────┘
         ▼
┌─────────────────┐
│  LLM Extraction │  ← Extract remaining fields via AI
└────────┬────────┘
         ▼
┌─────────────────┐
│  State Machine  │  ← Dialogue management: question → answer → update
└────────┬────────┘
         ▼
┌─────────────────┐
│   Calculation   │  ← Math formula + optimization suggestions
└────────┬────────┘
         ▼
┌─────────────────┐
│     Output      │  ← Response + background storage
└─────────────────┘
```

Each stage consumes the output of the preceding stage. If all fields are satisfied at an early stage, subsequent unnecessary stages are skipped.

---

## Stage 1 — Normalization

**Component**: `heuristics.py` → `normalize_text()`

**Input**: Raw user text (string)

**Processing**:

1. **Convert non-Western digits** to 0-9:
   - Arabic-Indic (٠١٢٣٤٥٦٧٨٩) → 0123456789
   - Persian (۰۱۲۳۴۵۶۷۸۹) → 0123456789
   - Any other numeral system is converted to its Western equivalent

2. **Separate text from attached digits**:
   - Insert a space between non-Latin characters and adjacent digits
   - Example: "بـ50000" → "بـ 50000"
   - Ensures regex patterns work correctly in the next stage

**Output**: Normalized string

**Purpose**: Unify different numeral formats (Arabic/Persian/Western, attached/detached) before processing. Without this stage, regex and the LLM would fail to extract numbers entered in non-Western scripts.

---

## Stage 2 — Heuristic Extraction

**Component**: `heuristics.py` → `heuristic_classify()`

**Input**: Normalized text + list of required fields

**Processing**:

1. **Extract all numbers** from text via `extract_number_mentions()` — handles integers, decimals, currencies, suffixes, and thousands separators

2. **Classify numbers into fields** by matching regex patterns:
   - `goal_price`
   - `monthly_income`
   - `monthly_expenses`
   - `current_savings`
   - `current_debts`
   - `extra_income`

3. **Early completeness check** via `is_ready_for_calculation()`:
   - If all six fields are found with non-null values → skip the LLM stage entirely
   - If any field is missing → proceed to the LLM stage

**Output**: `FinancialData` object (some fields may be null) + preliminary completeness flag

**Purpose**: Fast extraction with zero API cost. Regex runs locally in milliseconds. It fully covers ~40-60% of simple cases.

---

## Stage 3 — LLM Extraction

**Component**: `llm_chain.py` → `chain_call()` + prompts

**Input**: Normalized text + incomplete `FinancialData` object

**Processing**:

1. **Build the prompt** (`PROCESS_INPUT_PROMPT`) with field definitions in both Arabic and English, including time unit normalization rules

2. **Send to the LLM** via the model chain (`chain_call()`):
   - Primary model: gpt-4o-mini via OpenRouter
   - Fallback model: openrouter/free
   - Each model gets up to 2 attempts; `RateLimitError` → skip to next model
   - If all fail: return `"{}"`, heuristic values only are used

3. **Normalize time units** to monthly equivalents (weekly, daily, yearly — or assume monthly if unspecified)

4. **Merge results**: LLM results merge with heuristic results (they do not replace them)

**Output**: Updated `FinancialData` object (more non-null fields)

**Purpose**: Extract fields that heuristic regex failed to capture due to linguistic complexity. The LLM understands context and implications that regex cannot.

---

## Stage 4 — State Machine

**Component**: `financial_agent/pipeline.py` → `FinancialAgentPipeline`

**Input**: `FinancialData` object + `FinancialAgentState` (session state)

**Processing**:

### 4.1 — Completeness Check (`check_completeness`)
- Iterate over all six fields
- If any field is null → dialogue is incomplete
- If all are non-null → dialogue is complete

### 4.2 — Question Generation (`generate_question`) [if incomplete]
- Identify the first missing field in order:
  1. `monthly_income` — ask directly (ask_value)
  2. `monthly_expenses` — ask Yes/No (yesno)
  3. `current_savings` — ask Yes/No (yesno)
  4. `current_debts` — ask Yes/No (yesno)
  5. `extra_income` — ask Yes/No (yesno)
- Build the question text in the user's detected language (Arabic or English)
- Store `question_type` and `question_field` in the session state

### 4.3 — Data Update (`update_data`) [on user answer]
- If question type is `yesno`:
  - "No" or negation → set value to 0
  - "Yes" with a number → extract the number (with time unit normalization)
  - "Yes" without a number → set an estimated value
- If question type is `ask_value`:
  - Extract the number directly from the answer
- If question type is `restore_context` (previous session):
  - "Yes" → restore all values from the previous session
  - "No" → start a new session

### 4.4 — Routing
- If all fields are complete → proceed to the calculation stage
- If a field is still missing → generate a new question for the next field

**Output**: Either a new question (with `is_complete: false`) or complete data for calculation

**Purpose**: Collect missing information interactively. Instead of overwhelming the user by asking for everything at once, the process is broken into small, natural steps.

---

## Stage 5 — Calculation

**Component**: `calculator.py` → `calculate_goal()`

**Input**: Complete `FinancialData` object

**Processing**:

### 5.1 — Core Formulas

```
net_monthly_savings = (income + extra_income) - expenses
effective_savings   = max(savings - debts, 0)
remaining           = max(goal - effective_savings, 0)
months              = ceil(remaining / net_monthly_savings)   (if net_savings > 0)
```

### 5.2 — Edge Cases
- **No goal** (`goal` is null or 0) → result: unachievable
- **Remaining ≤ 0** (savings already cover the goal) → `months = 0`, message: "already funded"
- **Net savings ≤ 0** (expenses ≥ income) → unachievable, suggestion to reduce expenses
- **Income is null** → unachievable (cannot calculate without income)

### 5.3 — Duration Formatting (`format_duration`)
- Convert months to a bilingual display string (e.g. "3 years and 5 months" / "٣ سنوات و ٥ أشهر")

### 5.4 — Suggestion Generation (`build_suggestions`)
Maximum 3 suggestions from the following pool:
- If `months > 0`: suggest setting aside a monthly reserve
- If `months > 12`: suggest ways to shorten the timeline
- If `expenses > 0.6 × income`: suggest reviewing expenses
- If multiple goals exist: suggest consolidating goals

**Output**: `CalculationResult` object (months, duration_display, is_achievable, suggestions)

**Purpose**: Transform the extracted financial data into an understandable, actionable result.

---

## Stage 6 — Output & Storage

**Component**: `main.py` → `handle_message()` + `storage.py`

**Input**: `FinancialData` object + `CalculationResult`

**Processing**:

### 6.1 — Build Response
- `assistant_message`: response text in the appropriate language (Arabic/English)
- `extracted_data`: all extracted financial fields
- `calculation`: calculation result (if complete)
- `is_complete`: true/false
- `question_type` and `question_field`: (if incomplete)

### 6.2 — Background Storage
`asyncio.create_task` performs the following without blocking the response:
1. Local save: `~/.mujarrad-chat/history.json`
2. Remote save: POST to Mujarrad API (best-effort — failures logged, never raised)

**Output**: JSON response to the frontend

**Purpose**: Return the result immediately while persisting records in the background. Remote storage failure does not affect the user experience.

---

## Complementary Systems

The six-stage pipeline above describes the core chat flow. This section covers all other systems that complete the full project architecture.

---

## 7 — Agents Mode (Financial Smart Extractor)

A separate pipeline for extracting financial entities and relationships from text and files.

**Component**: `backend/app/agents/` package (8 files)

**Endpoints**: `/api/agents/process`, `/api/agents/upload`, `/api/agents/history`, `/api/agents/files/{file_id}`

### Process Flow

```
Input (text or file)
      │
      ▼
┌─────────────────┐
│  Text Extraction │  ← Image → Vision LLM, PDF → PyMuPDF
└────────┬────────┘
         ▼
┌─────────────────┐
│  Mudawin        │  ← LLM extracts entities (7 types)
└────────┬────────┘
         ▼
┌─────────────────┐
│  Mudrik         │  ← LLM extracts relationships (7 types)
└────────┬────────┘
         ▼
┌─────────────────┐
│  Musghi         │  ← Language detection + summary generation
└────────┬────────┘
         ▼
┌─────────────────┐
│  Storage        │  ← Local JSON + Mujarrad API (background)
└─────────────────┘
```

### Stages

#### 7.1 — Text Extraction
- **Text input**: Used directly (no extraction needed)
- **Image input**: `extract_text_from_image()` → sends base64 image to Vision LLM (same model chain with image support)
- **PDF input**: `extract_text_from_pdf()` → PyMuPDF (fitz) extracts text from all pages

#### 7.2 — Entity Extraction (Mudawin)
LLM prompt extracts 7 financial entity types: person, organization, amount, percentage, date, duration, financial_product. Returns JSON array with IDs, names, types, and original text.

#### 7.3 — Relationship Extraction (Mudrik)
LLM receives entities + original text, extracts 7 relationship types: pays_to, owed_to, guarantor_for, due_date, interest_rate, duration, purpose. Each includes source, target, direction, and evidence.

#### 7.4 — Orchestrator (Musghi)
1. Detect language (Arabic Unicode check or English)
2. Call Mudawin for entities
3. Call Mudrik for relationships
4. Generate a bilingual summary via LLM
5. Return complete `KnowledgeGraph`

#### 7.5 — Storage
Background save to `~/.mujarrad-chat/agents/<user_id>.json` + Mujarrad API `/spaces/agents`. Uploaded files saved to `~/.mujarrad-chat/uploads/<user_id>/`.

---

## 8 — LLM Model Chain Infrastructure

**Component**: `backend/app/llm_chain.py` + `backend/app/agents/llm_client.py`

### Chat Model Chain (`chain_call()` for `/chat`)
- **Primary**: `gpt-4o-mini` (via OpenRouter)
- **Fallback**: `openrouter/free`
- **Last resort**: `google/gemma-4-31b-it:free`
- Configurable via `openai_model_chain` env var
- 2 attempts per model; `RateLimitError` → immediate skip
- All fail → return `"{}"` (heuristic values used)
- No API key set → return `"{}"` immediately

### Agent Model Chain (`agent_chat()` for `/api/agents/*`)
- **Primary**: `openrouter/free`
- **Fallback**: `google/gemma-4-31b-it:free`
- Configurable via `agent_model_chain` env var
- Same retry/fallback logic
- `agent_chat_vision()` supports OpenAI-compatible image format (`data:image/...;base64,...`)

### Client
- Uses `AsyncOpenAI` client with `temperature=0` (deterministic output)
- Configurable via `openai_base_url` (default: `https://openrouter.ai/api/v1`)

---

## 9 — Complete API Endpoints

All routes are in `backend/app/main.py` (chat mode) and `backend/app/agents/router.py` (agents mode).

### Chat Mode

| Method | Route | Purpose | When Used |
|--------|-------|---------|-----------|
| POST | `/chat` | Main conversation pipeline | Every user message |
| POST | `/analyze` | Legacy one-shot LLM extraction | Fallback only |
| POST | `/calculate` | Pure timeline math without AI | Debug / manual |
| GET | `/history` | List past conversations | Load sidebar |
| DELETE | `/history/{conversation_id}` | Delete a conversation | User action |
| POST | `/diagram` | Generate draw.io XML | User clicks "View Financial Plan" |
| POST | `/diagram/save` | Save edited diagram XML | User saves in draw.io |
| GET | `/diagram/load` | Load saved diagram | Re-open diagram |
| GET | `/health` | Liveness check | Monitoring |
| GET | `/mujarrad/status` | Check remote storage connection | Debug |

### Agents Mode

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/api/agents/process` | Extract entities from text |
| POST | `/api/agents/upload` | Extract entities from file (image/PDF) |
| GET | `/api/agents/history` | List past agent sessions |
| GET | `/api/agents/files/{file_id}` | Retrieve uploaded file |

---

## 10 — Storage System

**Component**: `backend/app/storage.py` → `MujarradStorage` class

### Dual Persistence Strategy

All data is saved both locally and remotely. Remote is always best-effort.

#### Local Storage
| Data | Path | Format |
|------|------|--------|
| Chat history | `~/.mujarrad-chat/history.json` | JSON array of ChatRecord |
| Agent graphs | `~/.mujarrad-chat/agents/<user_id>.json` | JSON array of graph records |
| Uploaded files | `~/.mujarrad-chat/uploads/<user_id>/<file_id>.<ext>` | Binary files |

#### Remote Storage Spaces

| Slug | API URL | Content |
|------|---------|---------|
| `chat` | `/spaces/chat` | Chat records |
| `example` | `/spaces/example` | Segment nodes (legacy) |
| `graph` | `/spaces/graph` | Diagram XML |
| `roi` | `/spaces/roi` | ROI data (legacy System Builder) |
| `agents` | `/spaces/agents` | Agent graph records |

### History Merge Strategy
1. Load local JSON file
2. Fetch remote records (paginated, 50/page)
3. Local records are primary — remote items supplement missing `session_id`s
4. If remote fetch succeeds → replace local with merged result
5. If remote fetch fails → return local data only

### Auth
| Header | Value |
|--------|-------|
| `X-API-Key` | `mujarrad_public_key` |
| `X-API-Secret` | `mujarrad_secret_key` |

---

## 11 — Session Restoration

**Component**: `main.py` → `_restore_session()`

When a user returns to an existing `conversation_id`:

1. **Fetch** ChatRecords from history for that conversation
2. **Extract** last `FinancialData` and `CalculationResult` from the records
3. **Build** `previous_context` dict with all field values
4. **Set** `question_type = "restore_context"` — asks user "Would you like to restore your previous data?"
5. **Handle answer**:
   - **Yes** → populate all financial fields from `previous_context`, mark complete, re-calculate
   - **No** → start fresh (all fields reset to null)

### State Lifecycle
- State lives in memory (`guided_sessions` dict in `main.py`)
- No cleanup mechanism (in-memory only — for production, use a database)
- On restore, a new `FinancialAgentState` is created and populated from history

---

## 12 — Diagram Generation

**Component**: `backend/app/diagram_generator.py` → `generate_financial_roadmap()`

**Trigger**: User clicks "View Financial Plan" after calculation completes

**Input**: `FinancialData` + `CalculationResult`

**Output**: `mxGraphModel` XML for draw.io

### Layout
- **Canvas**: 1100×850, dark theme background `#070511`
- **Row 1 (Y=45)**: Cash Flow — Income → Expenses → (Extra Income) → Net Savings
- **Row 2 (Y=195)**: Goal Progress — Savings → Debts → Goal → Still Needed → Timeline
- **Connecting edge** from Net Savings down to Still Needed

### Color Scheme
| Element | Color | Hex |
|---------|-------|-----|
| Income | Purple | `#8E3DFF` |
| Expenses | Pink | `#E35CFF` |
| Savings | Light purple | `#C9A4FF` |
| Achievable result | Green | `#27AE60` |
| Unachievable result | Pink | `#E35CFF` |

### Frontend Integration
- Embedded iframe → `https://embed.diagrams.net?embed=1&ui=dark&save=1&proto=json`
- `postMessage` protocol: draw.io sends "init" → frontend replies with XML; user clicks "save" → frontend POSTs to `/diagram/save`
- Origin validation: only `*.diagrams.net`, `*.draw.io`

---

## 13 — Frontend Rendering

**Component**: `frontend/src/main.jsx` + `frontend/src/agents/AgentApp.jsx`

### Chat Mode Components

#### App (root)
- Manages mode switching: `chat` / `agents`
- State: `userId` (localStorage), `conversationId`, `messages`, `history`, `loading`, `pendingYesNo`, `diagramOpen`, etc.
- Persists `userId` via `crypto.randomUUID()` in localStorage

#### Message
- Renders chat bubbles with:
  - **Text** only (during question phase)
  - **Analysis grid** + **result panel** + "View Financial Plan" button (when `is_complete`)
- Analysis grid: up to 7 `Metric` rows in a 5-column layout (responsive → 2 columns at ≤860px)

#### Metric
- Returns null for null/undefined values (hides unmentioned fields)
- Formats numbers with `Intl.NumberFormat` (0 decimals)

#### History Sidebar
- Toggled by hamburger icon
- Groups conversations by `conversation_id`, sorted by latest message
- Each entry: first user message as title
- Long-press (200ms) or right-click → delete confirmation
- Click → restore conversation

#### Yes/No Prompt
- Green-tinted (Yes), red-tinted (No) buttons
- Yes → inline input for value
- No → auto-send "No" to backend

#### Diagram Modal
- Full-screen on mobile (≤860px), 90vw×90vh on desktop
- Spinner during load
- XML held in `useRef` to survive re-renders

### Agents Mode Components

#### AgentApp
- Process tab: text input + file drop zone (image/PDF) + result grid
- Result: entities grouped by type + relationships list + summary
- History sidebar overlay: new session button, X close, click-to-load, hold-to-delete

### Styling
| Variable | Value |
|----------|-------|
| `--bg` | `#070511` |
| `--primary` | `#8E3DFF` |
| `--accent` | `#B56CFF` |
| `--text` | `#F3EEFF` |
| `--text-muted` | `#C9A4FF` |

Responsive breakpoint at 860px. No CSS framework.

---

## 14 — Heuristic + LLM Integration

The two extraction methods (Stage 2 heuristic and Stage 3 LLM) do not operate independently — they form a unified extraction system.

### Priority Rule
- Heuristic results are always kept (regex is deterministic and precise)
- LLM results fill gaps but never override heuristic findings
- If both find a value for the same field: heuristic value wins

### Completeness Bypass
- If heuristic finds all 6 fields: LLM is never called (Stage 3 skipped entirely)
- If heuristic finds some fields: LLM receives only the raw text (not heuristic results), and both results are merged afterward

### Merge Strategy
```python
merged = FinancialData(
    goal=heuristic.goal or llm.goal,
    monthly_income=heuristic.monthly_income or llm.monthly_income,
    monthly_expenses=heuristic.monthly_expenses or llm.monthly_expenses,
    ...
)
```

This ensures deterministic regex results are never lost, while LLM provides intelligent extraction for complex or ambiguous cases.

---

## Summary

| Stage | Component | Cost | Latency | Depends on LLM? |
|-------|-----------|------|---------|-----------------|
| 1. Normalization | `heuristics.py` | Free | <1ms | No |
| 2. Heuristic Extraction | `heuristics.py` | Free | <5ms | No |
| 3. LLM Extraction | `llm_chain.py` + prompts | Free | ~1-3s | Yes |
| 4. State Machine | `financial_agent/pipeline.py` | Free | <1ms | No |
| 5. Calculation | `calculator.py` | Free | <1ms | No |
| 6. Output & Storage | `main.py` + `storage.py` | Free | <1ms (+ async) | No |

All stages are free (using free-tier OpenRouter models). In simple cases where the heuristic covers all fields, Stage 3 is skipped entirely, resulting in <10ms response time.
