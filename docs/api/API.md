# HSAAI API Documentation (Phase 14)

## Base URL
- Production: `https://hsaai.internal/api/v1`
- Staging: `https://staging.hsaai.internal/api/v1`

## Authentication
All endpoints require a Bearer JWT obtained from Keycloak:
```
Authorization: Bearer <jwt>
```
JWT contains: `sub` (user_id), `tenant_id`, `roles`, `exp`.

## Standard Response Format
```json
{
  "data": { ... },
  "meta": {
    "request_id": "uuid",
    "timestamp": "2026-07-04T12:00:00Z",
    "page": 1,
    "per_page": 20,
    "total": 100
  },
  "errors": []
}
```

## Standard Error Format
```json
{
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "message": "Field 'prompt' is required",
      "field": "prompt"
    }
  ]
}
```

## Endpoints

### LLM Gateway (`/v1/llm`)

#### POST /v1/llm/generate
Generate text via LLM.

**Request:**
```json
{
  "prompt": "Summarize this contract: ...",
  "max_tokens": 512,
  "temperature": 0.7,
  "top_p": 0.9,
  "tenant_id": "hsa-foods",
  "use_cache": true
}
```

**Response:**
```json
{
  "text": "This contract establishes...",
  "tokens_used": 248,
  "model": "Qwen/Qwen2.5-7B-Instruct",
  "backend": "vllm",
  "cache_hit": false,
  "latency_ms": 1240
}
```

#### GET /v1/llm/budget/{tenant_id}
Get remaining token budget.

**Response:**
```json
{
  "tenant_id": "hsa-foods",
  "remaining_tokens": 752000,
  "daily_limit": 1000000
}
```

### RAG (`/v1/rag`)

#### POST /v1/rag/query
Retrieve relevant documents.

**Request:**
```json
{
  "query": "What is our procurement policy for suppliers?",
  "tenant_id": "hsa-foods",
  "top_k": 5,
  "min_confidence": 0.7,
  "filters": {"category": "policy"}
}
```

**Response:**
```json
{
  "results": [
    {
      "document_id": "uuid",
      "title": "Procurement Policy v3",
      "content": "All suppliers must...",
      "confidence": 0.92,
      "source": "SharePoint/Policies/procurement_v3.pdf"
    }
  ],
  "count": 5,
  "latency_ms": 350
}
```

#### POST /v1/rag/ingest
Ingest a document. (Admin only)

### Agents (`/v1/agents`)

#### POST /v1/agents/execute
Execute an agent.

**Request:**
```json
{
  "agent_id": "procurement-analyst",
  "task": "Analyze this contract for compliance",
  "context": {"contract_id": "123"},
  "tenant_id": "hsa-foods"
}
```

**Response:**
```json
{
  "execution_id": "uuid",
  "status": "completed",
  "result": {"compliant": true, "issues": []},
  "tools_called": ["rag_query", "contract_analyzer"],
  "tokens_used": 1500,
  "duration_ms": 4500
}
```

### Governance (`/v1/governance`)

#### POST /v1/governance/access/check
Check access permission.

#### GET /v1/governance/audit/query
Query audit log. (Governance role only)

#### GET /v1/governance/compliance/assess
Generate compliance report.

### Safety (`/v1/safety`)

#### GET /v1/safety/approvals/pending
Get pending approval requests.

#### POST /v1/safety/approvals/{id}/approve
Approve a high-severity action.

#### POST /v1/safety/kill-switch
Activate kill switch. (Governance role only)

### Health & Metrics

#### GET /health
Service health check.

#### GET /metrics
Prometheus metrics.

## Rate Limits
- Anonymous: 10 req/min
- Authenticated: 100 req/min
- Admin: 1000 req/min
- LLM endpoints: 50 req/min per tenant

## Versioning
API versioned via URL prefix (`/v1/`). Breaking changes require new version.
