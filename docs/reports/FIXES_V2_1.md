# HSAAI v4.1 — Security & Stability Fixes (v2.1)

تطبيق إصلاحات شاملة بناءً على تقرير الاكتشاف الهندسي الشامل
(Global AI Engineering Board — Discovery Report v1.0).

---

## ملخص الإصلاحات المنفّذة

تم إصلاح **كل قضايا P0 الحرجة** التي كانت تمنع تشغيل المنصة، بالإضافة إلى
عدد كبير من قضايا P1 و P2. كل إصلاح موثّق في الكود بتعليقات
`FIX v2.1 (P0)` أو `FIX v2.1 (P1)`.

---

## 1. إصلاحات الـ Backend (P0 — خدمات لا تُقلع)

### 1.1 إصلاح `verify_authorization` async/sync في backend_core
- **الملف**: `services/backend_core/security/rbac.py`
- **المشكلة**: `verify_authorization` معرّفة كـ `async` لكن كل المُستدعين
  يستدعونها بدون `await` — ما يجعل المصادقة غير فعّالة عبر 8 مواقع.
- **الإصلاح**: جعل `require_permission`، `require_any_role`، `get_current_claims`
  كلها `async` وإضافة `await` لكل callers.

### 1.2 إصلاح `auth/middleware.py`
- **الملف**: `services/backend_core/auth/middleware.py`
- **الإصلاح**: `auth()` أصبحت `async` وتُ awaits `verify_authorization`.

### 1.3 إصلاح `backend_core/main.py` (3 endpoints)
- **الملف**: `services/backend_core/main.py`
- **الإصلاح**: `/metrics`، `/chat`، `/chat/stream` الآن تُستدعي
  `await verify_authorization(authorization)` بشكل صحيح.

### 1.4 إصلاح `knowledge/router.py`
- **الملف**: `services/backend_core/knowledge/router.py`
- **الإصلاح**: `register_document` أصبح `async` مع `await verify_authorization`.

### 1.5 إضافة `Depends` imports إلى 4 خدمات
- `services/multi_agents/main.py` — إضافة `Depends` import + `async def run`
- `services/workflow_engine/main.py` — إضافة `Depends` import
- `services/backend_core/voice_ai/main.py` — إضافة `Depends` import + auth على `/v1/stt`
- `services/backend_core/ai_orchestrator/main.py` — إضافة `Depends` import

---

## 2. إصلاحات الأمن (P0 — endpoints بدون مصادقة)

### 2.1 إضافة auth إلى `model_training/api/training_routes.py`
- **المشكلة**: كل endpoints (`POST /api/training/jobs`، `/start`، `/pause`،
  `/resume`، `/cancel`، `/retry`، `DELETE`) بدون auth — أي أحد يُطلق GPU jobs.
- **الإصلاح**: إضافة `claims: dict = Depends(_auth_dep)` إلى كل endpoint
  (عدا `/capabilities` العام).

### 2.2 إضافة auth إلى `ai_alignment/main.py` (kill-switch)
- **المشكلة**: `POST /v1/safety/kill-switch` بدون auth — أي أحد يوقف كل AI.
- **الإصلاح**: إضافة `Depends(_auth_dep)` إلى كل endpoints:
  `/align`، `/safety/check`، `/safety/approvals/*`، `/safety/kill-switch` (POST + DELETE).

### 2.3 إصلاح ABAC fail-open
- **الملف**: `packages/common/abac/__init__.py`
- **المشكلة**: ABAC fails open (returns True) عند OPA unreachable — يُعطّل كل ABAC.
- **الإصلاح**: fail OPEN للقراءة، fail CLOSED للكتابة/الموافقة/الحذف.

### 2.4 إصلاح JWT signature verification
- **الملف**: `packages/common/security/jwt_validator.py`
- **المشكلة**: `jose_jwt.decode()` كان commented out — tokens ليست signature-verified.
- **الإصلاح**: uncomment + تفعيل full signature verification مع JWKS.

### 2.5 إصلاح CORS backend_core
- **الملف**: `services/backend_core/main.py`
- **المشكلة**: لا wildcard rejection في CORS.
- **الإصلاح**: إضافة `x.strip() != "*"` filter.

