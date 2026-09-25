# HSAAI — Enterprise AI Operating System

**Enterprise AI Platform for RAG · AI Agents · Knowledge Management · Workflow Automation · AI Governance · MLOps · Kubernetes**

HSAAI is a modular **Enterprise Artificial Intelligence Operating System** designed for secure organizational knowledge discovery, Retrieval-Augmented Generation (RAG), intelligent assistants, multi-agent workflows, enterprise automation, governed LLM operations, MLOps, and cloud-native deployment.

**HSAAI (Hayel Saeed Anam Artificial Intelligence)** is designed around the enterprise requirements of **Hayel Saeed Anam & Co. (HSA Group)** and brings together organizational knowledge, conversational AI, RAG, AI agents, workflow approvals, enterprise integrations, security controls, and observability in a unified architecture.

منصة **HSAAI** هي نظام تشغيل للذكاء الاصطناعي المؤسسي يجمع بين إدارة المعرفة، وتقنيات RAG، والوكلاء الأذكياء، وأتمتة سير العمل، وحوكمة الذكاء الاصطناعي، وإدارة النماذج، والتكاملات المؤسسية ضمن بنية موحدة وآمنة وقابلة للتوسع.

> **Release status: Production Candidate — validation in progress.**
>
> Latest verified coverage evidence from the active production-hardening work reports **17,302 Python statements, 11,420 covered statements, and 66.00% coverage**.
>
> The enforced production coverage target remains **≥80%**, requiring **2,422 additional covered statements** at the current measured code size.
>
> Docker build validation, dependency auditing, continuous integration, and the current security-validation workflow are passing. The **Full Backend Coverage** check remains open. Full runtime acceptance, remaining E2E validation, real Kubernetes deployment, production secrets validation, and final production approval remain separate release gates.

**Enterprise AI · Retrieval-Augmented Generation · AI Agents · Multi-Agent Systems · Knowledge Graphs · LLM Gateway · Workflow Automation · AI Governance · MLOps · DevSecOps · Kubernetes · Observability**

