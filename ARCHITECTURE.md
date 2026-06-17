# توثيق مشروع Financial Chat Assistant

## نظرة عامة

تطبيق شات مالي يساعد المستخدم على تحليل أهدافه المالية وحساب المدة اللازمة لتحقيقها. يدخل المستخدم نصاً عادياً (بالعربية أو الإنجليزية) يصف دخله، مصاريفه، مدخراته، وهدفه، فيقوم النظام باستخراج الأرقام وتصنيفها وحساب الجدول الزمني.

---

## 1. مسار البيانات من البداية إلى النهاية

```
  المستخدم
     │
     ▼  يكتب: "اريد شراء عربة 800000 وعندي ادخار 300000..."
     │
┌────┴────────────────────────────────────────────────────┐
│ ❶  استخراج الأرقام الأولي  (NLP)                        │
│    extract_numbers(message) → list[float]               │
│    الأدوات: regex, spaCy (en_core_web_sm)              │
│    الناتج: [800000, 300000, 50000, 10000, 4000, 2000]  │
└─────────────────────────────────────────────────────────┘
     │
     ▼  token_numbers
     │
┌────┴────────────────────────────────────────────────────┐
│ ❷  استخراج البيانات المالية  (Extraction)              │
│    OpenAIExtractionService.extract(message, numbers)    │
│                                                         │
│    ┌─────────────────┐     ┌──────────────────┐        │
│    │    المسار الذكي  │     │  المسار التقليدي  │        │
│    │  OpenAI GPT-4o   │     │  heuristic_extract│        │
│    │ (إن وجد المفتاح) │     │  (دائماً كاحتياطي)│        │
│    └────────┬────────┘     └────────┬─────────┘        │
│             │                       │                   │
│             └────────┬──────────────┘                   │
│                      ▼                                  │
│             merge_extractions(AI, heuristic)            │
│                      │                                  │
│                      ▼                                  │
│             FinancialData                               │
│             {goal_price, monthly_income,                │
│              monthly_expenses, current_savings,         │
│              extra_income, goals, all_numbers}          │
└─────────────────────────────────────────────────────────┘
     │
     ▼  extracted
     │
┌────┴────────────────────────────────────────────────────┐
│ ❸  الحساب المالي  (Calculation)                        │
│    calculate_goal(data) → CalculationResult             │
│                                                         │
│    net = income + extra - expenses                      │
│    remaining = max(goal - savings, 0)                   │
│    months = ceil(remaining / net)                       │
│                                                         │
│    الناتج: {net_monthly_savings, remaining, months,     │
│             duration_display, is_achievable,            │
│             suggestions}                                │
└─────────────────────────────────────────────────────────┘
     │
     ▼  calculation
     │
┌────┴────────────────────────────────────────────────────┐
│ ❹  بناء الرد  (Response)                                │
│    build_assistant_response(calc) → str                 │
│                                                         │
│    • إن كان غير قابل → رسالة توضح السبب                 │
│    • إن كان منجزاً → "Your goal is already funded"      │
│    • إن كان قابلاً → المدة + صافي الادخار + المتبقي    │
└─────────────────────────────────────────────────────────┘
     │
     ▼  assistant_text
     │
┌────┴────────────────────────────────────────────────────┐
│ ❺  الحفظ  (Storage)                                     │
│    MujarradStorage.save_chat_record(record)             │
│                                                         │
│    • محلياً: ~/.mujarrad-chat/history.json (JSON)       │
│    • سحابياً: Mujarrad API (async POST, best-effort)   │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌────┴────────────────────────────────────────────────────┐
│ ❻  العرض  (Frontend)                                    │
│    React + Vite → واجهة مستخدم مظلمة                    │
│    • فقاعة المحادثة (Message component)                 │
│    • جدول تحليل الأرقام (Metric component)              │
│    • لوحة النتيجة (Goal, Income, Expenses, Savings...)  │
│    • الشريط الجانبي (سجل المحادثات)                     │
└─────────────────────────────────────────────────────────┘
     │
     ▼
   المستخدم يرى الرد
```

