# HSAAI Enterprise AI Platform — System Architecture

## 1. Architecture Overview

HSAAI follows a layered enterprise architecture designed for internal deployment within HSA Group's VMware infrastructure.

```
User Interface (Next.js + React)
        ↓
API Gateway (Authentication + Routing)
        ↓
HSAAI AI Orchestrator (Query Router + Security Policy Engine)
        ↓
HSAAI RAG Engine (Chunking + Embedding + Hybrid Retrieval)
        ↓
Vector Database (Qdrant Enterprise)
        ↓
Reranker Engine (Cross-Encoder + MMR)
        ↓
HSAAI Agent Framework (21 Department Agents)
        ↓
LLM Gateway (vLLM + Model Router)
        ↓
Response Generator (Citation + Verification + Filtering)
```

## 2. Core Components

### 2.1 API Gateway
- **Technology:** FastAPI + NGINX Ingress
- **Port:** 8000
- **Responsibilities:** Request authentication, rate limiting, routing, CORS enforcement

### 2.2 HSAAI AI Orchestrator
- **Technology:** FastAPI (backend_core)
- **Port:** 8001
- **Responsibilities:** Query routing, security policy enforcement, PII detection, prompt injection defense, session management

### 2.3 HSAAI RAG Engine
- **Technology:** FastAPI + Qdrant + BAAI/bge-m3
- **Port:** 8030
- **Responsibilities:** Document chunking, embedding generation, hybrid retrieval (vector + BM25), citation verification, hallucination control

### 2.4 HSAAI Knowledge Brain
- **Technology:** Qdrant Enterprise (3-node cluster)
- **Port:** 6333 (REST), 6334 (gRPC)
- **Responsibilities:** Vector storage, tenant-isolated collections, payload filtering, similarity search

### 2.5 Reranker Engine
- **Technology:** BAAI/bge-reranker-v2-m3 (ONNX-optimized)
- **Responsibilities:** Cross-encoder scoring, MMR diversity selection, business context ranking, explainable ranking traces

### 2.6 HSAAI Agent Framework
- **Technology:** FastAPI + Celery
- **Port:** 8040
- **Responsibilities:** 21 specialized department agents, tool calling, memory management, workflow execution

### 2.7 LLM Gateway
- **Technology:** vLLM + OpenAI-compatible API
- **Port:** 8090
- **Responsibilities:** Model serving (Qwen2.5-72B), model routing, token management, streaming responses

### 2.8 HSAAI Security Layer
- **Technology:** Keycloak + Vault + OPA
- **Responsibilities:** OIDC authentication, RBAC + ABAC authorization, secrets management, policy enforcement

### 2.9 HSAAI Enterprise Analytics
- **Technology:** FastAPI + Prometheus + Grafana
- **Responsibilities:** KPI tracking, cost analytics, usage monitoring, executive dashboards

## 3. Data Flow

1. User submits query via web interface
2. API Gateway authenticates request via Keycloak JWT
3. HSAAI AI Orchestrator routes query through security checks (PII detection, prompt injection defense)
4. HSAAI RAG Engine retrieves relevant knowledge from Qdrant
5. Reranker Engine scores and ranks retrieved chunks
6. HSAAI Agent Framework processes query with department-specific agent
7. LLM Gateway generates response using grounded context
8. Response Generator verifies citations and calculates confidence scores
9. Response delivered to user with full audit trail

## 4. Infrastructure

### 4.1 VMware vSphere Clusters
| Cluster | Hosts | Purpose |
|---------|-------|---------|
| Management | 3 | vCenter, monitoring, security tools |
| AI Compute | 4 | RAG, LLM, embeddings, reranker (GPU) |
| Application | 4 | Frontend, backend, APIs |
| Data | 3 | PostgreSQL, Qdrant, Redis, MinIO |

### 4.2 Kubernetes (VMware Tanzu)
- 4 workload clusters (management, app, AI, data)
- NVIDIA GPU Operator for AI workloads
- Istio service mesh for mTLS
- Kyverno for admission control

### 4.3 Storage
- vSAN NVMe (Tier 0): AI model cache, Qdrant hot data
- vSAN SSD (Tier 1): VM storage, PostgreSQL
- vSAN Hybrid (Tier 2): Documents, backups

## 5. Multi-Tenant Isolation

- PostgreSQL Row Level Security (RLS) on all tables
- Qdrant payload filtering with mandatory `tenant_id`
- Application-level `TenantGuard` enforcement
- `tenant_id` extracted from JWT only — never from user input

## 6. Brand Identity

- **Product Name:** HSAAI Enterprise AI Platform
- **Organization:** Hayel Saeed Anam Artificial Intelligence
- **Colors:** Gold (#F4C430), Dark Gold (#A67C00), Black (#111111), White (#FFFFFF)
- **Logo:** `docs/brand/hsaai-logo.png`
