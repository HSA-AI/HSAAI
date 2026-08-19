# HSAAI AI Engine Documentation

## 1. AI Pipeline Overview

The HSAAI AI Engine processes queries through a 10-stage pipeline:

```
1. Query Intake → 2. Security Check → 3. Language Detection →
4. Query Embedding → 5. Hybrid Retrieval → 6. Cross-Encoder Reranking →
7. MMR Diversity → 8. LLM Generation → 9. Citation Verification →
10. Response Delivery
```

## 2. Embedding System

### Model Registry
| Model | Provider | Dimension | Languages | Use Case |
|-------|----------|-----------|-----------|----------|
| BAAI/bge-m3 | Local (GPU) | 1024 | Arabic, English, Mixed | Default (Arabic-optimized) |
| text-embedding-3-large | OpenAI | 3072 | English | English-heavy workloads |
| multilingual-e5-large | Local (GPU) | 1024 | Multilingual | Fallback |

### Automatic Language Routing
- Arabic query → BAAI/bge-m3
- English query → text-embedding-3-large
- Mixed query → BAAI/bge-m3

### Caching
- LRU cache (100,000 entries)
- Redis distributed cache (1-hour TTL)
- Target hit ratio: > 65%

## 3. LLM Gateway

### Models
| Model | VRAM | Purpose | Deployment |
|-------|------|---------|------------|
| Qwen2.5-72B-Instruct (AWQ) | 72 GB | Primary LLM | vLLM on A100 |
| Qwen2.5-7B-Instruct | 16 GB | Lightweight tasks | vLLM on A100 |
| GPT-4o (fallback) | — | Cloud fallback | OpenAI API |

### Model Router
- Routes based on: query complexity, language, token budget, cost
- Fallback chain: Qwen2.5-72B → Qwen2.5-7B → GPT-4o
- Streaming responses via Server-Sent Events

## 4. Document Intelligence

### Ingestion Pipeline
```
Upload → File Validation → Virus Scan (ClamAV) → OCR (Tesseract) →
Document Classification → PII Detection → Metadata Extraction →
Smart Chunking → Embedding Generation → Vector Indexing
```

### Chunking Strategy
- **Semantic chunking:** Sentence-boundary aware
- **Markdown hierarchy:** H1-H6 section detection
- **PDF page intelligence:** Page-aware chunk boundaries
- **Table preservation:** Tables as standalone chunks
- **Code block preservation:** Fenced code blocks never split
- **Arabic optimization:** Tatweel removal, diacritic handling, RTL embedding

### Chunk Metadata
```json
{
  "id": "uuid",
  "document_id": "string",
  "tenant_id": "string",
  "page": 1,
  "section": "Annual Leave",
  "heading": "## Annual Leave",
  "language": "ar",
  "token_count": 487,
  "checksum": "sha256",
  "chunk_type": "paragraph"
}
```

## 5. Hallucination Control

### Verification Scores
| Score | What it measures | Threshold |
|-------|------------------|-----------|
| confidence_score | Overall trust in answer | ≥ 0.65 |
| grounding_score | Answer supported by context (n-gram overlap) | ≥ 0.70 |
| citation_score | Citations point to real chunks + excerpts match | ≥ 0.75 |

### Low-Confidence Fallback
- English: "I don't have enough verified information to answer this question."
- Arabic: "لا أمتلك معلومات موثّقة كافية للإجابة على هذا السؤال."

## 6. GPU Resource Management

### GPU Allocation
| GPU | Mode | Workload |
|-----|------|----------|
| A100 #1-2 | Passthrough | LLM Gateway (vLLM) |
| A100 #3-4 | Passthrough | Model Training |
| A100 #5-6 | vGPU (2×40GB) | RAG Engine + Embeddings |
| A100 #7-8 | vGPU (2×40GB) | Reranker + Voice AI |

### Performance Targets
| Metric | Target |
|--------|--------|
| Embedding latency (batch 64) | < 50ms |
| Cross-encoder latency (batch 32) | < 30ms |
| LLM token generation | < 500ms/token |
| RAG end-to-end P95 | < 2s |
| Hallucination rate | < 5% |
