# Fine-tuning Guide

## Why

Instead of writing 57 examples in the prompt every time and wrestling with the LLM to understand — we train a dedicated model that understands Arabic and English immediately without prompts or examples.

## Steps

### 1. Generate training data

Done: `scripts/finetune_data.jsonl` — 57 examples (Arabic + English, all fields x time units)

### 2. Upload to OpenAI and fine-tune

You need an **OpenAI API key** (not OpenRouter) for fine-tuning. Run:

```bash
cd backend
set OPENAI_API_KEY=sk-...
.venv\Scripts\python scripts\generate_training_data.py --upload
```

The script automatically:
- Uploads the JSONL file
- Creates a fine-tuning job (gpt-4o-mini, 3 epochs)
- Returns model ID like: `ft:gpt-4o-mini-2024-07-18:...:...`

### 3. Monitor job status

```bash
.venv\Scripts\python -c "
from openai import OpenAI
import os
client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
print(client.fine_tuning.jobs.list(limit=5))
"
```

### 4. Update config

Once the job finishes, set the model ID in `.env`:

```
openai_model=ft:gpt-4o-mini-2024-07-18:your-org-name:model-id
```

### 5. Verify

Start the backend and test:

```
POST /chat
{"message": "اريد شراء عربة 800000ولدي ادخار20000 مرتب 50000 اسبوعي مصاريف 10000 حوافز 4000"}
```

## Expected results

- **Before fine-tuning**: Needs 57 examples + instruction in the prompt (heavy weight)
- **After fine-tuning**: Same accuracy without examples — just a light system message

## Cost estimate

- gpt-4o-mini fine-tuning: ~$3-5 per 57 examples
- Usage after: same price as regular gpt-4o-mini
