# Enterprise RAG Production Design

## Pipeline

1. Upload from frontend.
2. Validate file type and size.
3. Store file locally or private object storage.
4. Extract text through Document AI.
5. Run OCR when needed.
6. Clean and normalize text.
7. Split into chunks.
8. Create internal embeddings.
9. Store vectors in Qdrant.
10. Store metadata in PostgreSQL.
11. Search using semantic and keyword signals.
12. Generate answer through local LLM with citations.

## Isolation

Every document, chunk, embedding, query, and result must include:

- tenant_id
- organization_id
- workspace_id
- created_by
- access_policy

## Anti-leakage controls

- Never query Qdrant without workspace filter.
- Never return a source document without RBAC verification.
- Never send document text to external providers in internal-only mode.
- Log all document reads and search events.
