 # HSAAI Enterprise AI Platform

**Hayel Saeed Anam Artificial Intelligence (HSAAI)**

HSAAI is a secure, governed **Enterprise AI Platform** designed as the digital intelligence layer for **HSA Group**. The platform integrates enterprise knowledge, operational data, business applications, AI models, and intelligent agents to deliver secure and scalable **Artificial Intelligence capabilities** across corporate departments.

HSAAI combines **Large Language Models (LLMs)**, **Retrieval-Augmented Generation (RAG)**, AI agents, enterprise knowledge management, workflow automation, and security governance within a unified internal AI architecture.

## Platform Overview

HSAAI provides an enterprise-grade foundation for deploying secure and governed AI applications while maintaining strict controls over corporate data, identity, access, and AI operations.

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js + React + TypeScript |
| Backend | FastAPI + Python 3.12 |
| AI Layer | LLM Gateway + RAG Engine + Agent Framework |
| Knowledge Layer | Enterprise Knowledge Base + Vector Search + Retrieval-Augmented Generation |
| Data Layer | PostgreSQL + Qdrant Vector Database + Redis |
| Infrastructure | Docker + Kubernetes (VMware Tanzu) |
| Identity & Access | Keycloak OIDC + RBAC + ABAC |
| Security | Vault + Zero Trust + PII Protection + Policy Enforcement |
| AI Governance | AI Governance + Security Controls + Auditability |

## Core Capabilities

HSAAI is designed to provide secure enterprise AI capabilities including:

* **Enterprise AI** — Secure artificial intelligence services for internal business operations.
* **Retrieval-Augmented Generation (RAG)** — Context-aware AI responses grounded in enterprise knowledge.
* **Large Language Model (LLM) Integration** — Centralized model routing and inference through the LLM Gateway.
* **AI Agents** — Department-specific AI agents for specialized business workflows and tasks.
* **Enterprise Knowledge Management** — Secure ingestion, indexing, retrieval, and governance of organizational knowledge.
* **Workflow Automation** — AI-assisted business process orchestration and automation.
* **AI Governance** — Policy enforcement, authorization, auditability, and responsible AI controls.
* **Identity and Access Management** — Centralized authentication and authorization using Keycloak OIDC.
* **Role-Based and Attribute-Based Access Control** — RBAC and ABAC controls for enterprise resources and AI capabilities.
* **PII Protection** — Detection and filtering of personally identifiable information.
* **Vector Search** — Semantic retrieval using Qdrant Vector Database.
* **Enterprise Security** — Defense-in-depth security controls for internal AI workloads and corporate data.

## Enterprise Architecture

The HSAAI architecture separates the platform into specialized layers:

1. **Presentation Layer** — Web-based enterprise AI interfaces built with Next.js, React, and TypeScript.
2. **API Layer** — Secure API Gateway and backend services responsible for request routing, authentication, and business logic.
3. **AI Layer** — LLM Gateway, RAG Engine, AI agents, and model orchestration services.
4. **Knowledge Layer** — Enterprise document processing, indexing, embeddings, vector search, and retrieval.
5. **Data Layer** — PostgreSQL, Qdrant, Redis, and other enterprise data services.
6. **Security Layer** — Keycloak, RBAC, ABAC, Vault, PII protection, and security policies.
7. **Infrastructure Layer** — Docker and Kubernetes-based infrastructure designed for enterprise deployment.

## Documentation

All technical documentation is located in [`/docs`](docs/):

| Document | Purpose |
|-----------|---------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Enterprise AI architecture and component design |
| [SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) | Detailed system architecture, services, and data flows |
| [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | Production deployment and infrastructure procedures |
| [SECURITY_MODEL.md](docs/SECURITY_MODEL.md) | Authentication, authorization, security, and data protection |
| [API_REFERENCE.md](docs/API_REFERENCE.md) | API contracts, services, and endpoint documentation |
| [OPERATIONS_GUIDE.md](docs/OPERATIONS_GUIDE.md) | Production operations, monitoring, and operational runbooks |
| [AI_ENGINE_DOCUMENTATION.md](docs/AI_ENGINE_DOCUMENTATION.md) | AI pipeline, model architecture, and inference services |
| [RAG_ARCHITECTURE.md](docs/RAG_ARCHITECTURE.md) | Retrieval-Augmented Generation architecture and knowledge retrieval |
| [AGENT_FRAMEWORK.md](docs/AGENT_FRAMEWORK.md) | AI agent architecture and department-specific agents |
| [CHANGE_MANAGEMENT.md](docs/CHANGE_MANAGEMENT.md) | Release, versioning, and enterprise change management |

## Quick Start

```bash
# Configure the environment
cp .env.example .env

# Build the platform services
docker compose build

# Start the platform
docker compose up -d

# Run database migrations
docker compose exec backend-core alembic upgrade head

# Verify VMware infrastructure readiness
python3 hsaai-vmware-readiness.py

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
