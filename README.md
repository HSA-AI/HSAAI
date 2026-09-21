# HSAAI — Enterprise AI Operating System

**An enterprise AI platform for knowledge discovery, intelligent assistants, agent workflows, and governed AI operations.**

**منصة الذكاء الاصطناعي المؤسسية لإدارة المعرفة والمساعدين الأذكياء وسير العمل وحوكمة الذكاء الاصطناعي.**

HSAAI (Hayel Saeed Anam Artificial Intelligence) is designed around the organizational requirements of **Hayel Saeed Anam & Co. (HSA Group)**. It brings together enterprise knowledge, conversational AI, retrieval-augmented generation (RAG), agents, workflow approvals, integrations, and observability in a unified architecture.

> **Release status — production candidate, not production approved.** The repository's September 19, 2026 delivery snapshot reports **690 passing backend tests and 56.56% coverage**. These figures are snapshot-specific and must be regenerated for the current commit. An earlier release report cites **598 backend tests, 38 frontend tests, and 54.78% Python coverage**; those are historical results, not an additional current test claim. Full enterprise runtime, real Kubernetes deployment, the ≥80% coverage gate, and outstanding acceptance and security checks require separate evidence. Refer to [`START_HERE_AR.md`](START_HERE_AR.md) and [`FINAL_PRODUCTION_READINESS_REPORT.md`](FINAL_PRODUCTION_READINESS_REPORT.md) for the repository's release assessment. Do not interpret the presence of configuration or documentation as proof of live operation.

