# سجل بناء المشروع — Financial Chat Assistant

## 1. إنشاء المشروع الأساسي

```
mkdir chat && cd chat
```

### Backend — Python FastAPI

```
mkdir backend && cd backend
python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn httpx pydantic pydantic-settings python-dotenv openai spacy
python -m spacy download en_core_web_sm
pip install pytest pytest-asyncio
```

إنشاء هيكل الملفات:
```
backend/
├── .env
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI routes
│   ├── config.py         # Settings from .env
│   ├── models.py         # Pydantic models
│   ├── storage.py        # Local JSON + Mujarrad API
│   ├── openai_service.py  # OpenRouter client
│   ├── heuristics.py      # Rule-based extraction (fallback)
│   ├── calculator.py      # Goal timeline calculator
│   └── nlp.py             # Number extraction (spaCy + regex)
├── tests/
│   ├── test_calculator.py
│   ├── test_heuristics.py
│   ├── test_models.py
│   └── test_nlp.py
└── schema.json
```

### Frontend — React + Vite

```
cd .. && mkdir frontend && cd frontend
npm create vite@latest . -- --template react
npm install
npm install lucide-react
```

إنشاء ملف `.env`:
```
VITE_API_BASE_URL=http://localhost:8000
```

---

## 2. تشغيل المشروع

### تشغيل الباك إند
```
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

### تشغيل الفرونت إند
```
cd frontend
npm run dev
```

---

## 3. ربط Mujarrad API

### التسجيل وإنشاء مفاتيح API

```
npx mujarrad-cli auth login
# Email: gabdo4109@gmail.com
# Password: ********
npx mujarrad-cli sdk keygen --name "chat-app"
```

النتيجة:
```
Public Key:  pk_live_1L89OgCW86H5bWpoYmvDAofRi8kbHus6
Secret Key:  sk_live_ygJ09HeVFGgy9N1c7YDR069SNw4Pf9nb3JAe6AVBOFVgJ__98WcQgCiNjRMCN-EP
```

إضافة المتغيرات إلى `backend/.env`:
```
MUJARRAD_PUBLIC_KEY=pk_live_1L89OgCW86H5bWpoYmvDAofRi8kbHus6
MUJARRAD_SECRET_KEY=sk_live_ygJ09HeVFGgy9N1c7YDR069SNw4Pf9nb3JAe6AVBOFVgJ__98WcQgCiNjRMCN-EP
MUJARRAD_API_BASE=https://www.mujarrad.com/api
MUJARRAD_SPACE_URL=https://www.mujarrad.com/spaces/chat
```

### اختبار الاتصال بمتغيرات البيئة

```
curl http://localhost:8000/mujarrad/status
# {"connected":true,"space":"chat","api":"https://www.mujarrad.com/api"}
```

### اختبار إرسال شات (يدوي)

```
curl -X POST http://localhost:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"I want to buy a 40000 car. I earn 6500 monthly, spend 4200, have 8000 saved.\",\"user_id\":\"test-user\",\"conversation_id\":\"test-conv\"}"
```

الرد:
```json
{
  "conversation_id": "test-conv",
  "assistant_message": {
    "content": "...",
    "extracted_data": { ... },
    "calculation": { ... }
  }
}
```

التحقق من حفظ البيانات في Mujarrad:
```
curl -H "X-API-Key: pk_live_..." -H "X-API-Secret: sk_live_..." ^
  "https://www.mujarrad.com/api/spaces/chat/nodes?size=10"
```

---

## 4. المشاكل اللي واجهتنا والحلول

### مشكلة 1: OpenRouter key كانت مضبوطة غلط
- **المشكلة**: حطينا Mujarrad secret key في `OPENAI_API_KEY` بالغلط
- **الحل**: فصلنا المتغيرات — `OPENAI_API_KEY` للـ AI و `MUJARRAD_SECRET_KEY` للـ API

### مشكلة 2: الاتصال بـ Mujarrad API بيرفض المفاتيح
- **المشكلة**: `401 Invalid secret key`
- **السبب**: المفاتيح القديمة كانت غير صالحة (اتعملت قبل التسجيل)
- **الحل**: سجلنا دخول بـ `npx mujarrad-cli auth login` وبعدين عملنا `npx mujarrad-cli sdk keygen --name "chat-app"` وجابنا مفاتيح جديدة شغالة

### مشكلة 3: API base URL غلط
- **المشكلة**: `MUJARRAD_API_BASE` كانت `https://www.mujarrad.com/settings`
- **الحل**: غيرناها لـ `https://www.mujarrad.com/api` (دا endpoint الباك إند يستخدمه مش بتفتحه في المتصفح)

### مشكلة 4: Storage code بيقرا الـ response غلط
- **المشكلة**: `get_history` كان بيستخدم `data.get("data", [])` بس الـ API بيرجع `{"content": [...]}`
- **الحل**: غيرناها لـ `data.get("content", [])`

### مشكلة 5: POST body ناقص
- **المشكلة**: كنا بنبعت `{"nodeDetails": ...}` بس الـ API محتاج `title` + `nodeType` + `nodeDetails`
- **الحل**: ضبطنا الـ payload في `storage.py` عشان يبقى `{"title": "chat-xxx", "nodeType": "REGULAR", "nodeDetails": ...}`

### مشكلة 6: History attribute error
- **المشكلة**: `r.conversation_id` → AttributeError (لأن `r` كانت dict مش object)
- **الحل**: ضبطنا الوصول للـ key

### مشكلة 7: Sidebar غير مرتب
- **المشكلة**: تاريخ المحادثات مش مرتب حسب الأحدث
- **الحل**: ضفنا sorting في الفرونت إند

---

## 5. التنظيف قبل الـ Push

### ملفات اتمسحت
```
.history/               # نسخ احتياطية قديمة
.pytest_cache/          # cache الاختبارات
backend/.pytest_cache/
frontend/dist/          # build output
backend/.env.example    # (اتدمج مع .env)
frontend/.env.example   # (اتمسح)
backend/app/mujarrad_bridge.py  # (كان unused)
backend/.history/       # old .env backups
```

### ملفات أضيفت لـ .gitignore
```
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.env
node_modules/
dist/
.DS_Store
Thumbs.db
.claude/
.history/
CLAUDE.md
```

---

## 6. تشغيل الاختبارات

```
cd backend
.venv\Scripts\python -m pytest tests -v
# 45 tests passed
```

---

## 7. هيكل المشروع النهائي

```
chat/
├── .gitignore
├── BUILD_LOG.md
├── README.md
├── CLAUDE.md              # (مهمل في git)
├── backend/
│   ├── .env               # (مهمل في git)
│   ├── requirements.txt
│   ├── schema.json
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── storage.py
│   │   ├── openai_service.py
│   │   ├── heuristics.py
│   │   ├── calculator.py
│   │   └── nlp.py
│   └── tests/
│       ├── test_calculator.py
│       ├── test_heuristics.py
│       ├── test_models.py
│       └── test_nlp.py
└── frontend/
    ├── .env
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── src/
    │   ├── main.jsx
    │   └── styles.css
    └── node_modules/       # (مهمل في git)
```
