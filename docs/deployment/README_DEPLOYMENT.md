# HSAAI Production Deployment - Ubuntu Server

## 1. المتطلبات
- Ubuntu Server 22.04 أو أحدث
- Docker Engine + Docker Compose Plugin
- 16GB RAM على الأقل للتجربة، ويفضل 32GB عند تشغيل نماذج محلية
- مساحة 80GB+ للنماذج والوثائق والمتجهات

## 2. الإعداد
```bash
cp .env.production.example .env.production
nano .env.production
```
غيّر كلمات المرور وقيم Keycloak واسم النموذج.

## 3. التشغيل الكامل
```bash
chmod +x scripts/deploy-production.sh
./scripts/deploy-production.sh
```

أو يدويًا:
```bash
docker compose --env-file .env.production -f docker-compose.production.yml up --build
```

## 4. الخدمات
- Frontend عبر Nginx: `http://SERVER_IP/`
- API Gateway: `http://SERVER_IP:8080/health`
- Backend مباشر محليًا: `http://127.0.0.1:8000/health`
- Keycloak داخل الشبكة: `http://keycloak:8080`
- Qdrant داخل الشبكة: `http://qdrant:6333`

## 5. إنشاء أدوار Keycloak
داخل Realm باسم `hsaai` أنشئ Realm Roles التالية:
- `hsaai_admin`
- `knowledge_admin`
- `document_reviewer`
- `document_uploader`
- `department_manager`
- `ai_user`
- `auditor`

ثم اربطها بالمستخدمين أو المجموعات. HSAAI يقرأ الأدوار من:
- `realm_access.roles`
- `resource_access.*.roles`

## 6. تجربة Approval Workflow
1. سجّل الدخول بمستخدم لديه `document_uploader`.
2. سجّل وثيقة حساسة عبر `/v1/knowledge-hub/documents/register` مع `sensitivity=confidential`.
3. ستظهر الحالة `pending_review`.
4. سجّل الدخول بمستخدم لديه `document_reviewer` أو `knowledge_admin`.
5. افتح `/admin/knowledge-governance` ثم Approve أو Reject.
6. الوثائق غير المعتمدة لا تظهر في بحث RAG metadata.

## 7. التأكد من حذف Qdrant Vectors
عند تنفيذ:
```bash
DELETE /v1/knowledge-hub/documents/{document_id}
```
سيتم استدعاء Qdrant filter:
```json
{"key":"document_id","match":{"value":"doc_xxx"}}
```
وتسجيل العملية في Audit Trail.

## 8. تقييم النماذج
```bash
python tests/model_quality_tests/run_model_quality_eval.py
cat reports/model_eval_report.md
```
للتقييم الحي:
```bash
EVAL_CALL_LLM=true LLM_GATEWAY_URL=http://localhost:8090 python tests/model_quality_tests/run_model_quality_eval.py
```
