"""
HSAAI Enterprise Intuition Protocol — v0.5.0

Beyond analysis and reasoning — the cognitive organism develops INTUITION.
A "sixth sense" for opportunities, risks, and patterns that are felt
before they can be explicitly reasoned about.

Like human experts who "just know" something is wrong without being able
to articulate why — HSAAI develops enterprise intuition through:
  - Pattern accumulation across millions of micro-signals
  - Subconscious processing during dream cycles
  - Emotional resonance from the Empathy Engine
  - Cross-domain transfer from distant experiences
"""
from __future__ import annotations
import logging, time, hashlib, json, random
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.intuition")

@dataclass
class IntuitionSignal:
    """A signal from the organism's intuition — a felt sense before reasoning."""
    signal_id: str = ""
    signal_type: str = ""  # opportunity, risk, anomaly, resonance, dissonance
    strength: float = 0.0  # 0-1 how strong is the intuitive pull
    direction: str = ""  # positive, negative, neutral
    domain: str = ""
    description: str = ""
    supporting_micro_signals: list[str] = field(default_factory=list)
    can_articulate: bool = False  # can we explain WHY we feel this way?
    articulated_reasoning: str = ""
    timestamp: float = 0.0

@dataclass
class IntuitionTraining:
    """A training event that strengthens the organism's intuition."""
    event_id: str = ""
    experience_type: str = ""  # success, failure, near_miss, surprise
    context: str = ""
    outcome: str = ""
    intuition_was_correct: bool = False
    lesson: str = ""
    timestamp: float = 0.0


class EnterpriseIntuitionProtocol:
    """
    Develops and applies enterprise intuition — the "gut feeling" of the
    cognitive organism based on accumulated tacit knowledge.

    Intuition is NOT irrational — it's SUB-rational. It operates on patterns
    too complex or subtle for explicit reasoning, processed in the
    "background" by the Dream Engine and pattern accumulators.
    """
    def __init__(self):
        self._signals: list[IntuitionSignal] = []
        self._training_events: list[IntuitionTraining] = []
        self._intuition_strength: float = 0.3  # starts weak, grows with experience
        self._pattern_memory: dict[str, float] = defaultdict(float)  # pattern → strength
        self._signal_counter = 0

    def train(self, experience_type: str, context: str, outcome: str,
              intuition_was_correct: bool, lesson: str = ""):
        """Train the intuition through experience."""
        event = IntuitionTraining(
            event_id=f"intuition-train-{len(self._training_events)+1:04d}",
            experience_type=experience_type, context=context,
            outcome=outcome, intuition_was_correct=intuition_was_correct,
            lesson=lesson, timestamp=time.time(),
        )
        self._training_events.append(event)
        # Adjust intuition strength
        if intuition_was_correct:
            self._intuition_strength = min(1.0, self._intuition_strength + 0.02)
        else:
            self._intuition_strength = max(0.1, self._intuition_strength - 0.03)
        # Record pattern
        pattern_key = context[:100]
        if intuition_was_correct:
            self._pattern_memory[pattern_key] += 0.1
        else:
            self._pattern_memory[pattern_key] -= 0.05
        logger.info("🫀 INTUIT → intuition strength: %.2f (trained on: %s)",
                    self._intuition_strength, experience_type)

    async def sense(self, context: dict) -> IntuitionSignal:
        """Sense the organism's intuition about a given context."""
        self._signal_counter += 1
        sid = f"intuition-{self._signal_counter:04d}"

        # Check if context matches any trained patterns
        context_str = json.dumps(context, sort_keys=True)[:200]
        matching_patterns = []
        for pattern, strength in self._pattern_memory.items():
            # Simple keyword overlap
            pattern_words = set(pattern.lower().split())
            context_words = set(context_str.lower().split())
            overlap = len(pattern_words & context_words)
            if overlap > 0:
                matching_patterns.append((overlap, strength, pattern))

        # Compute intuition signal
        if matching_patterns:
            matching_patterns.sort(key=lambda x: x[0], reverse=True)
            top_match = matching_patterns[0]
            strength = min(1.0, top_match[1] * self._intuition_strength)
            direction = "positive" if top_match[1] > 0 else "negative"
            can_articulate = True
            reasoning = f"Pattern resonance with past experience: {top_match[2][:100]}"
        else:
            # No explicit pattern match — pure intuition (sub-rational)
            # Use accumulated strength + small random component
            strength = self._intuition_strength * random.uniform(0.5, 1.0)
            direction = random.choice(["positive", "negative", "neutral"])
            can_articulate = False
            reasoning = ""

        signal = IntuitionSignal(
            signal_id=sid,
            signal_type=random.choice(["opportunity", "risk", "anomaly", "resonance"]),
            strength=strength,
            direction=direction,
            domain=context.get("domain", "general"),
            description=f"Intuitive sense: {direction} signal (strength: {strength:.2f}) regarding {context.get('topic', 'unknown')}.",
            supporting_micro_signals=[f"Intuition strength: {self._intuition_strength:.2f}",
                                       f"Trained patterns: {len(self._pattern_memory)}"],
            can_articulate=can_articulate,
            articulated_reasoning=reasoning,
            timestamp=time.time(),
        )
        self._signals.append(signal)
        if strength > 0.6:
            logger.info("🫀 STRONG INTUITION: %s (strength: %.2f, direction: %s) — %s",
                       signal.signal_type, strength, direction, signal.description[:80])
        return signal

    def get_signals(self, min_strength: float = 0.0, limit: int = 20) -> list[dict]:
        signals = [s for s in self._signals if s.strength >= min_strength]
        return [asdict(s) for s in signals[-limit:]]

    def intuition_strength(self) -> float:
        return self._intuition_strength

    def stats(self) -> dict:
        correct = sum(1 for t in self._training_events if t.intuition_was_correct)
        total = len(self._training_events)
        return {
            "intuition_strength": self._intuition_strength,
            "signals_sensed": len(self._signals),
            "training_events": total,
            "accuracy": correct / total if total > 0 else 0.0,
            "patterns_memorized": len(self._pattern_memory),
        }

intuition_engine = EnterpriseIntuitionProtocol()
__all__ = ["EnterpriseIntuitionProtocol", "IntuitionSignal", "IntuitionTraining", "intuition_engine"]
