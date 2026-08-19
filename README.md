# HSAAI Enterprise AI Platform

**Hayel Saeed Anam Artificial Intelligence**

HSAAI is an internal enterprise AI platform that serves as the digital intelligence layer for HSA Group. It integrates corporate knowledge, operational data, and enterprise systems to deliver secure, governed AI capabilities across all business departments.

## Platform Overview

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js + React + TypeScript |
| Backend | FastAPI (Python 3.11) |
| AI Layer | LLM Gateway + RAG Engine + Agent Framework |
| Data Layer | PostgreSQL + Qdrant Vector DB + Redis |
| Infrastructure | Docker + Kubernetes (VMware Tanzu) |
| Security | Keycloak OIDC + RBAC + ABAC + Vault |

## Documentation

All documentation is located in [`/docs`](docs/):

| Document | Purpose |
|----------|---------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture and component design |
| [SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) | Detailed system design and data flow |
| [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | Production deployment instructions |
| [SECURITY_MODEL.md](docs/SECURITY_MODEL.md) | Authentication, authorization, and data protection |
| [API_REFERENCE.md](docs/API_REFERENCE.md) | API contracts and endpoint documentation |
| [OPERATIONS_GUIDE.md](docs/OPERATIONS_GUIDE.md) | Production operations and runbooks |
| [AI_ENGINE_DOCUMENTATION.md](docs/AI_ENGINE_DOCUMENTATION.md) | AI pipeline and model architecture |
| [RAG_ARCHITECTURE.md](docs/RAG_ARCHITECTURE.md) | Retrieval-Augmented Generation design |
| [AGENT_FRAMEWORK.md](docs/AGENT_FRAMEWORK.md) | AI agent framework and department agents |
| [CHANGE_MANAGEMENT.md](docs/CHANGE_MANAGEMENT.md) | Release and change management process |

## Quick Start

```bash
# Configure environment
cp .env.example .env

# Build and start services
docker compose build
docker compose up -d

# Run database migrations
docker compose exec backend-core alembic upgrade head

# Verify deployment
python3 hsaai-vmware-readiness.py
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| API Gateway | 8000 | Request routing and authentication |
| Backend Core | 8001 | Core business logic and orchestration |
| RAG Engine | 8030 | Knowledge retrieval and generation |
| LLM Gateway | 8090 | LLM inference and model routing |
| Auth Service | 8010 | Keycloak OIDC integration |
| Governance Service | 8011 | ABAC policy enforcement |
| PII Detector | 8012 | Data protection and PII filtering |
| Workflow Engine | 8070 | Business process automation |
| Agent Runtime | 8040 | AI agent execution environment |

## Compliance

- ISO 27001:2022
- NIST AI Risk Management Framework
- OWASP ASVS Level 2
- CIS Docker Benchmark
- Zero Trust Architecture (NIST SP 800-207)

## Classification

**Internal Use Only** — This platform is private and restricted to HSA Group internal employees.

## License

© HSA Group · Information Technology
