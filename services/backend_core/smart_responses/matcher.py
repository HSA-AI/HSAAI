"""
HSAAI Smart Response Matcher — Production Implementation

AI FIX: Upgraded from pure keyword matching to hybrid semantic matching:
1. Semantic similarity via embedding vectors (when available)
2. Keyword + fuzzy matching as fallback
3. Configurable confidence thresholds
"""
import re
import logging
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger("hsaai.smart_responses.matcher")

# Minimum confidence to trigger a smart response
SEMANTIC_THRESHOLD = 0.75
KEYWORD_THRESHOLD = 0.6


def match_keywords(query: str, patterns: list[str], keywords: list[str]) -> float:
    """
    Score match using keyword overlap + fuzzy matching.

    Returns confidence score 0.0-1.0
    """
    if not patterns and not keywords:
        return 0.0

    query_lower = query.lower()
    query_tokens = set(re.findall(r"[\w\u0600-\u06ff]+", query_lower))

    score = 0.0
    total_signals = len(patterns) + len(keywords)

    # Exact pattern match
    for pattern in patterns:
        if pattern.lower() in query_lower:
            score += 1.0

    # Keyword match
    for keyword in keywords:
        if keyword.lower() in query_lower:
            score += 0.8

    # Fuzzy token match
    for token in query_tokens:
        for kw in keywords + patterns:
            if SequenceMatcher(None, token, kw.lower()).ratio() > 0.85:
                score += 0.5
                break

    return min(score / max(total_signals, 1), 1.0)


def find_best_match(
    query: str,
    templates: list[dict[str, Any]],
    embedding_service: Any = None,
) -> dict[str, Any] | None:
    """
    Find the best matching smart response template.

    Strategy:
    1. If embedding service available, compute semantic similarity
    2. Fall back to keyword + fuzzy matching
    3. Return best match above threshold
    """
    best_match = None
    best_score = 0.0
    best_method = "none"

    # Strategy 1: Semantic matching (when embeddings available)
    if embedding_service is not None:
        try:
            query_vector = embedding_service.embed(query)
            for template in templates:
                template_text = f"{template.get('name', '')} {template.get('description', '')}"
                template_vector = embedding_service.embed(template_text)
                # Cosine similarity
                similarity = sum(a * b for a, b in zip(query_vector, template_vector))
                if similarity > best_score:
                    best_score = similarity
                    best_match = template
                    best_method = "semantic"
        except Exception as exc:
            logger.debug("Semantic matching failed: %s", exc)

    # Strategy 2: Keyword matching (always available)
    for template in templates:
        patterns = template.get("patterns", [])
        keywords = template.get("keywords", [])
        kw_score = match_keywords(query, patterns, keywords)

        if kw_score > best_score:
            best_score = kw_score
            best_match = template
            best_method = "keyword"

    # Apply threshold
    threshold = SEMANTIC_THRESHOLD if best_method == "semantic" else KEYWORD_THRESHOLD
    if best_score < threshold:
        return None

    return {
        "template": best_match,
        "confidence": round(best_score, 3),
        "method": best_method,
    }
