"""
HSAAI Hallucination Guard (v1.0 — AI-IMPROVEMENTS)
===================================================

Production-grade hallucination mitigation layer for HSAAI's RAG/LLM
pipeline. Sits between the LLM gateway and the response consumer and
verifies that every factual claim in the response is *grounded* in the
retrieved context.

Layers of defense
-----------------
1. **Citation verification** — every claim must have a source citation
   in the form `[n]` that maps to a retrieved chunk. Claims without
   citations are flagged.
2. **Confidence threshold** — if the LLM reports confidence < 0.7
   (or if the groundedness score is < 0.7), append an explicit
   "This response may be incomplete" notice.
3. **Factual consistency check** — compare the response against the
   retrieved context using cosine similarity of sentence-level embeddings
   (or, when embeddings are unavailable, a Jaccard fallback).
4. **Groundedness score** — percentage of response sentences that are
   supported by the retrieved context (similarity ≥ threshold).
5. **Safe fallback** — if groundedness < 0.5, return the safe fallback
   string instead of the ungrounded response.

The module is dependency-light: it uses `math` + `re` for the Jaccard
fallback, and lazily imports `sentence_transformers`/`numpy` only when
the caller requests embedding-based scoring. This means the guard can
run in lightweight environments (e.g. the API gateway) without paying
the embedding-model load cost.

Usage
-----
    from packages.common.ai.hallucination_guard import HallucinationGuard, GuardResult

    guard = HallucinationGuard(
        min_groundedness=0.5,        # below this → safe fallback
        warn_threshold=0.7,          # below this → append incompleteness notice
        similarity_threshold=0.55,   # sentence-vs-context cosine cutoff
    )

    result = guard.evaluate(
        response="...LLM output...",
        context_chunks=[{"text": "...", "doc_id": "..."}],
        llm_confidence=0.62,         # optional
    )
    if result.use_fallback:
        return result.safe_fallback
    return result.final_response
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("hsaai.hallucination_guard")

# ─────────────────────────────────────────────────────────────────────
# Constants & defaults
# ─────────────────────────────────────────────────────────────────────

DEFAULT_MIN_GROUNDEDNESS = 0.5
DEFAULT_WARN_THRESHOLD = 0.7
DEFAULT_SIMILARITY_THRESHOLD = 0.55
DEFAULT_MIN_CONFIDENCE = 0.7

# Citation markers — matches `[1]`, `[2]`, `[1,2]`, `[1, 2, 3]`, `[1-3]`.
# We capture the inner list of indices so the citation engine can map
# them back to retrieved chunks.
_CITATION_RE = re.compile(r"\[((?:\d+(?:\s*[-,]\s*\d+)*))\]")

# Sentence splitter — handles English (.!?), Arabic (؟؛), and newlines.
# The pattern preserves the sentence boundaries so we can recover spans.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?؟؛])\s+|\n{2,}")

# Incompleteness notices — appended to the response when confidence is
# low. Both English and Arabic versions are available; the guard picks
# based on the dominant script of the response.
_INCOMPLETENESS_NOTICE_EN = (
    "\n\n⚠️ This response may be incomplete. Please verify with the "
    "cited sources before relying on it for decisions."
)
_INCOMPLETENESS_NOTICE_AR = (
    "\n\n⚠️ قد تكون هذه الإجابة غير مكتملة. يرجى التحقق من المصادر "
    "المُستشهد بها قبل الاعتماد عليها لاتخاذ القرارات."
)

# Safe fallback string returned when groundedness is below the minimum.
SAFE_FALLBACK_EN = (
    "I cannot confidently answer this question from the available internal "
    "sources. Please refine your question, upload additional documents, or "
    "contact the relevant department."
)
SAFE_FALLBACK_AR = (
    "تعذر تقديم إجابة موثوقة من المصادر الداخلية المتاحة. يرجى إعادة صياغة "
    "السؤال أو رفع وثائق إضافية أو التواصل مع الإدارة المختصة."
)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _is_arabic_dominant(text: str) -> bool:
    """Return True if the text contains more Arabic than Latin characters."""
    ar = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    la = sum(1 for c in text if c.isascii() and c.isalpha())
    return ar > la


def _split_sentences(text: str) -> list[str]:
    """Split text into non-empty sentences (English + Arabic aware)."""
    if not text:
        return []
    sentences = []
    for raw in _SENTENCE_SPLIT_RE.split(text):
        s = (raw or "").strip()
        if len(s) >= 3:  # ignore fragments like "1." or "[2]"
            sentences.append(s)
    return sentences


def _extract_citation_indices(sentence: str) -> list[int]:
    """Extract all unique citation indices referenced in a sentence.

    Supports `[1]`, `[2,3]`, `[1-3]`. Returns a sorted list of 1-based
    indices. Returns an empty list if no citations are present.
    """
    indices: set[int] = set()
    for match in _CITATION_RE.finditer(sentence):
        inner = match.group(1)
        # Split on commas, then expand ranges like "1-3".
        for part in inner.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    lo, hi = part.split("-", 1)
                    lo_i, hi_i = int(lo.strip()), int(hi.strip())
                    if hi_i < lo_i:
                        lo_i, hi_i = hi_i, lo_i
                    # Sanity bound — citations above 50 are almost
                    # certainly an artifact (e.g. a year like "[2024]").
                    for i in range(lo_i, min(hi_i, 50) + 1):
                        indices.add(i)
                except ValueError:
                    continue
            else:
                try:
                    n = int(part)
                    if 1 <= n <= 50:
                        indices.add(n)
                except ValueError:
                    continue
    return sorted(indices)


def _tokenize_light(text: str) -> set[str]:
    """Lightweight word tokenizer for the Jaccard fallback.

    Lowercases, strips punctuation, splits on whitespace. Returns a set
    of tokens. We deliberately exclude very short tokens (length < 2)
    to reduce noise from punctuation artifacts.
    """
    text = (text or "").lower()
    # Preserve Arabic letter ranges when stripping punctuation.
    text = re.sub(r"[^\w\u0600-\u06ff]+", " ", text)
    return {tok for tok in text.split() if len(tok) >= 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets (0.0 - 1.0)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ─────────────────────────────────────────────────────────────────────
# Embedding-based similarity (lazy import to keep the guard lightweight)
# ─────────────────────────────────────────────────────────────────────


_EMBED_CACHE: dict[str, list[float]] = {}
_EMBED_MODEL = None
_EMBED_MODEL_LOAD_ERROR: Optional[Exception] = None


def _get_embed_model():
    """Lazily load the sentence-transformers model for the guard.

    We use the same multilingual MiniLM that the RAG engine uses so the
    similarity scores are consistent with retrieval scoring.
    """
    global _EMBED_MODEL, _EMBED_MODEL_LOAD_ERROR
    if _EMBED_MODEL is not None:
        return _EMBED_MODEL
    if _EMBED_MODEL_LOAD_ERROR is not None:
        return None
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        import os
        model_name = os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        _EMBED_MODEL = SentenceTransformer(model_name)
        return _EMBED_MODEL
    except Exception as exc:  # pragma: no cover - depends on env
        _EMBED_MODEL_LOAD_ERROR = exc
        logger.info(
            "Hallucination guard: sentence-transformers unavailable (%s) — "
            "falling back to Jaccard similarity.",
            exc,
        )
        return None


def _embed(text: str) -> Optional[list[float]]:
    """Embed a single text, with an in-process cache. Returns None if
    no embedding model is available."""
    model = _get_embed_model()
    if model is None:
        return None
    if text in _EMBED_CACHE:
        return _EMBED_CACHE[text]
    try:
        vec = model.encode(text, normalize_embeddings=True)
        out = [float(x) for x in vec]
    except Exception as exc:
        logger.debug("Embedding failed for text (%s): %s", text[:40], exc)
        return None
    _EMBED_CACHE[text] = out
    # Bound cache growth — keep the last 4096 entries.
    if len(_EMBED_CACHE) > 4096:
        # Drop an arbitrary ~25% of the oldest entries.
        for key in list(_EMBED_CACHE.keys())[:1024]:
            _EMBED_CACHE.pop(key, None)
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity for two equal-length vectors. Vectors are
    assumed normalized (the embedder normalizes by default), so this
    is just a dot product — but we guard against zero norms anyway."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


def _best_similarity(
    sentence: str,
    context_texts: list[str],
    context_embeddings: Optional[list[list[float]]] = None,
) -> float:
    """Return the best similarity score between `sentence` and any
    context text. Uses cosine similarity of embeddings when available,
    falls back to Jaccard otherwise."""
    if not context_texts:
        return 0.0
    # Embedding path:
    if context_embeddings and any(context_embeddings):
        sent_emb = _embed(sentence)
        if sent_emb is not None:
            best = 0.0
            for ctx_emb in context_embeddings:
                if ctx_emb is None:
                    continue
                sim = _cosine(sent_emb, ctx_emb)
                if sim > best:
                    best = sim
            return best
    # Jaccard fallback:
    sent_tokens = _tokenize_light(sentence)
    if not sent_tokens:
        return 0.0
    best = 0.0
    for ctx in context_texts:
        ctx_tokens = _tokenize_light(ctx)
        if not ctx_tokens:
            continue
        j = _jaccard(sent_tokens, ctx_tokens)
        if j > best:
            best = j
    return best


# ─────────────────────────────────────────────────────────────────────
# Public dataclass
# ─────────────────────────────────────────────────────────────────────


@dataclass
class SentenceCheck:
    """Per-sentence grounding details."""
    sentence: str
    supported: bool
    best_similarity: float
    citation_indices: list[int]
    citation_valid: bool  # True if every cited index points to a real chunk


@dataclass
class GuardResult:
    """Result of HallucinationGuard.evaluate()."""
    final_response: str
    use_fallback: bool
    safe_fallback: str
    groundedness: float  # 0.0 - 1.0 — fraction of supported sentences
    avg_similarity: float
    min_similarity: float
    llm_confidence: Optional[float]
    sentences_total: int
    sentences_supported: int
    sentences_with_citations: int
    sentences_missing_citations: int
    sentences_invalid_citations: int
    incomplete_notice_appended: bool
    sentence_details: list[SentenceCheck] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_response": self.final_response,
            "use_fallback": self.use_fallback,
            "safe_fallback": self.safe_fallback,
            "groundedness": round(self.groundedness, 4),
            "avg_similarity": round(self.avg_similarity, 4),
            "min_similarity": round(self.min_similarity, 4),
            "llm_confidence": self.llm_confidence,
            "sentences_total": self.sentences_total,
            "sentences_supported": self.sentences_supported,
            "sentences_with_citations": self.sentences_with_citations,
            "sentences_missing_citations": self.sentences_missing_citations,
            "sentences_invalid_citations": self.sentences_invalid_citations,
            "incomplete_notice_appended": self.incomplete_notice_appended,
            "notes": self.notes,
        }


# ─────────────────────────────────────────────────────────────────────
# HallucinationGuard
# ─────────────────────────────────────────────────────────────────────


class HallucinationGuard:
    """Evaluate LLM responses for groundedness and citation accuracy.

    Parameters
    ----------
    min_groundedness : float
        If the fraction of supported sentences is below this, the guard
        returns `use_fallback=True` and the caller should serve
        `safe_fallback` instead of the ungrounded response.
    warn_threshold : float
        If groundedness (or LLM confidence) is below this, an
        "incomplete" notice is appended to the response.
    similarity_threshold : float
        Per-sentence similarity cutoff above which a sentence is
        considered "supported" by the retrieved context.
    min_confidence : float
        LLM-confidence threshold below which the incomplete notice is
        also appended.
    fallback_en / fallback_ar : str
        Override the default safe-fallback strings.
    """

    def __init__(
        self,
        *,
        min_groundedness: float = DEFAULT_MIN_GROUNDEDNESS,
        warn_threshold: float = DEFAULT_WARN_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        fallback_en: str = SAFE_FALLBACK_EN,
        fallback_ar: str = SAFE_FALLBACK_AR,
        use_embeddings: bool = True,
    ):
        self.min_groundedness = float(min_groundedness)
        self.warn_threshold = float(warn_threshold)
        self.similarity_threshold = float(similarity_threshold)
        self.min_confidence = float(min_confidence)
        self.fallback_en = fallback_en
        self.fallback_ar = fallback_ar
        self.use_embeddings = bool(use_embeddings)

    # ── public API ──────────────────────────────────────────────────

    def evaluate(
        self,
        response: str,
        context_chunks: list[dict[str, Any]],
        *,
        llm_confidence: Optional[float] = None,
        require_citations: bool = True,
    ) -> GuardResult:
        """Evaluate the response against the retrieved context.

        Args:
            response: The LLM-generated answer text.
            context_chunks: List of chunk dicts, each with at least a
                `text` key (and optionally `doc_id`, `filename`,
                `chunk_index`, …). These are the chunks retrieved by
                the RAG engine.
            llm_confidence: Optional float in [0,1] reported by the LLM.
                If below `min_confidence`, an incomplete notice is
                appended to the final response.
            require_citations: If True, sentences that make factual
                claims (heuristic: contain a number, a proper noun, or
                are longer than 80 chars) must carry a `[n]` citation.
                Otherwise they are flagged as missing-citation.

        Returns:
            GuardResult. Callers should check `use_fallback` first; if
            True, serve `safe_fallback` instead of `final_response`.
        """
        if not response or not response.strip():
            # Empty response — return fallback.
            return self._fallback_result(response or "", reason="empty_response")

        context_texts = [
            (c.get("text") or "").strip()
            for c in (context_chunks or [])
            if (c.get("text") or "").strip()
        ]
        if not context_texts:
            # No context retrieved → every claim is ungrounded by
            # definition. This is the strongest hallucination signal.
            logger.warning(
                "Hallucination guard: no context chunks provided — "
                "returning fallback."
            )
            return self._fallback_result(
                response, reason="no_context_chunks"
            )

        # Pre-compute context embeddings (one batch call).
        context_embeddings: list[Optional[list[float]]] = []
        if self.use_embeddings:
            for txt in context_texts:
                context_embeddings.append(_embed(txt))

        sentences = _split_sentences(response)
        if not sentences:
            return self._fallback_result(response, reason="unparseable_response")

        sentence_details: list[SentenceCheck] = []
        sim_scores: list[float] = []
        supported_count = 0
        with_citation_count = 0
        missing_citation_count = 0
        invalid_citation_count = 0

        max_valid_index = len(context_chunks)

        for sentence in sentences:
            best_sim = _best_similarity(
                sentence, context_texts, context_embeddings
            )
            sim_scores.append(best_sim)
            supported = best_sim >= self.similarity_threshold
            if supported:
                supported_count += 1

            citations = _extract_citation_indices(sentence)
            if citations:
                with_citation_count += 1
                # Citation is valid if every index is in [1, max_valid_index].
                invalid = [i for i in citations if i < 1 or i > max_valid_index]
                citation_valid = not invalid
                if not citation_valid:
                    invalid_citation_count += 1
            else:
                citation_valid = True  # no citation → trivially valid
                if require_citations and self._looks_like_claim(sentence):
                    missing_citation_count += 1

            sentence_details.append(SentenceCheck(
                sentence=sentence,
                supported=supported,
                best_similarity=best_sim,
                citation_indices=citations,
                citation_valid=citation_valid,
            ))

        total = len(sentences)
        groundedness = supported_count / total if total else 0.0
        avg_sim = sum(sim_scores) / len(sim_scores) if sim_scores else 0.0
        min_sim = min(sim_scores) if sim_scores else 0.0

        notes: list[str] = []
        use_fallback = groundedness < self.min_groundedness
        if use_fallback:
            notes.append(
                f"groundedness {groundedness:.2f} < "
                f"min_groundedness {self.min_groundedness:.2f}"
            )

        # Build the final response — possibly with an incompleteness notice.
        final_response = response
        append_notice = False
        if llm_confidence is not None and llm_confidence < self.min_confidence:
            append_notice = True
            notes.append(
                f"llm_confidence {llm_confidence:.2f} < "
                f"min_confidence {self.min_confidence:.2f}"
            )
        if groundedness < self.warn_threshold and not use_fallback:
            append_notice = True
            notes.append(
                f"groundedness {groundedness:.2f} < "
                f"warn_threshold {self.warn_threshold:.2f}"
            )

        if append_notice and not use_fallback:
            notice = (
                _INCOMPLETENESS_NOTICE_AR
                if _is_arabic_dominant(final_response)
                else _INCOMPLETENESS_NOTICE_EN
            )
            if notice.strip() not in final_response:
                final_response = final_response.rstrip() + notice

        safe_fallback = (
            self.fallback_ar if _is_arabic_dominant(response) else self.fallback_en
        )

        return GuardResult(
            final_response=final_response,
            use_fallback=use_fallback,
            safe_fallback=safe_fallback,
            groundedness=groundedness,
            avg_similarity=avg_sim,
            min_similarity=min_sim,
            llm_confidence=llm_confidence,
            sentences_total=total,
            sentences_supported=supported_count,
            sentences_with_citations=with_citation_count,
            sentences_missing_citations=missing_citation_count,
            sentences_invalid_citations=invalid_citation_count,
            incomplete_notice_appended=append_notice and not use_fallback,
            sentence_details=sentence_details,
            notes=notes,
        )

    # ── helpers ─────────────────────────────────────────────────────

    def _looks_like_claim(self, sentence: str) -> bool:
        """Heuristic: does this sentence make a factual claim?

        We consider a sentence to be a claim if it:
          - contains a digit (number, year, statistic), OR
          - is longer than 80 characters (i.e. a substantive statement), OR
          - contains a quoted phrase (single/double quotes).
        Pure greetings, questions, or short connector sentences are not
        flagged.
        """
        if not sentence:
            return False
        # Skip interrogative sentences — they're not claims.
        if sentence.rstrip().endswith(("?", "؟")):
            return False
        # Skip greetings / acknowledgements.
        first_word = sentence.split()[0].lower().strip(".,;:!?")
        if first_word in {"hello", "hi", "hey", "مرحبا", "أهلا", "اهلا", "thanks", "شكرا"}:
            return False
        if any(ch.isdigit() for ch in sentence):
            return True
        if len(sentence) > 80:
            return True
        if '"' in sentence or "'" in sentence or "«" in sentence or "»" in sentence:
            return True
        return False

    def _fallback_result(self, response: str, *, reason: str) -> GuardResult:
        safe = (
            self.fallback_ar if _is_arabic_dominant(response) else self.fallback_en
        )
        return GuardResult(
            final_response=response,
            use_fallback=True,
            safe_fallback=safe,
            groundedness=0.0,
            avg_similarity=0.0,
            min_similarity=0.0,
            llm_confidence=None,
            sentences_total=0,
            sentences_supported=0,
            sentences_with_citations=0,
            sentences_missing_citations=0,
            sentences_invalid_citations=0,
            incomplete_notice_appended=False,
            sentence_details=[],
            notes=[reason],
        )


# ─────────────────────────────────────────────────────────────────────
# Module-level convenience instance
# ─────────────────────────────────────────────────────────────────────

_default_guard: Optional[HallucinationGuard] = None


def get_default_guard() -> HallucinationGuard:
    """Return a process-wide default guard instance."""
    global _default_guard
    if _default_guard is None:
        _default_guard = HallucinationGuard()
    return _default_guard


__all__ = [
    "HallucinationGuard",
    "GuardResult",
    "SentenceCheck",
    "SAFE_FALLBACK_EN",
    "SAFE_FALLBACK_AR",
    "get_default_guard",
]
