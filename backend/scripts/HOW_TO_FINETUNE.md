# Fine-tuning Guide

## Why
بدل ما نكتب 57 مثال في الـ prompt كل مرة و نضرب كف مع الـ LLM عشان يفهم — ندرّب مودل مخصص يفهم العربي والإنجليزي فوراً من غير prompt ولا examples.

## Steps

### 1. Generate training data
تم: `scripts/finetune_data.jsonl` — 57 مثال (عربي + إنجليزي، كل fields × time units)

### 2. Upload to OpenAI and fine-tune
تحتاج **OpenAI API key** (مش OpenRouter) عشان الـ fine-tuning. نفذ:

```bash
cd backend
set OPENAI_API_KEY=sk-...
.venv\Scripts\python scripts\generate_training_data.py --upload
```

الـ script هيعمل automatically:
- Upload الـ JSONL file
- Create fine-tuning job (gpt-4o-mini, 3 epochs)
- رجعلك model ID زي: `ft:gpt-4o-mini-2024-07-18:...:...`

### 3. Monitor job status
```bash
# شوف الـ status
.venv\Scripts\python -c "
from openai import OpenAI
import os
client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
print(client.fine_tuning.jobs.list(limit=5))
"
```

### 4. Update config
لما الـ job يخلص، حط الـ model ID في `.env`:

```
openai_model=ft:gpt-4o-mini-2024-07-18:your-org-name:model-id
```

### 5. Verify
ابدأ الـ backend و جرب:
```
POST /chat
{"message": "اريد شراء عربة 800000ولدي ادخار20000 مرتب 50000 اسبوعي مصاريف 10000 حوافز 4000"}
```

## Expected results
- **قبل fine-tuning**: محتاج 57 example + instruction في الـ prompt (وزن تقيل)
- **بعد fine-tuning**: نفس الدقة من غير examples — بس system message خفيف

## Cost estimate
- gpt-4o-mini fine-tuning: ~$3-5 لكل 57 مثال
- الاستخدام بعد كده: نفس سعر gpt-4o-mini العادي
