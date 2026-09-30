# HSAAI — Enterprise AI Operating System

**Enterprise AI Platform for Secure RAG · Agentic AI · AI Agents · Multi-Agent Systems · Knowledge Graphs · Workflow Automation · AI Governance · LLMOps · MLOps · DevSecOps · Kubernetes**

[![Release](https://img.shields.io/github/v/release/HSA-AI/HSAAI?display_name=tag)](https://github.com/HSA-AI/HSAAI/releases/latest)
[![Final Release Gate](https://github.com/HSA-AI/HSAAI/actions/workflows/final-release-gate.yml/badge.svg)](https://github.com/HSA-AI/HSAAI/actions/workflows/final-release-gate.yml)
[![Enterprise E2E](https://github.com/HSA-AI/HSAAI/actions/workflows/enterprise-e2e.yml/badge.svg)](https://github.com/HSA-AI/HSAAI/actions/workflows/enterprise-e2e.yml)
[![Runtime Parity](https://github.com/HSA-AI/HSAAI/actions/workflows/production-runtime-parity.yml/badge.svg)](https://github.com/HSA-AI/HSAAI/actions/workflows/production-runtime-parity.yml)
[![Security](https://github.com/HSA-AI/HSAAI/actions/workflows/security-scan.yml/badge.svg)](https://github.com/HSA-AI/HSAAI/actions/workflows/security-scan.yml)

HSAAI is a modular **Enterprise Artificial Intelligence Operating System** for securely connecting organizational knowledge, Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), AI agents, multi-agent systems, knowledge graphs, enterprise workflows, model lifecycle management, governance, security and cloud-native infrastructure.

Designed around the enterprise AI requirements of **Hayel Saeed Anam & Co. (HSA Group)**, HSAAI provides a unified architecture for enterprise knowledge discovery, intelligent assistants, governed AI automation, AI agents, LLMOps, MLOps and Kubernetes-oriented deployment.

**Current Release: `HSAAI v4.0.0 — Production Release`**

> HSAAI v4.0.0 passed its automated engineering, security, dependency, coverage, enterprise runtime, E2E, production runtime parity, image supply-chain, package-integrity and final release gates.
>
> Real external Kubernetes cluster acceptance remains a separate deployment-specific operator gate.

---

## العربية

**HSAAI** منصة ذكاء اصطناعي مؤسسية متكاملة تجمع بين إدارة المعرفة، وRAG، والوكلاء الأذكياء، والأنظمة متعددة الوكلاء، والرسوم البيانية المعرفية، وأتمتة سير العمل، وحوكمة الذكاء الاصطناعي، وLLMOps، وMLOps، والبنية التحتية السحابية ضمن معمارية موحدة وآمنة وقابلة للتوسع.

**الإصدار الحالي: `HSAAI v4.0.0 — Production Release`**

اجتاز الإصدار بوابات الجودة والهندسة والأمان والاعتماديات والتغطية واختبارات Enterprise E2E وProduction Runtime Parity وسلسلة بناء الصور والتحقق النهائي من حزمة الإصدار.

يبقى الاختبار على **Kubernetes Cluster خارجي حقيقي** خطوة قبول تشغيلية مرتبطة ببيئة النشر المستهدفة.

---

## Release Status

| Area | Status |
|---|---|
| Current Release | ✅ `v4.0.0` |
| Release Type | ✅ Production Release |
| GitHub Release | ✅ Published |
| Enterprise E2E | ✅ Passed |
| Enterprise Runtime Acceptance | ✅ Passed |
| Production Runtime Parity | ✅ Passed |
| Final Release Gate | ✅ Passed |
| Backend Coverage Gate | ✅ Passed |
| Coverage Threshold | ✅ ≥ 80% |
| Docker Build Validation | ✅ Passed |
| Python Dependency Audit | ✅ Passed |
| Frontend Dependency Audit | ✅ Passed |
| Security Validation | ✅ Passed |
| Production Image Supply Chain | ✅ Passed |
| Kubernetes CI Acceptance | ✅ Passed |
| Clean Delivery Package | ✅ Passed |
| SHA-256 Artifact Integrity | ✅ Published |
| Real External Kubernetes Acceptance | 🚧 Deployment-specific operator gate |

The final v4.0.0 release branch completed **32 automated checks successfully with zero failures and zero pending checks** before merge.

---


## Current Validation Status

**Current release:** `HSAAI v4.0.0 — Production Release`
**Source version:** `v4.0.0`
**Release commit:** `80b78065d9a6623e98f4ef6e1411866776fdae0c`
**Last verified:** 30 September 2026
**Release status:** ✅ Published

| Quality / Release Gate | Verified Status |
|---|---|
| Final release PR validation | ✅ 32/32 successful · 0 failing · 0 pending |
| Full Backend Coverage | ✅ Passing |
| Required backend coverage | ✅ ≥80% enforced |
| Verified backend coverage snapshot | ✅ 80.43% |
| Docker Build Validation | ✅ Passing |
| Continuous Integration | ✅ Passing |
| Python Dependency Audit | ✅ Passing |
| Frontend Dependency Audit | ✅ Passing |
| Security Validation | ✅ Passing |
| Enterprise Runtime Acceptance | ✅ Passing |
| Enterprise E2E | ✅ Passing |
| Production Enterprise Wiring | ✅ Passing |
| Production Runtime Parity | ✅ Passing |
| Kubernetes CI Acceptance | ✅ Passing |
| Production Image Supply Chain | ✅ Passing |
| Final Release Gate | ✅ Passing |
| Release Source Integrity | ✅ Passing |
| Release Package Hygiene | ✅ Passing |
| GitHub Production Release | ✅ `v4.0.0` published |
| Release Artifact Integrity | ✅ SHA-256 published |
| Real External Kubernetes Acceptance | 🚧 Separate operator deployment gate |

### Release Artifact

**Artifact:** `HSAAI_v4.0.0.zip`

**SHA-256:**
`4e8e69695537adccbc969c4f7a3047ffd844cc46439d3cc86d055da9b6e9c2d2`

HSAAI v4.0.0 has completed its automated repository-level engineering, security, dependency, coverage, enterprise runtime, authenticated E2E, production enterprise wiring, production runtime parity, image supply-chain, package-integrity and final release validation.

The **HSAAI v4.0.0 Production Release is published**.

### Deployment Acceptance Boundary

Repository-level and software-release validation is complete for `v4.0.0`.

A real external Kubernetes cluster remains a separate environment-specific operator acceptance step. Production secrets, TLS, networking, persistent storage, backup, restore and disaster-recovery controls must be validated against the actual target infrastructure.

These deployment-specific activities are not represented as completed by GitHub CI alone.

---

## What is HSAAI?

HSAAI provides an enterprise AI control plane for connecting:

- Enterprise knowledge and documents
- Large Language Models
- Retrieval-Augmented Generation pipelines
- Intelligent assistants
- AI agents
- Multi-agent systems
- Knowledge graphs
- Enterprise workflows
- Internal business applications
- Identity and access-management systems
- Model training and evaluation pipelines
- Observability infrastructure
- Security and governance controls

The platform is designed so AI capabilities can operate under enterprise authentication, authorization, governance, auditing and observability.

---

## Core Capabilities

| Domain | Capabilities |
|---|---|
| Enterprise AI | LLM integration, intelligent assistants and governed AI execution |
| Enterprise RAG | Document ingestion, embeddings, retrieval, reranking and citations |
| AI Agents | Specialized agents, routing, tools and task execution |
| Multi-Agent Systems | Supervisor logic, agent coordination and orchestration |
| Knowledge Management | Enterprise search and organizational knowledge discovery |
| Knowledge Graphs | Neo4j-oriented graph integration and ontology |
| Workflow Automation | Automated workflows, approvals and human-in-the-loop |
| AI Governance | Policy, audit, evaluation and responsible AI controls |
| Identity & Access | Authentication, JWT, RBAC, ABAC and Keycloak integration |
| LLMOps | LLM routing, provider abstraction, controlled model access and evaluation |
| MLOps | Training, experiment tracking, evaluation, registry and lifecycle |
| Enterprise Integrations | Extensible connectors and internal-system integration |
| Observability | Metrics, logs, traces and dashboards |
| DevSecOps | CI/CD, security validation, dependency auditing and image supply chain |
| Cloud Native | Docker, Kubernetes, Helm and production infrastructure |
| Enterprise UX | Next.js web interface with Arabic and RTL-oriented support |

---

## Enterprise RAG

HSAAI provides a Retrieval-Augmented Generation architecture for securely connecting LLMs with enterprise knowledge.

Capabilities include:

- Document ingestion
- Text extraction
- Chunking
- Embeddings
- Vector retrieval
- Semantic search
- Hybrid search
- Reranking
- Citation-oriented retrieval
- Tenant-aware access controls
- Enterprise knowledge discovery
- Knowledge-graph augmentation

### RAG Technologies

**Qdrant · PostgreSQL · Redis · Embeddings · Reranking · LLM Gateway · Knowledge Graphs**

---

## AI Agents & Multi-Agent Orchestration

HSAAI includes an agent-oriented architecture for intelligent enterprise task execution.

Capabilities include:

- Specialized AI agents
- Supervisor and routing logic
- Multi-agent orchestration
- Agent tools
- Task decomposition
- Workflow coordination
- Memory components
- Reasoning components
- Agent execution policies
- Human approval workflows
- Enterprise integrations

AI agents operate behind authentication, authorization, governance and audit controls.

---

## Enterprise Knowledge

### Vector Knowledge
Qdrant-based vector retrieval supports semantic search and RAG workloads.

### Knowledge Graph
Neo4j-oriented components support graph-based organizational knowledge, ontology, ingestion and querying.

### Enterprise Search
Enterprise search combines organizational content, semantic retrieval and access-control context.

### Document Intelligence
Document-processing pipelines support structured and unstructured enterprise information.

---

## LLM Gateway

The HSAAI LLM Gateway separates enterprise applications from direct model-provider dependencies.

Capabilities include:

- Model routing
- Provider abstraction
- Controlled model access
- Generation services
- Model-selection logic
- Local-model integration
- Evaluation
- Quality controls

The architecture supports local model serving through technologies such as **Ollama** and extensible external model-provider integrations.

---

## Workflow Automation

HSAAI combines AI execution with enterprise business processes.

Capabilities include:

- Workflow execution
- Automated tasks
- Approval workflows
- Human-in-the-loop validation
- AI-assisted business processes
- Event-driven processing
- Enterprise-system integration

---

## AI Governance & Security

Security and governance are architectural layers within HSAAI.

Key areas include:

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
- AI evaluation
- Secrets management
- Dependency auditing
- Human approvals

See:

- `SECURITY.md`
- `docs/security/`

Never publish credentials, tokens, private keys or exploitable security findings through public issues.

---

## MLOps & Model Lifecycle

HSAAI includes model lifecycle capabilities for:

- Model training
- Fine-tuning pipelines
- Model evaluation
- Experiment tracking
- Model registry
- Model routing
- Quality evaluation
- Lifecycle workflows

Core technologies include:

**MLflow · Ollama · MinIO · PostgreSQL · Prometheus · Grafana**

---

## Architecture

```text
HSAAI/
├── apps/
│   └── web/                     # Enterprise Next.js application
├── services/
│   ├── api_gateway/
│   ├── auth_service/
│   ├── backend_core/
│   ├── governance/
│   ├── llm_gateway/
│   ├── model_training/
│   ├── multi_agents/
│   ├── pii_detector/
│   ├── rag_engine/
│   └── workflow_engine/
├── packages/
│   └── common/
├── infrastructure/
│   ├── docker/
│   ├── kubernetes/
│   ├── helm/
│   ├── monitoring/
│   └── vault/
├── alembic/
├── benchmarks/
├── demo-runtime/
├── deployment/
├── docs/
├── evals/
├── examples/
├── tests/
├── scripts/
├── runbooks/
└── .github/workflows/
```

---

## Enterprise Infrastructure

HSAAI integrates with enterprise infrastructure including:

- **PostgreSQL** — relational application data
- **Redis** — caching and runtime state
- **Qdrant** — vector search and semantic retrieval
- **Neo4j** — enterprise knowledge graphs
- **Kafka** — event streaming
- **MinIO** — S3-compatible object storage
- **Keycloak** — identity and access management
- **Vault** — secrets management
- **Ollama** — local LLM serving
- **MLflow** — MLOps and model lifecycle

### Observability

**Prometheus · Grafana · Loki · Tempo · Thanos**

---

## Technology Stack

### AI & Machine Learning

**LLMs · RAG · Agentic AI · AI Agents · Multi-Agent Systems · Embeddings · Vector Search · Reranking · Knowledge Graphs**

### Backend

**Python · FastAPI · PostgreSQL · Redis · Kafka · Qdrant · Neo4j**

### Frontend

**Next.js · TypeScript · Enterprise Web UI · Arabic / RTL**

### Identity & Security

**Keycloak · JWT · RBAC · ABAC · Vault · Audit Logging · Policy Enforcement · PII Controls**

### Infrastructure

**Docker · Docker Compose · Kubernetes · Helm · MinIO**

### MLOps & LLMOps

**MLflow · Ollama · Model Evaluation · Model Registry · Model Routing**

### DevSecOps & Observability

**GitHub Actions · Security Validation · Dependency Auditing · Coverage Gates · Prometheus · Grafana · Loki · Tempo · Thanos**

---

## Deployment

### Docker

A Linux environment with Docker Engine and Docker Compose v2 is recommended.

```bash
cp .env.example .env
docker compose config --quiet
docker compose ps --all
```

Never commit production credentials or real secrets.

> Termux without a Docker daemon is not considered a production runtime environment.

### Kubernetes

Deployment assets are available under:

```text
infrastructure/kubernetes/
infrastructure/helm/
```

Production deployment should provide:

- approved immutable images
- secure secrets management
- persistent storage
- resource requests and limits
- readiness and liveness probes
- ingress and TLS
- network controls
- monitoring and alerting
- backup and disaster recovery procedures

Repository CI validates Kubernetes assets and CI-oriented runtime scenarios.

> **Real external Kubernetes cluster acceptance remains a separate environment-specific operator deployment gate.**

---

## CI/CD & Quality Engineering

HSAAI uses GitHub Actions for automated engineering and release controls including:

- Continuous Integration
- Full Backend Coverage
- Docker Build Validation
- Python Dependency Audit
- Frontend Dependency Audit
- Security Validation
- Enterprise Runtime Acceptance
- Enterprise E2E
- Kubernetes CI Acceptance
- Production Runtime Parity
- Production Enterprise Wiring
- Production Image Supply Chain
- Final Release Gate
- Delivery Package Integrity

The final `v4.0.0` release branch completed **32 automated checks successfully with zero failures and zero pending checks** before merge.

### Coverage Policy

```text
Backend coverage threshold: ≥ 80%
```

The threshold is enforced by CI.

---

## Production Image Supply Chain

HSAAI production images cover application components including:

- API Gateway
- Auth Service
- Backend Core
- RAG Service
- LLM Gateway
- Agent Runtime
- Workflow Engine
- Alignment Service
- Governance Service
- MCP Server
- PII Detector
- Frontend

Production image workflows validate buildability and release-oriented image supply-chain requirements.

---

## Release Integrity

Current stable release:

**HSAAI v4.0.0 — Production Release**

Release controls include:

- source-integrity validation
- security validation
- dependency auditing
- coverage enforcement
- Enterprise E2E
- production runtime parity
- image supply-chain validation
- package hygiene
- ZIP integrity validation
- SHA-256 artifact verification

The final delivery package excludes private and runtime-only artifacts such as:

- `.git`
- private `.env` files
- `node_modules`
- dependency caches
- Python caches
- runtime databases
- temporary application state
- generated test/runtime artifacts

### Latest Release

https://github.com/HSA-AI/HSAAI/releases/tag/v4.0.0

---

## Documentation

| Resource | Purpose |
|---|---|
| `START_HERE_AR.md` | Arabic starting point and handover |
| `QUICKSTART.md` | Getting started |
| `CHANGELOG.md` | Release history |
| `SECURITY.md` | Security policy |
| `FINAL_PRODUCTION_READINESS_REPORT.md` | Readiness and validation evidence |
| `docs/` | Architecture, APIs, security and engineering documentation |
| `runbooks/` | Operational procedures |
| `infrastructure/` | Deployment and infrastructure assets |
| `.github/workflows/` | CI/CD and validation workflows |

Historical reports should be interpreted according to the release or commit for which they were generated.

Current CI and release evidence takes precedence over older validation snapshots.

---

## Project Status

| Area | Status |
|---|---|
| Software Release | ✅ v4.0.0 Production Release |
| Enterprise AI | ✅ Implemented |
| Enterprise RAG | ✅ Implemented |
| AI Agents | ✅ Implemented |
| Multi-Agent Architecture | ✅ Implemented |
| Knowledge Graph | ✅ Implemented |
| Workflow Automation | ✅ Implemented |
| AI Governance | ✅ Implemented |
| Backend Coverage Gate | ✅ Passed |
| Docker Validation | ✅ Passed |
| Dependency Audits | ✅ Passed |
| Security Validation | ✅ Passed |
| Enterprise Runtime Acceptance | ✅ Passed |
| Enterprise E2E | ✅ Passed |
| Production Runtime Parity | ✅ Passed |
| Production Image Supply Chain | ✅ Passed |
| Final Release Gate | ✅ Passed |
| Release Package Hygiene | ✅ Passed |
| GitHub Release | ✅ Published |
| Real External Kubernetes Acceptance | 🚧 Deployment-specific operator gate |

---

## Repository Scope

HSAAI is designed around the enterprise AI requirements of **Hayel Saeed Anam & Co. (HSA Group)**.

The platform demonstrates how enterprise knowledge, Retrieval-Augmented Generation, AI agents, multi-agent orchestration, knowledge graphs, workflow automation, AI governance, LLMOps, MLOps, DevSecOps and cloud-native infrastructure can operate within one unified **Enterprise AI Operating System**.

---

## License

Review `LICENSE` for applicable rights, restrictions and permitted usage.

This README does not grant rights beyond those defined by the repository license.

---

# HSAAI

### Enterprise Artificial Intelligence Operating System

**Enterprise AI · RAG · Agentic AI · AI Agents · Multi-Agent Systems · Knowledge Graphs · Workflow Automation · AI Governance · LLMOps · MLOps · DevSecOps · Kubernetes · Observability**

منصة ذكاء اصطناعي مؤسسية متكاملة للمعرفة، وRAG، والوكلاء الأذكياء، والأنظمة متعددة الوكلاء، وأتمتة الأعمال، وحوكمة الذكاء الاصطناعي، وإدارة النماذج والبنية التحتية المؤسسية.

**Current Release: HSAAI v4.0.0**
