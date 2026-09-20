<div align="center">

# HSAAI
### Enterprise AI Operating System

**منصة التشغيل الذكي المؤسسية — مجموعة هائل سعيد أنعم وشركاه**

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](VERSION)
[![License](https://img.shields.io/badge/license-Enterprise-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org)

</div>

> ## v3.0.0 — Full Platform Audit Applied
>
> This release passed a complete project-wide audit (build, runtime, security,
> configuration, tests, docs). Highlights: the broken root `docker-compose.yml`
> restructured (all 56 services now parse), 27 Dockerfiles repaired, unauthenticated
> backend endpoints locked behind JWT, datastore ports bound to loopback,
> demo-IdP credentials removed from the production path, changelog files
> consolidated. See `CHANGELOG.md` for details.

---

## نظرة عامة

**HSAAI** (Hayel Saeed Anam Artificial Intelligence) هو نظام تشغيل ذكاء اصطناعي مؤسسي
موحّد، يجمع المحادثة، المعرفة، الوكلاء، الحوكمة، الموافقات، البحث، التكاملات المؤسسية،
تتبع التكلفة، والمراقبة ضمن تجربة تشغيل واحدة.

المنصة مصممة خصيصاً لمجموعة **هائل سعيد أنعم وشركاه (HSA Group)** اليمنية،
لتوحيد الوصول إلى المعرفة المؤسسية الموزعة عبر ملفات، أنظمة ERP/HR/IT، إدارات متعددة،
ورسائل داخلية.

---

## الهيكلية المؤسسية

```
HSAAI/
│
├── apps/                          # تجربة المستخدم (Frontend)
│   └── web/                       # Next.js 15 (App Router, RTL Arabic-first)
│
├── services/                      # الـ Microservices (34 خدمة)
│   ├── backend_core/              # الموجّه المركزي للـ Enterprise OS
│   ├── api_gateway/               # البوابة (auth + rate limit + routing)
│   ├── auth_service/              # Keycloak OIDC + PKCE + MFA
│   ├── rag_engine/                # Qdrant + sentence-transformers
│   ├── llm_gateway/               # Ollama + Model Routing (internal-only)
│   ├── multi_agents/              # Department Agents + Tool Calling
│   ├── workflow_engine/           # Workflows + HITL Approvals
│   ├── model_training/            # QLoRA/SFT Training (PEFT + TRL)
│   ├── pii_detector/              # Presidio PII Detection
│   ├── mcp_server/                # MCP JSON-RPC Server
│   ├── governance/                # RBAC + ABAC + Audit + Policy Engines
│   ├── ai_alignment/              # Safety / Alignment Layer
│   └── ...                        # + 21 طبقة ذكاء (engines) — انظر أدناه
│
├── packages/                      # المكتبات المشتركة (packages/common — 52 حزمة)
│   └── common/
│       ├── auth/                  # مصادقة الخدمات (verify_service_auth)
│       ├── abac/                  # عميل OPA للـ ABAC (fail-closed)
│       ├── prompt_security/       # حماية من حقن الأوامر
│       ├── tool_registry/         # سجل الأدوات + Dispatcher
│       ├── rate_limit/            # Rate Limiting per-tenant
│       ├── resilience/            # Circuit Breaker + Retry + Bulkhead
│       ├── observability/         # OpenTelemetry + Tracing + Logging
│       ├── security/              # mTLS + Encryption + CORS
│       ├── vault_client.py        # HashiCorp Vault client
│       └── siem_sink.py           # SIEM Streaming (Splunk/Sentinel)
│
├── infrastructure/                # البنية التحتية + IaC
│   ├── docker/                    # Compose variants (dev + internal + production)
│   ├── kubernetes/                # K8s Manifests + Kustomize Overlays
│   ├── helm/                      # Helm Charts
│   ├── patroni/                   # PostgreSQL HA (3 nodes + PgBouncer)
│   ├── qdrant-cluster/            # Qdrant Clustering (3 nodes + sharding)
│   ├── redis-sentinel/            # Redis Sentinel HA (3 nodes)
│   ├── monitoring/                # Prometheus + Grafana + Alertmanager + OTel
│   ├── postgres/                  # init.sql (extensions + roles + DBs)
│   ├── keycloak/                  # Keycloak Realm Configuration
│   ├── opa/                       # ABAC Engine (Open Policy Agent)
│   ├── vault/                     # Secrets Management (HashiCorp Vault)
│   ├── thanos/                    # Long-term metrics storage
│   ├── waf/ + mtls/ + nginx/      # WAF rules, mTLS certs, ingress
│   └── secrets/                   # Secrets Templates (examples only)
│
├── alembic/                       # Database Migrations (0001 … 0005 — 5 revisions)
├── docs/                          # التوثيق (architecture, api, security, reports, …)
│   └── history/                   # سجلات التغيير القديمة المؤرشفة
├── tests/                         # 20 مجلد اختبار (unit, backend, security, e2e, …)
├── scripts/                       # عمليات: qa/, dr/, seed/, backup_*, deploy-production, …
├── deployment/                    # native (dockerless) + production systemd paths
├── mobile/                        # تطبيق Expo/RN (غير مدمج في CI بعد)
├── .adr/                          # Architecture Decision Records (12 ADR)
├── runbooks/                      # Operational Runbooks (10 Runbooks)
├── .github/workflows/             # CI/CD (ci, security-scan, docker-build)
│
├── .env.example                   # Environment Template
├── .env.hsa-internal.example      # Internal Deployment Template
├── .env.production.example        # Production Template
├── .dockerignore / apps/web/.dockerignore
├── .gitignore                     # FIXED — يغطي .env و node_modules و build artifacts
├── alembic.ini / pytest.ini / pyproject.toml / Makefile
├── LICENSE / VERSION / CHANGELOG.md / RELEASE_NOTES_v3.md / QUICKSTART.md
└── README.md                      # هذا الملف
```

### طبقة محركات الذكاء (Intelligence Engines)

إلى جانب الخدمات الأساسية الـ 12 أعلاه، تتضمن المنصة 21 محركاً ذاتياً
(`consciousness_stream`, `dream_engine`, `empathy_engine`, `wisdom_marketplace`,
`quantum_decision_engine`, `immune_system`, …) تعمل عبر Redis وتشارك
`packages/common`. جميعها في `docker-compose.yml` بمنافذ 8070–8096
(باستثناء consciousness-stream على المضيف 8100 لتجنّب التعارض مع workflow-engine).

---

## الخدمات الأساسية (Core Services)

| # | Service | Internal Port | Host Port | Purpose |
|---|---------|---------------|-----------|---------|
| 1 | `web` (Next.js) | 3000 | 3000 | الواجهة (RTL/LTR) |
| 2 | `api-gateway` | 8000 | 8000 | البوابة، Auth، Rate Limiting |
| 3 | `backend-core` | 8000 | 127.0.0.1:8001 | الموجّه المركزي للـ Enterprise OS |
| 4 | `auth-service` | 8010 | — | Keycloak OIDC + PKCE + MFA |
| 5 | `rag-engine` | 8030 | — | Qdrant + Reranker |
| 6 | `agent-runtime` (multi_agents) | 8040 | — | Department Agents + Tools |
| 7 | `workflow-engine` | 8070 | 8070 | Workflows + HITL |
| 8 | `llm-gateway` | 8090 | 8090 | Ollama + Model Routing |
| 9 | `model-training` | 8090 | 8091 | QLoRA/SFT Training |
| 10 | `pii-detector` | 8092 | 8092 | PII Detection |
| 11 | `mcp-server` | 8094 | 8094 | MCP JSON-RPC |
| 12 | `governance-service` | 8011 | 8011 | Governance + Audit |

**ملاحظة أمنية:** منافذ مخازن البيانات (postgres, redis, qdrant, neo4j, kafka,
minio, vault, opa, mlflow, prometheus, tempo, loki, thanos) وbackend-core
مرتبطة بـ `127.0.0.1` فقط — غير معرّضة للشبكة. Grafana على 3001 (3000 للواجهة).

---

## الميزات الرئيسية

### 🤖 هندسة الذكاء الاصطناعي
- **RAG Pipeline** كامل (Qdrant + sentence-transformers + hybrid reranker)
- **Prompt Injection Defense** (40+ patterns + sanitize + block)
- **PII Detection** (Presidio + Arabic patterns + auto-block على uploads)
- **Real Tool Calling** (أدوات حقيقية مع dispatch mechanism)
- **MCP Server** (متوافق مع Claude Desktop, Cursor, Cline)
- **Model Training** (QLoRA/SFT حقيقي عبر PEFT + bitsandbytes + MLflow registry)
- **Knowledge Graph** (Neo4j native: shortest path, communities, PageRank)
- **Multi-Agent System** (Supervisor + department agents)

### 🔒 الأمن السيبراني
- **Keycloak OIDC + PKCE + MFA** (httpOnly cookies)
- **JWT على كل نقاط النهاية الحساسة** — FIXED: أُغلقت 19+ نقطة غير محمية في backend-core
- **ABAC** via Open Policy Agent (**fail-closed** افتراضياً)
- **HashiCorp Vault** (dynamic DB credentials + AppRole auth)
- **SIEM Streaming** (Splunk + Azure Sentinel + CloudWatch)
- **WAF** (SQL injection, XSS, prompt injection, geo-block, bot)
- **HMAC-signed Audit Logs** (tamper-evident)
- **Image Signing** (cosign + SBOM via Syft)
- **لا أسرار مُ commit-zة**: hsaai-ctl يفشل عند غياب `.env.native`، ولا IdP تجريبي في وحدات الإنتاج

### 🏗️ البنية المؤسسية
- **PostgreSQL HA** (Patroni 3 nodes + PgBouncer + HAProxy)
- **Qdrant Clustering** (3 nodes + sharding)
- **Redis Sentinel** (3 nodes + automatic failover)
- **Thanos** (long-term metrics عبر MinIO)
- **Circuit Breakers** بين الخدمات
- **Per-Tenant Rate Limiting** (Redis-based, tiered quotas)
- **Alembic هو مصدر الحقيقة الوحيد للـ Schema** — الترحيلات تُشغَّل عند الإقلاع في production

### 🌍 الهوية العربية
- **Arabic-first** (UI, embeddings, system prompts, intent detection, OCR)
- **RTL** Support كامل + تبديل LTR للإنجليزية
- **Arabic PII patterns** (Saudi Iqama, Emirates ID, Arabic names)
- **Arabic Compliance** (NDMO Saudi + PDPL UAE)

---

## النشر السريع

### Docker Compose (موصى به)
```bash
cp .env.example .env        # ثم املأ: POSTGRES_PASSWORD, KEYCLOAK_ADMIN_PASSWORD,
                            # MINIO_ROOT_PASSWORD, GRAFANA_PASSWORD, SESSION_SECRET
./start.sh                  # أو: docker compose up -d
```

بعد الإقلاع:
- الواجهة: http://localhost:3000
- API Gateway: http://localhost:8000
- Grafana: http://localhost:3001
- سحب نموذج LLM الافتراضي: `docker exec -it $(docker ps -qf name=ollama) ollama pull qwen2.5:7b-instruct`
  (أو `scripts/bootstrap_ollama_models.sh`)

### النشر بدون Docker (Native)
```bash
cp deployment/native/env.native.example .env.native   # املأ الأسرار
./deployment/native/hsaai-ctl start
```
> للأمان: `hsaai-ctl` يرفض العمل بدون أسرار حقيقية. للتجربة المعزولة فقط
> أضف `HSAAI_ALLOW_INSECURE_DEMO=1`.

### الأوامر المتاحة (Makefile)
```bash
make help          # Show all commands
make dev-up        # Start development stack
make prod-up       # Start production stack
make ha-up         # Start HA infrastructure
make init-db       # Run Alembic migrations
make init-qdrant   # Create Qdrant collection
make init-vault    # Initialize Vault (credentials shown out-of-band only)
make test          # Run all tests
make test-unit     # Run unit tests only
make test-load     # Run load tests (locust)
make lint          # Lint all code
make security-scan # Run security scans
make backup        # Backup databases (backup-qdrant أيضاً)
make docs          # Generate documentation
```

---

## التوثيق

- [`QUICKSTART.md`](QUICKSTART.md) — البدء السريع المحدَّث
- [`CHANGELOG.md`](CHANGELOG.md) — سجل الإصدارات الكامل (موحّد)
- [`RELEASE_NOTES_v3.md`](RELEASE_NOTES_v3.md) — ملاحظات الإصدار الحالي
- [`docs/architecture/`](docs/architecture/) — المعمارية الشاملة
- [`docs/security/`](docs/security/) — الأمن السيبراني + Pen Test Checklist
- [`docs/reports/`](docs/reports/) — تقارير التدقيق والإصلاحات (V2 → v5.1)
- [`.adr/`](.adr/) — Architecture Decision Records (12 ADR) + [`docs/adr/`](docs/adr/) (ADRs التحتية)
- [`runbooks/`](runbooks/) — Operational Runbooks (10 Runbooks)

---

## الترخيص

**Enterprise Internal Use** — Hayel Saeed Anam Group (HSA Group)

© 2026 HSA Group. All rights reserved.

---

<div align="center">

**Hayel Saeed Anam Group** | Yemen
**Enterprise AI Operating System** | Version 3.0.0

</div>
