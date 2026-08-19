# HSAAI — Production Runbook

## 1. Internal-only deployment
Use `docker-compose.production.yml` for a private single-server deployment. Services bind to `127.0.0.1` unless exposed through a private reverse proxy/VPN.

```bash
cp .env.production.example .env
# edit secrets
sudo docker compose -f docker-compose.production.yml up -d --build
```

## 2. Local LLM
Default provider is Ollama.

```bash
docker compose -f docker-compose.production.yml exec ollama ollama pull qwen2.5:7b-instruct
# optional alternatives:
# ollama pull llama3.1:8b
# ollama pull mistral:7b
```

No OpenAI/Anthropic/Google/Mistral hosted API keys are required or allowed in strict mode.

## 3. RAG with Qdrant
Upload from the Knowledge page or call:

```bash
curl -F file=@policy.txt -F tenant_id=default -F workspace_id=default http://127.0.0.1:8000/v1/rag/upload
curl -X POST http://127.0.0.1:8000/v1/rag/search -H 'Content-Type: application/json' -d '{"query":"policy","workspace_id":"default"}'
```

## 4. Keycloak
Import `infrastructure/keycloak/hsaai-realm.json`. Enable OTP for admin roles. Connect LDAP/AD through Keycloak User Federation.

## 5. Security baseline
- `INTERNAL_ONLY_MODE=true`
- `ALLOW_EXTERNAL_AI=false`
- NetworkPolicy default deny egress
- Secrets managed through Kubernetes secrets or external vault
- Audit all admin/security/RAG operations

## 6. Kubernetes
Use Helm values:

```bash
helm upgrade --install hsaai ./deployment/helm -f deployment/helm/values-production.yaml -n hsaai --create-namespace
```

## 7. Tests
```bash
python -m compileall backend llm_gateway rag_engine auth_service multi_agents document_ai voice_ai
pytest tests -q
locust -f tests/load/locustfile.py --host http://127.0.0.1:8000
```

## 8. Production hardening checklist
- Replace all CHANGE_ME secrets
- Enable TLS through private ingress
- Configure backups for PostgreSQL/Qdrant
- Pull local models before air-gap
- Enable Grafana/Prometheus/Sentry/OpenTelemetry collectors
- Run Bandit, pip-audit, and container scanning
