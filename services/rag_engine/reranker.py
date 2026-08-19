"""
HSAAI Re-Ranker (v4.0 — AI-IMPROVEMENTS)
========================================

Production re-ranking for the RAG engine. Extends the v3.0
BM25 + semantic + proximity fusion with:

  1. **Cross-encoder re-ranking** — uses a cross-encoder model
     (sentence-transformers `cross-encoder/ms-marco-MiniLM-L-6-v2`
     by default) to compute query-aware relevance scores. Falls back
     to a BM25+semantic proxy when the cross-encoder is unavailable.
  2. **MMR (Maximal Marginal Relevance)** — promotes diversity by
     penalizing chunks that are too similar to already-selected ones.
  3. **Business-context boosting** — boosts chunks whose `department`
     or `document_type` matches the query's inferred department.
  4. **Recency boost** — newer documents score higher (configurable
     half-life, default 180 days).
  5. **Explanation scores** — every returned chunk carries an
     `explanation` dict breaking down its score by component so
     callers can show "why this result ranked #1" in the UI.

Backward compatibility: the v3.0 public API (`bm25_scores`,
`normalize_scores`, `rerank`) is preserved. v4.0 only adds new
optional kwargs and an `explanation` field on each result.

The module is import-safe: heavy ML deps (sentence-transformers,
numpy) are imported lazily inside the cross-encoder path so the
reranker can be used in lightweight unit tests without them.
"""
from __future__ import annotations

import logging
import math
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("hsaai.reranker")

# Re-export the v3.0 chunking.tokenize so legacy callers continue to work.
try:
    from .chunking import tokenize  # type: ignore
except Exception:  # pragma: no cover — when imported standalone
    import re as _re

    _AR_DIACRITICS = _re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")
    _ARABIC_NORMALIZATION = str.maketrans({
        "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي",
        "ؤ": "و", "ة": "ه", "ـ": "",
    })

    def normalize_for_search(text: str) -> str:  # type: ignore[no-redef]
        text = _AR_DIACRITICS.sub("", text or "")
        return _re.sub(r"\s+", " ", _re.sub(r"[^\w\u0600-\u06ff]+", " ",
                       text.translate(_ARABIC_NORMALIZATION).lower())).strip()

    def tokenize(text: str) -> list[str]:  # type: ignore[no-redef]
        return _re.findall(r"[\w\u0600-\u06ff]+", normalize_for_search(text))


# ─────────────────────────────────────────────────────────────────────
# v3.0 BM25 (unchanged, kept for backward compat)
# ─────────────────────────────────────────────────────────────────────


def bm25_scores(query: str, docs: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    q_tokens = tokenize(query)
    if not docs or not q_tokens:
        return [0.0 for _ in docs]
    tokenized = [tokenize(d) for d in docs]
    avgdl = sum(len(t) for t in tokenized) / max(1, len(tokenized))
    df: Counter[str] = Counter()
    for toks in tokenized:
        df.update(set(toks))
    scores = []
    for toks in tokenized:
        tf = Counter(toks)
        dl = len(toks) or 1
        score = 0.0
        for term in q_tokens:
            if not tf[term]:
                continue
            idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
            denom = tf[term] + k1 * (1 - b + b * dl / max(1, avgdl))
            score += idf * (tf[term] * (k1 + 1)) / denom
        scores.append(float(score))
    return scores


def normalize_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


# ─────────────────────────────────────────────────────────────────────
# v4.0 — Department inference (for business-context boosting)
# ─────────────────────────────────────────────────────────────────────

# Keyword → department map. Arabic + English keywords.
_DEPARTMENT_KEYWORDS: dict[str, list[str]] = {
    "human_resources": [
        "hr", "human resources", "employee", "leave", "salary", "payroll",
        "موظف", "موارد بشرية", "رواتب", "إجازة", "اجازة", "الراتب",
    ],
    "finance": [
        "budget", "invoice", "cost", "expense", "finance", "financial",
        "ميزانية", "فاتورة", "مالي", "تكلفة", "المالية",
    ],
    "executive": [
        "strategy", "kpi", "okr", "board", "executive", "ceo", "cfo",
        "استراتيجية", "مؤشر", "تنفيذي", "مجلس الإدارة",
    ],
    "documents": [
        "document", "pdf", "file", "contract", "agreement",
        "ملف", "وثيقة", "مستند", "عقد", "اتفاقية",
    ],
    "operations": [
        "operations", "logistics", "supply chain", "warehouse",
        "العمليات", "اللوجستيات", "سلسلة التوريد", "مستودع",
    ],
    "it": [
        "system", "it", "software", "infrastructure", "network",
        "نظام", "تقنية", "برمجيات", "البنية التحتية", "شبكة",
    ],
}

# Document types eligible for boosting.
_DOCUMENT_TYPES: set[str] = {
    "policy", "procedure", "manual", "contract", "invoice", "report",
    "memo", "directive", "plan", "guideline",
}


def infer_department(query: str) -> Optional[str]:
    """Infer the business department from the query string.

    Returns the department with the most keyword hits, or None if no
    keyword matches.
    """
    if not query:
        return None
    q_lower = query.lower()
    best_dept: Optional[str] = None
    best_hits = 0
    for dept, keywords in _DEPARTMENT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in q_lower)
        if hits > best_hits:
            best_hits = hits
            best_dept = dept
    return best_dept


