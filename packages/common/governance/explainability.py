"""
HSAAI Explainability Engine — Decision Audit + XAI + Lineage (v1.0)
====================================================================

Provides three complementary capabilities for trustworthy AI:

1. **Decision Audit** — every AI decision is recorded with full context:
   input, model, prompt, retrieved context, output, confidence, and the
   factors that contributed to the decision. Satisfies ISO 42001 §8.2
   (AI System Impact Assessment) and NIST AI RMF MEASURE-2.3.

2. **Explainable AI (XAI)** — generates a human-readable explanation
   of WHY a decision was made, suitable for end users, auditors, and
   regulators. The explanation references the top contributing factors
   and the supporting source documents.

3. **Decision Lineage** — traces from an output back through RAG
   context → embedding → source document. Answers the auditor's
   question "where did this answer come from?" with citation-grade
   provenance.

Persistence
-----------
Decision records are stored in:
  - Redis (recent decisions, fast query) — 30-day TTL
  - PostgreSQL (durable, queryable) — table `ai_decision_audit`
  - Optional S3/MinIO archive for >90-day-old records (handled by the
    same archive_cron that handles `audit_logs`).

Usage
-----
    from packages.common.governance.explainability import (
        ExplainabilityEngine, DecisionRecord, LineageNode,
    )

    engine = ExplainabilityEngine()

    # Record a decision (called by the LLM gateway after generation)
    rec = DecisionRecord(
        decision_id=str(uuid.uuid4()),
        user_id="u1",
        tenant_id="t1",
        model="qwen2.5-14b",
        prompt="What is the leave policy?",
        input_context={"department": "hr", "conversation_id": "c1"},
        output="Annual leave is 30 days ...",
        confidence=0.87,
        rag_chunks=[
            {"chunk_id": "c1", "doc_id": "d1", "text": "...", "score": 0.92},
            {"chunk_id": "c2", "doc_id": "d2", "text": "...", "score": 0.78},
        ],
        factors={
            "rag_grounding": 0.92,
            "model_confidence": 0.87,
            "citation_density": 1.5,
            "safety_filter_passed": True,
        },
    )
    engine.record(rec)

    # Retrieve + explain
    fetched = engine.get(decision_id)
    explanation = engine.explain(decision_id)
    lineage = engine.lineage(decision_id)
"""
from __future__ import annotations

import os
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hsaai.governance.explainability")

try:
    import redis  # type: ignore
    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _REDIS_AVAILABLE = False

try:
    from sqlalchemy import create_engine, text as sa_text  # type: ignore
    from sqlalchemy.exc import SQLAlchemyError  # type: ignore
    _SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SQLALCHEMY_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════
# Decision record
# ═══════════════════════════════════════════════════════════════════
@dataclass
class RAGChunk:
    """One retrieved chunk used as grounding for the AI decision."""
    chunk_id: str
    doc_id: str
    text: str
    score: float = 0.0                       # retrieval similarity score
    embedding_model: Optional[str] = None   # e.g. "multilingual-MiniLM-L12-v2"
    source_uri: Optional[str] = None        # e.g. "s3://bucket/doc.pdf#page=3"
    page: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionRecord:
    """Full audit record for one AI decision."""
    decision_id: str
    user_id: str
    tenant_id: str
    model: str                              # e.g. "qwen2.5-14b"
    prompt: str
    input_context: Dict[str, Any] = field(default_factory=dict)
    output: str = ""
    confidence: float = 0.0                  # model's self-reported confidence
    rag_chunks: List[Dict[str, Any]] = field(default_factory=list)  # list of RAGChunk-like dicts
    factors: Dict[str, Any] = field(default_factory=dict)           # see FACTOR_WEIGHTS below
    safety_filter_passed: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: Optional[int] = None
    token_usage: Dict[str, int] = field(default_factory=dict)  # {prompt_tokens, completion_tokens}

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
# Lineage
# ═══════════════════════════════════════════════════════════════════
@dataclass
class LineageNode:
    """One node in the decision lineage graph."""
    node_type: str            # decision | chunk | embedding | source_document
    node_id: str
    label: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageEdge:
    from_node: str
    to_node: str
    relationship: str         # grounded_in | embedded_by | extracted_from
    weight: float = 1.0


