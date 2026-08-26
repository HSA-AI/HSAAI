"""
HSAAI Citation Engine (v1.0 — AI-IMPROVEMENTS)
===============================================

Generates, verifies, and formats inline citations for LLM-generated
answers in the HSAAI RAG pipeline.

Capabilities
------------
1. **Inline citation insertion** — post-processes an LLM answer to
   inject `[n]` markers next to claims that are supported by retrieved
   chunks.
2. **Citation map** — produces a structured table mapping each `[n]`
   back to the underlying chunk: `{doc_id, title, page, chunk_text,
   confidence}`.
3. **Citation accuracy verification** — for every `[n]` in the answer,
   verifies that the cited claim actually appears in (or is supported
   by) the referenced source. Uses Jaccard / cosine similarity against
   the source's `chunk_text`.
4. **APA + Arabic citation formats** — supports both Western academic
   APA-style references and an Arabic citation format.
5. **Anti-fabrication** — if no retrieved source supports a claim, the
   engine omits the citation and flags the sentence as `unsourced`
   (so the caller can either append a disclaimer or strip the claim).

The engine is intentionally model-free: it uses lexical + embedding
similarity (the embedding path is optional and lazily imported) to
decide whether a claim is supported. This keeps it fast, deterministic,
and easy to unit-test.

Usage
-----
    from packages.common.ai.citation_engine import CitationEngine

    engine = CitationEngine(similarity_threshold=0.45)
    result = engine.cite(
        answer="Employees receive 30 days of paid annual leave.",
        sources=[
            {"doc_id": "d1", "title": "Leave Policy 2024",
             "page": 4, "chunk_text": "Annual leave: 30 days paid..."},
        ],
    )
    print(result.cited_answer)   # "Employees receive 30 days of paid annual leave [1]."
    print(result.citations)      # [{index: 1, doc_id: "d1", ...}]
    print(result.unsourced_claims)  # []
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("hsaai.citation_engine")

# ─────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────

DEFAULT_SIMILARITY_THRESHOLD = 0.45  # Jaccard fallback cutoff
DEFAULT_EMBEDDING_THRESHOLD = 0.55   # cosine cutoff (stricter — embeddings over-score)
MAX_CITATIONS_PER_SENTENCE = 3
SENTENCE_END_PUNCT = (".", "!", "؟", "؟.")
_CITATION_RE = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")


# ─────────────────────────────────────────────────────────────────────
# Helpers (reused from hallucination_guard pattern)
# ─────────────────────────────────────────────────────────────────────


def _is_arabic_dominant(text: str) -> bool:
    if not text:
        return False
    ar = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    la = sum(1 for c in text if c.isascii() and c.isalpha())
    return ar > la


def _split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Split text into sentences with character spans."""
    if not text:
        return []
    spans: list[tuple[str, int, int]] = []
    start = 0
    for m in re.finditer(r"(?<=[.!?؟؛])\s+|\n{2,}", text):
        end = m.start()
        s = text[start:end].strip()
        if len(s) >= 3:
            spans.append((s, start, end))
        start = m.end()
    tail = text[start:].strip()
    if tail and len(tail) >= 3:
        spans.append((tail, start, len(text)))
    return spans


