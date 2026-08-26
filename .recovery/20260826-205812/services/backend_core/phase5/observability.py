"""
HSAAI AI Observability Metrics (Production)
=============================================
Real AI metrics computed from operational event data.
No placeholders — all metrics are calculated from actual events.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import json, os, math
from .schemas import ObservabilityEvent

STORE = Path(os.getenv("HSAAI_OBSERVABILITY_STORE", "storage/audit_logs/ai_observability.jsonl"))

def _ensure_store():
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.touch(exist_ok=True)

def record_event(event: ObservabilityEvent) -> dict:
    _ensure_store()
    payload = event.model_dump()
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    with STORE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return {"status": "recorded", "event": payload}

def read_events(limit: int = 200) -> list[dict]:
    _ensure_store()
    lines = STORE.read_text(encoding="utf-8").splitlines()[-limit:]
    out=[]
    for line in lines:
        try: out.append(json.loads(line))
        except Exception: continue
    return out


def _compute_rag_metrics(events: list[dict]) -> dict:
    """
    Compute real RAG metrics from event data.
    Each event may contain: has_sources, source_count, query, response, citations.
    """
    rag_events = [e for e in events if e.get("component") == "rag" or e.get("has_sources") is not None]
    if not rag_events:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "mrr": 0.0,
            "ndcg": 0.0,
            "hit_rate": 0.0,
            "faithfulness": 0.0,
            "context_precision": 0.0,
            "context_recall": 0.0,
            "answer_relevancy": 0.0,
            "hallucination_rate": 0.0,
            "sample_size": 0,
        }

    total = len(rag_events)
    hits = sum(1 for e in rag_events if e.get("has_sources"))
    source_counts = [int(e.get("source_count", 0)) for e in rag_events]
    citations = [e for e in rag_events if e.get("citations")]

    # Hit Rate: fraction of queries that returned at least one source
    hit_rate = hits / total if total else 0.0

    # MRR (Mean Reciprocal Rank): average of 1/rank of first relevant result
    reciprocal_ranks = []
    for e in rag_events:
        rank = e.get("first_relevant_rank")
        if rank and rank > 0:
            reciprocal_ranks.append(1.0 / rank)
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0

    # nDCG: normalized discounted cumulative gain
    dcg_values = []
    for e in rag_events:
        relevance_scores = e.get("relevance_scores", [])
        if relevance_scores:
            dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(relevance_scores[:10]))
            ideal = sorted(relevance_scores, reverse=True)
            idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal[:10]))
            dcg_values.append(dcg / idcg if idcg > 0 else 0.0)
    ndcg = sum(dcg_values) / len(dcg_values) if dcg_values else 0.0

    # Faithfulness: fraction of responses with grounded sources
    faithfulness = len(citations) / total if total else 0.0

    # Hallucination Rate: 1 - faithfulness (responses without sources)
    hallucination_rate = 1.0 - faithfulness

    # Context Precision: average relevance of top-k retrieved contexts
    context_precisions = [e.get("context_precision", 0.0) for e in rag_events if e.get("context_precision") is not None]
    context_precision = sum(context_precisions) / len(context_precisions) if context_precisions else 0.0

    # Context Recall: fraction of expected entities found in retrieved context
    context_recalls = [e.get("context_recall", 0.0) for e in rag_events if e.get("context_recall") is not None]
    context_recall = sum(context_recalls) / len(context_recalls) if context_recalls else 0.0

    # Answer Relevancy: average user feedback score (if available)
    relevancy_scores = [e.get("answer_relevancy", 0.0) for e in rag_events if e.get("answer_relevancy") is not None]
    answer_relevancy = sum(relevancy_scores) / len(relevancy_scores) if relevancy_scores else 0.0

    # Precision & Recall (from explicit relevance judgments)
    precision_scores = [e.get("precision", 0.0) for e in rag_events if e.get("precision") is not None]
    recall_scores = [e.get("recall", 0.0) for e in rag_events if e.get("recall") is not None]
    precision = sum(precision_scores) / len(precision_scores) if precision_scores else 0.0
    recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "mrr": round(mrr, 4),
        "ndcg": round(ndcg, 4),
        "hit_rate": round(hit_rate, 4),
        "faithfulness": round(faithfulness, 4),
        "context_precision": round(context_precision, 4),
        "context_recall": round(context_recall, 4),
        "answer_relevancy": round(answer_relevancy, 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "sample_size": total,
    }


def _compute_cost_metrics(events: list[dict]) -> dict:
    """Compute cost metrics from token usage."""
    tokens_in = sum(int(e.get("tokens_in", 0) or 0) for e in events)
    tokens_out = sum(int(e.get("tokens_out", 0) or 0) for e in events)
    total_tokens = tokens_in + tokens_out

    # Cost model (configurable via env)
    cost_per_1k_input = float(os.getenv("COST_PER_1K_INPUT_TOKENS", "0.0"))
    cost_per_1k_output = float(os.getenv("COST_PER_1K_OUTPUT_TOKENS", "0.0"))

    estimated_cost = (tokens_in / 1000 * cost_per_1k_input) + (tokens_out / 1000 * cost_per_1k_output)
    cost_per_request = estimated_cost / len(events) if events else 0.0

    return {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(estimated_cost, 6),
        "cost_per_request_usd": round(cost_per_request, 6),
        "cost_model": "metered" if cost_per_1k_input > 0 else "local_execution",
    }


def ai_metrics() -> dict:
    """
    Compute real AI metrics from operational event data.
    All metrics are calculated from actual events — no placeholders.
    """
    events = read_events(500)
    total = len(events)
    success = sum(1 for e in events if e.get("success", True))
    latency = [e.get("latency_ms") for e in events if isinstance(e.get("latency_ms"), int)]
    by_component = Counter(e.get("component", "unknown") for e in events)
    by_model = Counter(e.get("model", "unknown") for e in events if e.get("model"))

    # Compute RAG metrics from real event data
    rag_metrics = _compute_rag_metrics(events)

    # Compute cost metrics from real token usage
    cost_metrics = _compute_cost_metrics(events)

    # Compute latency percentiles
    latency_sorted = sorted(latency) if latency else []
    p50 = latency_sorted[len(latency_sorted) // 2] if latency_sorted else 0
    p95 = latency_sorted[int(len(latency_sorted) * 0.95)] if latency_sorted else 0
    p99 = latency_sorted[int(len(latency_sorted) * 0.99)] if latency_sorted else 0

    return {
        "events": total,
        "success_rate": round((success / total) * 100, 2) if total else 100.0,
        "avg_latency_ms": int(sum(latency) / len(latency)) if latency else 0,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "p99_latency_ms": p99,
        "rag": rag_metrics,
        "cost": cost_metrics,
        "components": dict(by_component),
        "models": dict(by_model),
        "hallucination_guard": "source-grounded answers only when require_sources=true",
    }
