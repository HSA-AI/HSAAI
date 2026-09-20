# تقرير تطبيق البنية الهجينة في HSAAI

تمت إضافة طبقة تطبيقية أولى للبنية التالية:

```text
User Message
→ Smart Responses Engine
→ Arabic Intent Detection
→ Enterprise Knowledge Base / RAG
→ AI Orchestrator
→ Hybrid Model Router
→ Local Ollama Model أو External Optional Model
```

## ما تم تنفيذه

### 1) Smart Responses Engine
الميزة موجودة ومربوطة فعليًا قبل استدعاء نموذج الذكاء الاصطناعي في endpoint:

```text
POST /chat
```

إذا تطابق السؤال مع رد جاهز، يرجع النظام الرد مباشرة بدون استدعاء LLM.

### 2) Arabic Intent Detection
تمت إضافة وحدة جديدة:

```text
services/backend_core/intent_detection/
```

وتحتوي على:

- `service.py`: تطبيع عربي، اكتشاف النية، حساب score.
- `router.py`: API لاكتشاف النية.

Endpoint الجديد:

```text
POST /v1/intent/detect
```

مثال request:

```json
{
  "message": "أريد تقرير عن المبيعات"
}
```

مثال response:

```json
{
  "intent": "generate_report",
  "score": 0.82,
  "matched_terms": ["تقرير"],
  "language": "ar"
}
```

### 3) ربط Intent Detection بالمحادثة
تم تعديل:

```text
services/backend_core/core/engine.py
```

بحيث يتم اكتشاف النية قبل اختيار الوكيل agent، ثم تمرير task إلى AI Orchestrator وLLM Gateway.

### 4) Hybrid Model Router
تم تحديث:

```text
services/llm_gateway/model_router.py
services/llm_gateway/main.py
services/llm_gateway/models.local.json
```

الافتراضي الآن:

```text
qwen3:8b
```

والنماذج المحلية المسجلة:

- `qwen3:8b` للعربية والمعرفة المؤسسية.
- `llama3.1:8b-instruct` للمهام العامة.
- `mistral:7b-instruct` للردود السريعة.
- `codellama:7b-instruct` للبرمجة.

### 5) خيار خارجي اختياري
تمت إضافة دعم اختياري لمزودات خارجية، لكنه مغلق افتراضيًا للحفاظ على الخصوصية.

لا يعمل المزود الخارجي إلا عند ضبط:

```env
INTERNAL_ONLY_MODE=false
ALLOW_EXTERNAL_AI=true
```

ومع ذلك، التوجيه الخارجي لا يتم إلا مع حساسية منخفضة:

```text
public / low / non_sensitive
```

المزودات الاختيارية المدعومة في الكود:

- OpenAI
- Anthropic
- Gemini

### 6) APIs لإدارة النماذج
تمت إضافة proxy endpoints في backend:

```text
GET  /v1/llm/models
POST /v1/llm/route
POST /v1/llm/generate
POST /v1/llm/stream
```

### 7) Scripts لتحميل النماذج المحلية
تمت إضافة:

```text
scripts/bootstrap_ollama_models.sh
scripts/bootstrap_ollama_models_windows.bat
```

لتنزيل:

```text
qwen3:8b
llama3.1:8b-instruct
mistral:7b-instruct
```

## طريقة التشغيل المختصرة

### 1) تشغيل الخدمات

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

### 2) تنزيل النماذج داخل Ollama

Linux/Mac:

```bash
./scripts/bootstrap_ollama_models.sh
```

Windows:

```bat
scripts\bootstrap_ollama_models_windows.bat
```

### 3) اختبار Smart Responses

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin" \
  -d '{"user":"demo","message":"السلام عليكم","workspace_id":"default"}'
```

### 4) اختبار Intent Detection

```bash
curl -X POST http://localhost:8000/v1/intent/detect \
  -H "Content-Type: application/json" \
  -d '{"message":"أريد تقرير عن المبيعات"}'
```

### 5) اختبار Model Router

```bash
curl -X POST http://localhost:8000/v1/llm/route \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin" \
  -d '{"prompt":"حلل سياسة الموارد البشرية","task":"knowledge_search","sensitivity":"internal"}'
```

## ملاحظات إنتاجية مهمة

- لا تبدأ Fine-Tuning الآن.
- الأفضل تشغيل: Smart Responses + RAG + Qwen أولًا.
- اجمع أسئلة وإجابات المؤسسة لمدة كافية.
- بعد ذلك جهّز Dataset معتمد لعمل Fine-Tuning عربي.
- لا ترسل بيانات سرية لأي API خارجي إلا بقرار حوكمة واضح.
