HSAAI — Enterprise AI Platform for RAG, LLMs, AI Agents & Governance

Hayel Saeed Anam Artificial Intelligence

HSAAI is an enterprise AI platform developed for HSA Group, providing a secure and governed digital intelligence layer for corporate knowledge, operational data, and enterprise systems.

The platform brings together Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), AI agents, enterprise search, workflow automation, AI governance, identity management, and security controls into a unified enterprise architecture.

«Classification: Internal Use Only
Organization: HSA Group
Repository Status: Private / Internal»

---

Platform Overview

HSAAI is designed to provide enterprise departments with controlled access to AI capabilities while maintaining organizational security, authorization, governance, and data-protection requirements.

Core platform capabilities include:

- Enterprise AI and LLM integration
- Retrieval-Augmented Generation (RAG)
- Enterprise knowledge retrieval
- AI agent orchestration and runtime
- LLM routing and model gateway services
- Enterprise connectors and integrations
- Workflow automation
- AI governance and policy enforcement
- Role-Based Access Control (RBAC)
- Attribute-Based Access Control (ABAC)
- Identity and access management
- PII detection and data protection
- Observability, monitoring, and operational controls
- Vector search and knowledge management

---

Architecture

The platform is organized into several major layers:

┌─────────────────────────────────────────────────────────────┐
│                    Enterprise Applications                  │
├─────────────────────────────────────────────────────────────┤
│              Frontend / BFF / API Gateway                   │
├─────────────────────────────────────────────────────────────┤
│        AI Orchestration • Agents • Workflows • Governance   │
├─────────────────────────────────────────────────────────────┤
│             RAG • Knowledge • Search • Memory               │
├─────────────────────────────────────────────────────────────┤
│              LLM Gateway • Model Routing                    │
├─────────────────────────────────────────────────────────────┤
│       PostgreSQL • Qdrant • Redis • Enterprise Data        │
├─────────────────────────────────────────────────────────────┤
│     Keycloak • Vault • RBAC • ABAC • Security Controls     │
├─────────────────────────────────────────────────────────────┤
│             Docker • Kubernetes • VMware Tanzu              │
└─────────────────────────────────────────────────────────────┘

For the detailed architecture and data flows, see the project documentation.

---

Technology Stack

Layer| Technology
Frontend| Next.js, React, TypeScript
Backend| FastAPI, Python 3.11
AI Platform| LLM Gateway, RAG Engine, Agent Framework
Vector Database| Qdrant
Relational Database| PostgreSQL
Cache / Messaging| Redis
Identity| Keycloak OIDC
Authorization| RBAC, ABAC
Secrets Management| HashiCorp Vault
Containers| Docker
Orchestration| Kubernetes
Virtualization / Platform| VMware Tanzu

---

Core AI Capabilities

Large Language Models

HSAAI provides an abstraction layer for integrating and routing requests across supported language models through the LLM Gateway.

Retrieval-Augmented Generation

The RAG architecture enables AI applications to retrieve relevant enterprise knowledge before generating responses.

Key components include:

- Document ingestion
- Chunking
- Embedding generation
- Vector retrieval
- Reranking
- Context assembly
- Citation handling
- Retrieval security
- Knowledge access controls

AI Agents

The agent framework provides controlled execution environments for enterprise AI agents, including:

- Agent orchestration
- Tool execution
- Agent runtime
- Department-oriented agents
- Workflow integration
- Policy enforcement
- Observability

AI Governance

Governance capabilities are designed to provide controlled AI usage across enterprise environments, including:

- Policy enforcement
- Risk evaluation
- Explainability
- Authorization
- Auditability
- Data protection
- Operational controls

---

Enterprise Security

Security is a core architectural principle of HSAAI.

The platform integrates multiple security controls, including:

- Keycloak OIDC
- Role-Based Access Control (RBAC)
- Attribute-Based Access Control (ABAC)
- Secrets management
- Authentication and authorization
- Tenant and organizational isolation
- PII detection
- Prompt security
- SSRF protection
- SQL safety controls
- Rate limiting
- Structured security logging
- Audit controls
- Secure service-to-service communication

Security architecture and implementation details are documented separately to avoid exposing sensitive operational information.

---

Enterprise Integrations

HSAAI provides an extensible connector architecture for integrating AI capabilities with enterprise platforms and data sources.

The repository contains integration components for supported enterprise systems and protocols, including areas such as:

- Identity and directory services
- Collaboration platforms
- Enterprise resource planning
- Human resources systems
- IT service management
- Business intelligence
- Databases
- Messaging systems
- File and document platforms
- REST and GraphQL APIs

Connector availability and production configuration depend on the target enterprise environment.

