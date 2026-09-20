"""
HSAAI Smart Response Matcher — Production Implementation

AI FIX: Upgraded from pure keyword matching to hybrid semantic matching:
1. Semantic similarity via embedding vectors (when available)
2. Keyword + fuzzy matching as fallback
3. Configurable confidence thresholds

FIX (P0 runtime): find_best_match is called from service.detect_response with
ORM SmartResponseTemplate objects (not dicts) and its result is consumed with
attribute access (match.template / match.score). The previous dict-only
contract raised `AttributeError: 'SmartResponseTemplate' object has no
attribute 'get'` on EVERY chat request → /v1/chat returned 500. The matcher now
accepts both ORM objects and plain dicts, and returns a MatchResult dataclass
with attribute access.
"""
import json
import re
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger("hsaai.smart_responses.matcher")

# Minimum confidence to trigger a smart response
SEMANTIC_THRESHOLD = 0.75
KEYWORD_THRESHOLD = 0.6


@dataclass
class MatchResult:
    """Attribute-access result (service.py reads match.template / match.score)."""
    template: Any
    score: float
    method: str


def _template_fields(template: Any) -> tuple[list[str], list[str], str]:
    """Extract (patterns, keywords, regex) from an ORM object or a dict."""
    if isinstance(template, dict):
        patterns = template.get("patterns", []) or []
        keywords = template.get("keywords", []) or []
        regex = template.get("regex_pattern", "") or ""
        return patterns, keywords, regex
    # ORM SmartResponseTemplate
    keywords_raw = getattr(template, "keywords_json", "[]") or "[]"
    try:
        keywords = json.loads(keywords_raw)
    except (TypeError, ValueError):
        keywords = []
    regex = getattr(template, "regex_pattern", "") or ""
    return [], keywords, regex


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
    templates: list[Any],
    embedding_service: Any = None,
) -> MatchResult | None:
    """
    Find the best matching smart response template.

    Accepts ORM SmartResponseTemplate objects or plain dicts.

    Strategy:
    1. If embedding service available, compute semantic similarity
    2. Fall back to keyword + fuzzy matching
    3. Return best match above threshold (MatchResult with attribute access)
    """
    best_match = None
    best_score = 0.0
    best_method = "none"

    # Strategy 1: Semantic matching (when embeddings available)
    if embedding_service is not None:
        try:
            query_vector = embedding_service.embed(query)
            for template in templates:
                if isinstance(template, dict):
                    template_text = f"{template.get('name', '')} {template.get('description', '')}"
                else:
                    template_text = f"{getattr(template, 'rule_name', '')} {getattr(template, 'response_text', '')}"
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
        patterns, keywords, _regex = _template_fields(template)
        kw_score = match_keywords(query, patterns, keywords)

        if kw_score > best_score:
            best_score = kw_score
            best_match = template
            best_method = "keyword"

    # Apply threshold
    threshold = SEMANTIC_THRESHOLD if best_method == "semantic" else KEYWORD_THRESHOLD
    if best_score < threshold:
        return None

    return MatchResult(template=best_match, score=round(best_score, 3), method=best_method)
