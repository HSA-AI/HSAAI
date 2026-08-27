# HSAAI Enterprise AI Platform

**Hayel Saeed Anam Artificial Intelligence (HSAAI)**

HSAAI is a secure, governed **Enterprise AI Platform** designed to serve as the digital intelligence layer for **HSA Group**. The platform integrates enterprise knowledge, operational data, business applications, AI models, intelligent agents, and workflow automation to deliver secure, scalable, and governed **Artificial Intelligence capabilities** across corporate departments.

HSAAI combines **Large Language Models (LLMs)**, **Retrieval-Augmented Generation (RAG)**, AI agents, enterprise knowledge management, semantic search, workflow automation, identity and access management, security controls, and AI governance within a unified internal enterprise AI architecture.

## Platform Overview

HSAAI provides an enterprise-grade foundation for building, deploying, and operating secure internal AI applications while maintaining strict controls over corporate data, identity, access, AI models, and enterprise operations.

The platform is designed around security, governance, scalability, observability, data protection, and controlled AI adoption.

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js + React + TypeScript |
| Backend | FastAPI + Python 3.12 |
| AI Layer | LLM Gateway + RAG Engine + Agent Framework |
| Knowledge Layer | Enterprise Knowledge Base + Embeddings + Vector Search + RAG |
| Data Layer | PostgreSQL + Qdrant Vector Database + Redis |
| Identity & Access | Keycloak OIDC + RBAC + ABAC |
| Security | Vault + Zero Trust + PII Protection + Policy Enforcement |
| Infrastructure | Docker + Kubernetes + VMware Tanzu |
| AI Governance | Policy Enforcement + Auditability + Security Controls |
| Observability | Metrics + Logging + Monitoring + Audit Trails |

## Core Capabilities

HSAAI is designed to provide secure enterprise AI capabilities for internal business operations, knowledge access, automation, and intelligent decision support.

* **Enterprise AI** — Secure artificial intelligence capabilities for internal business operations and enterprise applications.
* **Retrieval-Augmented Generation (RAG)** — Context-aware AI responses grounded in trusted enterprise knowledge and organizational data.
* **Large Language Model (LLM) Integration** — Centralized model routing, inference, and AI model management through the LLM Gateway.
* **AI Agents** — Department-specific AI agents designed for specialized business workflows, tasks, and enterprise use cases.
* **Enterprise Knowledge Management** — Secure ingestion, processing, indexing, retrieval, and governance of organizational knowledge.
* **Semantic Search** — Intelligent knowledge discovery using embeddings and vector-based semantic retrieval.
* **Workflow Automation** — AI-assisted business process orchestration, automation, and workflow execution.
* **AI Governance** — Policy enforcement, authorization, auditability, responsible AI controls, and operational governance.
* **Identity and Access Management** — Centralized authentication and authorization using Keycloak OIDC.
* **Role-Based Access Control (RBAC)** — Role-based authorization for enterprise users, services, and resources.
* **Attribute-Based Access Control (ABAC)** — Attribute-based policy enforcement for fine-grained enterprise authorization.
* **PII Protection** — Detection, filtering, and protection of personally identifiable information.
* **Vector Search** — Semantic retrieval powered by Qdrant Vector Database.
* **Enterprise Security** — Defense-in-depth security controls protecting AI workloads, enterprise data, APIs, and infrastructure.
* **Internal AI Infrastructure** — Controlled AI services designed for private enterprise environments.
* **Auditability** — Security and operational auditing for enterprise AI activities and system events.

## Enterprise AI Architecture

The HSAAI architecture is organized into specialized layers to provide separation of concerns, security boundaries, scalability, and maintainability.

1. **Presentation Layer** — Web-based enterprise AI interfaces built with Next.js, React, and TypeScript.

2. **API Layer** — Secure API Gateway and backend services responsible for request routing, authentication, authorization, validation, rate limiting, and business logic.

3. **AI Layer** — LLM Gateway, RAG Engine, AI agents, model orchestration, and intelligent inference services.

4. **Knowledge Layer** — Enterprise document processing, ingestion, chunking, embeddings, indexing, vector search, retrieval, and knowledge governance.

5. **Data Layer** — PostgreSQL, Qdrant, Redis, and supporting enterprise data services.

6. **Security Layer** — Keycloak OIDC, RBAC, ABAC, Vault, PII protection, policy enforcement, security controls, and audit mechanisms.

7. **Workflow Layer** — Business process automation, workflow orchestration, task execution, and AI-assisted enterprise workflows.

8. **Infrastructure Layer** — Docker and Kubernetes-based infrastructure designed for enterprise deployment and VMware Tanzu environments.

