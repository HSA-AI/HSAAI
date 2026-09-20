"""
HSAAI Wisdom Crystallization Engine — v0.2.0

Transforms thousands of decisions and experiences into reusable Wisdom Crystals.
Also manages Failure Memory — never forgets failures.

Wisdom Crystals are the highest tier of enterprise memory (T8).
Failure Memory is T7 — sacred, never deleted.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

logger = logging.getLogger("hsaai.wisdom")


@dataclass
class WisdomCrystal:
    """A crystallized piece of enterprise wisdom — the highest form of knowledge."""
    wisdom_id: str
    statement: str
    confidence: float = 0.0
    evidence_base: str = ""  # "847 decisions, 5 years, 23 industries"
    derived_from: list[str] = field(default_factory=list)  # decision IDs
    applicable_when: str = ""  # conditions for application
    counter_examples: int = 0  # when this wisdom didn't hold
    refinements: list[str] = field(default_factory=list)
    tenant_id: str = "default"
    domain: str = "general"
    crystallized_at: float = 0.0
    review_cycle: str = "annual"
    last_applied: float = 0.0
    application_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "WisdomCrystal":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class FailureRecord:
    """A failure memory record — sacred, never deleted."""
    failure_id: str
    what_happened: str
    what_was_expected: str
    root_cause: str
    cost_estimate: float = 0.0
    lesson_learned: str = ""
    avoidance_strategy: str = ""
    similar_decision_pattern: str = ""  # for future matching
    occurred_at: float = 0.0
    decision_id: str = ""
    actor: str = "unknown"
    tenant_id: str = "default"
    domain: str = "general"

    def to_dict(self) -> dict:
        return asdict(self)


class WisdomCrystallizationEngine:
    """
    Transforms raw experience into Wisdom Crystals.

    Pipeline: Collect → Pattern Extract → Causal Infer → Validate → Crystallize
    """

    def __init__(self):
        self._crystals: dict[str, WisdomCrystal] = {}
        self._failures: dict[str, FailureRecord] = {}
        self._crystal_counter = 0
        self._failure_counter = 0

    async def crystallize(
        self,
        decisions: list[dict],
        domain: str = "general",
        tenant_id: str = "default",
        min_confidence: float = 0.7,
        min_evidence: int = 10,
    ) -> list[WisdomCrystal]:
        """
        Crystallize wisdom from a batch of decisions.
        Returns list of new WisdomCrystals created.
        """
        if len(decisions) < min_evidence:
            logger.info("Insufficient decisions for crystallization: %d < %d", len(decisions), min_evidence)
            return []

        # Step 1: Extract patterns
        patterns = await self._extract_patterns(decisions, domain)

        # Step 2: Validate each pattern
        new_crystals: list[WisdomCrystal] = []
        for pattern in patterns:
            if pattern.get("confidence", 0) < min_confidence:
                continue

            crystal = WisdomCrystal(
                wisdom_id=self._next_wisdom_id(),
                statement=pattern["statement"],
                confidence=pattern["confidence"],
                evidence_base=f"{len(decisions)} decisions, domain: {domain}",
                derived_from=[d.get("decision_id", "") for d in decisions[:20]],
                applicable_when=pattern.get("conditions", ""),
                counter_examples=pattern.get("counter_examples", 0),
                domain=domain,
                tenant_id=tenant_id,
                crystallized_at=time.time(),
            )
            self._crystals[crystal.wisdom_id] = crystal
            new_crystals.append(crystal)
            logger.info("Crystallized wisdom-%s: %s (confidence: %.2f)",
                       crystal.wisdom_id, crystal.statement[:80], crystal.confidence)

        return new_crystals

    async def _extract_patterns(self, decisions: list[dict], domain: str) -> list[dict]:
        """Extract recurring patterns from decisions."""
        patterns = []

        # Pattern 1: Success factors
        successes = [d for d in decisions if d.get("outcome") == "success"]
        failures = [d for d in decisions if d.get("outcome") == "failure"]

        if successes and failures:
            success_rate = len(successes) / len(decisions)

            # Find common attributes in successes
            success_attrs = self._find_common_attributes(successes)
            failure_attrs = self._find_common_attributes(failures)

            for attr, val in success_attrs.items():
                if attr in failure_attrs and failure_attrs[attr] != val:
                    statement = (
                        f"Decisions with {attr}='{val}' succeeded "
                        f"{success_rate*100:.0f}% of the time vs "
                        f"{(1-success_rate)*100:.0f}% failure rate."
                    )
                    patterns.append({
                        "statement": statement,
                        "confidence": min(0.9, success_rate),
                        "conditions": f"{attr} == '{val}'",
                        "counter_examples": len(failures),
                    })

        return patterns

    def _find_common_attributes(self, decisions: list[dict]) -> dict:
        """Find attributes common across a set of decisions."""
        if not decisions:
            return {}
        common = {}
        keys = set()
        for d in decisions:
            keys.update(d.keys())
        for key in keys:
            values = [d.get(key) for d in decisions if d.get(key) is not None]
            if values and len(values) > len(decisions) * 0.7:
                # More than 70% have this value
                from collections import Counter
                most_common = Counter(values).most_common(1)
                if most_common:
                    common[key] = most_common[0][0]
        return common

    def _next_wisdom_id(self) -> str:
        self._crystal_counter += 1
        return f"wisdom-{self._crystal_counter:04d}"

    def get_wisdom(self, wisdom_id: str) -> WisdomCrystal | None:
        return self._crystals.get(wisdom_id)

    def list_wisdom(self, domain: str | None = None) -> list[WisdomCrystal]:
        if domain:
            return [c for c in self._crystals.values() if c.domain == domain]
        return list(self._crystals.values())

    def find_applicable_wisdom(self, context: dict) -> list[WisdomCrystal]:
        """Find wisdom crystals applicable to the given context."""
        applicable = []
        for crystal in self._crystals.values():
            if crystal.tenant_id != context.get("tenant_id", "default"):
                continue
            # Simple matching: check if context keys appear in applicable_when
            if not crystal.applicable_when:
                applicable.append(crystal)
                continue
            for key, val in context.items():
                if str(val) in crystal.applicable_when:
                    applicable.append(crystal)
                    break
        return applicable

    def record_application(self, wisdom_id: str):
        """Record that a wisdom crystal was applied."""
        if wisdom_id in self._crystals:
            self._crystals[wisdom_id].application_count += 1
            self._crystals[wisdom_id].last_applied = time.time()


class FailureMemory:
    """
    Failure Memory — T7. Sacred, never deleted.
    Every failure is recorded with root cause and avoidance strategy.
    Any future similar decision checks Failure Memory FIRST.
    """

    def __init__(self):
        self._failures: dict[str, FailureRecord] = {}
        self._failure_counter = 0

    def record_failure(
        self,
        what_happened: str,
        what_was_expected: str,
        root_cause: str,
        cost_estimate: float = 0.0,
        lesson_learned: str = "",
        avoidance_strategy: str = "",
        similar_decision_pattern: str = "",
        decision_id: str = "",
        actor: str = "unknown",
        domain: str = "general",
        tenant_id: str = "default",
    ) -> FailureRecord:
        """Record a failure. This is PERMANENT — never deleted."""
        self._failure_counter += 1
        failure_id = f"failure-{self._failure_counter:04d}"
        record = FailureRecord(
            failure_id=failure_id,
            what_happened=what_happened,
            what_was_expected=what_was_expected,
            root_cause=root_cause,
            cost_estimate=cost_estimate,
            lesson_learned=lesson_learned,
            avoidance_strategy=avoidance_strategy,
            similar_decision_pattern=similar_decision_pattern,
            occurred_at=time.time(),
            decision_id=decision_id,
            actor=actor,
            domain=domain,
            tenant_id=tenant_id,
        )
        self._failures[failure_id] = record
        logger.warning("FAILURE RECORDED [%s]: %s (cost: $%.2f, root cause: %s)",
                      failure_id, what_happened[:80], cost_estimate, root_cause[:80])
        return record

    def find_similar_failures(
        self, decision_description: str, domain: str | None = None, limit: int = 5, tenant_id: str = "default"
    ) -> list[FailureRecord]:
        """
        Find past failures similar to a pending decision.
        Called BEFORE any decision to check: "Have we failed at something similar before?"
        """
        # Simple keyword matching (production: use embeddings)
        keywords = set(decision_description.lower().split())
        scored = []
        for failure in self._failures.values():
            if failure.tenant_id != tenant_id:
                continue
            if domain and failure.domain != domain:
                continue
            failure_words = set(failure.what_happened.lower().split())
            overlap = len(keywords & failure_words)
            if overlap > 0:
                scored.append((overlap, failure))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored[:limit]]

    def get_failure(self, failure_id: str) -> FailureRecord | None:
        return self._failures.get(failure_id)

    def list_failures(self, domain: str | None = None, limit: int = 50) -> list[FailureRecord]:
        failures = list(self._failures.values())
        if domain:
            failures = [f for f in failures if f.domain == domain]
        failures.sort(key=lambda f: f.occurred_at, reverse=True)
        return failures[:limit]

    def total_failure_cost(self) -> float:
        """Total estimated cost of all recorded failures."""
        return sum(f.cost_estimate for f in self._failures.values())

    def lessons_learned(self, domain: str | None = None) -> list[str]:
        """All lessons learned from failures."""
        failures = self.list_failures(domain, limit=1000)
        return [f.lesson_learned for f in failures if f.lesson_learned]


# Module-level singletons
wisdom_engine = WisdomCrystallizationEngine()
failure_memory = FailureMemory()


__all__ = [
    "WisdomCrystallizationEngine",
    "WisdomCrystal",
    "FailureMemory",
    "FailureRecord",
    "wisdom_engine",
    "failure_memory",
]
