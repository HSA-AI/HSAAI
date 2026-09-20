# HSAAI Enterprise Integration Upgrade

تمت إضافة إطار تكاملات مؤسسي موحد يربط HSAAI بأنظمة الشركة الأساسية بطريقة آمنة وقابلة للتوسع والتدقيق.

## الأنظمة المدعومة

- SAP S/4HANA: المشتريات، المخزون، المبيعات، المالية، العمليات.
- SAP SuccessFactors: بيانات الموظفين، الإجازات، الهيكل التنظيمي، الحضور، الوظائف.
- Active Directory: مزامنة المستخدمين والمجموعات وربطها بـ Keycloak Roles.
- Exchange / Outlook: البريد، التقويم، الاجتماعات، سلاسل البريد.
- SharePoint: فهرسة الوثائق وإدخالها إلى RAG.
- Power BI: قراءة التقارير والـ Dashboards والـ Datasets.
- Jira: المشاريع، التذاكر، Epics، Sprints.
- Service Desk: تذاكر الدعم، التصنيف، التصعيد، SLA.
- DMS: البحث، التلخيص، التصنيف، النسخ، الموافقات.
- Data Warehouse: استعلامات تحليلية Read Only مع منع أوامر UPDATE/DELETE/DROP/ALTER.

## واجهات API

- `GET /v1/enterprise-integrations/overview`
- `GET /v1/enterprise-integrations/supported`
- `GET /v1/enterprise-integrations/connectors`
- `PUT /v1/enterprise-integrations/connectors`
- `POST /v1/enterprise-integrations/connectors/{key}/test`
- `POST /v1/enterprise-integrations/connectors/{key}/fetch`
- `POST /v1/enterprise-integrations/connectors/{key}/sync`
- `GET /v1/enterprise-integrations/agents/{agent_key}/data-sources`
- `GET /v1/enterprise-integrations/workflows/{template_key}/connectors`
- `GET /v1/enterprise-integrations/audit-logs`

## الأمان

- Read Only افتراضيًا.
- أسرار الاتصال لا تحفظ كنص صريح، بل عبر `credentials_ref`.
- كل عملية Fetch/Test/Sync تسجل في Audit Log.
- دعم Tenant/Workspace Isolation.
- التكامل مع Keycloak RBAC عبر صلاحيات `connectors:read`, `connectors:admin`, `connectors:sync`.
- Data Warehouse يمنع أوامر الكتابة والحذف والتغيير.

## ربط الوكلاء بالأنظمة

- HR Agent: SuccessFactors + SharePoint + DMS.
- Finance Agent: SAP S/4HANA + Power BI + Data Warehouse.
- IT Agent: Active Directory + Jira + Service Desk + Outlook.
- Knowledge Agent: SharePoint + DMS + Knowledge Base.
- Executive Agent: SAP + Power BI + Data Warehouse.

## ملاحظة إنتاجية

الملفات الحالية تضيف طبقة العقود والواجهات والتدقيق والأمان. لتفعيل الاتصال الحقيقي يجب إدخال endpoints وcredentials references الخاصة بالشركة، ثم تشغيل اختبارات الاتصال من واجهة Enterprise Integrations.