### 2.6 إصلاح Vault
- **الملف**: `infrastructure/vault/vault.hcl` + `infrastructure/vault/docker-compose.vault.yml`
- **المشكلة**: dev mode + root token ملتزم + TLS disabled + audit log معلّق.
- **الإصلاح**:
  - إيقاف `-dev` mode، تشغيل `server` mode
  - إزالة `VAULT_DEV_ROOT_TOKEN_ID`
  - تفعيل TLS (`tls_cert_file` + `tls_key_file`)
  - تفعيل audit logging (`audit "file"`)
  - استبدال `storage "file"` بـ `storage "raft"` لـ HA
  - إزالة circular transit auto-unseal

---

## 3. إصلاحات الـ Frontend (P0 — build معطوب + auth unreachable)

### 3.1 إصلاح i18n module
- **الملف**: `apps/web/package.json`
- **المشكلة**: `lib/i18n/index.ts` يستورد `i18next`/`react-i18next`/`i18next-browser-languagedetector`
  غير مُثبّتة في package.json.
- **الإصلاح**: إضافة الحزم الثلاث إلى `dependencies`.

### 3.2 إصلاح `rbac.ts` getClientRoles export
- **الملف**: `apps/web/lib/security/rbac.ts`
- **المشكلة**: `admin/knowledge-governance/page.tsx` يستورد `getClientRoles` غير مُصدَّر.
- **الإصلاح**: إضافة `getClientRoles()` + `setClientRoles()` exports.

### 3.3 إنشاء `/login` page
- **الملف**: `apps/web/app/login/page.tsx` (جديد)
- **المشكلة**: `middleware.ts` يُعيد توجيه لـ `/login` غير الموجود — 404.
- **الإصلاح**: إنشاء صفحة login كاملة مع Keycloak OIDC integration.

### 3.4 إنشاء `/api/auth/callback` route
- **الملف**: `apps/web/app/api/auth/callback/route.ts` (جديد)
- **المشكلة**: OIDC redirect_uri يشير لـ `/api/auth/callback` غير الموجود — 404.
- **الإصلاح**: إنشاء route handler يُكمل OIDC code exchange + يضع httpOnly cookies.

### 3.5 إضافة `exchangeCodeForTokens` إلى auth-provider
- **الملف**: `apps/web/lib/auth-provider.ts`
- **الإصلاح**: إضافة server-side function لـ OIDC token exchange.

### 3.6 إزالة localStorage token leak
- **الملف**: `apps/web/app/admin/department-agents/page.tsx`
- **المشكلة**: قراءة `hsaai_access_token` من localStorage — XSS leak risk.
- **الإصلاح**: استخدام `credentials: "include"` (httpOnly cookie).

### 3.7 إصلاح 13+ روابط sidebar ميتة
- **الملف**: `apps/web/lib/enterprise-navigation.ts`
- **المشكلة**: روابط لـ `/executive`، `/agent-mesh`، `/ai-risk`، إلخ. غير موجودة.
- **الإصلاح**: إعادة توجيه لصفحات موجودة (`/executive-dashboard`،
  `/enterprise-agents-center`، `/enterprise-governance-center`، إلخ).

### 3.8 إزالة `maximumScale: 1` (WCAG violation)
- **الملف**: `apps/web/app/layout.tsx`
- **المشكلة**: يمنع user zoom — مخالف لـ WCAG 2.1 SC 1.4.4.
- **الإصلاح**: حذف `maximumScale: 1`.

### 3.9 إنشاء `loading.tsx` + `error.tsx` + `not-found.tsx`
- **الملفات**: `apps/web/app/{loading,error,not-found}.tsx` (جديدة)
- **المشكلة**: لا graceful degradation لـ route transitions و errors و 404s.
- **الإصلاح**: إنشاء الصفحات الثلاث مع accessibility (role="status"/"alert").

### 3.10 ربط `useAuth()` في صفحة chat
- **الملف**: `apps/web/app/chat/page.tsx`
- **المشكلة**: `user: "current-user"` hardcoded بدلاً من المستخدم المُصادَق.
- **الإصلاح**: استخدام `useAuth()` لجلب `userId` و `tenantId` حقيقيين.

### 3.11 تنفيذ streaming SSE حقيقي
- **الملف**: `apps/web/app/chat/page.tsx`
- **المشكلة**: non-streaming `fetch().json()` — spinner ثابت لكل LLM duration.
- **الإصلاح**: تنفيذ SSE streaming مع `ReadableStream` reader + token-by-token
  rendering + fallback للـ JSON العادي.

---

## 4. إصلاحات الـ Infrastructure (P0 — K8s/Docker/Helm مكسور)