---

## 2. الأدوات والمكتبات في كل مرحلة

### المرحلة ❶ — استخراج الأرقام (NLP)
| الأداة | الاستخدام |
|--------|-----------|
| `re` (regex) | نمط `(?:[$€£])?\s*\d+(?:,\d{3})*(?:\.\d+)?[kKmM]?` لالتقاط الأرقام |
| `spaCy` (`en_core_web_sm`) | `token.like_num` للكشف عن الأرقام النصية (مثل "five hundred") |
| `normalize_text()` | تحويل الأرقام العربية الهندية (٠-٩, ۰-۹) إلى غربية |
| **ملف**: `backend/app/nlp.py` | |

### المرحلة ❷ — استخراج البيانات المالية (Extraction)

#### المسار التقليدي (heuristic — يعمل دائماً)
| الأداة | الاستخدام |
|--------|-----------|
| `re` | استخراج Mention لكل رقم (قيمة + موقع) |
| `FIELD_KEYWORDS` | 6 قوائم كلمات مفتاحية للـ 6 حقول المالية (goal, income, expenses, savings, extra, assumptions) |
| `_score_context()` | حساب درجة تطابق كل رقم مع كل حقل بناءً على الكلمات القريبة (±42 حرف) |
| `_classify_mention()` | اختيار أفضل حقل لكل رقم (أعلى درجة + أولوية الحقل في حال التساوي) |
| `merge_extractions()` | دمج نتائج AI + heuristic مع تفضيل القيمة الموجودة في `all_numbers` |
| `apply_intelligent_defaults()` | تعبئة القيم الفارغة (None → 0)، إنشاء `goals` من `goal_price` |
| **ملف**: `backend/app/heuristics.py` | |

**نظام التسجيل (الكلمات المفتاحية):**

| الحقل | كلمات عربية (مثال) | كلمات إنجليزية (مثال) |
|-------|-------------------|----------------------|
| `goal_price` | اريد, أريد, شراء, عربة, سيارة, عايز, اشتري, هدف, سعر, قيمة | want to buy, goal, target, car, save for |
| `monthly_income` | راتب, مرتب, شهري, دخلي, قبض | salary, income, earn, take home |
| `monthly_expenses` | مصاريف, مصروف, ايجار, فواتير | expenses, spend, rent, bills |
| `current_savings` | ادخار, مدخرات, عندي, معايا, لدى, لدي | savings, saved, have, bank |
| `extra_income` | حوافز, اضافي, مكافأة, فريلانس | bonus, extra, freelance, side |

#### المسار الذكي (AI — إن وُجد مفتاح OpenAI)
| الأداة | الاستخدام |
|--------|-----------|
| `openai` (AsyncOpenAI) | `gpt-4o-mini` عبر OpenRouter |
| `response_format={"type": "json_object"}` | إجبار GPT على إرجاع JSON صالح |
| `temperature=0` | استقرار في النتائج |
| `timeout=8, max_retries=0` | منع timeout طويل (خاصة لـ Vercel) |
| **ملف**: `backend/app/openai_service.py` | |

### المرحلة ❸ — الحساب المالي (Calculator)
| الأداة | الاستخدام |
|--------|-----------|
| `math.ceil()` | تقريب المدة لأعلى (لا يمكن أن يكون الشهر إلا كاملاً) |
| `format_duration()` | تحويل الشهور إلى نص: "11 months", "2 years and 3 months" |
| `build_suggestions()` | توليد 3 نصائح كحد أقصى (حفظ احتياطي، تحسين الدخل/المصاريف، تحديد أولويات) |
| **ملف**: `backend/app/calculator.py` | |

### المرحلة ❹ — بناء الرد (Response Builder)
| الأداة | الاستخدام |
|--------|-----------|
| قوالب نصية (3 حالات) | • غير قابل للتحقيق • منجَز بالفعل • قابل للتحقيق مع المدة |
| **ملف**: `backend/app/main.py` (`build_assistant_response()`) | |

