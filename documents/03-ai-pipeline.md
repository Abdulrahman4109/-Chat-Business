# AI Pipeline

The extraction pipeline has 5 stages: number extraction → segmentation → LLM extraction (with aggregation) → calculation → background storage.

---

## Stage 1: Number Extraction (`nlp.py`)

**Purpose:** Find all numeric values in text before LLM processing.

**Method:** Two-pass:
1. Regex pattern matching: `(?:[$€£])?\s*\d+(?:,\d{3})*(?:\.\d+)?[kKmM]?`
2. spaCy `like_num` token detection (if spaCy model is loaded)

**Output:** `list[float]` — deduplicated list of all numbers found.

---

## Stage 2: Text Segmentation (`segmenter.py` + LLM #1)

**Purpose:** Split user message into atomic "thought units" for independent analysis.

### Method: Two-tier

#### Tier 1: LLM #1 — `segment_with_llm()`
- Calls GPT-4o-mini with `SEGMENTER_PROMPT` → `{"segments": [...]}`
- Temperature=0, timeout=10s
- Understands Arabic context: knows that و joins separate thoughts

#### Tier 2: Fallback — Regex `segment_text()`
Used when LLM is unavailable or fails.

### Regex Split Rules
- English sentence boundaries: `. ` `! ` `? ` (period + space)
- Arabic sentence boundaries: `؟ ` (Arabic question mark + space)
- Newlines: `\n`
- **Arabic attached-number boundaries**: Insert a break before Arabic connectors (`و`, `ف`, `ب`, `ل`) when preceded by a digit
  - `800000ولدي` → `800000. ولدي` (then splits at `. `)
  - `ادخار20000مرتب50000` → `ادخار20000. مرتب50000`
  - NO splitting inside words: `اسبوعي` stays as `اسبوعي` (not `اسب. وعي`)
- Uses `(\d+)` (full number, not single digit) to prevent number corruption

### Max Segments
- Hard limit: **15 segments**
- Beyond 15: truncated, excess merged into last segment

### Rationale
Earlier experiments used only regex, but Arabic text often lacks clear delimiters. The LLM understands that "دخلي 50000 ومصروفي 10000" are two separate facts joined by و. The regex handles attached numbers while the LLM handles semantic splitting.

---

## Stage 3: LLM Extraction (`openai_service.py`)

**Purpose:** Classify each number into the correct financial field using GPT, with time unit normalization.

### Time Unit Normalization Pipeline

The system normalizes ANY time unit to monthly equivalents:

#### Dictionary Lookup (`extract_time_unit`)
Matches time phrases against `TIME_UNITS` dict with word-boundary regex:
- `hourly`, `per hour`, `بالساعة`, `كل ساعة` → ×171.43
- `daily`, `per day`, `يومياً`, `في اليوم`, `يومي`, `كل يوم` → ×30
- `weekly`, `per week`, `اسبوعياً`, `في الاسبوع`, `كل اسبوع`, `أسبوعي` → ×4.2857
- `biweekly`, `bi-weekly`, `كل اسبوعين`, `كل أسبوعين` → ×2.1429
- `every 10 days`, `كل 10 ايام`, `عشرة ايام` → ×3
- `monthly`, `per month`, `شهرياً`, `في الشهر`, `كل شهر` → ×1
- `semi-monthly`, `semi-monthly`, `نصف شهري`, `مرتين بالشهر` → ×2
- `quarterly`, `كل 3 شهور`, `ربع سنوي` → ×1/3
- `semi-annually`, `كل 6 شهور`, `نصف سنوي` → ×1/6
- `yearly`, `per year`, `سنوياً`, `في السنة`, `كل سنة`, `سنوي`, `كل عام` → ×1/12
- `biennially`, `كل سنتين`, `سنتين`, `كل عامين` → ×1/24
- 25+ Arabic variants including all hamza forms (أسبوع, الأسبوع)

#### General Pattern Matching (`_TIME_GENERAL_PATTERNS`)
For patterns like `كل 2 شهر` or `every 3 months`:
- Extracts the count (e.g. 2, 3)
- Computes multiplier = 1 / count (e.g. `كل 2 شهر` → multiplier 0.5)
- Returns computed value as `__MULT_<float>__` string

#### Value Normalization (`normalize_value`)
1. Parses time unit from text
2. If known unit → multiply by stored multiplier
3. If `__MULT_<float>__` → parse and multiply
4. If no unit → keep as-is (assumed monthly)

### EXTRACTION_PROMPT

See `EXTRACTION_PROMPT` in `openai_service.py`. Key instruction: **"DO NOT copy example values — COMPUTE using the table multiplier."**

### Fallback (`heuristic_extract`)

If LLM is unavailable (no API key or API error):
1. `extract_number_mentions()` — regex finds all number mentions
2. Stores them in `all_numbers` list
3. **No field classification** (LLM is the sole classifier)
4. `apply_intelligent_defaults()` — fills None→0 for calculator math

---

### Aggregation (inside LLM Extraction — `_aggregate_segment_extractions`)

**Purpose:** Merge per-segment extractions into a single `FinancialData` object.

Rules:
- Same field across segments → **sum** values (e.g., two extra_income = 4000 + 2000)
- Multiple `goal_price` values → **take largest** (primary goal)
- Skip extractions with missing field/value/segment_index
- Build `segments[]` list with per-segment classifications

---

## Stage 4: Calculation (`calculator.py`)

After extraction, the calculator computes the timeline:

```python
net_savings = (income or 0) + (extra or 0) - (expenses or 0)
effective_savings = max((savings or 0) - (debts or 0), 0)
remaining = max(goal - effective_savings, 0)
months = ceil(remaining / net_savings)
```

### Edge Cases

| Case | Behavior |
|------|----------|
| No goal | Unachievable, `duration_display: "goal amount not provided"` |
| Already funded (`remaining == 0`) | Months = 0, "already achieved" |
| Negative/zero savings | Unachievable, suggests reducing expenses |
| Achievable | `format_duration(months)` → "5 months", "1 year", "2 years and 3 months" |
| Debts present | `effective_savings = savings - debts` (debts reduce available capital) |

### Suggestions (max 3)
1. Always: "Keep at least {net_savings} per month reserved"
2. If >12 months: "A small income increase or expense reduction can shorten the timeline"
3. If expenses > 60% of income: "Review fixed costs"
4. If multiple goals: "Prioritize one goal at a time"
