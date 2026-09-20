# HSAAI Architecture Documentation (Phase 14)

## 1. System Overview

HSAAI is the Enterprise AI Platform for Hayel Saeed Anam Group (HSA Group).
It provides AI assistants, agents, knowledge retrieval, and workflow automation
to HSA Group employees across 6 business units.

### 1.1 Design Principles
1. **Simplicity first** — operable by a team of 2-5 engineers
2. **Domain-driven boundaries** — services aligned with business domains
3. **Defense in depth** — security at network, identity, app, and data layers
4. **Observability by default** — every request is traced
5. **Tenant isolation** — multi-tenant from day one

### 1.2 Architecture Style
The platform uses a **modular monolith with selective microservices** pattern:
- Services with independent scaling needs are deployed as separate containers
- Services that always co-scale are modules within `backend_core`
- Inter-service communication is sync HTTP for queries, async via Kafka for commands

## 2. Service Inventory (11 Services)

| Service | Purpose | Lines | Independent Scale? |
|---------|---------|-------|-------------------|
| api_gateway | Ingress + BFF + routing | 264 | Yes |
| auth_service | Identity (Keycloak integration) | 476 | No |
| llm_gateway | LLM serving (vLLM + cache + budgets) | 679 | Yes (GPU) |
| rag_engine | RAG + document AI + knowledge graph | 1,184 | Yes |
| multi_agents | Agent runtime + orchestration | 290 | Yes |
| ai_alignment | Constitutional AI + safety layer | 603 | No |
| governance | RBAC + ABAC + audit + data gov + compliance | 600 | No |
| mcp_server | Tool calling (MCP protocol) | 477 | No |
| workflow_engine | Workflow orchestration | 325 | No |
| pii_detector | PII scanning (independent scaling for batch) | 332 | Yes |
| backend_core | Enterprise modules (38 subdirs) | 12,059 | No |
| model_training | MLOps + fine-tuning (GPU) | 1,795 | Yes (GPU) |

## 3. Data Layer

| Store | Purpose | HA Strategy |
|-------|---------|-------------|
| PostgreSQL | Operational data + audit logs + episodic memory | Patroni (3 nodes) + 2 read replicas |
| Qdrant | Vector embeddings (RAG + memory recall) | Cluster (3 nodes) + SQ8 quantization |
| Neo4j | Knowledge graph | Causal cluster (3 nodes) |
| Redis | Cache + token budgets + safety state + sessions | Sentinel (3 nodes) |

## 4. Infrastructure Layer

| Component | Purpose | Classification |
|-----------|---------|---------------|
| Kubernetes | Container orchestration | Critical |
| Helm | K8s package management | Critical |
| NGINX Ingress | SSL termination + routing | Critical |
| Keycloak | OIDC identity provider | Critical |
| Vault | Secrets management | Recommended |
| OPA | Policy-as-code | Critical |
| Kafka | Event bus | Recommended |
| vLLM | LLM serving engine | Critical |
| OpenTelemetry | Distributed tracing | Critical |
| Prometheus | Metrics scraping | Critical |
| Loki | Log aggregation | Recommended |
| Grafana | Dashboards | Critical |

## 5. Request Flow

```
User → NGINX → api_gateway → auth_service (validate JWT)
                            → governance (RBAC+ABAC check)
                            → prompt_firewall (LLM01 defense)
                            → multi_agents (orchestrate)
                              → rag_engine (retrieve)
                              → llm_gateway (generate)
                              → ai_alignment (output filter + self-critique)
                            → governance (audit log)
                            → response → User
```

## 6. Data Flow

```
Document ingestion:
  SharePoint/Drive/Email → connector → rag_engine
    → parse (PyMuPDF/python-docx)
    → chunk (semantic, 1000 tokens)
    → embed (BGE-M3)
    → store (Qdrant + PostgreSQL)
    → extract entities (LLM) → Neo4j

Query retrieval:
  User query → rag_engine
    → BM25 (PostgreSQL FTS) + Dense (Qdrant) + Graph (Neo4j)
    → RRF fusion
    → Cross-encoder rerank (BGE-Reranker-v2-m3)
    → Top-K context → LLM
```

## 7. Security Architecture (Defense in Depth)

| Layer | Control |
|-------|---------|
| Network | K8s network policies (default deny) + mTLS |
| Identity | Keycloak OIDC + JWT + MFA for admins |
| Authorization | OPA policies + RBAC + ABAC + PostgreSQL RLS |
| Application | Prompt firewall + output filter + tool sandboxing |
| Data | Encryption at rest (PostgreSQL TDE) + in transit (TLS 1.3) |
| Audit | Immutable audit log (hash-chained) + SIEM forwarding |
| Supply chain | SBOM (Syft) + image scanning (Trivy) + SAST (Semgrep) |

## 8. Observability Architecture

| Pillar | Tool | Retention |
|--------|------|-----------|
| Metrics | Prometheus → Grafana | 90 days |
| Logs | Loki → Grafana | 30 days |
| Traces | Tempo → Grafana | 7 days |
| Alerts | Alertmanager → Slack/PagerDuty | Real-time |

## 9. Deployment Architecture

```
GitHub → CI/CD (10 jobs) → GHCR (images) → K8s staging → DAST → Canary (10%) → Prod
```

## 10. Cost Architecture

| Component | Monthly Cost (est.) | Notes |
|-----------|---------------------|-------|
| GPU node (A100 80GB) | $3,000 | For vLLM |
| K8s cluster (5 nodes) | $1,500 | CPU nodes |
| PostgreSQL (managed) | $500 | RDS equivalent |
| Redis (managed) | $200 | |
| Qdrant (self-managed) | $200 | |
| Neo4j (self-managed) | $200 | |
| Storage (1TB) | $100 | |
| Observability | $300 | Grafana Cloud |
| **Total** | **~$6,000/month** | |