9. **Observability Layer** — Monitoring, metrics, logging, health checks, security auditing, and operational visibility.

## AI and Machine Learning Architecture

HSAAI provides a modular AI architecture designed to support enterprise AI workloads and controlled internal model operations.

### Large Language Models

The platform provides a centralized architecture for integrating and routing requests to approved **Large Language Models (LLMs)**.

The LLM Gateway provides a controlled interface between enterprise applications and AI inference services.

### Retrieval-Augmented Generation

HSAAI uses **Retrieval-Augmented Generation (RAG)** to ground AI responses in enterprise knowledge.

The RAG architecture enables the platform to:

* Ingest enterprise documents.
* Process and normalize knowledge sources.
* Generate embeddings.
* Store vectors in a vector database.
* Perform semantic retrieval.
* Retrieve relevant enterprise context.
* Provide grounded context to AI models.
* Generate context-aware responses.
* Apply security and authorization controls.

### AI Agents

The Agent Framework provides a controlled runtime for specialized AI agents.

Agents can be designed for department-specific use cases such as:

* Enterprise knowledge assistance.
* Business process automation.
* Document analysis.
* Operational support.
* Enterprise research.
* Data analysis.
* Workflow execution.
* Internal productivity.

## Enterprise Knowledge Management

HSAAI provides a secure enterprise knowledge architecture for managing organizational information.

The knowledge pipeline can include:

1. Document ingestion.
2. File validation.
3. Content extraction.
4. Text normalization.
5. Document chunking.
6. Metadata extraction.
7. Embedding generation.
8. Vector indexing.
9. Semantic retrieval.
10. Access control enforcement.
11. Knowledge governance.
12. Audit logging.

Enterprise knowledge remains subject to identity, authorization, security, and governance policies.

## Security Architecture

Security is a core architectural requirement of HSAAI.

The platform follows a defense-in-depth approach that combines identity, authorization, network controls, data protection, application security, and auditability.

### Identity and Authentication

HSAAI integrates with **Keycloak OIDC** for centralized enterprise identity and authentication.

Authentication controls include:

* OpenID Connect (OIDC).
* Centralized identity management.
* Token-based authentication.
* Service authentication.
* Session security.
* Enterprise identity integration.

### Authorization

Authorization is implemented using multiple security controls:

* **RBAC** — Role-Based Access Control.
* **ABAC** — Attribute-Based Access Control.
* Resource-level authorization.
* Service-level authorization.
* Policy enforcement.
* Least-privilege access.

### Data Protection

The platform is designed to protect sensitive enterprise information through:

* Encryption.
* PII detection.
* Access control.
* Secure service communication.
* Audit logging.
* Secret management.
* Data isolation.
* Network segmentation.

## Zero Trust Architecture

HSAAI follows a **Zero Trust Architecture** approach based on the principle of continuously validating identity, authorization, and access.

Security decisions are designed around:

* Never trust by default.
* Verify identity.
* Enforce least privilege.
* Segment services.
* Restrict network access.
* Protect enterprise data.
* Monitor system activity.
* Audit security events.

The architecture aligns with principles described in **NIST SP 800-207 Zero Trust Architecture**.

## Enterprise Infrastructure

HSAAI supports containerized enterprise infrastructure using:

* Docker.
* Docker Compose.
* Kubernetes.
* VMware Tanzu.
* Private enterprise networks.
* Containerized application services.
* Internal AI infrastructure.

The architecture is designed to support development, testing, staging, and production environments.

## Platform Services

| Service | Port | Purpose |
|---------|------|---------|
| API Gateway | 8000 | Secure request routing, authentication, and API access |
| Backend Core | 8001 | Core business logic and platform orchestration |
| Auth Service | 8010 | Keycloak OIDC integration and authentication services |
| Governance Service | 8011 | ABAC policy enforcement and governance |
| PII Detector | 8012 | Personally identifiable information detection and protection |
| Agent Runtime | 8040 | AI agent execution environment |
| Workflow Engine | 8070 | Enterprise workflow automation and orchestration |
| RAG Engine | 8030 | Enterprise knowledge retrieval and RAG processing |
| LLM Gateway | 8090 | AI model routing and inference gateway |

## Data and Storage Technologies

| Technology | Purpose |
|-----------|---------|
| PostgreSQL | Relational enterprise application data |
| Qdrant | Vector database and semantic search |
| Redis | Caching, queues, and transient application data |
| Enterprise Knowledge Base | Managed organizational knowledge |
| Object Storage | Enterprise AI and document storage |
| Audit Storage | Security and operational audit data |

## Documentation

All technical documentation is located in [`/docs`](docs/).

| Document | Purpose |
|----------|---------|
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