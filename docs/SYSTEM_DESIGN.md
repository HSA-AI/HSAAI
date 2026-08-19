# HSAAI System Design

## 1. Design Principles

- **Internal-Only Deployment:** Closed network, no external API exposure
- **Zero Trust Architecture:** Every request authenticated and authorized
- **Multi-Tenant Isolation:** Strict tenant separation at database, vector, and application layers
- **Bilingual Support:** Full Arabic (RTL) and English (LTR) interface
- **Enterprise Security:** ISO 27001, OWASP ASVS, CIS Benchmark compliance

## 2. Service Decomposition

### 2.1 Core Services (14 FastAPI microservices)

| Service | Port | Database | GPU Required |
|---------|------|----------|-------------|
| API Gateway | 8000 | — | No |
| Backend Core | 8001 | PostgreSQL | No |
| Auth Service | 8010 | PostgreSQL | No |
| Governance Service | 8011 | PostgreSQL | No |
| RAG Engine | 8030 | Qdrant + PostgreSQL | Yes (embedding) |
| LLM Gateway | 8090 | — | Yes (inference) |
| PII Detector | 8012 | — | No |
| Workflow Engine | 8070 | PostgreSQL + Redis | No |
| Agent Runtime | 8040 | PostgreSQL + Redis | No |
| Multi-Agents | 8060 | Redis | No |
| AI Alignment | 8005 | — | No |
| MCP Server | 8094 | — | No |
| Model Training | 8091 | PostgreSQL + MinIO | Yes (training) |
| Voice AI | 8096 | — | Yes (Whisper) |

### 2.2 Data Services

| Service | Technology | HA Configuration |
|---------|-----------|------------------|
| PostgreSQL | Patroni (1 primary + 2 replicas) | Sync + Async replication |
| Qdrant | 3-node cluster | Raft consensus |
| Redis | 3 redis + 3 sentinel | Sentinel quorum |
| MinIO | 4-node distributed | Erasure coding |
| Vault | 3-node Raft | Auto-unseal |
| Keycloak | 2-node cluster | Shared PostgreSQL |
| Neo4j | Single node (planned HA) | — |
| Kafka | 3-node cluster | Replication factor 3 |

## 3. Data Model

### 3.1 PostgreSQL Tables
- `rag_documents` — Document metadata and indexing status
- `rag_chunks` — Chunk content with lineage (page, section, heading)
- `rag_embeddings` — Per-chunk embedding records
- `rag_queries` — Full query log with scores and citations
- `rag_feedback` — User feedback on responses
- `rag_metrics` — Time-series metrics
- `rag_retrieval_logs` — Per-chunk retrieval audit trail
- All tables: RLS enabled, `tenant_id` mandatory

### 3.2 Qdrant Collections
- `hsaai_documents_vectors` — Primary vector collection
- Payload: `tenant_id`, `workspace_id`, `document_id`, `department`, `security_level`, `classification`, `language`, `model_version`

## 4. AI Pipeline Design

### 4.1 Document Ingestion Pipeline
```
Upload → Validation → Virus Scan → OCR → Classification →
PII Detection → Metadata Extraction → Smart Chunking →
Embedding Generation → Vector Indexing
```

### 4.2 Query Pipeline
```
User Query → Security Check → Language Detection →
Query Embedding → Hybrid Retrieval (Top 50) →
Cross-Encoder Reranking (Top 10) → MMR Diversity (Top 5) →
LLM Generation → Citation Verification → Response Filtering
```

## 5. Security Design

### 5.1 Authentication
- Keycloak OIDC + PKCE
- MFA (TOTP) for all roles
- JWT with JWKS caching (5-minute TTL)
- Session timeout: 8 hours

### 5.2 Authorization
- RBAC: 7 enterprise roles × 15 permissions
- ABAC: Central Policy Decision Point (fail-closed)
- Classification: PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED

### 5.3 Data Protection
- AES-256 encryption at rest (PostgreSQL, MinIO)
- TLS 1.3 in transit
- PII detection before LLM calls (9 patterns)
- Prompt injection defense (9 patterns)
- HMAC-signed audit trail

## 6. Observability Design

| Signal | Tool | Storage |
|--------|------|---------|
| Metrics | Prometheus | 15 metric families, 30-day retention |
| Logs | Loki | Structured JSON, 30-day retention |
| Traces | OpenTelemetry + Tempo | Distributed tracing, 7-day retention |
| Dashboards | Grafana | 10+ provisioned dashboards |
| Alerts | Alertmanager | Slack + PagerDuty routing |
