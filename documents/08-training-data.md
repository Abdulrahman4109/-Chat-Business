# Fine-Tuning Dataset

## Overview

The script `scripts/generate_training_data.py` generates a JSONL dataset for fine-tuning `gpt-4o-mini` on the financial extraction task.

**Generated file:** `scripts/finetune_data.jsonl`

**Current size:** 317 training examples.

---

## System Message (used in all examples)

```
Extract financial data from text segments. Each segment is numbered [index].
Normalize ALL time values to monthly equivalents:
hourly x171.43, daily x30, weekly x4.2857, bi-weekly x2.1429,
every-10-days x3, semi-monthly x2, quarterly /3, semi-annually /6,
yearly /12, biennially /24.
Monthly or no-unit means keep as-is.
Return JSON: {"extractions": [{"segment_index": 0, "field": "...", "value": 0.0}]}
```

---

## Example Categories

### 1. Static Fields (goal, savings) — 26 examples
- Goal: اريد شراء X, عايز سيارة ب X, i need X, save for X, worth X
- Savings: عندي X في البنك, i have X saved, cash X, saved X

### 2. Time Units × Fields × Language — 234 examples
Generated programmatically: every combination of:
- **Field:** monthly_income, monthly_expenses, extra_income
- **Time unit:** hourly, daily, weekly, bi-weekly, every-10-days, semi-monthly, monthly, quarterly, semi-annual, yearly, biennial
- **Language:** Arabic, English
- **Phrasing:** Multiple templates per unit (e.g., "X per week", "X weekly", "X اسبوعيا", "X اسبوعي")

### 3. Multi-Field (same segment) — 12 examples
- "مرتب 10000 ومصاريف 5000" → income + expenses
- "salary 12000 rent 3000 bonus 1000" → 3 fields in one segment
- Mixed time units: "5000 per week salary 2000 monthly expenses"

### 4. Arabic Attached Numbers — 8 examples
- `ادخار20000` (segmenter splits to [ادخار, 20000])
- `مرتب50000` → segment_index 0, field income, value 50000
- `حوافز4000` → segment_index 1, field extra, value 4000

### 5. Full Complex Messages — 16 examples
Multi-segment inputs covering:
- Arabic classic (goal + savings + weekly income + expenses + extras)
- English classic (goal + savings + weekly income + expenses + bonus)
- **English comma-separated** (the failing case: 800,000 | 20,000 | 4,000 per week → 17143)
- Hourly, daily, weekly, quarterly, semi-annual, biennial mixed

### 6. Edge Cases — 23 examples
- Empty / greeting messages → empty extractions
- Goal-only messages
- Savings-only messages
- Multiple goals (take largest)
- K/M shorthand: 5k → 5000, 1.5m → 1500000
- Arabic text numbers: 5 الاف → 5000, 20 الف → 20000
- Various phrasings: ميزانية, كشف راتب, net pay, take home

### 7. Currency & Commas — 21 examples
- $, €, £ prefixes
- Comma-separated: `10,000` → 10000
- Arabic-Indic digits: `١٠٠٠` → 1000
- Combined: `$3,000 per month`, `$4,000 per week`

### 8. Alternate Arabic Phrasings — 22 examples
- الهدف, التكلفة, المبلغ المطلوب for goal
- الراتب, الدخل, المرتب for income
- المصروفات, الايجار, الفواتير for expenses
- المكافأة, الحوافز, العلاوة for extra
- مدخراتي, في البنك for savings

---

## How to Upload & Fine-Tune

Requires an **OpenAI API key** (`sk-...` without `or-v1`). OpenRouter keys do NOT work with fine-tuning API.

```bash
cd backend
set OPENAI_API_KEY=sk-...
.venv\Scripts\python scripts/generate_training_data.py --upload
```

The script will:
1. Upload JSONL file to OpenAI
2. Create fine-tuning job on `gpt-4o-mini-2024-07-18`
3. Run for 3 epochs
4. Return model ID: `ft:gpt-4o-mini-2024-07-18:...:...`

### Check Status

```python
from openai import OpenAI
client = OpenAI(api_key="sk-...")
print(client.fine_tuning.jobs.list(limit=5))
```

### After Training

Set the fine-tuned model in `.env`:

```
openai_model=ft:gpt-4o-mini-2024-07-18:your-org-name:model-id
```

The EXTRACTION_PROMPT examples can then be stripped to just the system message (the fine-tuned model already knows the task).

---

## Cost Estimate

| Item | Cost |
|------|------|
| Fine-tuning (317 examples × 3 epochs) | ~$5-10 |
| Inference after fine-tuning | Same as gpt-4o-mini (~$0.15/1M input tokens) |

---

## Future Expansion

To add more examples:
1. Edit `scripts/generate_training_data.py`
2. Add new cases to the appropriate generator function
3. Re-run: `python scripts/generate_training_data.py`
4. Re-upload for fine-tuning
