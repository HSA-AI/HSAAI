# تقرير إضافة Smart Responses Engine إلى منصة HSAAI

تمت إضافة نظام **Smart Responses Engine** كطبقة ذكية قبل استدعاء نموذج الذكاء الاصطناعي.

## ما تم تنفيذه

### Backend - FastAPI
تمت إضافة Module جديد:

`services/backend_core/smart_responses/`

ويحتوي على:

- `models.py` نماذج قاعدة البيانات
- `schemas.py` مخططات Pydantic
- `matcher.py` محرك المطابقة ودعم العربية
- `service.py` منطق الخدمة والـ caching والـ seeding
- `router.py` واجهات API للإدارة والاستيراد والتصدير والتحليلات

### قاعدة البيانات
تمت إضافة الجداول:

- `smart_response_templates`
- `smart_response_logs`

وتعمل تلقائيًا مع `Base.metadata.create_all` عند تشغيل backend.

### ربط المحادثة
تم تعديل endpoint:

`POST /chat`

ليعمل بهذا المسار:

`User Message → Smart Responses Engine → Matched? return template → Not Matched? LLM/RAG`

### أنواع المطابقة
يدعم النظام:

- Exact Match
- Partial Match
- Keyword Match
- Regex Match

### دعم العربية
تمت إضافة normalization للنص العربي:

- إزالة التشكيل
- إزالة التطويل
- توحيد الهمزات
- توحيد الألف المقصورة والياء
- تنظيف علامات الترقيم والمسافات

### Multi-Tenant
كل الردود والـ logs مربوطة بـ:

- `tenant_id`
- `workspace_id`

### API Management
تمت إضافة endpoints:

- `GET /v1/smart-responses`
- `POST /v1/smart-responses`
- `GET /v1/smart-responses/{id}`
- `PUT /v1/smart-responses/{id}`
- `DELETE /v1/smart-responses/{id}`
- `PATCH /v1/smart-responses/{id}/toggle`
- `PATCH /v1/smart-responses/{id}/priority`
- `POST /v1/smart-responses/import/json`
- `POST /v1/smart-responses/import/csv`
- `POST /v1/smart-responses/import/excel`
- `GET /v1/smart-responses/export/json`
- `GET /v1/smart-responses/export/csv`
- `GET /v1/smart-responses/export/excel`
- `GET /v1/smart-responses/analytics`

### Frontend - Next.js
تمت إضافة صفحة إدارية:

`apps/web/app/admin/smart-responses/page.tsx`

وتحتوي على:

- عرض الردود الجاهزة
- إضافة رد
- تعديل رد
- حذف رد
- تفعيل/تعطيل
- Export JSON/CSV/Excel
- مؤشرات Analytics أساسية

كما تمت إضافة API Proxy داخل Next.js:

`apps/web/app/api/smart-responses/`

### الردود الافتراضية
تمت إضافة seed تلقائي للردود:

- greeting
- thanks
- who_are_you
- help
- contact_support
- goodbye

## ملاحظات تشغيل

- أضيفت dependency جديدة: `openpyxl==3.1.5` لدعم Excel import/export.
- في بيئة التطوير، إذا لم يكن نظام التوثيق جاهزًا، شغّل backend مع:

`ALLOW_DEV_RBAC=true`

- صفحة الإدارة الجديدة:

`/admin/smart-responses`
