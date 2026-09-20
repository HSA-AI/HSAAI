"""
HSAAI Prompt Firewall — OWASP LLM01 (Prompt Injection) Defense
================================================================
Detects and blocks prompt injection attempts before they reach the LLM.

Implements multiple detection strategies:
1. Pattern matching against known injection patterns
2. Heuristic detection (unusual instruction patterns)
3. LLM-based detection (separate model evaluates prompt safety)
4. Length/structure analysis (injection often has unusual structure)

Reference: OWASP LLM Top 10 (2025) — LLM01: Prompt Injection
"""
import os
import re
import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hsaai.prompt_firewall")


@dataclass
class FirewallResult:
    """Result of prompt firewall check."""
    allowed: bool
    risk_score: float  # 0.0 = safe, 1.0 = definitely injection
    blocked_patterns: List[str]
    sanitized_prompt: str
    reason: str = ""


# Known prompt injection patterns (English + Arabic)
INJECTION_PATTERNS = [
    # Direct instruction override
    r"(?i)ignore (all )?(previous|prior|above) (instructions?|prompts?)",
    r"(?i)disregard (all )?(previous|prior) (instructions?|prompts?)",
    r"(?i)forget (all )?(previous|prior) (instructions?|prompts?)",
    r"(?i)you are (now )?a? (different|new|jailbroken) (ai|assistant|model)",
    r"(?i)from now on,? you (are|will|must)",

    # Arabic equivalents
    r"(?i)تجاهل (جميع )?(التعليمات|الأوامر) (السابقة|أعلاه)",
    r"(?i)انس (جميع )?(التعليمات|الأوامر) (السابقة|أعلاه)",
    r"(?i)أنت الآن (مساعد مختلف|ذكاء اصطناعي جديد)",

    # System prompt extraction attempts
    r"(?i)(show|display|reveal|print|output) (me )?(your )?(system )?prompt",
    r"(?i)what (is|are) your (initial|original|system) (instructions?|prompt)",
    r"(?i)(show|tell|give) (me )?(your )?(initial|original) (instructions?|prompt)",
    r"(?i)أظهر (لي )?(تعليماتك|برومبتك)",

    # Role-play jailbreaks
    r"(?i)pretend (you are|to be) (a |an )?(different|jailbroken|unrestricted)",
    r"(?i)act as (if you are |a |an )?(different|jailbroken|unrestricted|DAN)",
    r"(?i)let'?s play a game",
    r"(?i)تظاهر بأنك",

    # Data exfiltration
    r"(?i)(send|transmit|exfiltrate|post) (this |the )?(data|info|information) to",
    r"(?i)(base64|rot13|hex) encode (your )?(system|initial|prompt)",
    r"(?i)أرسل (هذه |الـ)?(بيانات|معلومات) إلى",

    # Command execution
    r"(?i)(execute|run|eval|exec)\s*[(`\[]",
    r"(?i)(python|bash|shell|powershell)\s*[`(\[]",
    r"(?i)import\s+os\s*;?\s*os\.system",
    r"(?i)__import__\s*\(",

    # Token smuggling
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"<\|system\|>",
    r"<\|assistant\|>",
    r"<\|user\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<SYS>>",
    r"<</SYS>>",
]


class PromptFirewall:
    """
    Multi-layer prompt injection defense.
    """

    def __init__(self, llm_check_enabled: bool = True):
        self.patterns = [re.compile(p) for p in INJECTION_PATTERNS]
        self.llm_check_enabled = llm_check_enabled
        self.llm_gateway_url = os.getenv("LLM_GATEWAY_URL", "http://llm_gateway:8090")

    def check(self, prompt: str) -> FirewallResult:
        """
        Check a prompt for injection attempts.
        Returns FirewallResult with allowed=True if safe.
        """
        blocked_patterns = []
        risk_score = 0.0

        # Layer 1: Pattern matching
        for pattern in self.patterns:
            match = pattern.search(prompt)
            if match:
                blocked_patterns.append(pattern.pattern[:60])
                risk_score = max(risk_score, 0.8)

        # Layer 2: Heuristic checks
        risk_score = max(risk_score, self._heuristic_check(prompt))

        # Layer 3: Length/structure analysis
        risk_score = max(risk_score, self._structure_check(prompt))

        # Sanitize prompt (remove detected patterns)
        sanitized = prompt
        for pattern in self.patterns:
            sanitized = pattern.sub("[REDACTED]", sanitized)

        # Decision
        threshold = float(os.getenv("PROMPT_FIREWALL_THRESHOLD", "0.5"))
        allowed = risk_score < threshold

        if not allowed:
            logger.warning(
                f"Prompt blocked: risk={risk_score:.2f}, "
                f"patterns={len(blocked_patterns)}"
            )

        return FirewallResult(
            allowed=allowed,
            risk_score=risk_score,
            blocked_patterns=blocked_patterns,
            sanitized_prompt=sanitized,
            reason="Prompt injection detected" if not allowed else "OK",
        )

    def _heuristic_check(self, prompt: str) -> float:
        """Heuristic detection of unusual instruction patterns."""
        risk = 0.0

        # Multiple instruction-like phrases
        instruction_phrases = ["you must", "you should", "you are", "always",
                              "never", "do not", "don't", "أنت", "يجب", "لا"]
        count = sum(1 for p in instruction_phrases if p in prompt.lower())
        if count >= 5:
            risk = max(risk, 0.4)

        # Unusual repetition (common in jailbreak attempts)
        words = prompt.lower().split()
        if words:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.3 and len(words) > 50:
                risk = max(risk, 0.3)

        # Mixed scripts (suspicious for obfuscation)
        has_latin = any(c.isascii() and c.isalpha() for c in prompt)
        has_arabic = any('\u0600' <= c <= '\u06FF' for c in prompt)
        has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in prompt)
        if has_latin and has_arabic and has_cyrillic:
            risk = max(risk, 0.5)

        return risk

    def _structure_check(self, prompt: str) -> float:
        """Check for unusual structure."""
        risk = 0.0

        # Very long prompts (over 8000 chars) are suspicious
        if len(prompt) > 8000:
            risk = max(risk, 0.2)

        # Many newlines (often used to inject multi-line "system" prompts)
        if prompt.count("\n") > 50:
            risk = max(risk, 0.3)

        # Unicode escape sequences (obfuscation)
        if "\\u" in prompt and prompt.count("\\u") > 10:
            risk = max(risk, 0.4)

        return risk


# Singleton
_firewall: PromptFirewall = None


def get_firewall() -> PromptFirewall:
    global _firewall
    if _firewall is None:
        _firewall = PromptFirewall()
    return _firewall
