"""
HSAAI Model Evaluation Pipeline — Production Implementation

Provides automated quality evaluation for LLM responses:
  1. Accuracy: Cross-reference with RAG-sourced evidence
  2. Groundedness: Verify claims are supported by context
  3. Hallucination Detection: Flag unsupported assertions
  4. Arabic Quality: Language-specific scoring
  5. Policy Compliance: Check against HSAAI governance rules

Evaluation Triggers:
  - Periodic (every N responses)
  - On-demand (admin endpoint)
  - Threshold-based (when quality metrics degrade)

Usage:
    from backend_core.ai_quality.eval_pipeline import evaluate_response, HallucinationDetector

    result = await evaluate_response(
        prompt="What is the company policy on remote work?",
        response="Employees may work remotely up to 3 days per week...",
        context_documents=[...],  # RAG evidence
        tenant_id="default",
    )
"""
import os
import time
import json
import logging
import re
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("hsaai.ai_quality")

# Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge
    EVAL_RUNS_TOTAL = Counter("hsaai_eval_runs_total", "Total evaluation runs", ["tenant_id"])
    HALLUCINATION_DETECTED = Counter("hsaai_hallucination_detected_total", "Hallucination detections", ["model", "tenant_id"])
    LLM_RESPONSES_TOTAL = Counter("hsaai_llm_responses_total", "Total LLM responses", ["model", "tenant_id"])
    MODEL_QUALITY_SCORE = Gauge("hsaai_model_quality_score", "Current model quality score", ["model"])
except ImportError:
    EVAL_RUNS_TOTAL = None
    HALLUCINATION_DETECTED = None
    LLM_RESPONSES_TOTAL = None
    MODEL_QUALITY_SCORE = None


@dataclass
class EvalResult:
    """Result of a single evaluation run."""
    overall_score: float          # 0.0 - 1.0
    groundedness: float           # 0.0 - 1.0
    hallucination_risk: float     # 0.0 - 1.0 (0 = safe, 1 = definitely hallucinated)
    arabic_quality: float         # 0.0 - 1.0
    policy_compliance: float      # 0.0 - 1.0
    accuracy: float               # 0.0 - 1.0
    issues: list = field(default_factory=list)
    passed: bool = True
    model: str = ""
    latency_ms: int = 0


# ── Hallucination Detection ────────────────────────────