@dataclass
class LineageGraph:
    nodes: List[LineageNode] = field(default_factory=list)
    edges: List[LineageEdge] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
        }


# ═══════════════════════════════════════════════════════════════════
# Explainability weights — used by explain()
# ═══════════════════════════════════════════════════════════════════
FACTOR_WEIGHTS: Dict[str, float] = {
    "rag_grounding": 0.35,        # retrieval grounding score
    "model_confidence": 0.25,     # model's self-reported confidence
    "citation_density": 0.15,     # citations per output sentence
    "safety_filter_passed": 0.15, # did safety filters pass?
    "freshness": 0.10,            # is the source data fresh?
}


# ═══════════════════════════════════════════════════════════════════
# Explainability engine
# ═══════════════════════════════════════════════════════════════════
class ExplainabilityEngine:
    """Records, explains, and traces AI decisions."""

    REDIS_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days

    def __init__(
        self,
        redis_url: Optional[str] = None,
        postgres_url: Optional[str] = None,
    ):
        self.redis = None
        if _REDIS_AVAILABLE:
            url = redis_url or os.getenv("EXPLAIN_REDIS_URL", "redis://redis:6379/8")
            try:
                self.redis = redis.from_url(url, decode_responses=True)
                self.redis.ping()
            except Exception as e:
                logger.warning("ExplainabilityEngine: Redis unavailable: %s", e)
                self.redis = None

        self.pg_engine = None
        if _SQLALCHEMY_AVAILABLE:
            pg_url = postgres_url or os.getenv("EXPLAIN_POSTGRES_URL") or os.getenv("DATABASE_URL")
            if pg_url:
                try:
                    self.pg_engine = create_engine(pg_url, pool_pre_ping=True, future=True)
                    with self.pg_engine.connect() as conn:
                        conn.execute(sa_text("SELECT 1"))
                    logger.info("ExplainabilityEngine: PostgreSQL durable store connected")
                except Exception as e:
                    logger.error("ExplainabilityEngine: PostgreSQL unavailable: %s", e)
                    self.pg_engine = None

    # ── Recording ────────────────────────────────────────────────────
    def record(self, rec: DecisionRecord) -> str:
        """Persist a decision record. Returns the decision_id."""
        payload = rec.to_dict()
        payload_str = json.dumps(payload, default=str, sort_keys=True)
        entry_hash = hashlib.sha256(payload_str.encode()).hexdigest()
        payload["entry_hash"] = entry_hash

        # Durable store first
        if self.pg_engine:
            try:
                with self.pg_engine.begin() as conn:
                    conn.execute(
                        sa_text(
                            "INSERT INTO audit_logs "
                            "(actor, action, resource, workspace_id, tenant_id, success, detail) "
                            "VALUES (:actor, :action, :resource, :workspace_id, :tenant_id, :success, :detail)"
                        ),
                        {
                            "actor": rec.user_id,
                            "action": "ai_decision",
                            "resource": rec.model,
                            "workspace_id": "default",
                            "tenant_id": rec.tenant_id,
                            "success": rec.safety_filter_passed,
                            "detail": json.dumps(payload, default=str),
                        },
                    )
            except SQLAlchemyError as e:
                logger.error("EXPLAIN DURABLE WRITE FAILED: %s | decision=%s", e, rec.decision_id)

        # Redis cache (fast recent retrieval)
        if self.redis:
            try:
                key = f"explain:decision:{rec.decision_id}"
                self.redis.setex(key, self.REDIS_TTL_SECONDS, json.dumps(payload, default=str))
                # Index by tenant for listing
                self.redis.lpush(
                    f"explain:decisions:tenant:{rec.tenant_id}",
                    rec.decision_id,
                )
                self.redis.ltrim(f"explain:decisions:tenant:{rec.tenant_id}", 0, 9999)
                self.redis.expire(f"explain:decisions:tenant:{rec.tenant_id}", self.REDIS_TTL_SECONDS)
            except Exception as e:
                logger.error("ExplainabilityEngine: Redis write failed: %s", e)

        return rec.decision_id

    def get(self, decision_id: str) -> Optional[DecisionRecord]:
        """Retrieve a decision record by ID."""
        if not self.redis:
            return None
        raw = self.redis.get(f"explain:decision:{decision_id}")
        if not raw:
            return None
        try:
            d = json.loads(raw)
            # Strip audit fields not part of the dataclass
            d.pop("entry_hash", None)
            return DecisionRecord(**d)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("ExplainabilityEngine: failed to decode %s: %s", decision_id, e)
            return None

    def list_for_tenant(self, tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.redis:
            return []
        ids = self.redis.lrange(f"explain:decisions:tenant:{tenant_id}", 0, limit - 1)
        out: List[Dict[str, Any]] = []
        for did in ids:
            raw = self.redis.get(f"explain:decision:{did}")
            if raw:
                try:
                    out.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
        return out

    # ── Explainable AI (XAI) ─────────────────────────────────────────
    def explain(self, decision_id: str) -> Dict[str, Any]:
        """Generate a human-readable explanation of a decision.

        Returns a dict with:
          - summary: 1-2 sentence plain-language explanation
          - contributing_factors: ranked list of factors with weight + value
          - supporting_sources: top RAG chunks with scores
          - composite_score: weighted trust score (0-1)
          - caveats: list of trust caveats (e.g. low confidence, no citations)
        """
        rec = self.get(decision_id)
        if rec is None:
            return {
                "decision_id": decision_id,
                "summary": "Decision record not found (expired or never recorded).",
                "contributing_factors": [],
                "supporting_sources": [],
                "composite_score": 0.0,
                "caveats": ["record_missing"],
            }

        # Rank factors by weight × normalised value
        ranked: List[Dict[str, Any]] = []
        composite = 0.0
        for fname, weight in FACTOR_WEIGHTS.items():
            raw = rec.factors.get(fname)
            if fname == "safety_filter_passed":
                value = 1.0 if rec.safety_filter_passed else 0.0
            elif fname == "rag_grounding":
                value = float(raw or 0.0)
            elif fname == "model_confidence":
                value = float(rec.confidence)
            elif fname == "citation_density":
                value = min(float(raw or 0.0) / 2.0, 1.0)  # 2 cites/sentence → 1.0
            elif fname == "freshness":
                value = float(raw or 0.0)
            else:
                value = float(raw or 0.0)
            contribution = weight * value
            composite += contribution
            ranked.append({
                "factor": fname,
                "weight": weight,
                "value": round(value, 3),
                "contribution": round(contribution, 3),
            })
        ranked.sort(key=lambda x: x["contribution"], reverse=True)

        # Top supporting sources
        sources: List[Dict[str, Any]] = []
        for chunk in (rec.rag_chunks or [])[:5]:
            sources.append({
                "doc_id": chunk.get("doc_id"),
                "chunk_id": chunk.get("chunk_id"),
                "score": chunk.get("score"),
                "text_preview": (chunk.get("text") or "")[:200],
                "source_uri": chunk.get("source_uri"),
                "page": chunk.get("page"),
            })

        # Build plain-language summary
        summary_parts: List[str] = []
        summary_parts.append(
            f"This answer was generated by model '{rec.model}' with "
            f"{int(rec.confidence * 100)}% self-reported confidence."
        )
        if rec.rag_chunks:
            summary_parts.append(
                f"It is grounded in {len(rec.rag_chunks)} retrieved document "
                f"chunk(s) (top score: {rec.rag_chunks[0].get('score', 0):.2f})."
            )
        else:
            summary_parts.append("It is NOT grounded in any retrieved documents (purely generative).")
        if not rec.safety_filter_passed:
            summary_parts.append("WARNING: Safety filters did not pass for this output.")

        # Caveats
        caveats: List[str] = []
        if rec.confidence < 0.5:
            caveats.append("low_model_confidence")
        if not rec.rag_chunks:
            caveats.append("no_rag_grounding")
        if rec.factors.get("citation_density", 0) < 0.5:
            caveats.append("low_citation_density")
        if not rec.safety_filter_passed:
            caveats.append("safety_filter_failed")
        if composite < 0.5:
            caveats.append("low_composite_trust_score")

        return {
            "decision_id": decision_id,
            "summary": " ".join(summary_parts),
            "contributing_factors": ranked,
            "supporting_sources": sources,
            "composite_score": round(composite, 3),
            "caveats": caveats,
        }

    # ── Decision lineage ─────────────────────────────────────────────
    def lineage(self, decision_id: str) -> LineageGraph:
        """Trace from an AI decision back through RAG chunks → embeddings → source docs.

        Returns a DAG (typically a star with the decision at the hub and one
        branch per chunk). The graph is suitable for visualisation in the
        admin console (e.g. with react-flow or vis-network).
        """
        graph = LineageGraph()
        rec = self.get(decision_id)
        if rec is None:
            return graph

        # Root node: the decision itself
        graph.nodes.append(LineageNode(
            node_type="decision",
            node_id=f"decision:{decision_id}",
            label=f"AI decision ({rec.model})",
            metadata={
                "decision_id": decision_id,
                "user_id": rec.user_id,
                "tenant_id": rec.tenant_id,
                "confidence": rec.confidence,
                "timestamp": rec.timestamp,
            },
        ))

        for chunk in rec.rag_chunks or []:
            chunk_id = chunk.get("chunk_id") or str(uuid.uuid4())
            doc_id = chunk.get("doc_id") or "unknown"

            # Chunk node
            chunk_node_id = f"chunk:{chunk_id}"
            graph.nodes.append(LineageNode(
                node_type="chunk",
                node_id=chunk_node_id,
                label=f"Chunk {chunk_id[:8]}",
                metadata={
                    "doc_id": doc_id,
                    "score": chunk.get("score"),
                    "page": chunk.get("page"),
                    "preview": (chunk.get("text") or "")[:120],
                },
            ))
            graph.edges.append(LineageEdge(
                from_node=f"decision:{decision_id}",
                to_node=chunk_node_id,
                relationship="grounded_in",
                weight=float(chunk.get("score", 1.0)),
            ))

            # Embedding node (one per chunk — models can differ per chunk)
            emb_model = chunk.get("embedding_model", "multilingual-MiniLM-L12-v2")
            emb_node_id = f"embedding:{chunk_id}:{emb_model}"
            graph.nodes.append(LineageNode(
                node_type="embedding",
                node_id=emb_node_id,
                label=f"Embedding ({emb_model})",
                metadata={"model": emb_model, "chunk_id": chunk_id},
            ))
            graph.edges.append(LineageEdge(
                from_node=chunk_node_id,
                to_node=emb_node_id,
                relationship="embedded_by",
                weight=1.0,
            ))

            # Source document node (deduplicated by doc_id)
            doc_node_id = f"source_document:{doc_id}"
            if not any(n.node_id == doc_node_id for n in graph.nodes):
                graph.nodes.append(LineageNode(
                    node_type="source_document",
                    node_id=doc_node_id,
                    label=f"Document {doc_id}",
                    metadata={
                        "doc_id": doc_id,
                        "source_uri": chunk.get("source_uri"),
                    },
                ))
            graph.edges.append(LineageEdge(
                from_node=chunk_node_id,
                to_node=doc_node_id,
                relationship="extracted_from",
                weight=1.0,
            ))

        return graph


__all__ = [
    "RAGChunk",
    "DecisionRecord",
    "LineageNode",
    "LineageEdge",
    "LineageGraph",
    "ExplainabilityEngine",
    "FACTOR_WEIGHTS",
]