### المرحلة ❺ — الحفظ والتخزين (Storage)
| الأداة | الاستخدام |
|--------|-----------|
| `json` (محلي) | قراءة/كتابة `~/.mujarrad-chat/history.json` |
| `httpx.AsyncClient` (سحابي) | POST/GET `https://www.mujarrad.com/api/spaces/{slug}/nodes` |
| **ملف**: `backend/app/storage.py` | |

### المرحلة ❻ — واجهة المستخدم (Frontend)
| الأداة | الاستخدام |
|--------|-----------|
| `React 19` | بناء المكونات (App, Message, Metric) |
| `Vite` | بناء وتشغيل مع Proxy → backend (localhost:8001) |
| `lucide-react` | أيقونات (Send, Menu, X) |
| **ملف**: `frontend/src/main.jsx` | |

### البنية التحتية
| الأداة | الاستخدام |
|--------|-----------|
| `FastAPI` (Python) | خادم الـ API (routes: /health, /analyze, /calculate, /chat, /history) |
| `Pydantic` | نماذج البيانات مع التحقق (Validation) |
| `pydantic-settings` | إعدادات البيئة (.env → Settings) |
| `Mangum` | Adaptor لـ Vercel Serverless |
| `Uvicorn` | تشغيل محلي (`uvicorn app.main:app --reload --port 8000`) |

---

## 3. هيكل المشروع

```
chat/
├── ARCHITECTURE.md          ← هذا الملف
├── CLAUDE.md                ← ذاكرة المشروع للمساعد
├── README.md
├── .gitignore
│
├── backend/
│   ├── .env                 ← مفاتيح API (OpenRouter, Mujarrad)
│   ├── requirements.txt     ← fastapi, openai, pydantic, httpx, mangum, spacy
│   ├── vercel.json
│   ├── api/
│   │   └── index.py         ← Mangum handler لـ Vercel
│   ├── tests/
│   │   ├── test_calculator.py    ← 10 اختبارات
│   │   ├── test_heuristics.py    ← 15 اختبارات
│   │   ├── test_models.py        ← 8 اختبارات
│   │   ├── test_nlp.py           ← 10 اختبارات
│   │   └── test_openai_service.py ← 4 اختبارات
│   └── app/
│       ├── __init__.py
│       ├── main.py          ← FastAPI, كل الـ routes
│       ├── models.py        ← Pydantic models
│       ├── config.py        ← Settings (pydantic-settings)
│       ├── nlp.py           ← استخراج الأرقام (regex + spaCy)
│       ├── heuristics.py    ← استخراج تقليدي + تصنيف + دمج
│       ├── openai_service.py ← استخراج ذكي (GPT-4o-mini)
│       ├── calculator.py    ← حساب المدة المالية
│       ├── storage.py       ← حفظ محلي + سحابي (Mujarrad)
│       └── schema.json      ← schema لعقد Mujarrad
│
├── frontend/
│   ├── package.json         ← react, lucide-react, vite
│   ├── vite.config.js       ← Proxy /chat, /history → localhost:8001
│   ├── index.html
│   └── src/
│       ├── main.jsx         ← React (App, Message, Metric)
│       └── styles.css       ← Dark theme
│
└── api/                     ← نسخة مكررة لـ Vercel deployment
```

---

## 4. النماذج (Pydantic Models)

```
ChatRequest
  message: str (1-8000)
  user_id: str (default: "default-user")
  conversation_id: str | None

FinancialData
  goal_price: float | None
  monthly_income: float | None
  monthly_expenses: float | None
  current_savings: float (default 0)
  extra_income: float (default 0)
  goals: list[dict] = []
  all_numbers: list[float] = []
  assumptions: list[str] = []

CalculationResult
  net_monthly_savings: float
  remaining: float
  months: int | None
  raw_months: float | None
  duration_display: str
  is_achievable: bool
  suggestions: list[str]
```

---

## 5. كيفية عمل التصنيف التقليدي (Heuristics)

