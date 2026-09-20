# HSAAI — Quick Start (v3.0.0)

> FIXED (audit): this guide previously described a vLLM-era stack and
> referenced files that do not exist (`services/ai_safety/…`,
> `infrastructure/otel/`, `infrastructure/prometheus/`,
> `HSAAI_Complete_Engineering_Audit.pdf`). Rewritten for the current
> Ollama-based, compose-first platform.

---

## 0. المتطلبات

| Requirement | Notes |
|-------------|-------|
| Docker 24+ with Compose v2 | `docker compose version` |
| RAM | 32GB+ (64GB recommended) |
| Disk | 50GB+ (models + data volumes) |
| GPU (optional) | NVIDIA toolkit — أطلق تعليق GPU في خدمة `ollama` داخل `docker-compose.yml` |

---

## 1. Compose (المسار الأساسي)

```bash
# 1) Secrets
cp .env.example .env
# REQUIRED at minimum:
#   POSTGRES_PASSWORD, KEYCLOAK_ADMIN_PASSWORD,
#   MINIO_ROOT_PASSWORD, GRAFANA_PASSWORD, SESSION_SECRET, NEO4J_PASSWORD
# INTERNAL_ONLY_MODE يبقى true — لا مفاتيح خارجية مطلوبة.

# 2) Up
./start.sh                    # يتحقق من Compose ويشغّل كامل الـ stack؛ ويفعّل GPU override عند توفر NVIDIA runtime
# أو بدون GPU override: docker compose up -d

# 3) تحقق
docker compose ps
curl -s http://localhost:8000/health    # api-gateway
curl -s http://localhost:8001/health    # backend-core (loopback فقط)
```

### المنافذ بعد الإقلاع
| URL | Service |
|-----|---------|
| http://localhost:3000 | **الواجهة (Next.js)** |
| http://localhost:8000 | API Gateway |
| http://localhost:8080 | Keycloak (admin console) |
| http://localhost:3001 | Grafana |
| http://localhost:9001 | MinIO console (loopback) |
| 5432 / 6379 / 6333 / 7687 / 9092 | postgres / redis / qdrant / neo4j / kafka (**loopback فقط**) |

### نموذج LLM الافتراضي (Ollama)
```bash
docker exec -it $(docker ps -qf name=ollama) ollama pull qwen2.5:7b-instruct
# أو: scripts/bootstrap_ollama_models.sh
```
`llm-gateway` يعمل بوضع INTERNAL_ONLY (لا مكالمات خارجية) — أي
`OPENAI_API_KEY` في `.env` يبقى غير مستخدم إلا إذا عطّلت الوضع صراحةً.

---

## 2. النشر بدون Docker (Native)

```bash
cp deployment/native/env.native.example .env.native   # املأ الأسرار فعلياً
./deployment/native/hsaai-ctl start                   # postgres, redis, qdrant, backend, web
./deployment/native/hsaai-ctl status
```
- بدون `.env.native` صحيح يفشل التشغيل عمداً (fail-closed) — هذا مقصود.
- في بيئات العرض المعزولة فقط: `HSAAI_ALLOW_INSECURE_DEMO=1`.
- الوحدات المؤسسية (systemd): `deployment/production/install-systemd-units.sh`
  (يثبّت وحدات محصّنة — لا يثبّت الـ IdP التجريبي إلا بـ `HSAAI_ENABLE_DEMO_IDP=1`).

---

## 3. قاعدة البيانات

```bash
make init-db        # Alembic migrations (0001…0005) — RLS + indexes + constraints
make init-qdrant    # Qdrant collection
make init-vault     # Vault AppRole (القيم تُقرأ out-of-band — لا تُطبع في اللوج)
```
في production يشغّل backend-core الترحيلات تلقائياً عند الإقلاع ويرفض
البدء بدون Schema كاملة.

---

## 4. التطوير اليومي

```bash
# Frontend
cd apps/web && npm ci && npm run dev          # http://localhost:3000
npm run lint && npm run type-check && npm test

# Backend services (دون Docker)
python3 -m venv .venv-backend && source .venv-backend/bin/activate
pip install -r services/backend_core/requirements.txt
PYTHONPATH=. uvicorn _demo_oidc_shim:app --host 127.0.0.1 --port 8000

# الاختبارات
pip install -r tests/requirements.txt
pytest tests/ -p no:cacheprovider --no-cov -q --ignore=tests/e2e --ignore=tests/load
# e2e: playwright install chromium + تشغيل الستاك على localhost:3000
```

## 5. الهوية التجريبية (Demo IdP)

`deployment/native/mock-keycloak.js` يوفر:
- `demo.admin` — دور `hsaai_admin` (كلمة المرور عبر `MOCK_IDP_ADMIN_PASSWORD`،
  الافتراضي `Hsaai@Demo2026` — **للتجارب المحلية فقط**)
- `demo.user` — دور `ai_user`

الإنتاج يستخدم Keycloak الحقيقي دائماً.

## 6. مراجع سريعة

- Runbooks التشغيل: [`runbooks/`](runbooks/)
- بداية الأعطال الشائعة: `runbooks/RUNBOOK-01-postgres-down.md` … `RUNBOOK-10-tenant-isolation-breach.md`
- متغيرات البيئة: `.env.example` / `.env.hsa-internal.example` / `.env.production.example`
- سجل التغييرات: [`CHANGELOG.md`](CHANGELOG.md)
