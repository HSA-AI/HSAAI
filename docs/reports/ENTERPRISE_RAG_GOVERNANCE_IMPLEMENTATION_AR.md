# تقرير تنفيذ تطوير Enterprise RAG Governance في HSAAI

تم تطوير النسخة السابقة من HSAAI بإضافة طبقة أقوى لإدارة المعرفة المؤسسية، بحيث يصبح نظام RAG أكثر قربًا من متطلبات الإنتاج المؤسسي.

## ما تم إضافته

### 1. Document Governance
تمت إضافة خصائص حوكمة لكل وثيقة عند الرفع:

- `visibility`: workspace / public / restricted
- `allowed_roles`: أدوار مسموحة مثل finance, hr, it
- `allowed_users`: مستخدمون محددون
- `classification`: تصنيف الوثيقة مثل internal / confidential / public
- `tags`: وسوم للوثيقة

### 2. Knowledge ACL
تمت إضافة دالة صلاحيات داخل RAG Engine تمنع ظهور الوثائق غير المسموح بها في نتائج البحث.

التدفق الجديد:

```text
Upload Document
→ Extract Text / OCR
→ Chunking
→ Embeddings
→ Store ACL + Classification + Tags
→ Search
→ Tenant Filter
→ Workspace Filter
→ ACL Filter
→ Return Allowed Sources Only
```

### 3. إدارة الوثائق
تمت إضافة APIs جديدة:

```text
POST   /v1/rag/documents
DELETE /v1/rag/documents/{doc_id}
POST   /v1/rag/analytics
```

وفي RAG Engine:

```text
POST   /v1/documents
GET    /v1/documents/{doc_id}
DELETE /v1/documents/{doc_id}
POST   /v1/analytics
```

### 4. Analytics للمعرفة
تمت إضافة تسجيل أحداث داخلي لمعرفة:

- عدد الوثائق
- عدد المقاطع Chunks
- عدد عمليات الرفع
- عدد عمليات البحث
- عدد الإجابات
- نسبة تغطية المصادر
- أكثر الوثائق استخدامًا
- آخر الأحداث

### 5. تطوير واجهة Knowledge Page
تم تحديث صفحة المعرفة لإضافة:

- اختيار مستوى ظهور الوثيقة
- إدخال تصنيف الوثيقة
- إدخال الأدوار المسموحة
- عرض Document Governance
- حذف الوثائق
- عرض RAG Governance Analytics

### 6. تحسين مسار Upload
تم توحيد المسار بحيث يدعم:

```text
/v1/rag/upload
/v1/rag/documents/upload
```

مع تمرير بيانات الحوكمة إلى RAG Engine.

## الملفات التي تم تعديلها

```text
services/rag_engine/main.py
services/backend_core/rag/proxy_router.py
apps/web/services/rag.service.ts
apps/web/app/knowledge/page.tsx
```

## ملاحظات مهمة

- الصلاحيات الحالية تعمل كطبقة منطقية داخل RAG Engine.
- في بيئة الإنتاج يفضل ربط `user_roles` و `user_id` مباشرة من JWT/Keycloak بدل إدخالها يدويًا.
- حذف الوثائق في هذه النسخة يتم كـ Logical Delete للذاكرة الداخلية. في بيئة Qdrant الإنتاجية يمكن توسيعه إلى حذف فعلي بالنقاط المرتبطة بـ `doc_id`.
- تم فحص ملفات Python المعدلة عبر `py_compile` بنجاح.

## المرحلة التالية المقترحة

الخطوة التالية الأفضل:

1. ربط ACL مع Keycloak Roles تلقائيًا.
2. إضافة صفحة Admin Knowledge Governance مستقلة.
3. إضافة Approval Workflow قبل اعتماد الوثائق الحساسة.
4. إضافة No-Answer Review Queue للأسئلة التي لم تجد مصادر.
5. إضافة Evaluation Dataset لمقارنة جودة Qwen / Llama / Mistral على أسئلة المؤسسة.
