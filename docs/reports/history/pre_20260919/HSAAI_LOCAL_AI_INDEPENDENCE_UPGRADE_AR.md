# ترقية HSAAI إلى منصة ذكاء اصطناعي داخلية مستقلة

تمت إضافة تعديلات تجعل المشروع مناسبًا لهدف: لا OpenAI، لا Claude، لا Gemini، لا DeepSeek، ولا أي مزود ذكاء اصطناعي خارجي.

## ما تمت إضافته

1. **Local Model Gateway مطور**
   - الملف: `services/llm_gateway/models.local.json`
   - الملف: `services/llm_gateway/model_router.py`
   - يدعم اختيار النموذج المحلي حسب نوع المهمة والحساسية.

2. **واجهات API جديدة**
   - `GET /v1/models`
   - `POST /v1/models/route`
   - `POST /v1/generate`
   - `POST /v1/stream`

3. **خدمة تدريب داخلية**
   - المسار: `services/model_training/`
   - الهدف: تجهيز datasets وتشغيل مسار Fine-Tuning داخلي لاحقًا عبر LoRA/QLoRA.

4. **صفحة إدارة النماذج المحلية**
   - المسار: `apps/web/app/admin/models/page.tsx`
   - تعرض النماذج المحلية وسياسة Internal Only.

5. **جداول قاعدة البيانات**
   - المسار: `database/migrations/001_ai_models.sql`
   - جداول `ai_models` و `ai_model_routes`.

6. **Docker Compose**
   - تمت إضافة خدمة `model_training` إلى ملف التشغيل الداخلي.

## النماذج المحلية المقترحة

- `qwen2.5:7b-instruct` للغة العربية والسياسات والإجراءات.
- `llama3.1:8b-instruct` للمهام العامة.
- `codellama:7b-instruct` للبرمجة و DevOps.
- `mistral:7b-instruct` للردود السريعة والتلخيص.

## طريقة التشغيل المختصرة

```bash
cp .env.hsa-internal.example .env
docker compose -f docker-compose.hsa-internal.yml up -d --build
```

ثم تحميل النماذج داخل Ollama:

```bash
docker exec -it hsaai_enterprise_ux-local_llm-1 ollama pull qwen2.5:7b-instruct
docker exec -it hsaai_enterprise_ux-local_llm-1 ollama pull llama3.1:8b-instruct
docker exec -it hsaai_enterprise_ux-local_llm-1 ollama pull codellama:7b-instruct
docker exec -it hsaai_enterprise_ux-local_llm-1 ollama pull mistral:7b-instruct
```

## أهم نتيجة

أصبح مسار الذكاء في المشروع كالتالي:

```text
HSAAI
↓
Local LLM Gateway
↓
Model Router
↓
Ollama Local Models
↓
Company Knowledge + Local RAG + Local Training
```

أي أن البيانات لا تخرج إلى مزود خارجي.