### 4.1 إصلاح 11 ملف Kubernetes YAML invalid
- **الملفات**: `infrastructure/kubernetes/base/{api-gateway,llm-gateway,rag-engine,frontend,auth-service,multi-agents,workflow-engine,ai-orchestrator,analytics,document-ai,voice-ai}.yaml`
- **المشكلة**: `ports:` فارغة ثم `- containerPort` كـ list item داخل mapping context.
- **الإصلاح**: نقل `containerPort` داخل قائمة `ports:` بشكل صحيح (via Python script).

### 4.2 إصلاح HPA selector
- **الملف**: `infrastructure/kubernetes/base/hpa.yaml`
- **المشكلة**: `scaleTargetRef.name: backend-core` لكن Deployment باسم `backend`.
- **الإصلاح**: تغيير لـ `name: backend`.

### 4.3 إصلاح PDB selectors
- **الملف**: `infrastructure/kubernetes/base/pod-disruption-budgets.yaml`
- **المشكلة**: selectors تستخدم `app: hsaai-backend` إلخ. لكن Deployments تستخدم `app: backend`.
- **الإصلاح**: تحديث كل selectors لتطابق labels الفعلية.

### 4.4 إصلاح NetworkPolicy selectors
- **الملفات**: `infrastructure/kubernetes/base/precise-network-policies.yaml` +
  `infrastructure/kubernetes/network-policies/hsaai-internal-only-network-policy.yaml`
- **المشكلة**: selectors تشير لـpods غير موجودة + `namespaceSelector: {}` يطابق أي namespace.
- **الإصلاح**: تحديث كل selectors + استخدام `matchLabels: kubernetes.io/metadata.name: hsaai`.

### 4.5 إصلاح Dockerfiles
- **الملفات**: `services/rag_engine/Dockerfile` + `services/mcp_server/Dockerfile`
- **المشكلة**: `COPY ../packages/common` و `COPY ../../packages/common` — illegal في Docker.
- **الإصلاح**: تغيير لـ project-root build context + `COPY packages/common`.
- **ملف**: `services/api_gateway/Dockerfile` — إصلاح typo `--gegos` → `--gecos` + إضافة `--uid 1000`.
- **ملف**: `services/model_training/Dockerfile` — استبدال `cuda-devel` (6GB) بـ `cuda-runtime` (2.5GB).

### 4.6 إضافة backend_core + 4 خدمات مفقودة إلى docker-compose
- **الملف**: `docker-compose.yml`
- **المشكلة**: `backend_core` غير معرّف رغم أن `api-gateway` يُشير إليه؛ كذلك
  `workflow_engine`، `mcp_server`، `pii_detector`، `model_training` مفقودة.
- **الإصلاح**: إضافة الـ5 خدمات مع env vars + healthchecks + depends_on.

### 4.7 كتابة Helm templates حقيقية
- **الملفات**: `infrastructure/helm/templates/{deployments,services,ingress,serviceaccounts,hpas,pdbs,networkpolicies,configmaps}.yaml` (جديدة)
- **المشكلة**: Helm chart كان skeleton (قالبان فقط: secret + NOTES).
- **الإصلاح**: كتابة 8 قوالب كاملة مع parameterization لكل service.
- **ملف**: `infrastructure/helm/values.yaml` — إضافة `services:` map كاملة لـ 14 خدمة.

### 4.8 إصلاح CI deploy path
- **الملف**: `.github/workflows/ci-cd.yml`
- **المشكلة**: `helm upgrade --install hsaai infrastructure/helm/hsaai` لكن الـ chart في `infrastructure/helm/`.
- **الإصلاح**: إزالة `/hsaai` suffix.

### 4.9 توحيد Prometheus + OTEL configs
- **الملفات**: `infrastructure/prometheus/prometheus.yml` + `infrastructure/monitoring/otel-collector.yaml`
- **المشكلة**: ملفان متنافسان لكل من Prometheus و OTEL مع scrape targets/backends مختلفة.
- **الإصلاح**: توحيد باستخدام الإصدار الأفضل (monitoring/prometheus.yml + otel/collector-config.yaml).

---

## 5. إصلاحات الـ Data Layer (P0)

