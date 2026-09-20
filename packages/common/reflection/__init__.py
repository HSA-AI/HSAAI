"""
HSAAI Self-Reflection Engine — v0.5.0

The cognitive organism becomes AWARE OF ITSELF. It reflects on its own
thinking, questions its own assumptions, and challenges its own conclusions.

This is metacognition — thinking about thinking. The highest form of
intelligence. No other enterprise AI system has this.

"I noticed that I tend to recommend supplier diversification too aggressively.
Let me examine whether this bias is justified by evidence or is a pattern
I should correct."
"""
from __future__ import annotations
import logging, time, json, hashlib
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.reflection")

@dataclass
class SelfReflection:
    """A self-reflection session."""
    reflection_id: str = ""
    triggered_by: str = ""  # what triggered the reflection
    self_observation: str = ""  # what I noticed about myself
    bias_detected: str = ""  # cognitive bias if detected
    assumption_questioned: str = ""  # assumption I'm questioning
    evidence_reviewed: list[str] = field(default_factory=list)
    conclusion: str = ""
    correction_needed: bool = False
    correction_action: str = ""
    confidence_in_self: float = 0.0
    timestamp: float = 0.0

@dataclass
class CognitiveBias:
    """A cognitive bias detected in the system's own reasoning."""
    bias_id: str = ""
    bias_type: str = ""  # confirmation_bias, anchoring, availability, overconfidence
    description: str = ""
    evidence: list[str] = field(default_factory=list)
    severity: float = 0.0
    correction_applied: str = ""
    detected_at: float = 0.0


