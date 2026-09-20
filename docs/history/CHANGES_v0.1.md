# HSAAI v0.1.0 — Code-Level Fixes Applied

> **20+ critical P0 fixes** from the v5.0/v5.1 audit reports applied to actual source code.

## Files Modified (22 files across 8 services + packages)

### services/workflow_engine/
- `main.py` — **P0**: Fixed sync/async bug (workflows were non-functional). Added `tool` step executor.

### services/governance/
- `main.py` — **P0**: Fixed authorization bypass in `/v1/access/check`. Restored NDMO compliance framework.

### services/backend_core/
- `knowledge_graph/neo4j_repository.py` — **P0**: Fixed Cypher injection via `rel_type` (whitelist + format validation).
- `enterprise_integrations/real_connectors.py` — **P0**: Fixed OutlookConnector URL for client_credentials flow.
- `approvals/service.py` — **P0**: Fixed sync I/O in `notify_approval` (now async). Fixed SLA breach detection bug (`if True`).
- `security/audit.py` — **P0**: Fixed HMAC key silent downgrade (now required in production).

### services/auth_service/
- `main.py` — **P0**: PKCE state → Redis. MFA secrets → Redis. OTP now verified locally via pyotp.

### services/rag_engine/
- `main.py` — **P0**: Real streaming (was fake). Batched embeddings. Qdrant `query_points()` API.
- `reranker.py` — **P1**: Multilingual cross-encoder `BAAI/bge-reranker-v2-m3`.

### services/llm_gateway/
- `main.py` — **P0**: `/api/chat` with messages array (was `/api/generate` with raw concat). Real token counting via tiktoken.

### services/multi_agents/
- `main.py` — **P0**: Activated reflection layer (`run_with_self_correction`). Added `preferred_agent` field.

### packages/common/
- `ai/advanced_rag.py` — **P0**: Parameterized Cypher (was injectable).
- `abac/__init__.py` — **P0**: Fail-closed for all actions (was fail-open for reads).
- `resilience/bulkhead.py` — **P0**: asyncio.Semaphore (was threading). Fixed release bug.
- `security/vault_client.py` — **P0**: Fixed asyncio.run in async context.
- `siem_sink.py` — **P0**: Added `await` to async SIEM backends (logs never reached Splunk).

### infrastructure/
- `docker-compose.yml` — **P0**: Mounted Prometheus alert rules (alerts never fired before).

### Root files
- `VERSION` — 4.0.0 → 0.1.0
- `CHANGELOG.md` — Full v0.1.0 changelog with migration notes
- `CHANGES_v0.1.md` — This file

## Impact Summary

| Category | Fixes | Severity |
|----------|-------|----------|
| Security vulnerabilities | 7 | P0 Critical |
| Non-functional services | 3 | P0 Critical |
| Performance killers | 4 | P0 Critical |
| Dead code activation | 2 | P0 Critical |
| Compliance gaps | 2 | P0 Critical |
| Infrastructure | 1 | P0 Critical |
| AI/ML quality | 3 | P0-P1 |
| **Total** | **22** | — |

## New Dependencies

Add to your `requirements.txt` or install manually:

```bash
pip install tiktoken aiosmtplib redis pyotp
```

## Environment Variables (New/Changed)

| Variable | Status | Default | Notes |
|----------|--------|---------|-------|
| `AUDIT_HMAC_KEY` | **Required in prod** | — | Was optional, now fails closed |
| `OUTLOOK_SENDER_UPN` | Required for Outlook | — | Sender UPN for app-only flow |
| `ABAC_FAIL_OPEN` | Optional | `false` | Was implicit `true` for reads |
| `REDIS_URL` | Recommended | `redis://redis:6379/0` | For PKCE/MFA persistence |
| `RERANKER_CROSS_ENCODER` | Optional | `BAAI/bge-reranker-v2-m3` | Was English-only model |
| `PKCE_STATE_TTL` | Optional | `600` | PKCE state TTL in seconds |

## Verification

After deploying v0.1.0, verify these fixes:

1. **workflow_engine**: `POST /workflows/run` with a `rag` step — should return actual results (not empty).
2. **governance**: `POST /v1/access/check` with forged `subject.role: "super_admin"` — should be denied.
3. **auth_service**: Restart auth_service pod — in-flight logins should survive (PKCE in Redis).
4. **rag_engine**: `POST /v1/answer/stream` — TTFT should be < 1s (not full generation time).
5. **llm_gateway**: Check Ollama logs — should see `/api/chat` calls (not `/api/generate`).
6. **multi_agents**: `POST /v1/run` — response should include `"reflection_activated": true`.
7. **approvals**: Create approval — notification should complete in < 1s (not 30s).
8. **Prometheus**: Check `http://prometheus:9090/api/v1/rules` — should show alert rules.