---

Platform Services

Service| Port| Purpose
API Gateway| 8000| Request routing and authentication
Backend Core| 8001| Core business logic and orchestration
RAG Engine| 8030| Knowledge retrieval and generation
LLM Gateway| 8090| Model routing and LLM integration
Auth Service| 8010| Identity and authentication integration
Governance Service| 8011| Policy and governance enforcement
PII Detector| 8012| PII detection and data protection
Workflow Engine| 8070| Workflow and process automation
Agent Runtime| 8040| AI agent execution

«Service ports are intended for the internal deployment environment and should not be exposed directly to untrusted networks.»

---

Documentation

Detailed technical documentation is available under ""/docs"" (docs/).

Documentation| Description
"Architecture" (docs/ARCHITECTURE.md)| System architecture and major components
"System Design" (docs/SYSTEM_DESIGN.md)| Detailed system design and data flows
"Deployment Guide" (docs/DEPLOYMENT_GUIDE.md)| Deployment and environment configuration
"Security Model" (docs/SECURITY_MODEL.md)| Authentication, authorization, and security architecture
"API Reference" (docs/API_REFERENCE.md)| API contracts and endpoints
"Operations Guide" (docs/OPERATIONS_GUIDE.md)| Operations and production runbooks
"AI Engine Documentation" (docs/AI_ENGINE_DOCUMENTATION.md)| AI pipeline and model architecture
"RAG Architecture" (docs/RAG_ARCHITECTURE.md)| Retrieval-Augmented Generation architecture
"Agent Framework" (docs/AGENT_FRAMEWORK.md)| Agent architecture and execution
"Change Management" (docs/CHANGE_MANAGEMENT.md)| Release and change management

---

Quick Start

1. Configure the environment

cp .env.example .env

Configure the required environment variables according to the deployment documentation.

Never commit ".env", credentials, API keys, private keys, or production secrets to Git.

2. Build the platform

docker compose build

3. Start the services

docker compose up -d

4. Run database migrations

docker compose exec backend-core alembic upgrade head

5. Validate the deployment

python3 hsaai-vmware-readiness.py

For production deployment, follow the "Deployment Guide" (docs/DEPLOYMENT_GUIDE.md).

---

Compliance and Security Frameworks

HSAAI is designed with reference to enterprise security and governance frameworks, including:

- ISO/IEC 27001:2022
- NIST AI Risk Management Framework
- NIST SP 800-207 Zero Trust Architecture
- OWASP Application Security Verification Standard (ASVS)
- CIS Docker Benchmark

«Framework alignment does not by itself constitute certification or formal compliance. Applicable controls and certification status must be validated against the organization's actual implementation and audit requirements.»

---

Project Structure

HSAAI/
├── packages/
│   └── common/
│       ├── ai/
│       ├── auth/
│       ├── connectors/
│       ├── governance/
│       ├── observability/
│       ├── performance/
│       ├── resilience/
│       ├── safety/
│       └── security/
│
├── services/
│   ├── ai_alignment/
│   ├── ai_orchestrator/
│   ├── api_gateway/
│   ├── auth_service/
│   ├── backend_core/
│   ├── governance/
│   ├── llm_gateway/
│   ├── mcp_server/
│   ├── model_training/
│   ├── multi_agents/
│   ├── pii_detector/
│   ├── rag_engine/
│   ├── voice_ai/
│   └── workflow_engine/
│
├── docs/
├── deployment/
├── security/
├── tests/
└── pyproject.toml

---

Development

Before submitting changes, developers should verify:

git status

Run the applicable test suite:

pytest

Validate Docker Compose configuration when applicable:

docker compose config

Additional linting, type checking, security scanning, and CI requirements are documented in the project development documentation.

---

Security

Security issues must not be reported through public GitHub issues.

Follow the repository's internal security reporting procedure described in ""SECURITY.md"" (SECURITY.md).

Do not include the following in commits:

- API keys
- Passwords
- Access tokens
- Private keys
- Production credentials
- Database dumps
- Internal datasets
- ".env" files
- Sensitive customer or employee information

---

Repository Classification

Internal Use Only

HSAAI is an internal enterprise platform developed for HSA Group. The repository and its source code are restricted to authorized users.

Architecture documentation, credentials, deployment configuration, enterprise data, and operational information must be handled according to applicable HSA Group security policies.

---

License

Copyright © HSA Group — Information Technology.

This repository is currently proprietary and intended for authorized internal use only.

Redistribution, publication, modification, or commercial use outside the organization requires explicit authorization from the applicable rights holder.

---

Support

For internal technical support, deployment assistance, security issues, or architecture questions, follow the organization's approved internal support and escalation procedures.