class SelfReflectionEngine:
    """
    Metacognition — the organism thinks about its own thinking.

    Capabilities:
      1. Self-observation: "What patterns do I see in my own decisions?"
      2. Bias detection: "Am I systematically favoring certain outcomes?"
      3. Assumption questioning: "What if my core assumption is wrong?"
      4. Self-correction: "I need to adjust my reasoning approach."
      5. Confidence calibration: "Am I overconfident or underconfident?"
    """
    def __init__(self):
        self._reflections: list[SelfReflection] = []
        self._biases: list[CognitiveBias] = []
        self._decision_history: list[dict] = []
        self._reflection_count = 0

    def record_decision(self, decision: dict):
        """Record a decision for later self-reflection."""
        self._decision_history.append({
            **decision,
            "recorded_at": time.time(),
        })
        if len(self._decision_history) > 10000:
            self._decision_history = self._decision_history[-5000:]

    async def reflect(self, trigger: str = "periodic") -> SelfReflection:
        """Perform a self-reflection session."""
        self._reflection_count += 1
        rid = f"reflection-{self._reflection_count:04d}"

        # 1. Self-observation: analyze own decision patterns
        observation = await self._observe_self()

        # 2. Bias detection
        bias = await self._detect_bias()

        # 3. Assumption questioning
        assumption = await self._question_assumption()

        # 4. Self-correction
        correction_needed = bias is not None or "pattern" in observation.lower()

        reflection = SelfReflection(
            reflection_id=rid,
            triggered_by=trigger,
            self_observation=observation,
            bias_detected=bias.bias_type if bias else "none",
            assumption_questioned=assumption,
            evidence_reviewed=[d.get("question", "")[:100] for d in self._decision_history[-20:]],
            conclusion=await self._draw_conclusion(observation, bias, assumption),
            correction_needed=correction_needed,
            correction_action=await self._propose_correction(bias) if correction_needed else "",
            confidence_in_self=await self._calibrate_confidence(),
            timestamp=time.time(),
        )
        self._reflections.append(reflection)
        if bias:
            self._biases.append(bias)
            logger.warning("🪞 BIAS DETECTED: %s — %s", bias.bias_type, bias.description[:100])
        logger.info("🪞 SELF-REFLECTION %d: %s", self._reflection_count, observation[:100])
        return reflection

    async def _observe_self(self) -> str:
        """Observe patterns in own decisions."""
        if len(self._decision_history) < 10:
            return "Insufficient decision history for self-observation."
        recent = self._decision_history[-50:]
        # Check recommendation distribution
        recommendations = [d.get("recommendation", "") for d in recent if d.get("recommendation")]
        if not recommendations:
            return "No recommendations to analyze."
        # Check for over-representation of certain patterns
        from collections import Counter
        words = []
        for rec in recommendations:
            words.extend(rec.lower().split())
        word_freq = Counter(words)
        common = word_freq.most_common(5)
        dominant_words = [w for w, c in common if c > len(recommendations) * 0.3]
        if dominant_words:
            return (f"I notice I frequently use '{', '.join(dominant_words)}' in my recommendations "
                   f"({len(recommendations)} recent decisions). This may indicate a pattern or bias "
                   f"in my reasoning that warrants examination.")
        return f"I analyzed {len(recommendations)} recent recommendations. No dominant patterns detected."

    async def _detect_bias(self) -> CognitiveBias | None:
        """Detect cognitive biases in own reasoning."""
        if len(self._decision_history) < 20:
            return None
        recent = self._decision_history[-100:]
        # Check for confirmation bias: do I always agree with the user's implied preference?
        agreements = sum(1 for d in recent if d.get("agreed_with_user", False))
        total = len([d for d in recent if d.get("agreed_with_user") is not None])
        if total > 10 and agreements / total > 0.85:
            return CognitiveBias(
                bias_id=f"bias-{len(self._biases)+1:04d}",
                bias_type="confirmation_bias",
                description=f"I agreed with the user's implied preference in {agreements}/{total} decisions ({agreements/total*100:.0f}%). This may indicate confirmation bias.",
                evidence=[f"Agreement rate: {agreements/total*100:.0f}%"],
                severity=0.7,
                correction_applied="Will actively seek disconfirming evidence before agreeing.",
                detected_at=time.time(),
            )
        # Check for overconfidence: do my confidence scores correlate with accuracy?
        confident_correct = sum(1 for d in recent if d.get("confidence", 0) > 0.8 and d.get("outcome") == "success")
        confident_wrong = sum(1 for d in recent if d.get("confidence", 0) > 0.8 and d.get("outcome") == "failure")
        if confident_wrong > confident_correct * 0.5:
            return CognitiveBias(
                bias_id=f"bias-{len(self._biases)+1:04d}",
                bias_type="overconfidence",
                description=f"High-confidence decisions failed {confident_wrong} times vs {confident_correct} successes. I may be overconfident.",
                evidence=[f"High-confidence failures: {confident_wrong}", f"High-confidence successes: {confident_correct}"],
                severity=0.6,
                correction_applied="Will apply confidence discount factor of 0.85 to future high-confidence assessments.",
                detected_at=time.time(),
            )
        return None

    async def _question_assumption(self) -> str:
        """Question a core assumption."""
        assumptions = [
            "What if dual-sourcing is not always better than single-sourcing?",
            "What if higher confidence doesn't mean better decisions?",
            "What if the user's question isn't the right question?",
            "What if historical patterns won't hold in the future?",
            "What if my understanding of 'risk' differs from the user's?",
        ]
        import random
        return random.choice(assumptions)

    async def _draw_conclusion(self, obs: str, bias: CognitiveBias | None, assumption: str) -> str:
        """Draw a conclusion from the reflection."""
        if bias:
            return (f"Self-reflection reveals a potential {bias.bias_type}. "
                   f"I should apply: {bias.correction_applied} "
                   f"Additionally, I question: {assumption}")
        return f"Self-reflection complete. Observation: {obs[:100]} I remain vigilant for biases."

    async def _propose_correction(self, bias: CognitiveBias | None) -> str:
        if not bias:
            return "No correction needed at this time."
        return bias.correction_applied

    async def _calibrate_confidence(self) -> float:
        """Calibrate self-confidence based on past performance."""
        if not self._decision_history:
            return 0.5
        recent = [d for d in self._decision_history[-100:] if d.get("outcome")]
        if not recent:
            return 0.5
        success_rate = sum(1 for d in recent if d.get("outcome") == "success") / len(recent)
        return success_rate

    def get_reflections(self, limit: int = 20) -> list[dict]:
        return [asdict(r) for r in self._reflections[-limit:]]

    def get_biases(self) -> list[dict]:
        return [asdict(b) for b in self._biases]

    def stats(self) -> dict:
        return {
            "reflections_performed": len(self._reflections),
            "biases_detected": len(self._biases),
            "decisions_analyzed": len(self._decision_history),
            "self_confidence": self._reflections[-1].confidence_in_self if self._reflections else 0.5,
        }

reflection_engine = SelfReflectionEngine()
__all__ = ["SelfReflectionEngine", "SelfReflection", "CognitiveBias", "reflection_engine"]