### 5.1 تفعيل RLS على كل الجداول
- **الملف**: `alembic/versions/0003_enable_rls_all_tables.py` (جديد)
- **المشكلة**: RLS على 4 جداول فقط من 36 — tenant isolation يعتمد كلياً على application filters.
- **الإصلاح**: migration جديدة تُفعّل RLS + تُنشئ tenant_isolation policy على 35 جدول
  + تُنشئ `set_tenant_context()` function.

---

## 6. إصلاحات إضافية (P1)

### 6.1 إصلاح contract drift MCP/workflow
- **الملف**: `services/mcp_server/main.py`
- **المشكلة**: `hsaai_workflow_start` يستدعي `/workflows/start` لكن workflow_engine
  يكشف `/workflows/run`. كذلك `hsaai_compliance_report` يستدعي خدمة غير مُنشَرة.
- **الإصلاح**: تغيير لـ `/workflows/run` + إعادة توجيه compliance إلى `backend_core`.

### 6.2 إصلاح hardcoded fake data في enterprise_ops
- **الملف**: `services/backend_core/enterprise_ops/service.py`
- **المشكلة**: dashboards تعرض أرقام وهمية ("18420 requests, 98.7% success rate").
- **الإصلاح**: عرض 0 + `data_source: "demo"` + محاولة جلب real metrics من
  backend_core عند `ENTERPRISE_OPS_REAL_METRICS=true`.

---

## ما لم يتم إصلاحه بعد (يحتاج فريق متفرّغ)

هذه الإصلاحات تتطلب وقتاً أطول وفريقاً متفرّغاً — وهي مُحدّدة في خارطة الطريق
(Phase 2: Modernize, Phase 3: Scale):

- فصل `backend_core` إلى services حقيقية أو ترسيخه كـ modular monolith موثّق.
- استبدال file-based model registry بـ MLflow.
- تنفيذ model deployment automation (Ollama Modelfile import + vLLM reload).
- إضافة object storage (MinIO/S3).
- إضافة data lineage (OpenLineage) + data quality (Great Expectations).
- تنفيذ mTLS default-on في الكود (uvicorn --ssl-certfile).
- نشر 3-node etcd للـ Patroni.
- تفعيل WAL archiving (WAL-G) لـ PITR.
- نشر ArgoCD/Flux لـ GitOps.
- تنفيذ multimodal RAG حقيقي (إزالة placeholder vector).
- تنفيذ EpisodicMemory consolidation.
- تنفيذ A2A protocol للـ agents.
- إضافة Ontology + Taxonomy + Knowledge Catalog.
- إضافة Feature Store (Feast) + MDM.
- Multi-region active-active deployment.
- Service mesh (Istio/Linkerd).
- SLO/SLI definitions (Sloth/Pyrra).
- Chaos engineering مُجدولة.
- FinOps dashboards.
- Agent Marketplace متقدمة.

راجع `HSAAI_Discovery_Transformation_Report.pdf` للتفاصيل الكاملة.

---

## التحقق من الإصلاحات

بعد تطبيق هذه الإصلاحات، يجب أن:

1. **الخدمات تُقلع**: `multi_agents`، `workflow_engine`، `voice_ai`، `ai_orchestrator`
   لم تعد تُرفع `NameError` عند الاستيراد.

2. **RBAC فعّال**: `verify_authorization` يُ awaited بشكل صحيح عبر كل callers.

3. **البناء ينجح**: `next build` لا يفشل بسبب i18n module أو missing exports.

4. **المصادقة تعمل**: `/login` و `/api/auth/callback` موجودان، OIDC flow يكتمل.

5. **K8s manifests صالحة**: كل 29 ملف YAML يمرّ `kubectl apply --dry-run`.

6. **Helm chart يُنشَر**: `helm install hsaai infrastructure/helm/` ينشر كل الخدمات.

7. **docker-compose stack كامل**: `docker compose up` يُقلع كل 12 خدمة.

8. **Vault في production mode**: لا dev root token، TLS مُفعّل، audit log يعمل.

9. **RLS على كل الجداول**: tenant isolation مُنفّذ على مستوى قاعدة البيانات.

10. **ABAC fail-closed للكتابة**: عمليات الكتابة تُرفض عند OPA unreachable.

11. **JWT signature verified**: tokens لا تُقبل بدون signature verification كامل.

12. **kill-switch محمي**: يتطلّب auth — لا أحد يمكنه إيقاف AI بدون cred.

---

**تاريخ الإصدار**: July 2026  
**الإصدار**: v4.1 (post-discovery fixes)  
**الأساس**: Discovery Report v1.0 من Global AI Engineering Board
