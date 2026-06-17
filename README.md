# ChatBusiness — Financial Chat Assistant

تطبيق شات مالي ذكي يستخرج الأرقام من النصوص الطبيعية (عربي/إنجليزي)، يحسب الجدول الزمني لتحقيق الأهداف المالية، ويحفظ المحادثات عبر Mujarrad API.

## المميزات

- استخراج الدخل، المصروفات، المدخرات، والأهداف المالية من أي جملة
- حساب المدة اللازمة لتحقيق الهدف (شهور/سنوات)
- يدعم اللغة العربية والإنجليزية
- حفظ المحادثات محليًا (`~/.mujarrad-chat/history.json`) وسحابيًا (Mujarrad)
- واجهة شات مثل ChatGPT مع سجل جانبي

## التقنيات

| الطبقة | التقنية |
|--------|---------|
| Backend | Python FastAPI (port 8000) |
| Frontend | React + Vite (port 5173) |
| AI | OpenRouter (gpt-4o-mini) — OpenAI-compatible |
| NLP | spaCy + Regex |
| Storage | Local JSON + Mujarrad API |

## التشغيل

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

انسخ `backend/.env.example` إلى `backend/.env` وضع المفاتيح المطلوبة:

| المتغير | الشرح |
|---------|-------|
| `OPENAI_API_KEY` | مفتاح OpenRouter (أو OpenAI) |
| `MUJARRAD_PUBLIC_KEY` | public key من `npx mujarrad-cli sdk keygen` |
| `MUJARRAD_SECRET_KEY` | secret key من `npx mujarrad-cli sdk keygen` |

ثم:

```bash
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

تطبق التطبيق على `http://localhost:5173`.

## API Endpoints

| المسار | الوظيفة |
|--------|---------|
| `POST /chat` | إرسال رسالة واستلام رد |
| `GET /history?user_id=xxx` | جلب تاريخ المحادثات |
| `POST /analyze` | تحليل مالي للنص |
| `POST /calculate` | حساب الجدول الزمني |
| `GET /mujarrad/status` | حالة اتصال Mujarrad API |
| `GET /health` | فحص السيرفر |

## Mujarrad Space

المحادثات تنزل تلقائيًا في مساحة Mujarrad. افتح:

```
https://www.mujarrad.com/spaces/chat
```

## الاختبارات

```bash
cd backend
.venv\Scripts\python -m pytest tests -v
```