```
النص: "اريد شراء عربة 800000 وعندي ادخار 300000"
                │
                ▼
    1. normalize_text() ← ترجمة الأرقام العربية
    2. extract_number_mentions() ← regex
                │
                ▼
    لكل رقم:
    ┌──────────────────────────────────────────────
    │ أخذ سياق ±42 حرف حول الرقم
    │ لكل حقل من الحقول الـ6:
    │   البحث عن الكلمات المفتاحية في السياق
    │   حساب score = 80 - المسافة + bonus
    │ اختيار الحقل الأعلى score
    │ (في حال التساوي: goal > income > expenses
    │  > savings > extra)
    └──────────────────────────────────────────────
                │
                ▼
    لو goal_price لم يُحدد والنص يحتوي
    كلمات هدف → أكبر رقم غير مصنف = goal
```

### مثال للتسجيل:
```
"اريد شراء عربة 800000"
                  ▲
    keywords:     │
    "اريد" → score 69 (قبل الرقم بمسافة 11)
    "شراء" → score 74 (قبل الرقم بمسافة 6)
    "عرب"  → score 79 (قبل الرقم بمسافة 1) ← الفائز!
```

---

## 6. معادلات الحساب

```
صافي الادخار الشهري = الدخل + الإضافي - المصاريف
المتبقي = max(الهدف - المدخرات, 0)
المدة (شهور) = ceil(المتبقي / صافي الادخار)
```

مثال من رسالة المستخدم:
```
الهدف:      800,000
المدخرات:   300,000
الدخل:       50,000
المصاريف:    10,000
الإضافي:      6,000
─────────────────────
صافي الادخار:   46,000  (= 50,000 + 6,000 - 10,000)
المتبقي:       500,000  (= 800,000 - 300,000)
المدة:    11 شهراً       (= ceil(500,000 / 46,000))
```

---

## 7. أوامر التشغيل

### Backend
```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
.venv\Scripts\python -m pytest tests -v
```

### Frontend
```powershell
cd frontend
npm run dev   # localhost:5173, proxy → localhost:8001
npm run build
```

---