# ─────────────────────────────────────────────────────────────────────
# v4.0 — Cross-encoder (lazy-loaded)
# ─────────────────────────────────────────────────────────────────────

_CROSS_ENCODER = None
_CROSS_ENCODER_LOAD_ERROR: Optional[Exception] = None
_CROSS_ENCODER_MODEL = os.getenv(
    "RERANKER_CROSS_ENCODER",
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
)


def _get_cross_encoder():
    """Lazily load the cross-encoder model. Returns None if unavailable."""
    global _CROSS_ENCODER, _CROSS_ENCODER_LOAD_ERROR
    if _CROSS_ENCODER is not None:
        return _CROSS_ENCODER
    if _CROSS_ENCODER_LOAD_ERROR is not None:
        return None
    if os.getenv("RERANKER_DISABLE_CROSS_ENCODER", "false").lower() == "true":
        _CROSS_ENCODER_LOAD_ERROR = RuntimeError("disabled by env")
        return None
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
        _CROSS_ENCODER = CrossEncoder(_CROSS_ENCODER_MODEL)
        logger.info("Cross-encoder loaded: %s", _CROSS_ENCODER_MODEL)
        return _CROSS_ENCODER
    except Exception as exc:
        _CROSS_ENCODER_LOAD_ERROR = exc
        logger.info(
            "Cross-encoder unavailable (%s) — using BM25+semantic proxy.",
            exc,
        )
        return None


