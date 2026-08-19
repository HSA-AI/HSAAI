# HSAAI RAG Architecture

## 1. RAG Pipeline Design

The HSAAI RAG Engine implements a production-grade Retrieval-Augmented Generation pipeline with 5 core stages:

```
Document Ingestion → Semantic Chunking → Embedding Generation →
Hybrid Retrieval → Cross-Encoder Reranking → LLM Generation →
Citation Verification
```

## 2. Retrieval Strategy

### Hybrid Retrieval (Top 50)
- **Vector Similarity:** Dense embedding cosine similarity (weight: 0.7)
- **BM25 Keyword:** Sparse lexical matching with Arabic normalization (weight: 0.3)
- **Metadata Filtering:** tenant_id, department, security_level, classification, language

### Reranking (Top 10 → Top 5)
- **Cross-Encoder:** BAAI/bge-reranker-v2-m3 (ONNX-optimized, GPU-accelerated)
- **MMR Diversity:** λ=0.7 (relevance-heavy) to reduce redundant chunks
- **Business Context:** Recency boost, authority boost, department match

### Fusion Formula
```
final_score = α_lex × BM25 + α_sem × Dense + α_ce × CrossEncoder + α_biz × BusinessContext
Default weights: 0.20 / 0.30 / 0.40 / 0.10
```

## 3. Vector Database

### Qdrant Enterprise Configuration
- **Cluster:** 3 nodes with Raft consensus
- **Collection:** `hsaai_documents_vectors`
- **Payload Index:** tenant_id, workspace_id, document_id, department, security_level, classification, language
- **Tenant Isolation:** Mandatory `tenant_id` filter via `TenantGuard`

### Collection Schema
```json
{
  "tenant_id": "keyword (indexed)",
  "workspace_id": "keyword (indexed)",
  "document_id": "keyword (indexed)",
  "department": "keyword (indexed)",
  "security_level": "keyword (indexed)",
  "classification": "keyword (indexed)",
  "language": "keyword (indexed)",
  "model_version": "keyword",
  "chunk_type": "keyword",
  "page": "integer",
  "created_at": "datetime"
}
```

## 4. Enterprise Connectors

| Connector | Source | Status |
|-----------|--------|--------|
| SAP S/4HANA | ERP data, vendor master | Production |
| SharePoint Online | Document management | Production |
| Microsoft 365 | OneDrive, Teams, Outlook | Production |
| Google Drive | Document storage | Production |
| Active Directory | User directory | Production |
| SMTP/Email | Email ingestion | Production |
| Slack | Team communications | Production |

## 5. Knowledge Domains (17)

1. Human Resources Policies
2. Finance Procedures
3. Procurement Manuals
4. Legal Documents
5. Quality Assurance Standards
6. Supply Chain Procedures
7. Manufacturing Guidelines
8. Sales & Marketing
9. IT Operations
10. Corporate Governance
11. Compliance & Regulatory
12. Risk Management
13. Customer Service
14. Distribution & Logistics
15. Treasury
16. Accounting
17. Cybersecurity

## 6. Citation System

### Citation Format
Every response includes structured citations:
```json
{
  "chunk_id": "uuid",
  "document_id": "uuid",
  "document_title": "HR Policy v3.2",
  "page": 12,
  "section": "Annual Leave",
  "heading": "## Annual Leave",
  "excerpt": "Employees are entitled to 30 days...",
  "score": 1.0
}
```

### Verification Process
1. Retrieved context exists (non-empty)
2. Answer supported by context (n-gram overlap ≥ 0.70)
3. Citations point to real chunks (chunk_id exists in retrieved set)
4. Excerpt matches source content (≥ 70% word overlap)
5. Numeric entities in answer appear in context