def _tokenize_light(text: str) -> set[str]:
    text = (text or "").lower()
    text = re.sub(r"[^\w\u0600-\u06ff]+", " ", text)
    return {tok for tok in text.split() if len(tok) >= 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ─────────────────────────────────────────────────────────────────────
# Optional embedding similarity (lazy-loaded)
# ─────────────────────────────────────────────────────────────────────

_EMBED_CACHE: dict[str, list[float]] = {}
_EMBED_MODEL = None
_EMBED_MODEL_ERR: Optional[Exception] = None


def _get_embed_model():
    global _EMBED_MODEL, _EMBED_MODEL_ERR
    if _EMBED_MODEL is not None:
        return _EMBED_MODEL
    if _EMBED_MODEL_ERR is not None:
        return None
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        import os
        name = os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        _EMBED_MODEL = SentenceTransformer(name)
        return _EMBED_MODEL
    except Exception as exc:
        _EMBED_MODEL_ERR = exc
        return None


def _embed(text: str) -> Optional[list[float]]:
    model = _get_embed_model()
    if model is None:
        return None
    if text in _EMBED_CACHE:
        return _EMBED_CACHE[text]
    try:
        vec = model.encode(text, normalize_embeddings=True)
        out = [float(x) for x in vec]
    except Exception:
        return None
    _EMBED_CACHE[text] = out
    if len(_EMBED_CACHE) > 4096:
        for key in list(_EMBED_CACHE.keys())[:1024]:
            _EMBED_CACHE.pop(key, None)
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


def _best_similarity(
    sentence: str,
    sources: list[dict[str, Any]],
    cached_embeddings: Optional[list[Optional[list[float]]]] = None,
) -> tuple[int, float]:
    """Return (best_source_index_0based, best_score)."""
    best_idx = -1
    best_score = 0.0
    sent_tokens = _tokenize_light(sentence)

    for i, src in enumerate(sources):
        ctx = (src.get("chunk_text") or src.get("text") or "").strip()
        if not ctx:
            continue
        # Embedding path (preferred).
        if cached_embeddings is not None and cached_embeddings[i] is not None:
            sent_emb = _embed(sentence)
            if sent_emb is not None:
                sim = _cosine(sent_emb, cached_embeddings[i])
                if sim > best_score:
                    best_score = sim
                    best_idx = i
                continue
        # Jaccard fallback.
        if sent_tokens:
            j = _jaccard(sent_tokens, _tokenize_light(ctx))
            if j > best_score:
                best_score = j
                best_idx = i
    return best_idx, best_score


# ─────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────


@dataclass
class Citation:
    """A single citation entry."""
    index: int                # 1-based [n]
    doc_id: Optional[str]
    title: str
    page: Optional[int]
    chunk_text: str
    confidence: float         # 0.0 - 1.0
    supported: bool           # True if citation accuracy verified

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "doc_id": self.doc_id,
            "title": self.title,
            "page": self.page,
            "chunk_text": self.chunk_text[:500] if self.chunk_text else "",
            "confidence": round(self.confidence, 4),
            "supported": self.supported,
        }


@dataclass
class CitationResult:
    """Output of CitationEngine.cite()."""
    cited_answer: str
    citations: list[Citation] = field(default_factory=list)
    unsourced_claims: list[str] = field(default_factory=list)
    invalid_citations: list[int] = field(default_factory=list)
    format_apa: str = ""
    format_arabic: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cited_answer": self.cited_answer,
            "citations": [c.to_dict() for c in self.citations],
            "unsourced_claims": self.unsourced_claims,
            "invalid_citations": self.invalid_citations,
            "format_apa": self.format_apa,
            "format_arabic": self.format_arabic,
        }


# ─────────────────────────────────────────────────────────────────────
# CitationEngine
# ─────────────────────────────────────────────────────────────────────


