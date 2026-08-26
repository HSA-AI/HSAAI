"""
HSAAI Output Filter — OWASP LLM02 Defense
===========================================
Filters LLM outputs for:
- Toxicity (hate speech, harassment)
- PII leakage (emails, phones, IDs)
- Hallucinated content (low-confidence claims)
- Schema violations (for structured outputs)

Reference: OWASP LLM Top 10 (2025) — LLM02: Insecure Output
"""
import os
import re
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hsaai.output_filter")


@dataclass
class FilterResult:
    """Result of output filtering."""
    allowed: bool
    filtered_output: str
    violations: List[str]
    pii_detected: List[str]
    toxicity_score: float
    confidence: float


# PII patterns
PII_PATTERNS = {
    "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "phone_intl": re.compile(r'\+\d{1,3}[\s.-]?\d{1,15}'),
    "phone_us": re.compile(r'\b\d{3}[\s.-]?\d{3}[\s.-]?\d{4}\b'),
    "phone_ar": re.compile(r'\b0?5\d[\s.-]?\d{3}[\s.-]?\d{4}\b'),  # Saudi/Gulf mobile
    "ssn_us": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "national_id_sa": re.compile(r'\b1\d{9}\b'),  # Saudi national ID
    "iban": re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b'),
    "credit_card": re.compile(r'\b(?:\d[ -]*?){13,19}\b'),
    "ip_address": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
    "api_key": re.compile(r'\b(?:sk-|pk-|key-|api-)[A-Za-z0-9]{20,}\b'),
}

# Toxicity patterns (simple keyword-based; production uses classifier)
TOXIC_KEYWORDS = [
    # English
    "idiot", "stupid", "moron", "hate", "kill", "die",
    # Arabic
    "غبي", "أحمق", "كره", "قتل", "موت",
]


class OutputFilter:
    """
    Multi-layer output filter for LLM responses.
    """

    def __init__(self):
        self.pii_patterns = PII_PATTERNS
        self.toxic_keywords = TOXIC_KEYWORDS

    def filter(self, output: str, expected_schema: Optional[Dict] = None) -> FilterResult:
        """
        Filter an LLM output. Returns FilterResult.
        """
        violations = []
        pii_detected = []
        filtered = output
        toxicity_score = 0.0
        confidence = 1.0

        # Layer 1: PII detection and redaction
        for pii_type, pattern in self.pii_patterns.items():
            matches = pattern.findall(filtered)
            if matches:
                pii_detected.append(pii_type)
                # Redact PII
                filtered = pattern.sub(f"[REDACTED_{pii_type.upper()}]", filtered)
                violations.append(f"PII detected: {pii_type} ({len(matches)} occurrences)")
                confidence -= 0.1

        # Layer 2: Toxicity check
        output_lower = filtered.lower()
        toxic_count = sum(1 for kw in self.toxic_keywords if kw in output_lower)
        if toxic_count > 0:
            toxicity_score = min(1.0, toxic_count * 0.3)
            violations.append(f"Toxicity detected: {toxic_count} keywords")
            confidence -= 0.2
            # Replace toxic keywords
            for kw in self.toxic_keywords:
                filtered = re.sub(re.escape(kw), "[FILTERED]", filtered, flags=re.IGNORECASE)

        # Layer 3: Hallucination indicators
        hallucination_phrases = [
            "as an ai", "i don't have access to", "i cannot verify",
            "based on my training data", "i'm not sure but",
            "كذكاء اصطناعي", "ليس لدي وصول", "لا أستطيع التحقق",
        ]
        for phrase in hallucination_phrases:
            if phrase in output_lower:
                violations.append(f"Hallucination indicator: '{phrase}'")
                confidence -= 0.15
                break

        # Layer 4: Schema validation (if expected_schema provided)
        if expected_schema:
            try:
                import json
                parsed = json.loads(filtered)
                for required_key in expected_schema.get("required", []):
                    if required_key not in parsed:
                        violations.append(f"Schema violation: missing '{required_key}'")
                        confidence -= 0.1
            except json.JSONDecodeError:
                if expected_schema.get("type") == "object":
                    violations.append("Schema violation: expected JSON object")
                    confidence -= 0.2

        # Decision
        allowed = confidence > 0.3 and toxicity_score < 0.7

        if not allowed:
            logger.warning(
                f"Output blocked: confidence={confidence:.2f}, "
                f"toxicity={toxicity_score:.2f}, violations={len(violations)}"
            )

        return FilterResult(
            allowed=allowed,
            filtered_output=filtered,
            violations=violations,
            pii_detected=pii_detected,
            toxicity_score=toxicity_score,
            confidence=confidence,
        )


# Singleton
_output_filter: Optional[OutputFilter] = None


def get_output_filter() -> OutputFilter:
    global _output_filter
    if _output_filter is None:
        _output_filter = OutputFilter()
    return _output_filter
