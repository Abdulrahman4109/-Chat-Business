# AI Pipeline

The extraction pipeline has 4 stages: segmentation → LLM extraction → aggregation → calculation.

---

## Stage 1: Text Segmentation (`segmenter.py`)

**Purpose:** Split user message into atomic "thought units" for independent analysis.

**Method:** Regex-based (not LLM). Arabic-aware.

### Split Rules
- English sentence boundaries: `. ` `! ` `? ` (period + space)
- Arabic sentence boundaries: `؟ ` (Arabic question mark + space)
- Newlines: `\n`
- **Arabic attached-number boundaries**: Insert a break before Arabic connectors (`و`, `ف`, `ب`, `ل`) when preceded by a digit
  - `800000ولدي` → `800000. ولدي` (then splits at `. `)
  - `ادخار20000مرتب50000` → `ادخار20000. مرتب50000`
  - NO splitting inside words: `اسبوعي` stays as `اسبوعي` (not `اسب. وعي`)

### Max Segments
- Hard limit: **15 segments**
- Beyond 15: truncated, excess merged into last segment

### Why not LLM for segmentation?
Earlier experiments used an LLM segmenter, but GPT hallucinated word-internal splits in Arabic (سببوعي → اسب/وعي, حوافز → ح/وافز). The regex segmenter is deterministic and handles Arabic correctly.

---

## Stage 2: Number Extraction (`nlp.py`)

**Purpose:** Find all numeric values in text before LLM processing (for fallback use).

**Method:** Two-pass:
1. Regex pattern matching: `(?:[$€£])?\s*\d+(?:,\d{3})*(?:\.\d+)?[kKmM]?`
2. spaCy `like_num` token detection (if spaCy model is loaded)

**Output:** `list[float]` — deduplicated list of all numbers found.

**Also:** `extract_entities()` uses spaCy NER to find MONEY, DATE, CARDINAL, PERCENT, QUANTITY entities — passed to LLM as hints.

---

## Stage 3: LLM Extraction (`openai_service.py`)

**Purpose:** Classify each number into the correct financial field using GPT.

### Two LLM Calls

#### Call 1: Segmenter (LLM fallback)
**Prompt:** `SEGMENTER_PROMPT` — asks LLM to split the message into segments at natural boundaries.
**Fallback:** If LLM fails/unavailable → regex `segmenter.py`.

#### Call 2: Extractor
**Prompt:** `EXTRACTION_PROMPT` — instructs LLM to:
1. Read each `[index] segment`
2. Extract all numeric values
3. Classify into correct field
4. **Normalize time values to monthly** using the conversion table
5. Return JSON with `segment_index`, `field`, `value`

### Time Normalization Table

| Input Time Unit | Multiplier | Formula |
|----------------|-----------|---------|
| per hour / hourly | × 171.43 | 40h/week × 30/7 days |
| per day / daily | × 30 | 30 days/month |
| per week / weekly | × 4.2857 | 30 ÷ 7 |
| bi-weekly / كل اسبوعين | × 2.1429 | 30 ÷ 14 |
| every 10 days | × 3 | 30 ÷ 10 |
| per month / monthly | × 1 | keep as-is |
| semi-monthly (twice/month) | × 2 | — |
| quarterly | ÷ 3 | ÷ 3 months |
| semi-annually | ÷ 6 | ÷ 6 months |
| yearly / annually | ÷ 12 | ÷ 12 months |
| biennially | ÷ 24 | ÷ 24 months |

Normalize = multiply the stated value by the multiplier to get the monthly equivalent.

### EXTRACTION_PROMPT Examples (~31 organized examples)

Examples in the prompt demonstrate each field × multiple time units. They serve as format reference, with the instruction: **"DO NOT copy example values — COMPUTE using the table multiplier."**

### NER Entity Hints

spaCy NER results appended after segments:
```
NER financial entities detected in text:
- MONEY: "4,000"
- MONEY: "800,000"
- DATE: "per week"
```

The LLM uses these as hints but always verifies against the segment text.

### Fallback (`heuristic_extract`)

If LLM is unavailable (no API key or API error):
1. `extract_number_mentions()` — regex finds all number mentions
2. Stores them in `all_numbers` list
3. **No field classification** (LLM is the sole classifier)
4. `apply_intelligent_defaults()` — fills None→0

---

## Stage 4: Aggregation (`_aggregate_segment_extractions`)

**Purpose:** Merge per-segment extractions into a single `FinancialData` object.

Rules:
- Same field across segments → **sum** values (e.g., two extra_income = 4000 + 2000)
- Multiple `goal_price` values → **take largest** (primary goal)
- Skip extractions with missing field/value/segment_index
- Build `segments[]` list with per-segment classifications

---

## Stage 5: Calculation (`calculator.py`)

After extraction, the calculator computes the timeline:

```python
net_savings = income + extra - expenses
remaining = max(goal - savings, 0)
months = ceil(remaining / net_savings)
```

### Edge Cases

| Case | Behavior |
|------|----------|
| No goal | Unachievable, `duration_display: "goal amount not provided"` |
| Already funded (`remaining == 0`) | Months = 0, "already achieved" |
| Negative/zero savings | Unachievable, suggests reducing expenses |
| Achievable | `format_duration(months)` → "5 months", "1 year", "2 years and 3 months" |

### Suggestions (max 3)
1. Always: "Keep at least {net_savings} per month reserved"
2. If >12 months: "A small income increase or expense reduction can shorten the timeline"
3. If expenses > 60% of income: "Review fixed costs"
4. If multiple goals: "Prioritize one goal at a time"