[Overview](#overview--نظرة-عامة) ·
[Capabilities](#platform-capabilities--قدرات-المنصة) ·
[AI & RAG](#enterprise-ai--rag) ·
[AI Agents](#ai-agents--multi-agent-orchestration) ·
[Architecture](#architecture) ·
[Security](#security) ·
[Deployment](#deployment) ·
[Testing](#testing--release-evidence) ·
[Documentation](#documentation)

---

## Overview | نظرة عامة

HSAAI is a modular **enterprise AI platform** for connecting organizational knowledge, internal business systems, Large Language Models (LLMs), AI agents, and automated workflows through governed APIs and enterprise user experiences.

The platform is designed to support secure access to enterprise knowledge while providing AI-assisted search, conversational interfaces, intelligent automation, model orchestration, governance controls, observability, and cloud-native deployment capabilities.

HSAAI منصة ذكاء اصطناعي مؤسسية معيارية تهدف إلى ربط المعرفة المؤسسية والأنظمة الداخلية ونماذج اللغة الكبيرة والوكلاء الأذكياء وسير العمل الآلي ضمن بيئة موحدة.

تركز المنصة على الوصول الآمن للمعرفة، والبحث الذكي، والمحادثة المؤسسية، وأتمتة الأعمال، وإدارة النماذج، والحوكمة، والمراقبة، وقابلية التوسع.

---

## Platform Capabilities | قدرات المنصة

| Area | Capabilities represented in the repository |
|---|---|
| Enterprise AI | LLM integration, model routing, intelligent assistants and governed AI operations |
| Enterprise Knowledge | Document ingestion, embeddings, RAG, hybrid retrieval and knowledge discovery |
| AI Agents | Agent routing, tool execution, specialized agents and multi-agent orchestration |
| Knowledge Graph | Graph-oriented knowledge integration and Neo4j components |
| Workflow Automation | Workflow execution, approvals and human-in-the-loop processes |
| AI Governance | Policy controls, audit capabilities, security validation and responsible AI components |
| Identity & Access | Authentication, authorization, RBAC, ABAC and identity-provider integration |
| MLOps | Model training, evaluation, registry and model lifecycle components |
| Enterprise Integrations | Internal-system connectors, data integration and extensible connector architecture |
| Observability | Metrics, logs, traces, monitoring and distributed observability |
| Infrastructure | Docker Compose, Kubernetes, Helm and infrastructure-as-code assets |
| User Experience | Next.js enterprise web application with Arabic and RTL-oriented support |

These capabilities describe components represented in the repository. Availability in a specific environment depends on the active deployment profile, infrastructure, configuration, secrets, and validation evidence.

---

## Enterprise AI & RAG

### Retrieval-Augmented Generation

HSAAI includes a Retrieval-Augmented Generation architecture intended to connect Large Language Models with enterprise knowledge.

Repository components cover areas such as:

- document ingestion and processing
- text extraction and chunking
- embeddings
- vector retrieval
- hybrid search
- reranking
- citation-oriented retrieval workflows
- tenant-aware access controls
- Retrieval-Augmented Generation pipelines
- enterprise knowledge discovery

The RAG architecture is designed to support organizational documents and internal knowledge while keeping retrieval and access controls separate from unrestricted model generation.

### RAG technology components

Technologies represented in the architecture include:

**Qdrant · PostgreSQL · Redis · document loaders · embedding services · reranking · LLM gateways · knowledge graph integration**

---

## AI Agents & Multi-Agent Orchestration

HSAAI includes agent-oriented architecture for intelligent enterprise task execution.

The repository contains components for:

- specialized AI agents
- supervisor and routing logic
- multi-agent orchestration
- agent tools
- workflow coordination
- memory components
- reasoning components
- agent execution policies
- task decomposition
- enterprise agent integrations
- human approval workflows

The platform is intended to allow multiple specialized AI capabilities to cooperate while remaining governed by authentication, authorization, policy and audit controls.

---

## Enterprise Knowledge Management

HSAAI combines multiple approaches to enterprise knowledge management.

### Vector Knowledge

Vector retrieval components are represented through **Qdrant** and related embedding, search and reranking services.

### Knowledge Graph

Graph-oriented capabilities are represented through **Neo4j** and knowledge-graph repository, ontology, ingestion and query components.

### Enterprise Search

The architecture includes enterprise search services designed to combine organizational content with access-control and application context.

### Document Knowledge

The repository includes document-processing paths intended for structured and unstructured enterprise information.

---

## LLM Gateway & Model Routing

HSAAI includes an LLM gateway layer designed to separate enterprise applications from direct model-provider dependencies.

Capabilities represented in the repository include:

- model routing
- controlled model access
- request handling
- generation services
- provider abstraction
- model-selection logic
- local-model integration
- evaluation and quality components

The architecture includes support-oriented components for technologies such as **Ollama** and other model-serving paths represented by the repository configuration.

---

## Workflow Automation

The platform includes workflow and approval components for combining AI execution with enterprise business processes.

Areas represented include:

- workflow execution
- automated task processing
- approval workflows
- human-in-the-loop validation
- agent-assisted workflows
- enterprise operations
- event-driven processing
- business-system integration

This architecture is intended to keep sensitive or high-impact actions subject to policy and authorization controls.

---

## AI Governance

HSAAI includes governance components intended for enterprise AI environments.

Areas represented in the repository include:

- policy enforcement
- audit capabilities
- governance evaluation
- explainability components
- AI risk-management components
- access-control integration
- human approval workflows

---

## MLOps & Model Lifecycle

HSAAI includes model lifecycle and MLOps-oriented components.

Repository capabilities include:

- model training
- fine-tuning pipelines
- model evaluation
- model registry
- model routing
- quality evaluation
- MLflow-oriented integrations
- model lifecycle workflows

Supporting infrastructure represented in the repository includes technologies such as:

**MLflow · Ollama · object storage · PostgreSQL · monitoring services**

---

## Architecture

The repository is organized into applications, backend services, shared packages, infrastructure, tests and operational documentation.

```text
HSAAI/
├── apps/
│   └── web/                     # Enterprise web application
│
├── services/
│   ├── api_gateway/             # API gateway and request controls
│   ├── auth_service/            # Authentication and identity integration
│   ├── backend_core/            # Core enterprise application services
│   ├── governance/              # AI governance and policy services
│   ├── llm_gateway/             # LLM routing and model access
│   ├── model_training/          # Model training and registry
│   ├── multi_agents/            # Agent and multi-agent orchestration
│   ├── pii_detector/            # PII-oriented processing
│   ├── rag_engine/              # Enterprise RAG engine
│   └── workflow_engine/         # Workflow execution
│
├── packages/
│   └── common/                  # Shared AI, security and observability packages
│
├── infrastructure/
│   ├── docker/                  # Container infrastructure
│   ├── kubernetes/              # Kubernetes resources
│   ├── helm/                    # Helm deployment assets
│   ├── monitoring/              # Monitoring configuration
│   └── vault/                   # Secrets-management integration
│
├── alembic/                     # Database migrations
├── benchmarks/                  # Performance and benchmark assets
├── demo-runtime/                # Demonstration runtime components
├── deployment/                  # Deployment assets
├── docs/                        # Technical documentation
├── evals/                       # AI evaluation assets
├── examples/                    # Usage examples
├── tests/                       # Automated test suites
├── scripts/                     # Engineering and validation scripts
├── runbooks/                    # Operational runbooks
└── .github/workflows/           # CI/CD and validation workflows
```

---

## Main Application Services

| Service | Responsibility |
|---|---|
| `web` | Enterprise web user experience |
| `api-gateway` | API routing, request controls and gateway operations |
| `backend-core` | Central enterprise application APIs |
| `auth-service` | Authentication and identity integration |
| `rag-engine` | Retrieval-Augmented Generation and enterprise knowledge retrieval |
| `llm-gateway` | LLM access and model routing |
| `multi_agents` | AI agent coordination and tool execution |
| `workflow-engine` | Workflow execution and approvals |
| `governance` | Governance, policy and audit-oriented functionality |
| `model-training` | Model lifecycle, training and registry components |

Service availability depends on the selected deployment profile.

The presence of a service directory does not necessarily mean that the service is enabled in every runtime environment.

---

## Data & Infrastructure Integrations

Repository configuration includes components or integrations for:

- **PostgreSQL** — relational application and operational data
- **Redis** — caching, state and supporting runtime functionality
- **Qdrant** — vector storage and semantic retrieval
- **Neo4j** — knowledge graph storage and graph-oriented operations
- **Kafka** — event streaming and asynchronous integration
- **MinIO** — S3-compatible object storage
- **Keycloak** — identity and access-management integration
- **Ollama** — local-model and LLM-serving integration
- **MLflow** — model lifecycle and MLOps integration

---

## Observability Stack

HSAAI contains observability-related configuration and shared components for application metrics, infrastructure metrics, logs, distributed traces, dashboards and operational monitoring.

Technologies represented include:

**Prometheus · Grafana · Loki · Tempo · Thanos**

These integrations require appropriate deployment configuration and runtime validation.

---

## Deployment

HSAAI contains deployment assets for containerized and Kubernetes-oriented environments.

### Docker

A Linux host with a working Docker Engine and Docker Compose v2 is recommended for container-based validation.

```bash
cp .env.example .env

docker compose config --quiet
docker compose ps --all
```

Do not commit production credentials or real secrets to the repository.

Termux without a Docker daemon should not be considered a production runtime host.

### Kubernetes

Kubernetes assets are located under:

```text
infrastructure/kubernetes/
infrastructure/helm/
```

Production Kubernetes deployment should include:

- approved container images
- secure secret management
- persistent storage
- resource requests and limits
- readiness probes
- liveness probes
- service configuration
- ingress configuration
- network controls
- monitoring
- backup procedures
- disaster-recovery validation

The presence of manifests or Helm charts does not constitute evidence that a real cluster deployment has passed acceptance testing.

### Enterprise Infrastructure

The full enterprise architecture may include:

```text
PostgreSQL
Redis
Qdrant
Neo4j
Kafka
MinIO
Keycloak
Ollama
MLflow
Prometheus
Grafana
Loki
Tempo
Thanos
Vault
```

Running the complete stack requires sufficient CPU, RAM, storage and network capacity.

---

## Security

HSAAI contains security-oriented application and infrastructure components.

Security areas represented include:

- Authentication
- Authorization
- RBAC
- ABAC
- JWT validation
- Tenant isolation
- Policy enforcement
- PII handling
- Audit logging
- Prompt safety
- Output filtering
- Secrets management
- Dependency auditing
- Security validation
- Network-aware controls

Before production approval, deployment-specific evidence should verify identity-provider configuration, authorization boundaries, tenant separation, secret storage and rotation, dependency vulnerabilities, container-image vulnerabilities, network exposure, TLS configuration, audit-log integrity, backups, disaster recovery, production credentials and operational access controls.

Never disclose credentials, private keys, tokens or exploitable security findings in public issues.

See `SECURITY.md` and `docs/security/` where applicable.

---

## Testing & Release Evidence

HSAAI includes automated testing across backend services, shared packages, security controls, integrations and release validation.

### Current Verified Coverage Snapshot

Latest available coverage evidence from the current production-hardening work:

| Metric | Current evidence |
|---|---:|
| Python statements | **17,302** |
| Covered statements | **11,420** |
| Missing statements | **5,882** |
| Python coverage | **66.00%** |
| Required coverage | **≥80%** |
| Covered statements required for 80% | **13,842** |
| Additional covered statements required | **2,422** |

The production coverage threshold has **not yet been reached**.

Coverage is being increased through meaningful behavioral and unit tests rather than by lowering the threshold or excluding production modules solely to satisfy the gate.

### Current CI Status

The active production-hardening validation currently shows:

| Check | Status |
|---|---|
| Docker Build Validation | ✅ Passing |
| Production Dependency Audit — Python | ✅ Passing |
| Production Dependency Audit — Frontend | ✅ Passing |
| Continuous Integration | ✅ Passing |
| Security Validation | ✅ Passing |
| Full Backend Coverage | ❌ Coverage gate still open |

The failed coverage check indicates that the enforced coverage requirement has not yet reached the required **80%** threshold.

### Production Approval Gates

HSAAI should only be described as **Production Ready / Production Approved** after the required evidence has been completed for the intended deployment.

Remaining release validation includes:

- ≥80% Python coverage
- remaining E2E execution on the required runtime services
- full enterprise-stack validation
- service-to-service connectivity verification
- persistence validation
- Kubernetes real-cluster deployment
- ingress and health-check validation
- production secrets management
- vulnerability and security review
- backup and recovery validation
- final acceptance approval

Until those gates are complete, the appropriate release description is:

> **Production Candidate — validation in progress**

---

## Engineering Principles

### Modularity

AI, RAG, agent, workflow, governance and infrastructure capabilities are separated into modular services and shared packages.

### Security by Design

Authentication, authorization, policy enforcement, tenant boundaries and audit functionality are treated as architectural concerns.

### Enterprise Governance

AI execution should remain subject to policy, logging, access control and human approval where required.

### Observability

Operational metrics, logs and traces are represented across the platform architecture.

### Cloud-Native Deployment

Docker, Kubernetes and Helm assets support container-oriented deployment workflows.

### Extensibility

Connector, tool, agent and integration components are designed to allow expansion as organizational requirements evolve.

---

## Technology Stack

### AI & Machine Learning

- Large Language Models
- Retrieval-Augmented Generation
- AI Agents
- Multi-Agent Systems
- Embeddings
- Vector Search
- Reranking
- Knowledge Graphs
- MLOps
- Model Evaluation
- Model Registry

### Backend

- Python
- FastAPI
- PostgreSQL
- Redis
- Kafka
- Qdrant
- Neo4j

### Frontend

- Next.js
- Enterprise Web UI
- Arabic / RTL-oriented experience

### Identity & Security

- Keycloak
- JWT
- RBAC
- ABAC
- Vault
- Audit Logging
- Policy Enforcement
- PII Controls

### Infrastructure

- Docker
- Docker Compose
- Kubernetes
- Helm
- MinIO

### Observability

- Prometheus
- Grafana
- Loki
- Tempo
- Thanos

### MLOps

- MLflow
- Ollama
- Model Training
- Model Evaluation
- Model Registry

---

## Documentation

Important repository resources include:

| Resource | Purpose |
|---|---|
| `START_HERE_AR.md` | Arabic starting point and handover information |
| `FINAL_PRODUCTION_READINESS_REPORT.md` | Release-readiness evidence and open items |
| `QUICKSTART.md` | Getting started |
| `CHANGELOG.md` | Change history |
| `SECURITY.md` | Security reporting and security guidance |
| `docs/` | Architecture, security, API and engineering documentation |
| `runbooks/` | Operational procedures |
| `infrastructure/` | Infrastructure and deployment assets |
| `.github/workflows/` | CI/CD and validation workflows |

Historical reports should be interpreted according to the commit and release snapshot for which they were generated.

Current validation evidence should take precedence over older test and coverage numbers.

---

## Project Status

HSAAI is currently under active **production-hardening and validation**.

| Area | Status |
|---|---|
| Architecture | ✅ Implemented in repository |
| Enterprise AI services | ✅ Implemented in repository |
| RAG components | ✅ Implemented in repository |
| AI agent components | ✅ Implemented in repository |
| Governance components | ✅ Implemented in repository |
| Docker Build Validation | ✅ Passing |
| Dependency Audits | ✅ Passing |
| Continuous Integration | ✅ Passing |
| Security Validation | ✅ Passing |
| Python Coverage | 🚧 **66.00% / target ≥80%** |
| Full Enterprise Runtime Validation | 🚧 Pending final evidence |
| Remaining E2E Validation | 🚧 Pending runtime services |
| Real Kubernetes Acceptance | 🚧 Pending |
| Final Production Approval | 🚧 Not yet granted |

---

## Repository Scope

HSAAI is designed around the enterprise AI requirements of **Hayel Saeed Anam & Co. (HSA Group)**.

Its architecture demonstrates how organizational knowledge, intelligent assistants, enterprise RAG, AI agents, automation, governance, MLOps and infrastructure operations can be integrated into a unified enterprise AI platform.

---

## License

Review the repository's `LICENSE` for the applicable rights, restrictions and permitted usage.

The README does not grant rights beyond those defined by the repository license.

---

# HSAAI

**Enterprise Artificial Intelligence Operating System**

**Enterprise AI · RAG · AI Agents · Knowledge Management · Knowledge Graphs · Workflow Automation · AI Governance · MLOps · DevSecOps · Kubernetes · Observability**

منصة ذكاء اصطناعي مؤسسية متكاملة للمعرفة، والوكلاء الأذكياء، وRAG، وأتمتة الأعمال، والحوكمة، وإدارة النماذج، والبنية التحتية المؤسسية.