class CitationEngine:
    """Insert, verify, and format inline citations.

    Parameters
    ----------
    similarity_threshold : float
        Minimum similarity (Jaccard or cosine) for a sentence to be
        considered "supported" by a source. Sentences below this
        threshold are flagged as unsourced.
    use_embeddings : bool
        Whether to attempt embedding-based similarity. Falls back to
        Jaccard when embeddings are unavailable.
    embedding_threshold : float
        Cosine similarity cutoff (only used if embeddings are active).
    max_citations_per_sentence : int
        Cap on the number of citations inserted into a single sentence.
    """

    def __init__(
        self,
        *,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        use_embeddings: bool = True,
        embedding_threshold: float = DEFAULT_EMBEDDING_THRESHOLD,
        max_citations_per_sentence: int = MAX_CITATIONS_PER_SENTENCE,
    ):
        self.similarity_threshold = float(similarity_threshold)
        self.use_embeddings = bool(use_embeddings)
        self.embedding_threshold = float(embedding_threshold)
        self.max_citations_per_sentence = int(max_citations_per_sentence)

    # ── public API ──────────────────────────────────────────────────

    def cite(self, answer: str, sources: list[dict[str, Any]]) -> CitationResult:
        """Insert citations into the answer and verify their accuracy.

        Args:
            answer: The LLM-generated answer text. May already contain
                `[n]` markers (e.g. from a system prompt that asks the
                model to cite) — these are verified, not duplicated.
            sources: List of source dicts. Each must have at least
                `chunk_text` (or `text`). Recommended fields: `doc_id`,
                `title`, `page`.

        Returns:
            CitationResult with `cited_answer`, `citations`,
            `unsourced_claims`, `invalid_citations`, and APA/Arabic
            formatted reference lists.
        """
        if not answer or not answer.strip():
            return CitationResult(cited_answer=answer or "")
        if not sources:
            # No sources → every claim is unsourced.
            result = CitationResult(cited_answer=answer)
            for sent, _, _ in _split_sentences(answer):
                if self._looks_like_claim(sent):
                    result.unsourced_claims.append(sent)
            return result

        # Pre-compute source embeddings once.
        source_embeddings: Optional[list[Optional[list[float]]]] = None
        if self.use_embeddings:
            source_embeddings = []
            for src in sources:
                ctx = (src.get("chunk_text") or src.get("text") or "").strip()
                source_embeddings.append(_embed(ctx) if ctx else None)

        # Walk sentences and either verify existing citations or insert
        # new ones.
        sentences = _split_sentences(answer)
        if not sentences:
            return CitationResult(cited_answer=answer)

        # Build citation index assignment: source_index → citation_index.
        # We assign citations lazily — the first time a source supports
        # a sentence, it gets the next available [n].
        source_to_cite_idx: dict[int, int] = {}
        citations: list[Citation] = []
        unsourced: list[str] = []
        invalid: list[int] = []

        new_answer_parts: list[str] = []
        last_end = 0

        for sent, s_start, s_end in sentences:
            # Keep any text between the end of the last sentence and
            # the start of this one (e.g. whitespace).
            new_answer_parts.append(answer[last_end:s_start])
            last_end = s_end

            existing_cites = self._existing_citations(sent)
            if existing_cites:
                # Verify each existing citation.
                for n in existing_cites:
                    if n < 1 or n > len(sources):
                        invalid.append(n)
                        continue
                    src = sources[n - 1]
                    ctx = (src.get("chunk_text") or src.get("text") or "").strip()
                    sim = self._similarity(sent, ctx, None)
                    supported = sim >= self.similarity_threshold
                    if n not in source_to_cite_idx.values():
                        source_to_cite_idx[len(citations)] = n  # placeholder
                        citations.append(self._build_citation(
                            index=n, source=src, confidence=sim,
                            supported=supported,
                        ))
                    else:
                        # Update confidence if higher.
                        for c in citations:
                            if c.index == n and sim > c.confidence:
                                c.confidence = sim
                                c.supported = supported
                new_answer_parts.append(sent)
                continue

            # No existing citation — find best matching source.
            best_idx, best_sim = _best_similarity(
                sent, sources, source_embeddings,
            )
            threshold = self.embedding_threshold if (
                self.use_embeddings and source_embeddings and any(source_embeddings)
            ) else self.similarity_threshold

            if best_idx >= 0 and best_sim >= threshold:
                # Reuse existing citation index for this source if we've
                # already cited it, else assign a new one.
                cite_idx = None
                for ci, src_i in source_to_cite_idx.items():
                    if src_i == best_idx:
                        cite_idx = ci
                        break
                if cite_idx is None:
                    cite_idx = len(citations) + 1  # 1-based
                    source_to_cite_idx[cite_idx] = best_idx
                    citations.append(self._build_citation(
                        index=cite_idx,
                        source=sources[best_idx],
                        confidence=best_sim,
                        supported=True,
                    ))
                # Insert citation marker at end of sentence (before
                # trailing punctuation).
                new_answer_parts.append(self._insert_citation(sent, cite_idx))
            else:
                # Unsourced claim — leave it as-is, but flag it.
                new_answer_parts.append(sent)
                if self._looks_like_claim(sent):
                    unsourced.append(sent)

        new_answer_parts.append(answer[last_end:])  # trailing text
        cited_answer = "".join(new_answer_parts)

        # Sort citations by index for display.
        citations.sort(key=lambda c: c.index)

        # Build formatted reference lists.
        format_apa = self._format_apa(citations, sources)
        format_ar = self._format_arabic(citations, sources)

        return CitationResult(
            cited_answer=cited_answer,
            citations=citations,
            unsourced_claims=unsourced,
            invalid_citations=sorted(set(invalid)),
            format_apa=format_apa,
            format_arabic=format_ar,
        )

    def verify(self, answer: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
        """Verify citations in an already-cited answer.

        Returns:
            {
              "valid": list[int],         # citation indices that resolve
              "invalid": list[int],       # citation indices out of range
              "unsupported": list[int],   # resolved but similarity below threshold
              "per_citation": {n: {"confidence": float, "supported": bool}},
            }
        """
        valid: list[int] = []
        invalid: list[int] = []
        unsupported: list[int] = []
        per_citation: dict[int, dict[str, Any]] = {}

        if not sources:
            return {"valid": [], "invalid": [], "unsupported": [], "per_citation": {}}

        seen: set[int] = set()
        for sent, _, _ in _split_sentences(answer):
            for n in self._existing_citations(sent):
                if n in seen:
                    continue
                seen.add(n)
                if n < 1 or n > len(sources):
                    invalid.append(n)
                    continue
                src = sources[n - 1]
                ctx = (src.get("chunk_text") or src.get("text") or "").strip()
                sim = self._similarity(sent, ctx, None)
                supported = sim >= self.similarity_threshold
                per_citation[n] = {
                    "confidence": round(sim, 4),
                    "supported": supported,
                    "doc_id": src.get("doc_id"),
                    "title": src.get("title") or src.get("filename") or "",
                }
                if supported:
                    valid.append(n)
                else:
                    unsupported.append(n)
        return {
            "valid": sorted(set(valid)),
            "invalid": sorted(set(invalid)),
            "unsupported": sorted(set(unsupported)),
            "per_citation": per_citation,
        }

    # ── formatting ──────────────────────────────────────────────────

    def _format_apa(self, citations: list[Citation], sources: list[dict[str, Any]]) -> str:
        """APA-style reference list (7th ed.).

        Format: Author/Org. (Year). *Title* (p. N). Source.
        We don't have a real author, so we use the tenant/workspace
        name from the source payload or fall back to "HSAAI Internal
        Document".
        """
        if not citations:
            return ""
        lines: list[str] = ["References (APA):"]
        for c in citations:
            src = sources[c.index - 1] if c.index - 1 < len(sources) else {}
            org = src.get("author") or src.get("organization") or src.get("tenant_id") or "HSAAI"
            year = src.get("year") or ""
            if not year and src.get("created_at"):
                m = re.match(r"(\d{4})", str(src.get("created_at")))
                if m:
                    year = m.group(1)
            title = src.get("title") or src.get("filename") or "Untitled Document"
            page = c.page if c.page is not None else src.get("page")
            page_str = f" (p. {page})" if page is not None else ""
            lines.append(f"[{c.index}] {org}. ({year}). *{title}*{page_str}. Internal knowledge base.")
        return "\n".join(lines)

    def _format_arabic(self, citations: list[Citation], sources: list[dict[str, Any]]) -> str:
        """Arabic citation format.

        Format: [n] المؤلف/الجهة. (السنة). «العنوان»، صفحة N. قاعدة المعرفة الداخلية.
        """
        if not citations:
            return ""
        lines: list[str] = ["المراجع:"]
        for c in citations:
            src = sources[c.index - 1] if c.index - 1 < len(sources) else {}
            org = src.get("author") or src.get("organization") or src.get("tenant_id") or "شركة هايل سعيد أنم"
            year = src.get("year") or ""
            if not year and src.get("created_at"):
                m = re.match(r"(\d{4})", str(src.get("created_at")))
                if m:
                    year = m.group(1)
            title = src.get("title") or src.get("filename") or "وثيقة بدون عنوان"
            page = c.page if c.page is not None else src.get("page")
            page_str = f"، صفحة {page}" if page is not None else ""
            lines.append(
                f"[{c.index}] {org}. ({year}). «{title}»{page_str}. قاعدة المعرفة الداخلية."
            )
        return "\n".join(lines)

    # ── helpers ─────────────────────────────────────────────────────

    def _existing_citations(self, sentence: str) -> list[int]:
        """Extract 1-based citation indices already present in a sentence."""
        out: list[int] = []
        for m in _CITATION_RE.finditer(sentence):
            inner = m.group(1)
            for part in inner.split(","):
                part = part.strip()
                if "-" in part:
                    try:
                        lo, hi = part.split("-", 1)
                        lo_i, hi_i = int(lo.strip()), int(hi.strip())
                        if hi_i < lo_i:
                            lo_i, hi_i = hi_i, lo_i
                        for i in range(lo_i, min(hi_i, 50) + 1):
                            out.append(i)
                    except ValueError:
                        continue
                else:
                    try:
                        n = int(part)
                        if 1 <= n <= 50:
                            out.append(n)
                    except ValueError:
                        continue
        return out

    def _looks_like_claim(self, sentence: str) -> bool:
        """Heuristic — does this sentence make a factual claim?

        We take a conservative approach: a sentence is a claim unless it
        is clearly a greeting, acknowledgement, question, or very short
        connector. This maximizes anti-fabrication coverage — better to
        over-flag (and let the caller filter) than to miss a fabricated
        claim.
        """
        if not sentence:
            return False
        stripped = sentence.rstrip()
        # Skip interrogatives.
        if stripped.endswith(("?", "؟")):
            return False
        # Skip very short fragments (< 20 chars).
        if len(stripped) < 20:
            return False
        # Skip greetings / acknowledgements.
        first = sentence.split()[0].lower().strip(".,;:!?")
        if first in {"hello", "hi", "hey", "مرحبا", "أهلا", "اهلا",
                     "thanks", "thank", "شكرا", "نعم", "yes", "no",
                     "لا", "ok", "okay"}:
            return False
        # Everything else is a claim worth sourcing.
        return True

    def _insert_citation(self, sentence: str, cite_idx: int) -> str:
        """Insert `[n]` at the end of the sentence, before trailing
        punctuation."""
        # Strip trailing whitespace.
        s = sentence.rstrip()
        ws = sentence[len(s):]
        if s and s[-1] in ".!?؟":
            return s[:-1] + f" [{cite_idx}]" + s[-1] + ws
        return s + f" [{cite_idx}]" + ws

    def _similarity(
        self,
        sentence: str,
        ctx: str,
        cached_emb: Optional[list[float]] = None,
    ) -> float:
        """Compute similarity between a sentence and a context string.
        Uses cosine similarity of embeddings when available, else
        Jaccard."""
        if not ctx:
            return 0.0
        if cached_emb is not None:
            sent_emb = _embed(sentence)
            if sent_emb is not None:
                return _cosine(sent_emb, cached_emb)
        return _jaccard(_tokenize_light(sentence), _tokenize_light(ctx))

    def _build_citation(
        self,
        *,
        index: int,
        source: dict[str, Any],
        confidence: float,
        supported: bool,
    ) -> Citation:
        return Citation(
            index=index,
            doc_id=source.get("doc_id"),
            title=(source.get("title") or source.get("filename") or "Untitled Document"),
            page=source.get("page"),
            chunk_text=(source.get("chunk_text") or source.get("text") or "")[:1000],
            confidence=float(confidence),
            supported=bool(supported),
        )


# ─────────────────────────────────────────────────────────────────────
# Module-level default engine
# ─────────────────────────────────────────────────────────────────────

_default_engine: Optional[CitationEngine] = None


def get_default_engine() -> CitationEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = CitationEngine()
    return _default_engine


__all__ = [
    "CitationEngine",
    "Citation",
    "CitationResult",
    "get_default_engine",
]