def _cross_encoder_scores(query: str, docs: list[str]) -> Optional[list[float]]:
    """Score (query, doc) pairs with the cross-encoder. Returns None
    if the cross-encoder is unavailable."""
    model = _get_cross_encoder()
    if model is None or not docs:
        return None
    try:
        pairs = [(query, d) for d in docs]
        raw = model.predict(pairs)
        # Cross-encoder returns logits — squash with sigmoid to [0,1].
        out = []
        for x in raw:
            try:
                x = float(x)
            except Exception:
                x = 0.0
            out.append(1.0 / (1.0 + math.exp(-x)) if x > -50 else 0.0)
        return out
    except Exception as exc:
        logger.warning("Cross-encoder prediction failed: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────
# v4.0 — Recency boost
# ─────────────────────────────────────────────────────────────────────


def _parse_timestamp(ts: Any) -> Optional[float]:
    """Parse a timestamp from a chunk payload into a Unix epoch float.

    Accepts: int/float epoch, ISO-8601 string, dict with `created_at`
    or `ts` key.
    """
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        # Try ISO-8601 first.
        try:
            from datetime import datetime
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            return datetime.fromisoformat(ts).timestamp()
        except Exception:
            try:
                return float(ts)
            except Exception:
                return None
    if isinstance(ts, dict):
        for key in ("created_at", "ts", "timestamp", "uploaded_at"):
            if key in ts:
                return _parse_timestamp(ts[key])
    return None


def _recency_boost(ts: Any, *, half_life_days: float = 180.0, now: Optional[float] = None) -> float:
    """Return a recency boost in [0, 1].

    Documents dated `now` → 1.0. Documents older than `half_life_days`
    decay exponentially. Documents with no timestamp get 0.5 (neutral).
    """
    epoch = _parse_timestamp(ts)
    if epoch is None:
        return 0.5
    now = now if now is not None else time.time()
    age_days = max(0.0, (now - epoch) / 86400.0)
    return math.pow(0.5, age_days / half_life_days)


# ─────────────────────────────────────────────────────────────────────
# v4.0 — Business-context boost
# ─────────────────────────────────────────────────────────────────────


def _business_boost(chunk: dict[str, Any], inferred_dept: Optional[str]) -> tuple[float, str]:
    """Return (boost_0_to_1, reason). Boosts chunks whose department
    or document_type matches the inferred department or the document
    type set."""
    boost = 0.0
    reason = ""
    chunk_dept = (chunk.get("department") or chunk.get("domain") or "").lower().strip()
    chunk_dtype = (chunk.get("document_type") or chunk.get("doc_type") or "").lower().strip()

    if inferred_dept and chunk_dept and inferred_dept in chunk_dept:
        boost = max(boost, 0.15)
        reason = f"dept_match:{chunk_dept}"
    if chunk_dtype and chunk_dtype in _DOCUMENT_TYPES:
        boost = max(boost, 0.10)
        if reason:
            reason += f"+doctype:{chunk_dtype}"
        else:
            reason = f"doctype:{chunk_dtype}"
    return boost, reason


# ─────────────────────────────────────────────────────────────────────
# v4.0 — MMR (Maximal Marginal Relevance) for diversity
# ─────────────────────────────────────────────────────────────────────


def _mmr_rerank(
    candidates: list[dict[str, Any]],
    *,
    lambda_: float = 0.7,
    top_k: int = 10,
    similarity_fn=None,
) -> list[dict[str, Any]]:
    """Greedy MMR selection.

    Args:
        candidates: List of dicts each with `rerank_score` and `text`.
        lambda_: Trade-off between relevance (1.0) and diversity (0.0).
        top_k: Number of items to select.

    Returns:
        Re-ordered list of length ≤ top_k maximizing:
            lambda_ * rel(item) - (1 - lambda_) * max_sim(item, selected)
    """
    if not candidates:
        return []
    if len(candidates) <= 1:
        return list(candidates)

    # Default similarity: token Jaccard (cheap, no deps).
    if similarity_fn is None:
        def similarity_fn(a: str, b: str) -> float:
            ta = set(tokenize(a))
            tb = set(tokenize(b))
            if not ta or not tb:
                return 0.0
            return len(ta & tb) / len(ta | tb)

    selected: list[dict[str, Any]] = []
    remaining = list(candidates)
    max_rel = max((c.get("rerank_score", 0.0) for c in remaining), default=0.0)
    if max_rel <= 0:
        max_rel = 1.0

    while remaining and len(selected) < top_k:
        best_item = None
        best_score = -float("inf")
        for item in remaining:
            rel = item.get("rerank_score", 0.0) / max_rel
            if not selected:
                diversity = 0.0
            else:
                diversity = max(
                    similarity_fn(item.get("text", ""), s.get("text", ""))
                    for s in selected
                )
            mmr = lambda_ * rel - (1 - lambda_) * diversity
            if mmr > best_score:
                best_score = mmr
                best_item = item
        if best_item is None:
            break
        selected.append(best_item)
        remaining.remove(best_item)

    return selected


# ─────────────────────────────────────────────────────────────────────
# v4.0 — Explanation dataclass
# ─────────────────────────────────────────────────────────────────────


@dataclass
class RerankExplanation:
    """Per-result score breakdown for UI/debugging."""
    cross_encoder_score: float = 0.0
    semantic_score: float = 0.0
    lexical_score: float = 0.0
    proximity_score: float = 0.0
    business_boost: float = 0.0
    recency_boost: float = 0.0
    mmr_penalty: float = 0.0
    final_score: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cross_encoder_score": round(self.cross_encoder_score, 4),
            "semantic_score": round(self.semantic_score, 4),
            "lexical_score": round(self.lexical_score, 4),
            "proximity_score": round(self.proximity_score, 4),
            "business_boost": round(self.business_boost, 4),
            "recency_boost": round(self.recency_boost, 4),
            "mmr_penalty": round(self.mmr_penalty, 4),
            "final_score": round(self.final_score, 4),
            "reason": self.reason,
        }


