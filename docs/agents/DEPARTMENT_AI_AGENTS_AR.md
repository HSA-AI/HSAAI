# وكلاء الأقسام في HSAAI — Department AI Agents

## الهدف
تحويل HSAAI من مساعد واحد عام إلى طبقة وكلاء مؤسسيين متخصصين، بحيث يتم توجيه سؤال المستخدم تلقائيًا إلى الوكيل المناسب حسب القسم والنية والصلاحية.

## الوكلاء الافتراضيون
- HR Agent: الموارد البشرية.
- Finance Agent: المالية.
- IT Support Agent: تقنية المعلومات والدعم الفني.
- Procurement Agent: المشتريات.
- Legal Agent: الشؤون القانونية والامتثال.
- Operations Agent: العمليات والإجراءات التشغيلية.
- Knowledge Agent: إدارة المعرفة والوثائق.
- Executive Agent: الإدارة التنفيذية والمؤشرات والتقارير.

## آلية العمل
```text
User Message
→ Smart Responses Engine
→ Arabic Intent Detection
→ Department Agent Router
→ RBAC Check
→ Knowledge Scopes Filter
→ RAG + Local Model Router
→ Answer with sources when available
```

## الفائدة المؤسسية
1. دقة أعلى لأن كل وكيل له تعليمات وسياق محدد.
2. تقليل الهلوسة لأن الوكيل يبحث في نطاق معرفة مناسب.
3. احترام الصلاحيات عبر Keycloak Roles.
4. عزل معرفة الأقسام: المالية، الموارد البشرية، التقنية، القانونية، إلخ.
5. إمكانية القياس والتحليل عبر DepartmentAgentRun logs.

## الصلاحيات
تمت إضافة صلاحيات:
- agents:read
- agents:admin

الأدوار:
- hsaai_admin: إدارة كاملة للوكلاء.
- knowledge_admin: إدارة وقراءة الوكلاء.
- ai_user: استخدام الوكلاء المسموحين فقط.
- department_manager: استخدام وكلاء قسمه والتقارير.
- auditor: قراءة وتحليل بدون تعديل.

## APIs
- GET /department-agents
- POST /department-agents
- PATCH /department-agents/{agent_id}
- DELETE /department-agents/{agent_id}
- POST /department-agents/route
- GET /department-agents/analytics

## واجهة الإدارة
تمت إضافة صفحة:

```text
apps/web/app/admin/department-agents/page.tsx
```

تعرض الوكلاء، القسم، الصلاحيات، نطاقات المعرفة، الأولوية، والحالة.
