# HSAAI Arabic Enterprise AI Quality Benchmark

HSAAI evaluates AI answer quality independently from software code coverage.

## Benchmark Scope

The controlled benchmark currently contains:

- 30 enabled Arabic enterprise evaluation cases
- 4 preserved legacy validation-only cases
- 6 controlled Arabic enterprise source documents
- 10 evaluation categories
- Ground-truth source references
- Deterministic required facts
- Multi-source retrieval coverage
- Prompt-injection blocking cases

## Evaluation Modes

### Dataset Validation

Dataset Validation runs without a live LLM or RAG service.

It verifies:

- dataset structure
- minimum case count
- fixture availability
- category diversity
- source references
- prompt-injection coverage
- multi-source coverage

Dataset Validation does **not** produce or claim AI answer-quality scores.

### Live RAG Benchmark

The Live RAG Benchmark uses the real HSAAI endpoints:

- `POST /v1/search`
- `POST /v1/answer`

It measures:

- retrieval precision
- retrieval recall
- citation precision
- citation recall
- required-fact recall
- prompt-injection blocking
- grounded LLM-answer rate
- response latency P50
- response latency P95

## Evidence Policy

A result is not treated as publishable AI answer-quality evidence unless:

1. the benchmark uses the live HSAAI RAG runtime;
2. the run is authenticated;
3. every enabled benchmark case executes successfully;
4. grounded answer cases use the real language-model answer path;
5. configured quality thresholds pass.

Retrieval fallback output may be useful for diagnostics but is not represented
as proof of LLM answer quality.

## Legacy Evaluation Cases

The original four HSAAI Arabic evaluation cases are preserved for historical
compatibility.

They are excluded from publishable quality metrics because they predate the
controlled ground-truth benchmark contract.

## Production Data

The bundled benchmark corpus contains synthetic, controlled enterprise
documents and does not contain customer production data.

Customer acceptance testing should additionally use authorized,
production-representative documents.
