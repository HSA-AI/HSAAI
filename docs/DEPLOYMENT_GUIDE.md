# HSAAI Deployment Guide

## 1. Prerequisites

### Infrastructure
- VMware vSphere 8.0+ with 4 clusters (Management, AI, Application, Data)
- 14 ESXi hosts minimum
- 16 NVIDIA A100 80GB GPUs (4 per AI host)
- 100 GbE spine-leaf network

### Software
- Docker 24+
- Kubernetes 1.28+ (VMware Tanzu recommended)
- Helm 3.12+
- kubectl 1.28+

## 2. Docker Compose Deployment (Development/Staging)

```bash
# Configure environment
cp .env.example .env
# Edit .env with production values (use Vault references for secrets)

# Build all services
docker compose build

# Start all services
docker compose up -d

# Run database migrations
docker compose exec backend-core alembic upgrade head

# Verify health
curl http://localhost:8000/health
python3 hsaai-vmware-readiness.py
```

## 3. Kubernetes Deployment (Production)

### 3.1 Apply Manifests
```bash
kubectl apply -k deploy/overlays/production
```

### 3.2 Verify Deployment
```bash
kubectl get pods -n hsaai-prod
kubectl rollout status deployment/rag-engine -n hsaai-prod
kubectl rollout status deployment/llm-gateway -n hsaai-prod
```

## 4. Environment Configuration

### Required Variables
| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | Database password | Vault reference |
| `QDRANT_URL` | Qdrant endpoint | `http://qdrant:6333` |
| `REDIS_URL` | Redis endpoint | `redis://redis:6379/0` |
| `OPENAI_API_KEY` | OpenAI API key | Vault reference |
| `KEYCLOAK_ISSUER` | Keycloak realm URL | `https://auth.hsaai.internal/realms/hsaai` |
| `CORS_ALLOW_ORIGINS` | Allowed origins | `https://hsaai.internal` |

### Brand Configuration
| Variable | Value |
|----------|-------|
| Primary Color | `#F4C430` |
| Dark Gold | `#A67C00` |
| Black | `#111111` |
| White | `#FFFFFF` |
| Logo Path | `/brand/hsaai-logo.png` |

## 5. Health Checks

| Endpoint | Purpose |
|----------|---------|
| `GET /health/live` | Liveness probe |
| `GET /health/ready` | Readiness probe (checks dependencies) |
| `GET /metrics` | Prometheus metrics |
| `GET /health` | Overall health status |

## 6. Post-Deployment Verification

```bash
# Check all services
python3 hsaai-vmware-readiness.py

# Check wiring
python3 hsaai-validate-wiring.py --project-root .

# Test RAG query
curl -X POST http://localhost:8000/rag/query \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the annual leave policy?"}'
```
