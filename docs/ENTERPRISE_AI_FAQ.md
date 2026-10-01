# HSAAI Enterprise AI Platform — FAQ

## What is HSAAI?

HSAAI is a private, sovereign, self-hosted Enterprise AI Platform for secure generative AI, Enterprise RAG, local LLMs, AI agents, workflow automation, enterprise knowledge, governance, observability, and Kubernetes deployment.

## Is HSAAI an Enterprise AI platform?

Yes. HSAAI is designed as an enterprise AI platform rather than a standalone chatbot. Its architecture combines identity, security, retrieval, model access, enterprise knowledge, agents, workflows, observability, governance, and deployment infrastructure.

## What is Sovereign AI in HSAAI?

HSAAI supports private and self-hosted AI architectures that allow organizations to retain greater control over their models, enterprise data, identity, infrastructure, access policies, and AI workloads.

## Does HSAAI support Local LLMs?

Yes.

The currently validated local inference path is:

Ollama → qwen2.5:7b-instruct

The model is accessed through the HSAAI LLM Gateway.

## Does HSAAI support Enterprise RAG?

Yes.

HSAAI Enterprise RAG includes:

- Qdrant vector retrieval
- semantic retrieval
- lexical/BM25 signals
- multilingual Cross-Encoder reranking
- relevance filtering
- tenant and workspace isolation
- prompt-injection protection
- grounded LLM answers
- citation validation

## What are the current HSAAI AI quality results?

On the current controlled live benchmark:

- Retrieval Precision: 100%
- Retrieval Recall: 100%
- Citation Precision: 100%
- Citation Recall: 100%
- Prompt Injection Accuracy: 100%
- LLM Grounded Rate: 100%
- Required Fact Recall: 86.61%
- Overall AI Quality Gate: PASS
- Errors: 0

These values apply to the current controlled evaluation suite and should not be interpreted as universal AI accuracy.

## Does HSAAI support Arabic Enterprise AI?

Yes.

HSAAI includes Arabic enterprise evaluation scenarios and controlled Arabic enterprise documents covering areas such as:

- Human Resources
- Travel Expenses
- Information Security
- Procurement
- Data Classification
- Remote Work

## Does HSAAI provide citation-backed AI answers?

Yes.

The live quality pipeline validates the sources referenced by generated answers and measures both citation precision and citation recall.

## How does HSAAI protect enterprise AI workloads?

The architecture includes:

- Keycloak
- JWT authentication
- tenant isolation
- workspace isolation
- RBAC / ABAC architecture
- PII screening
- prompt-injection protection
- security validation gates
- private/local LLM execution
- audit and observability capabilities

## Does HSAAI support AI Agents?

Yes.

HSAAI includes AI agents, multi-agent orchestration, workflow automation, enterprise knowledge services, and an LLM Gateway.

## Is HSAAI only a chatbot?

No.

A chatbot can be one interface built on top of HSAAI, but HSAAI itself is designed as a broader Enterprise AI Platform.

## What infrastructure does HSAAI use?

The architecture includes technologies such as:

- PostgreSQL
- Redis
- Qdrant
- Neo4j
- Kafka
- MinIO
- Keycloak
- Ollama
- Vault
- MLflow
- Prometheus
- Grafana
- Loki
- Tempo
- Thanos
- Docker
- Kubernetes

## Does HSAAI support Kubernetes?

Yes.

HSAAI includes Kubernetes deployment resources, Kubernetes CI validation, production acceptance workflows, and a dedicated real external Kubernetes preflight workflow.

Real external Kubernetes acceptance remains a separate infrastructure validation milestone.

## What has HSAAI validated End-to-End?

The validated live AI path covers:

Authentication
→ Security Controls
→ Enterprise RAG
→ Qdrant
→ Cross-Encoder Relevance Filtering
→ LLM Gateway
→ Ollama
→ Local LLM
→ Grounded Answer
→ Citation Validation

## ما هي منصة HSAAI؟

HSAAI هي منصة ذكاء اصطناعي مؤسسية خاصة وسيادية وذاتية الاستضافة، تجمع بين نماذج اللغة المحلية وRAG المؤسسي والوكلاء الأذكياء وإدارة المعرفة والأمان والمراقبة والتشغيل على Kubernetes.

## هل HSAAI يدعم الذكاء الاصطناعي العربي؟

نعم. يدعم HSAAI سيناريوهات عربية مؤسسية تشمل البحث في الوثائق العربية، والاسترجاع المعزز بالتوليد RAG، والتحقق من الإجابات والمراجع، وتشغيل نماذج لغة محلية.

## هل يمكن تشغيل HSAAI داخل المؤسسة؟

تم تصميم HSAAI لدعم الاستضافة الذاتية والنماذج المحلية، مما يسمح للمؤسسات بدرجة عالية من التحكم في البيانات والنماذج والهوية والبنية التحتية.
