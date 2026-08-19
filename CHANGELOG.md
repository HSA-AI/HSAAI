# HSAAI — Changelog

All notable changes to HSAAI Enterprise AI Operating System are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/).

---

## [4.0.0] — 2026-06-24 — World-Class Enterprise (94/100)

### Added — 14 Gap Closures (86 → 94/100)
- **Comprehensive Tests**: 27 test files (unit + integration + e2e + load + contract + security regression)
- **6 Real Connectors**: SharePoint, Power BI, Outlook, ITSM, DMS, SuccessFactors (MS Graph + OData)
- **Neo4j Native**: shortest path, community detection (Louvain), PageRank via GDS
- **HashiCorp Vault**: dynamic DB credentials, AppRole auth, secrets caching
- **SIEM Streaming**: Splunk HEC + Azure Sentinel + CloudWatch + webhook
- **DevOps Hardening**: 8 PodDisruptionBudgets, cosign image signing, Syft SBOM, precise NetworkPolicies
- **WAF**: 8 rules (SQL injection, XSS, prompt injection, geo-block, rate limit, bot, path traversal, body size)
- **Pen Test Checklist**: 10 sections, 80+ items
- **GraphQL BFF**: 1 query replaces 10+ REST calls (Strawberry)
- **Per-Tenant Rate Limiting**: Redis-based, tiered quotas (free/pro/enterprise)
- **Circuit Breakers**: CLOSED/OPEN/HALF_OPEN with auto-recovery
- **16 ADRs**: Architecture Decision Records
- **10 Runbooks**: Operational runbooks
- **CI/CD v4.0**: cosign + SBOM + Trivy + Gitleaks + Bandit + Checkov (all blocking)

## [3.0.0] — 2026-06-24 — Enterprise Production-Ready (86/100)

### Added — 10 Enterprise Features (73 → 86/100)
- Prompt Injection Defense (40+ patterns + sanitize + block)
- PostgreSQL HA (Patroni 3 nodes + PgBouncer + HAProxy)
- Qdrant Clustering (3 nodes + 4 shards + replication factor 2)
- Redis Sentinel (3 nodes + automatic failover)
- Loki + Promtail (centralized log aggregation)
- PII Detection (Presidio + Arabic patterns + auto-block)
- ABAC Engine (Open Policy Agent + Rego policies)
- Compliance Reports (SOX + GDPR + NDMO + PDPL)
- MCP Server (5 tools + 4 resources, JSON-RPC 2.0)
- Real Tool Calling (10 tools with dispatch mechanism)

## [2.0.0] — 2026-06-24 — Pilot-Ready (73/100)

### Fixed — 18 Critical + 25 High findings
- PKCE flow (verifier leak + state validation + atomic get+delete)
- MFA endpoints auth (no secret in response, server-side storage)
- Auth on 8 microservices + WebSocket
- Path traversal protection (dataset upload + RAG upload)
- Tenant ID hardcoded fix (agent_runtime)
- Tenant spoofing fix (api_gateway — JWT only, no X-Tenant-ID)
- CI scan fix (removed `|| true`, added SAST/SCA/secret scan)
- Docker-compose hardening (Keycloak start, ES security, Redis password, Neo4j ports)
- Workflow /approve + /history (auth + tenant filter)
- True streaming in RAG (was fake streaming)
- Next.js middleware + AuthProvider wiring
- localStorage token removal (httpOnly cookies only)
- Fabricated data removal (executive, analytics, dashboard)
- RBAC cleanup (legacy roles + default ai_user + executive permissions)
- Sync I/O → async (rbac.py, approvals/service.py)
- K8s hardening (securityContext + probes for all 11 manifests)
- Helm hardening (CHANGE_ME → required, imageTag pinned)
- Duplicate removal (3 docker-compose → 1, 3 network-policies → 1, migrations consolidated)

## [1.0.0] — 2026-01-15 — Initial Release (61/100)

### Added
- 11 microservices architecture
- Keycloak OIDC + PKCE authentication
- RAG pipeline (Qdrant + sentence-transformers)
- Multi-agent system (Supervisor + 5 department agents)
- Workflow engine (5 step types + HITL)
- Model training (QLoRA/SFT via PEFT/TRL)
- Knowledge graph (SQL-based, 13 entity types)
- Enterprise integrations (SAP, AD, 8 connector contracts)
- FinOps tracking
- HMAC-signed audit logs
- OpenTelemetry tracing
- Prometheus + Grafana monitoring
- CI/CD pipeline (GitHub Actions)
- Docker + Kubernetes deployment
- Arabic-first UI (RTL)
