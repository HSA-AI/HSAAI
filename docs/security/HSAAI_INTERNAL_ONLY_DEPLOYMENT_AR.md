# HSAAI — نسخة داخلية بالكامل لمجموعة هائل سعيد أنعم

هذا الملف يشرح نمط تشغيل HSAAI كمنصة محادثة شبيهة بـ ChatGPT لكن داخلية بالكامل داخل بنية الشركة. الهدف الأساسي: **لا يتم إرسال أي محادثة، مستند، Embedding، Prompt، Token، سجل تدقيق، أو بيانات موظفين إلى أي خدمة خارج الشركة**.

## 1. مبدأ التشغيل

المنصة تعمل بهذا المسار:

```text
مستخدم داخلي عبر المتصفح
→ Frontend على شبكة الشركة
→ API Gateway داخلي
→ Backend داخلي
→ RAG Engine داخلي + Qdrant داخلي
→ AI Orchestrator داخلي
→ LLM Gateway داخلي
→ Ollama / نموذج محلي داخل خوادم الشركة
```

لا يوجد اتصال تشغيلي مع:

```text
OpenAI
Anthropic
Google AI
Mistral
Cohere
Pinecone
Sentry خارجي
أي Vector DB سحابي
أي LLM API خارجي
```

## 2. ملفات التشغيل الداخلية

استخدم الملفات التالية:

```bash
cp .env.hsa-internal.example .env.hsa-internal
# عدّل القيم السرية داخل .env.hsa-internal
python scripts/verify_internal_only.py
docker compose --env-file .env.hsa-internal -f docker-compose.hsa-internal.yml up --build
```

## 3. أهم إعدادات الحماية

يجب أن تبقى هذه القيم كما يلي:

```env
INTERNAL_ONLY_MODE=true
ALLOW_EXTERNAL_APIS=false
ALLOW_EXTERNAL_AI=false
STRICT_EGRESS_DENY=true
AUTH_REQUIRED=true
ALLOW_DEV_AUTH=false
ALLOW_DEV_RBAC=false
```

أي تغيير لهذه القيم يعني أن المنصة لم تعد تعمل في الوضع الداخلي الصارم.

## 4. النموذج اللغوي المحلي

النموذج المستخدم افتراضيًا عبر Ollama:

```env
LOCAL_LLM_PROVIDER=ollama
LOCAL_LLM_MODEL=llama3.1:8b-instruct
OLLAMA_BASE_URL=http://local_llm:11434
```

يمكن استبداله بنموذج داخلي آخر بشرط أن يكون داخل شبكة الشركة، مثل:

```text
Qwen
Llama
Mistral open-weight deployed locally
Jais Arabic model deployed locally
```

المهم ألا يكون endpoint النموذج خارج الشركة.

## 5. عزل الشبكة

في Docker Compose الداخلي:

- `hsaai_private` شبكة داخلية فقط `internal: true`.
- لا يتم كشف قواعد البيانات أو Qdrant أو LLM أو RAG أو Backend على الإنترنت.
- يتم كشف Frontend و API Gateway فقط على عنوان intranet المحدد عبر `INTRANET_BIND_IP`.

في Kubernetes:

- استخدم `default-deny-egress`.
- اسمح فقط بحركة المرور داخل namespace الخاص بالمنصة.
- اربط Ingress على شبكة الشركة فقط، وليس Public Internet.

## 6. المستندات والذاكرة

كل الملفات المرفوعة تبقى داخل:

```text
storage/local_uploads
qdrant_data
postgres_data
storage/audit_logs
```

ولا يتم إرسالها إلى أي OCR أو Vector DB أو LLM خارجي.

## 7. التحقق قبل التشغيل

نفّذ:

```bash
python scripts/verify_internal_only.py
```

هذا السكربت يفشل إذا وجد:

- مفاتيح OpenAI/Anthropic/Google/Mistral/Cohere/Pinecone.
- إعداد `ALLOW_EXTERNAL_APIS=true` أو `ALLOW_EXTERNAL_AI=true`.
- روابط تشغيلية خارجية في ملفات النشر الداخلية.

## 8. الربط مع أنظمة الشركة

يتم الربط لاحقًا فقط عبر شبكة الشركة:

```text
HR System داخلي
ERP / Finance داخلي
KPI Dashboard داخلي
Document Management داخلي
Active Directory / Keycloak داخلي
```

ولا يجب استخدام Webhooks أو SaaS Connectors خارجية إلا إذا تمت الموافقة عليها رسميًا وخرجت من وضع Internal-Only الصارم.

## 9. قاعدة ذهبية

إذا كان أي جزء من الطلب يحتاج الخروج إلى الإنترنت لإجابة المستخدم، يجب أن يرفض النظام ذلك أو يطلب إدخال المصدر داخليًا عبر RAG.

الصياغة المناسبة داخل النظام:

```text
لا أستطيع استخدام مصادر خارجية في الوضع الداخلي. ارفع المستند أو اربط مصدرًا داخليًا معتمدًا حتى أجيب بناءً عليه.
```