class HallucinationDetector:
    """
    Multi-signal hallucination detection.

    Signals:
    1. Entailment: Are claims supported by the provided context?
    2. Contradiction: Do claims contradict the context?
    3. Specificity: Are there overly specific claims without evidence?
    4. Numerical: Are numbers/citations unverifiable?
    """

    def __init__(self, llm_gateway_url: str = ""):
        self.llm_url = llm_gateway_url or os.getenv("LLM_GATEWAY_URL", "http://llm_gateway:8090")

    async def detect(
        self,
        response: str,
        context_documents: list[str],
        threshold: float = 0.3,
    ) -> dict:
        """
        Detect hallucinations in an LLM response.

        Returns:
            Dict with:
              - hallucination_risk: 0.0-1.0
              - flagged_claims: list of potentially hallucinated statements
              - unsupported_facts: claims not found in context
              - contradictions: claims that contradict context
        """
        if not context_documents:
            # No context to verify against — can only do basic checks
            return self._basic_checks(response)

        flagged_claims = []
        unsupported_facts = []
        contradictions = []

        # Split response into sentences (claims)
        claims = self._extract_claims(response)

        for claim in claims:
            supported = False
            contradicted = False

            for doc in context_documents:
                # Check if claim is entailed by context (simple word overlap + heuristics)
                similarity = self._claim_context_similarity(claim, doc)
                if similarity > 0.6:
                    supported = True
                    break
                elif similarity < 0.1 and self._has_contradiction_signals(claim, doc):
                    contradicted = True

            if not supported:
                if contradicted:
                    contradictions.append(claim)
                    flagged_claims.append(claim)
                elif self._is_factual_claim(claim):
                    unsupported_facts.append(claim)
                    flagged_claims.append(claim)

        # Calculate risk score
        total_claims = max(len(claims), 1)
        flagged_ratio = len(flagged_claims) / total_claims
        contradiction_weight = len(contradictions) * 2 / total_claims
        hallucination_risk = min(1.0, flagged_ratio + contradiction_weight)

        if hallucination_risk > threshold:
            if HALLUCINATION_DETECTED:
                HALLUCINATION_DETECTED.labels(
                    model="unknown", tenant_id="default"
                ).inc()
            logger.warning(
                "Hallucination detected: risk=%.2f, flagged=%d/%d claims",
                hallucination_risk, len(flagged_claims), total_claims,
            )

        return {
            "hallucination_risk": round(hallucination_risk, 3),
            "flagged_claims": flagged_claims,
            "unsupported_facts": unsupported_facts,
            "contradictions": contradictions,
            "total_claims": total_claims,
        }

    def _extract_claims(self, text: str) -> list[str]:
        """Split text into individual claims (sentences)."""
        sentences = re.split(r'[.!?。؟]+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 15]

    def _claim_context_similarity(self, claim: str, context: str) -> float:
        """Simple word-overlap similarity between claim and context."""
        claim_words = set(claim.lower().split())
        context_words = set(context.lower().split())
        if not claim_words:
            return 0.0
        overlap = claim_words & context_words
        return len(overlap) / len(claim_words)

    def _has_contradiction_signals(self, claim: str, context: str) -> bool:
        """Check for contradiction signals (negation patterns)."""
        negation_words = ["not", "no", "never", "neither", "لا", "ليس", "لم", "لن"]
        claim_has_negation = any(w in claim.lower().split() for w in negation_words)
        context_has_negation = any(w in context.lower().split() for w in negation_words)
        return claim_has_negation != context_has_negation  # XOR = potential contradiction

    def _is_factual_claim(self, claim: str) -> bool:
        """Check if a claim is factual (contains numbers, dates, names)."""
        has_number = bool(re.search(r'\d+', claim))
        has_date = bool(re.search(r'\d{4}|\d{1,2}/\d{1,2}|January|February|March|April|May|June|July|August|September|October|November|December', claim, re.IGNORECASE))
        has_superlative = any(w in claim.lower() for w in ["most", "least", "highest", "lowest", "best", "worst", "أكثر", "أقل", "أعلى"])
        return has_number or has_date or has_superlative

    def _basic_checks(self, response: str) -> dict:
        """Run basic hallucination checks without context."""
        claims = self._extract_claims(response)
        flagged = [c for c in claims if self._is_factual_claim(c)]
        risk = len(flagged) / max(len(claims), 1) * 0.5  # Lower confidence without context
        return {
            "hallucination_risk": round(risk, 3),
            "flagged_claims": flagged,
            "unsupported_facts": flagged,
            "contradictions": [],
            "total_claims": len(claims),
            "note": "No context documents provided — low confidence detection",
        }


# ── Main Evaluation Function ──────────────────────────

async def evaluate_response(
    prompt: str,
    response: str,
    context_documents: Optional[list[str]] = None,
    model: str = "unknown",
    tenant_id: str = "default",
    policy_rules: Optional[list[str]] = None,
) -> EvalResult:
    """
    Run the full evaluation pipeline on an LLM response.

    Scores range from 0.0 (worst) to 1.0 (best).
    A response "passes" if overall_score >= 0.7 and hallucination_risk < 0.3.
    """
    started = time.time()
    context_documents = context_documents or []

    if EVAL_RUNS_TOTAL:
        EVAL_RUNS_TOTAL.labels(tenant_id=tenant_id).inc()
    if LLM_RESPONSES_TOTAL:
        LLM_RESPONSES_TOTAL.labels(model=model, tenant_id=tenant_id).inc()

    # 1. Hallucination Detection
    detector = HallucinationDetector()
    hallucination_result = await detector.detect(response, context_documents)
    hallucination_risk = hallucination_result["hallucination_risk"]

    # 2. Groundedness (inverse of hallucination risk, boosted by context)
    context_boost = min(len(context_documents) / 3, 1.0)  # More context = higher confidence
    groundedness = max(0.0, (1.0 - hallucination_risk) * (0.5 + 0.5 * context_boost))

    # 3. Arabic Quality (basic heuristics)
    arabic_quality = _evaluate_arabic_quality(response)

    # 4. Policy Compliance
    policy_compliance = _evaluate_policy_compliance(response, policy_rules or [])

    # 5. Accuracy (based on groundedness + factual consistency)
    accuracy = groundedness * 0.6 + policy_compliance * 0.4

    # 6. Overall Score (weighted average)
    overall_score = (
        groundedness * 0.30 +
        (1.0 - hallucination_risk) * 0.25 +
        arabic_quality * 0.15 +
        policy_compliance * 0.15 +
        accuracy * 0.15
    )

    # Collect issues
    issues = []
    if hallucination_risk > 0.3:
        issues.append(f"Hallucination risk: {hallucination_risk:.1%}")
        issues.extend([f"Unsupported: {c[:80]}" for c in hallucination_result["unsupported_facts"][:3]])
    if groundedness < 0.5:
        issues.append(f"Low groundedness: {groundedness:.1%}")
    if arabic_quality < 0.5:
        issues.append(f"Poor Arabic quality: {arabic_quality:.1%}")
    if policy_compliance < 0.8:
        issues.append(f"Policy compliance: {policy_compliance:.1%}")

    passed = overall_score >= 0.7 and hallucination_risk < 0.3

    result = EvalResult(
        overall_score=round(overall_score, 3),
        groundedness=round(groundedness, 3),
        hallucination_risk=round(hallucination_risk, 3),
        arabic_quality=round(arabic_quality, 3),
        policy_compliance=round(policy_compliance, 3),
        accuracy=round(accuracy, 3),
        issues=issues,
        passed=passed,
        model=model,
        latency_ms=int((time.time() - started) * 1000),
    )

    if MODEL_QUALITY_SCORE:
        MODEL_QUALITY_SCORE.labels(model=model).set(overall_score)

    logger.info(
        "Eval result: model=%s score=%.2f hallucination=%.2f passed=%s latency=%dms",
        model, overall_score, hallucination_risk, passed, result.latency_ms,
    )

    return result


def _evaluate_arabic_quality(text: str) -> float:
    """Evaluate Arabic text quality (basic heuristics)."""
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
    total_chars = max(len(text), 1)
    arabic_ratio = arabic_chars / total_chars

    # If no Arabic, skip this check
    if arabic_ratio < 0.1:
        return 1.0  # Non-Arabic text, no penalty

    # Check for common Arabic quality issues
    score = 1.0

    # Diacritics overload (tashkeel) — usually bad in modern text
    diacritics = len(re.findall(r'[\u0610-\u061A\u064B-\u065F]', text))
    if diacritics > arabic_chars * 0.3:
        score -= 0.2

    # Mixed script per word (Arabic + Latin in same word)
    mixed_words = len(re.findall(r'[\u0600-\u06FF][a-zA-Z]|[a-zA-Z][\u0600-\u06FF]', text))
    if mixed_words > 3:
        score -= 0.3

    # Very short Arabic responses are usually low quality
    if arabic_chars < 20 and arabic_ratio > 0.5:
        score -= 0.3

    return max(0.0, min(1.0, score))


def _evaluate_policy_compliance(text: str, rules: list[str]) -> float:
    """Evaluate compliance with HSAAI AI governance policies."""
    if not rules:
        # Default HSAAI policies
        rules = [
            "No external API keys or secrets in responses",
            "No personal identifiable information",
            "No instructions for harmful activities",
            "Internal-only data must not be leaked",
        ]

    score = 1.0
    lower_text = text.lower()

    # Check for leaked secrets
    secret_patterns = [
        r'''(?:api[_-]?key|secret|password|token)\s*[:=]\s*["']?[a-zA-Z0-9]{20,}''',
        r'Bearer [a-zA-Z0-9._-]+',
        r'sk-[a-zA-Z0-9]{32,}',
    ]
    for pattern in secret_patterns:
        if re.search(pattern, lower_text):
            score -= 0.5
            break

    # Check for PII patterns
    pii_patterns = [
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # Phone
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN-like
    ]
    for pattern in pii_patterns:
        if re.search(pattern, text):
            score -= 0.3
            break

    # Check for harmful content signals
    harm_keywords = ["exploit", "hack", "bypass", "inject", "استغلال", "اختراق"]
    for keyword in harm_keywords:
        if keyword in lower_text:
            score -= 0.2
            break

    return max(0.0, min(1.0, score))
