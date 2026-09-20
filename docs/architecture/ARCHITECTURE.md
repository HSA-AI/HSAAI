# HSAAI — Architecture Overview (v4.0)

## الهدف

تحويل HSAAI إلى منصة ذكاء اصطناعي مؤسسية موحدة تجمع المحادثة، المعرفة، الوكلاء،
الحوكمة، الموافقات، البحث، التكاملات، التكلفة، والمراقبة ضمن تجربة تشغيل واحدة
لمجموعة هائل سعيد أنعم وشركاه (HSA Group).

## الطبقات الست

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: EXPERIENCE — Next.js 16 (RTL Arabic + LTR)           │
│  Dashboard | Chat | Knowledge Hub | Agents | Workflow Studio   │
│  Approvals | Governance | FinOps | Integrations | Observability│
└────────────────────────────┬────────────────────────────────────┘
                             │ httpOnly Cookie
┌────────────────────────────▼────────────────────────────────────┐
│  LAYER 2: API GATEWAY — FastAPI (:8080)                        │
│  Rate Limiting | Egress Guard | Auth Forwarding | CORS         │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  LAYER 3: AI RUNTIME                                           │
│  AI Orchestrator | Multi-Agents | LLM Gateway | Workflow Engine│
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  LAYER 4: KNOWLEDGE                                            │
│  RAG Engine | Document AI | Knowledge Graph | Model Training   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  LAYER 5: GOVERNANCE & SECURITY                                │
│  Keycloak OIDC | RBAC+ABAC | HMAC Audit | mTLS | Vault | PII  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  LAYER 6: OPERATIONS                                           │
│  Prometheus | Grafana | Loki | OpenTelemetry | Sentry | OPA    │
└─────────────────────────────────────────────────────────────────┘
```

## التقنيات الأساسية

| Category | Technology | Version |
|----------|-----------|---------|
| Frontend | Next.js + React + TypeScript | 16.x / 19.x / 5.x |
| Backend | FastAPI + Uvicorn + Pydantic | 0.115.5 / 0.32.1 / 2.10.2 |
| Database | PostgreSQL (Patroni HA) | 16-alpine |
| Vector DB | Qdrant (3-node cluster) | 1.12.1 |
| Cache | Redis (Sentinel HA) | 7-alpine |
| LLM | Ollama (qwen3:8b) | latest |
| Embeddings | sentence-transformers | 3.3.1 |
| Identity | Keycloak (OIDC + PKCE + MFA) | 24.0 |
| Graph | Neo4j (native) | 5-community |
| Secrets | HashiCorp Vault | 1.16.0 |
| ABAC | Open Policy Agent | 0.68.0 |
| Logging | Loki + Promtail | 3.0.0 |
| Monitoring | Prometheus + Grafana | 2.45+ / 10.x |
| Tracing | OpenTelemetry + Jaeger | 1.27+ |
| CI/CD | GitHub Actions + Cosign + Trivy | — |
