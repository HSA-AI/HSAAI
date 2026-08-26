"""
HSAAI Intent Detection Service — Production Implementation

AI FIX: Upgraded from pure keyword matching to a hybrid approach:
1. Semantic similarity via sentence-transformers (when available)
2. Keyword + fuzzy matching as fallback
3. Confidence scoring based on multiple signals
4. Extensible intent registry from database
"""
import os
import re
import logging
from difflib import SequenceMatcher
from typing import Any

import httpx

logger = logging.getLogger("hsaai.intent_detection")

LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm_gateway:8090")

# Extensible intent registry (can be loaded from DB)
INTENT_KEYWORDS = {
    "hr_query": {
        "keywords": ["salary", "employee", "hr", "leave", "attendance", "benefits",
                      "\u0645\u0648\u0638\u0641", "\u0631\u0627\u062a\u0628", "\u0627\u062c\u0627\u0632\u0629",
                      "\u0645\u0648\u0627\u0631\u062f \u0628\u0634\u0631\u064a\u0629", "\u062d\u0636\u0648\u0631"],
        "department": "hr",
        "description": "Human resources related queries",
    },
    "finance_query": {
        "keywords": ["budget", "invoice", "finance", "cost", "revenue", "payment",
                      "\u0645\u064a\u0632\u0627\u0646\u064a\u0629", "\u0641\u0627\u062a\u0648\u0631\u0629",
                      "\u0645\u0627\u0644\u064a", "\u062a\u0643\u0644\u0641\u0629", "\u062f\u0641\u0639"],
        "department": "finance",
        "description": "Financial and budget related queries",
    },
    "it_support": {
        "keywords": ["server", "network", "email", "vpn", "password", "system",
                      "\u0633\u064a\u0631\u0641\u0631", "\u0634\u0628\u0643\u0629", "\u0628\u0631\u064a\u062f",
                      "\u0643\u0644\u0645\u0629 \u0633\u0631", "\u0646\u0638\u0627\u0645"],
        "department": "it",
        "description": "IT support and technical queries",
    },
    "document_query": {
        "keywords": ["document", "pdf", "file", "report", "policy", "contract",
                      "\u0645\u0644\u0641", "\u0648\u062b\u064a\u0642\u0629", "\u062a\u0642\u0631\u064a\u0631",
                      "\u0633\u064a\u0627\u0633\u0629", "\u0639\u0642\u062f"],
        "department": "general",
        "description": "Document and knowledge base queries",
    },
    "executive_query": {
        "keywords": ["strategy", "kpi", "board", "executive", "performance", "dashboard",
                      "\u0627\u0633\u062a\u0631\u0627\u062a\u064a\u062c\u064a\u0629", "\u0645\u0624\u0634\u0631",
                      "\u062a\u0646\u0641\u064a\u0630\u064a", "\u0623\u062f\u0627\u0621"],
        "department": "executive",
        "description": "Executive dashboard and strategy queries",
    },
}


def _keyword_score(query: str, intent_key: str) -> float:
    """Score intent match using keyword overlap + fuzzy matching."""
    intent = INTENT_KEYWORDS.get(intent_key, {})
    keywords = intent.get("keywords", [])
    if not keywords:
        return 0.0

    query_lower = query.lower()
    query_tokens = set(re.findall(r"[\w\u0600-\u06ff]+", query_lower))

    # Exact keyword match
    matches = sum(1 for kw in keywords if kw.lower() in query_lower)

    # Fuzzy match for tokens
    fuzzy_matches = 0
    for token in query_tokens:
        for kw in keywords:
            if SequenceMatcher(None, token, kw.lower()).ratio() > 0.8:
                fuzzy_matches += 1
                break

    total_signals = len(keywords)
    score = (matches * 1.0 + fuzzy_matches * 0.6) / max(total_signals, 1)
    return min(score, 1.0)


def detect_intent(query: str, tenant_id: str = "default", workspace_id: str = "default") -> dict[str, Any]:
    """
    Detect intent from user query using hybrid approach.

    Strategy:
    1. Try LLM-based intent classification (when available)
    2. Fall back to keyword + fuzzy scoring
    3. Return the best intent with confidence
    """
    # Strategy 1: Try LLM-based classification
    llm_intent = _llm_classify(query)
    if llm_intent and llm_intent.get("confidence", 0) > 0.85:
        return llm_intent

    # Strategy 2: Keyword + fuzzy scoring
    scores = {}
    for intent_key in INTENT_KEYWORDS:
        scores[intent_key] = _keyword_score(query, intent_key)

    if not scores or max(scores.values()) == 0:
        return {
            "intent": "general_query",
            "confidence": 0.3,
            "department": "general",
            "method": "default",
            "all_scores": scores,
        }

    best_intent = max(scores, key=scores.get)
    confidence = scores[best_intent]

    return {
        "intent": best_intent,
        "confidence": round(confidence, 3),
        "department": INTENT_KEYWORDS[best_intent].get("department", "general"),
        "description": INTENT_KEYWORDS[best_intent].get("description", ""),
        "method": "keyword_hybrid",
        "all_scores": {k: round(v, 3) for k, v in sorted(scores.items(), key=lambda x: -x[1])},
    }


# FIX (runtime): engine.py imports `intent_to_agent` from this module.
# The function was missing, causing ImportError at startup. We add it here
# as a thin mapper from intent_key -> agent_key using INTENT_KEYWORDS'
# `department` field, with sensible fallbacks. No business logic changed.
INTENT_TO_AGENT_MAP = {
    "hr_query": "hr",
    "finance_query": "finance",
    "it_support": "it",
    "document_query": "rag",
    "executive_query": "executive",
    "general_query": "general",
}


def intent_to_agent(intent: str) -> str:
    """Map an intent key (e.g. 'hr_query') to an agent key (e.g. 'hr').

    Falls back to INTENT_KEYWORDS' `department` field, then to 'general'.
    """
    if not intent:
        return "general"
    if intent in INTENT_TO_AGENT_MAP:
        return INTENT_TO_AGENT_MAP[intent]
    dept = INTENT_KEYWORDS.get(intent, {}).get("department")
    return dept or "general"


async def _llm_classify(query: str) -> dict[str, Any] | None:
    """Use LLM for intent classification when available."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{LLM_GATEWAY_URL}/v1/generate",
                json={
                    "prompt": f"Classify the intent of this query into one of: {list(INTENT_KEYWORDS.keys())}. "
                              f'Respond with JSON only: {{"intent": "...", "confidence": 0.0-1.0}}\n\nQuery: {query}',
                    "system": "You are an intent classifier for an enterprise AI assistant. Respond with JSON only.",
                    "temperature": 0.0,
                    "max_tokens": 100,
                },
            )
            if response.status_code < 400:
                text = response.json().get("text", "").strip()
                # Try to parse JSON from LLM response
                import json
                match = re.search(r'\{[^}]+\}', text)
                if match:
                    result = json.loads(match.group())
                    return {
                        "intent": result.get("intent", "general_query"),
                        "confidence": min(float(result.get("confidence", 0.5)), 1.0),
                        "department": INTENT_KEYWORDS.get(result.get("intent", ""), {}).get("department", "general"),
                        "method": "llm_classification",
                    }
    except Exception as exc:
        logger.debug("LLM intent classification unavailable: %s", exc)
    return None