## 8. مخطط تدفق البيانات (Data Flow Diagram)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            المستخدم (User)                                   │
│                يكتب رسالة: "اريد شراء عربة 800000..."                        │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ❶ NLP Layer (backend/app/nlp.py)                                          │
│ ┌────────────────────────────────────────────────────────────────────────┐ │
│ │ extract_numbers(message)                                              │ │
│ │ │ regex: (?:[$€£])?\s*\d+(?:,\d{3})*(?:\.\d+)?[kKmM]?               │ │
│ │ │ spaCy: token.like_num                                              │ │
│ │ └──────────────────────────┬─────────────────────────────────────────┘ │
│ │                            ▼                                           │
│ │                    token_numbers: list[float]                           │
│ │                    [800000, 300000, 50000, 10000, 4000, 2000]          │
│ └────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ❷ Extraction Layer (backend/app/openai_service.py + heuristics.py)        │
│                                                                           │
│  ┌────────────────────┐          ┌────────────────────────────────────┐   │
│  │  heuristic_extract │          │  OpenAI API (إن وُجد المفتاح)       │   │
│  │  (دائماً)           │          │  GPT-4o-mini → JSON                │   │
│  │                    │          │  مع timeout=8, temperature=0       │   │
│  │  لكل رقم:          │          │  response_format={"type":"json"}   │   │
│  │  • تحديد السياق    │          └──────────────┬─────────────────────┘   │
│  │  • بحث كلمات مفتاح │                         │                         │
│  │  • حساب score      │                         │                         │
│  │  • اختيار أفضل حقل │                         │                         │
│  └────────┬───────────┘          ┌──────────────┘                         │
│           │                      │                                        │
│           └──────────┬───────────┘                                        │
│                      ▼                                                     │
│           merge_extractions(AI, heuristic)                                 │
│           • goal_price من AI (أو fallback إن كان null)                     │
│           • باقي الحقول: max(AI, heuristic) مع تفضيل القيمة في all_numbers │
│                      ▼                                                     │
│              FinancialData (جميع الحقول مصنفة)                              │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ❸ Calculator Layer (backend/app/calculator.py)                            │
│                                                                           │
│  calculate_goal(data)                                                     │
│  │                                                                        │
│  │ net_monthly = income + extra - expenses = 50,000 + 6,000 - 10,000     │
│  │             = 46,000                                                   │
│  │                                                                        │
│  │ remaining = max(goal - savings, 0) = max(800,000 - 300,000, 0)       │
│  │           = 500,000                                                    │
│  │                                                                        │
│  │ months = ceil(500,000 / 46,000) = 11                                  │
│  │                                                                        │
│  │ duration_display = "11 months"                                         │
│  │                                                                        │
│  │ is_achievable = True (بما أن goal موجود و net > 0 و remaining > 0)    │
│  │                                                                        │
│  │ suggestions: ["Keep at least 46,000 per month reserved..."]            │
│  └──────────────────┬─────────────────────────────────────────────────────┘
│                     ▼                                                     │
│             CalculationResult                                             │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ❹ Response Builder (backend/app/main.py)                                  │
│                                                                           │
│  build_assistant_response(calc)                                           │
│  │                                                                        │
│  │ calc.is_achievable = True                                              │
│  │ calc.months = 11 ≠ 0                                                   │
│  │ ↓                                                                      │
│  │ "At your current pace, it will take 11 months.                         │
│  │  Net monthly savings: 46,000.                                          │
│  │  Remaining amount: 500,000.                                            │
│  │  Keep at least 46,000 per month reserved for this goal."               │
│  └──────────────────┬─────────────────────────────────────────────────────┘
│                     ▼                                                     │
│              assistant_text (str)                                          │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ❺ Storage Layer (backend/app/storage.py)                                  │
│                                                                           │
│  MujarradStorage.save_chat_record(record)                                 │
│  │                                                                        │
│  ├──► Local: ~/.mujarrad-chat/history.json (synchronous)                  │
│  │    JSON array of ChatRecord objects                                    │
│  │                                                                        │
│  └──► Cloud: POST https://www.mujarrad.com/api/spaces/chat/nodes          │
│       Headers: X-API-Key, X-API-Secret                                    │
│       (best-effort, لا يمنع الرد عند الفشل)                               │
│                                                                           │
│  get_history(user_id)                                                     │
│  ├──► Local (filtered by user_id)                                         │
│  └──► Cloud GET (paginated, size=50) ← يحدث المحلي إذا نجح                │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ❻ Frontend Layer (frontend/src/main.jsx)                                  │
│                                                                           │
│  ChatResponse ──► React رندِر                                            │
│                                                                           │
│  • Message component: فقاعة الدردشة (user/assistant)                     │
│  • Metric component: عرض كل حقل مالي (label + value)                     │
│  • Analysis Grid: جدول منظم (Goal, Income, Expenses, Savings, Extra)     │
│  • Result Panel: net_monthly_savings, remaining, months, suggestions      │
│  • Sidebar: سجل المحادثات مجمّع بـ conversation_id                       │
│                                                                           │
│  API calls: fetch('/chat', POST) → ChatResponse                           │
│             fetch('/history?user_id=...', GET) → ChatRecord[]             │
│                                                                           │
│  Styling: CSS custom properties (dark theme)                              │
│  --bg: #02000F, --primary: #541288, --accent: #A582B1                    │
└────────────────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                            المستخدم (User)                                 │
│                يرى الرد: "At your current pace, it will take 11 months."   │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. الملخص

```
التدفق الكامل في 6 خطوات:

  Text ─► ❶ NLP (regex + spaCy) ─► أرقام خام
         ─► ❷ Extraction (heuristic ± GPT) ─► FinancialData (مصنفة)
         ─► ❸ Calculator ─► CalculationResult (محسوبة)
         ─► ❹ Response Builder ─► نص الرد
         ─► ❺ Storage (local + cloud) ─► محفوظة
         ─► ❻ Frontend (React) ─► معروضة للمستخدم

كل خطوة لها:
  • ملف مخصص في backend/app/
  • مكتبات وأدوات محددة
  • منطق مستقل (قابل للاختبار)
  • اختبارات في backend/tests/
```