# ─────────────────────────────────────────────────────────────────────
# v4.0 — Main rerank() (backward-compatible signature)
# ─────────────────────────────────────────────────────────────────────


def rerank(
    query: str,
    hits: list[dict],
    semantic_weight: float = 0.30,
    lexical_weight: float = 0.35,
    proximity_weight: float = 0.10,
    cross_encoder_weight: float = 0.15,
    business_weight: float = 0.05,
    recency_weight: float = 0.05,
    *,
    use_cross_encoder: bool = True,
    use_mmr: bool = True,
    mmr_lambda: float = 0.7,
    mmr_top_k: Optional[int] = None,
    recency_half_life_days: float = 180.0,
    return_explanations: bool = True,
) -> list[dict]:
    """Re-rank RAG hits with cross-encoder + MMR + business + recency.

    FIX-31: Rebalanced default weights — lexical_weight is now the largest
    single component (0.35, up from 0.25) and semantic_weight reduced (0.30,
    down from 0.35). Rationale: in hybrid retrieval, a strong lexical match
    (exact keyword/phrase overlap) is a more reliable signal of relevance
    than a noisy semantic similarity score, especially for Arabic queries
    where embedding models are less mature. The previous blend let a
    high-semantic-score but lexically-unrelated result outrank a strong
    lexical match, which broke user expectations (see
    test_hybrid_reranker_promotes_lexical_match). The new blend ensures
    that when lexical_score is high and semantic_score is moderate, the
    lexical match wins — while still allowing semantic signals to break
    ties and handle synonym/morphology cases.

    Backward compatibility:
        The v3.0 positional signature (query, hits, semantic_weight,
        lexical_weight, proximity_weight) still works. v4.0 splits the
        weight budget differently to make room for the new layers —
        callers passing only positional args get the v4.0 default blend.

    New kwargs:
        use_cross_encoder: If True, attempt to load and use the
            cross-encoder. If unavailable, falls back to a BM25+
            semantic proxy with the same weight slot.
        use_mmr: If True, apply MMR diversity re-ranking after scoring.
        mmr_lambda: Relevance/diversity trade-off (1.0 = pure
            relevance, 0.0 = pure diversity).
        mmr_top_k: Number of results to keep after MMR (default:
            len(hits)).
        recency_half_life_days: Recency boost half-life. Documents
            older than this decay exponentially.
        return_explanations: If True, attach an `explanation` dict to
            each result.

    Returns:
        List of dicts, sorted by `rerank_score` descending (or by MMR
        order if `use_mmr=True`). Each dict carries all original fields
        plus `semantic_score`, `lexical_score`, `cross_encoder_score`,
        `business_boost`, `recency_boost`, `mmr_penalty`,
        `rerank_score`, and (optionally) `explanation`.
    """
    if not hits:
        return []

    docs = [str(h.get("text", "")) for h in hits]
    bm25 = normalize_scores(bm25_scores(query, docs))
    semantic = normalize_scores([
        float(h.get("score", h.get("semantic_score", 0.0)) or 0.0)
        for h in hits
    ])

    # Cross-encoder scores (or proxy if unavailable).
    ce_scores: Optional[list[float]] = None
    if use_cross_encoder:
        ce_scores = _cross_encoder_scores(query, docs)
    if ce_scores is None:
        # Proxy: average of normalized BM25 and normalized semantic.
        ce_scores = [
            0.5 * (bm25[i] if i < len(bm25) else 0.0) +
            0.5 * (semantic[i] if i < len(semantic) else 0.0)
            for i in range(len(hits))
        ]
        ce_used = False
    else:
        ce_used = True
        ce_scores = normalize_scores(ce_scores)

    q_terms = set(tokenize(query))
    inferred_dept = infer_department(query)
    now = time.time()

    output: list[dict] = []
    for i, h in enumerate(hits):
        # Proximity (carry-over from v3.0).
        terms = tokenize(str(h.get("text", "")))
        proximity = 0.0
        if q_terms and terms:
            positions = [idx for idx, token in enumerate(terms) if token in q_terms]
            if len(positions) >= 2:
                span = max(positions) - min(positions) + 1
                proximity = min(1.0, len(positions) / max(1, span))
            else:
                proximity = len(positions) / max(1, len(q_terms))

        # Business-context boost.
        biz_boost, biz_reason = _business_boost(h, inferred_dept)

        # Recency boost.
        recency = _recency_boost(
            h.get("created_at") or h.get("uploaded_at") or h.get("timestamp"),
            half_life_days=recency_half_life_days,
            now=now,
        )

        ce_i = ce_scores[i] if i < len(ce_scores) else 0.0
        sem_i = semantic[i] if i < len(semantic) else 0.0
        lex_i = bm25[i] if i < len(bm25) else 0.0

        # Weighted fusion. Weights are expected to sum to ~1.0; if they
        # don't, we normalize at the end.
        raw_total = (
            semantic_weight * sem_i
            + lexical_weight * lex_i
            + proximity_weight * proximity
            + cross_encoder_weight * ce_i
            + business_weight * biz_boost
            + recency_weight * recency
        )
        weight_sum = (
            semantic_weight + lexical_weight + proximity_weight
            + cross_encoder_weight + business_weight + recency_weight
        )
        final = raw_total / max(weight_sum, 1e-9)

        item = dict(h)
        item["semantic_score"] = float(sem_i)
        item["lexical_score"] = float(lex_i)
        item["cross_encoder_score"] = float(ce_i)
        item["cross_encoder_used"] = bool(ce_used)
        item["proximity_score"] = float(proximity)
        item["business_boost"] = float(biz_boost)
        item["recency_boost"] = float(recency)
        item["rerank_score"] = float(final)
        item["score"] = float(final)  # backward-compat alias

        if return_explanations:
            reason_parts = []
            if ce_used:
                reason_parts.append("cross-encoder")
            else:
                reason_parts.append("bm25+semantic-proxy")
            if biz_reason:
                reason_parts.append(biz_reason)
            if recency > 0.6:
                reason_parts.append("recent")
            elif recency < 0.4:
                reason_parts.append("stale")
            item["explanation"] = RerankExplanation(
                cross_encoder_score=float(ce_i),
                semantic_score=float(sem_i),
                lexical_score=float(lex_i),
                proximity_score=float(proximity),
                business_boost=float(biz_boost),
                recency_boost=float(recency),
                mmr_penalty=0.0,  # filled in by MMR step
                final_score=float(final),
                reason=", ".join(reason_parts),
            ).to_dict()
        output.append(item)

    # Initial sort by rerank_score (MMR will reorder for diversity).
    output.sort(key=lambda x: x.get("rerank_score", x.get("score", 0.0)), reverse=True)

    if use_mmr and len(output) > 1:
        top_k = mmr_top_k if mmr_top_k is not None else len(output)
        reordered = _mmr_rerank(output, lambda_=mmr_lambda, top_k=top_k)
        # Compute MMR penalty = (original_score - final_position_score).
        # We approximate the penalty as the drop in `rerank_score` from
        # the best candidate to the selected one. This is informative
        # for UI: "this result was selected to diversify the set, at a
        # small relevance cost of X".
        if reordered and return_explanations:
            max_orig = max((r.get("rerank_score", 0.0) for r in output), default=0.0)
            for item in reordered:
                penalty = max(0.0, max_orig - (item.get("rerank_score", 0.0)))
                if "explanation" in item:
                    item["explanation"]["mmr_penalty"] = round(float(penalty), 4)
        output = reordered

    return output


__all__ = [
    "bm25_scores",
    "normalize_scores",
    "rerank",
    "infer_department",
    "RerankExplanation",
]
