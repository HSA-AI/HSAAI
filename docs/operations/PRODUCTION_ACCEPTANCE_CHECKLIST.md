# Production Acceptance Checklist

A deployment is accepted only when all gates below pass.

## 1. Infrastructure

- [ ] Docker Compose production stack starts cleanly.
- [ ] Kubernetes namespace deploys with Helm without manual patching.
- [ ] PostgreSQL, Redis, Qdrant, Keycloak, backend services, frontend, monitoring are healthy.
- [ ] No private database/vector/cache ports are exposed externally.
- [ ] Persistent volumes are configured for PostgreSQL, Qdrant, uploads, model cache, and audit logs.

## 2. Local AI

- [ ] Ollama is reachable only from internal network.
- [ ] At least one model is loaded: `qwen2.5`, `llama3.1`, or `mistral`.
- [ ] LLM gateway rejects external providers when `STRICT_INTERNAL_ONLY=true`.
- [ ] Chat endpoint streams responses end-to-end from UI to local LLM.

## 3. RAG

- [ ] User can upload PDF/TXT/DOCX from frontend.
- [ ] Document is stored locally and encrypted at rest.
- [ ] Text extraction succeeds.
- [ ] Chunking succeeds.
- [ ] Embeddings are generated internally.
- [ ] Chunks are stored in Qdrant with tenant/workspace isolation.
- [ ] Hybrid search returns relevant results.
- [ ] RAG answers cite source document and chunk metadata.

## 4. Identity and Access

- [ ] Keycloak realm imported.
- [ ] MFA policy enabled for admin roles.
- [ ] LDAP/AD federation tested or explicitly disabled.
- [ ] RBAC enforces role permissions.
- [ ] Users cannot access documents outside their workspace.

## 5. Security

- [ ] Secrets are not committed in plain text.
- [ ] NetworkPolicy denies egress by default in internal-only mode.
- [ ] Audit logs are written for login, upload, search, chat, admin changes, and policy changes.
- [ ] Security headers are enabled at gateway/frontend.
- [ ] File upload type and size validation enabled.
- [ ] Encryption keys are rotated according to policy.

## 6. Observability

- [ ] Prometheus scrapes all services.
- [ ] Grafana dashboards show API latency, token usage, RAG ingestion, queue depth, GPU/CPU, and errors.
- [ ] OpenTelemetry traces are emitted.
- [ ] Alerts exist for failed login spikes, model unavailable, RAG ingestion failure, disk pressure, and high latency.

## 7. Testing

- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Security tests pass.
- [ ] Load tests meet target concurrency.
- [ ] Backup/restore test completed.
- [ ] Disaster recovery drill completed.

## Final Release Gate

Run:

```bash
./scripts/production_release_gate.sh
```

The system can be considered enterprise production-ready only after the script passes and manual infrastructure checks are documented.