[Documentation](#documentation) · [Architecture](#architecture) · [Deployment](#deployment) · [Testing-and-release-evidence](#testing-and-release-evidence) · [Security](#security)

---

## Overview | نظرة عامة

HSAAI is a modular enterprise AI platform intended to connect organizational knowledge and business workflows across documents, internal systems, and teams. Its codebase includes a web experience, API and identity components, knowledge retrieval, LLM routing, agent orchestration, workflow automation, governance, and infrastructure configurations.

**HSAAI** منصة معيارية تهدف إلى توحيد الوصول إلى المعرفة المؤسسية وإدارة التفاعل مع نماذج الذكاء الاصطناعي والوكلاء وسير العمل عبر واجهة تشغيل متكاملة. صُممت بنيتها لتتكامل مع الملفات والأنظمة الداخلية والفرق المختلفة، مع مراعاة المصادقة والصلاحيات والتدقيق والمراقبة.

### Platform capabilities | مكونات المنصة

| Area | Components represented in the repository |
| --- | --- |
| Enterprise knowledge | Document ingestion, RAG, embeddings, Qdrant, retrieval and knowledge graph integrations |
| AI applications | Conversational interface, LLM gateway, model routing, AI agents and tool execution |
| Process automation | Workflow engine, human-in-the-loop approvals and enterprise integrations |
| Governance | Authentication, authorization, RBAC/ABAC, policy enforcement and audit components |
| Operations | Docker Compose, Kubernetes manifests, Helm, monitoring, logging and tracing configurations |
| User experience | Next.js web application with Arabic-first and RTL-oriented design |

These are **repository capabilities and architectural components**. Their availability and operational readiness depend on the deployment profile and the corresponding validation results.

---

## Architecture

The source is organized into independently developed applications, services, shared packages and deployment assets:

```text
HSAAI/
├── apps/web/                 # Enterprise web application
├── services/                 # API, authentication, RAG, LLM, agents and workflows
├── packages/common/          # Shared authentication, security and observability
├── infrastructure/
│   ├── docker/               # Container configuration
│   ├── kubernetes/           # Kubernetes manifests and overlays
│   ├── helm/                 # Deployment charts
│   ├── monitoring/           # Observability configuration
│   └── vault/                # Secrets-management integration
├── alembic/                  # Database migrations
├── tests/                    # Automated test suites
├── scripts/                  # Validation and operational scripts
├── deployment/               # Additional deployment paths
├── runbooks/                 # Operating procedures
├── docs/                     # Architecture, security and release documentation
└── .github/workflows/        # CI workflows
```

### Main application services

| Service | Responsibility |
| --- | --- |
| `web` | Web interface and user experience |
| `api-gateway` | API routing and request controls |
| `backend-core` | Central application APIs |
| `auth-service` | Identity and authentication integration |
| `rag-engine` | Knowledge retrieval and RAG workflows |
| `llm-gateway` | Model access and routing |
| `multi_agents` | Agent coordination and tool execution |
| `workflow-engine` | Workflow execution and approvals |
| `governance` | Governance and policy components |

The repository also contains additional services and experimental or extended components. **Use the active Compose or Kubernetes configuration as the source of truth** for service names, dependencies, ports and enabled profiles; do not assume every directory is a running production service.

### Data and infrastructure integrations

Repository configuration includes integrations for PostgreSQL, Redis, Qdrant, Neo4j, Kafka, MinIO, Keycloak, Ollama, MLflow, Prometheus, Grafana, Loki, Tempo, Thanos and Vault. Some deployments require additional capacity, external secrets, model downloads or separately configured infrastructure.

---

## Deployment

### Prerequisites

- A Linux host with a working Docker Engine and Docker Compose v2 for container-based deployment.
- CPU, memory, storage and network capacity sized to the **selected** service profile; the entire enterprise stack is substantially larger than the core CI stack.
- An appropriately configured secrets source. Never commit actual credentials, private keys or production `.env` files.
- Kubernetes access, a container image registry and suitable persistent storage **only** when performing Kubernetes deployment.

### Docker Compose — controlled validation

```bash
# Run on a host with a Docker daemon; Termux without a daemon is not a runtime host.
cp .env.example .env
# Configure environment-specific values securely before starting services.
docker compose config --quiet
# Select and review the required services and profiles before deployment.
docker compose ps --all
```

After reviewing dependencies and host capacity, start the intended configuration with the project's deployment runbooks. Avoid treating an ephemeral CI runner as a persistent production host. Do not use demonstration credentials or test environment values for production.

### Kubernetes

Kubernetes manifests, overlays and Helm assets are located under [`infrastructure/kubernetes/`](infrastructure/kubernetes/) and [`infrastructure/helm/`](infrastructure/helm/). Inspect and render the actual chart or manifests, supply approved image references and secrets, run server-side validation, then deploy to an authorized staging cluster before any production rollout. Kubernetes readiness remains subject to real-cluster acceptance results.

### Native deployment

Additional non-container deployment assets are available under [`deployment/`](deployment/). Follow the matching environment template and operational documentation; development-only or insecure demo modes are not production defaults.

---

## Security

HSAAI includes code and configuration for identity integration, access controls, policy checks, prompt-safety controls, PII handling, audit logs, network isolation and secrets management. The existence of these controls **does not establish that a given deployment has passed a security audit**.

Before production approval, verify the active settings and evidence for identity and authorization, tenant isolation, secrets rotation, dependency and image scanning, network exposure, logging and backup recovery. Treat any exposed credentials as compromised and rotate them. Review [`docs/security/`](docs/security/) and the release readiness report for the relevant scope and open findings.

**Security reporting:** Follow the repository's [security policy](SECURITY.md), where available. Do not disclose credentials or exploitable findings in public issues.

---

## Testing and release evidence

The repository contains backend, frontend, integration, security and end-to-end test assets. CI results describe the **exact commit and workflow configuration tested**, not every deployment profile.

| Validation area | What constitutes evidence |
| --- | --- |
| Source and container build | Successful build workflow for the target commit |
| Core runtime | Actual container startup, health checks and HTTP integration tests |
| Full enterprise stack | Service-by-service readiness, connectivity, persistence and failure-recovery checks |
| Kubernetes | Rendered manifests, real-cluster deployment, pod/service health and storage tests |
| Test coverage | Current coverage report with an enforced threshold of at least 80% |
| Security | Current scans, manual review of high-risk areas and approved remediation status |

**Reported snapshot, September 19, 2026:** 690 passing backend tests and 56.56% coverage. **Historical report:** 598 backend passes, 38 frontend passes and 54.78% Python coverage. These measurements are from different documented snapshots and must not be combined. Consult current CI runs and generated reports for current evidence.

### Production approval criteria

A release should be designated production-ready only after its required runtime, Kubernetes (where applicable), coverage, security, persistence, disaster recovery and acceptance checks have passed and the approval is recorded. Until then, describe it as a **production candidate**.

---

## Documentation

| Resource | Purpose |
| --- | --- |
| [`START_HERE_AR.md`](START_HERE_AR.md) | Arabic handover and starting point |
| [`FINAL_PRODUCTION_READINESS_REPORT.md`](FINAL_PRODUCTION_READINESS_REPORT.md) | Release status, evidence and unresolved blockers |
| [`QUICKSTART.md`](QUICKSTART.md) | Getting started |
| [`CHANGELOG.md`](CHANGELOG.md) | Change history |
| [`docs/`](docs/) | Architecture, API, operations and security documentation |
| [`runbooks/`](runbooks/) | Operational procedures |

Older release notes and version badges may describe historical milestones. The authoritative current release number should be taken from the repository's `VERSION` file and the latest applicable release record; update both together when cutting a new release.

---

## Repository scope and license

Designed around the enterprise requirements of **Hayel Saeed Anam & Co. (HSA Group)**. Review [`LICENSE`](LICENSE) for the actual rights, restrictions and permitted use. This README does not grant additional redistribution or production-deployment rights.

**HSAAI — Enterprise AI Operating System | Enterprise Knowledge · AI Agents · RAG · Governance · MLOps**
