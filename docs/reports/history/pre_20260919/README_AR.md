# HSAAI Enterprise AI Operating System

منصة ذكاء اصطناعي مؤسسية داخلية تجمع: AI Chat، RAG، Agent Mesh، Workflow Automation، Human-in-the-Loop، Knowledge Graph، Enterprise Search، Governance، FinOps، Integrations، Observability.

## التشغيل السريع

```bash
python -m pytest -q
cd apps/web
npm install
npm run dev
```

## أهم المسارات
- `/dashboard`
- `/chat`
- `/enterprise-search`
- `/knowledge-hub`
- `/agents`
- `/agent-studio`
- `/workflow-studio`
- `/approvals`
- `/governance-center`
- `/finops`
- `/integrations`
- `/observability`
- `/getting-started`

## ملاحظة إنتاجية
التكاملات مع SAP وSharePoint وActive Directory جاهزة كطبقة إعداد واختبار، لكنها تحتاج بيانات اتصال حقيقية من المؤسسة قبل اعتبارها Production.


---

## Legacy Notes

# HSAAI — منصة الذكاء الاصطناعي المؤسسي الداخلي

تمت إعادة ترتيب هذا المستودع وفق بنية عالمية مناسبة للمشاريع المؤسسية الكبرى:

- `apps/web`: واجهة المستخدم.
- `services`: الخدمات الخلفية المستقلة.
- `packages`: الحزم المشتركة، التكاملات، والحوكمة.
- `infrastructure`: Docker وKubernetes وHelm وKeycloak والمراقبة.
- `docs`: التوثيق الرسمي والكتب والملاحق.
- `tests`: اختبارات الوحدة، التكامل، الأمن، E2E، والضغط.

## التشغيل الداخلي

```bash
cp .env.hsa-internal.example .env.hsa-internal
make internal
```

## فحص البنية

```bash
make validate
```

## HSAAI Hybrid AI Architecture

تمت إضافة مسار تطبيقي يدعم:

- Smart Responses Engine قبل استدعاء النموذج.
- Arabic Intent Detection لاكتشاف نية المستخدم عربيًا.
- RAG/Enterprise Knowledge Base عبر محرك المعرفة الحالي.
- Hybrid Model Router لتوجيه الطلبات إلى Qwen/Llama/Mistral محليًا عبر Ollama.
- خيار خارجي اختياري مغلق افتراضيًا ولا يعمل إلا عند تعطيل Internal-Only Mode.

راجع الملف:

```text
HYBRID_AI_IMPLEMENTATION_AR.md
```


## آخر ترقية: Enterprise Operations Centers

تمت إضافة مراكز تشغيل مؤسسية جديدة: Agent Control Center، Workflow Center فعلي، Integrations Monitoring، Executive Dashboard، وAI Operations Analytics. راجع التقرير: `HSAAI_ENTERPRISE_OPERATIONS_CENTERS_UPGRADE_AR.md`.
