# HSAAI API Reference

## Authentication

All endpoints require:
- `Authorization: Bearer <JWT>` (Keycloak OIDC)
- `Content-Type: application/json`
- `tenant_id` is extracted from JWT — never accepted from request body

## Core Endpoints

### Chat & Query

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/chat` | Send message to HSAAI Knowledge Assistant | Any authenticated user |
| POST | `/api/chat/stream` | Stream response via WebSocket | Any authenticated user |
| GET | `/api/dashboard/stats` | Get dashboard statistics | `analytics.view` |

### RAG Engine

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/rag/index` | Index a document | `knowledge.manage` |
| POST | `/rag/index/batch` | Batch index up to 1000 documents | `knowledge.manage` |
| POST | `/rag/search` | Hybrid retrieval (no LLM generation) | `analytics.view` |
| POST | `/rag/query` | Full RAG pipeline (retrieve + generate + verify) | `analytics.view` |
| GET | `/rag/status` | System health and metrics | `platform.monitor` |
| GET | `/rag/models` | List available embedding models | `platform.monitor` |
| POST | `/rag/feedback` | Submit feedback on a response | Any authenticated user |

### Agent Framework

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/agents` | List all available agents | Any authenticated user |
| POST | `/api/agents/{id}/execute` | Execute an agent task | `agents.manage` |
| POST | `/rag/agent/tool` | Invoke an agent tool | Per-tool permission |

### Governance

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/governance/policies` | List ABAC policies | `audit.view` |
| POST | `/api/governance/policies` | Create/update policy | `system.config` |
| GET | `/api/governance/audit` | Query audit log | `audit.view` |

### Administration

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/admin/users` | List users | `users.manage` |
| POST | `/api/admin/users` | Create user | `users.manage` |
| GET | `/api/admin/roles` | List roles and permissions | `users.manage` |

### System

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/health` | Overall health | None |
| GET | `/health/live` | Liveness probe | None |
| GET | `/health/ready` | Readiness probe | None |
| GET | `/metrics` | Prometheus metrics | None (scraped by Prometheus) |

## Response Format

### RAG Query Response
```json
{
  "query_id": "uuid",
  "query": "What is the annual leave policy?",
  "answer": "Employees are entitled to 30 days...",
  "citations": [...],
  "confidence_score": 0.92,
  "grounding_score": 0.88,
  "citation_score": 1.0,
  "hallucination_risk": 0.08,
  "status": "verified",
  "total_ms": 1842
}
```

### Error Responses
| Status | Meaning |
|--------|---------|
| 400 | Bad request (invalid input, PII detected) |
| 401 | Unauthorized (invalid/expired JWT) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 503 | Service unavailable (dependency down) |
