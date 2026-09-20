"""
HSAAI Emergent Intelligence Protocol — v0.4.0

The system DISCOVERS new intelligence capabilities that weren't explicitly
programmed. Like biological evolution, useful capabilities emerge from
the interaction of existing components and are retained if valuable.

This is what makes HSAAI truly alive — it grows new "organs" of
intelligence autonomously.
"""
from __future__ import annotations
import logging, time, json, hashlib
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.emergent")

@dataclass
class EmergentCapability:
    """A new intelligence capability that emerged from system interaction."""
    capability_id: str = ""
    name: str = ""
    description: str = ""
    emerged_from: list[str] = field(default_factory=list)  # which interactions created it
    first_observed: float = 0.0
    confidence: float = 0.0
    usefulness: float = 0.0  # measured value to the enterprise
    status: str = "discovered"  # discovered, testing, validated, integrated, deprecated
    applications: int = 0
    usage_trend: str = "unknown"  # increasing, stable, decreasing

@dataclass
class EmergenceEvent:
    """An event where a new capability was discovered."""
    event_id: str = ""
    timestamp: float = 0.0
    trigger: str = ""  # what triggered the emergence
    components_involved: list[str] = field(default_factory=list)
    capability_discovered: str = ""
    novelty_score: float = 0.0


class EmergentIntelligenceProtocol:
    """
    Discovers new intelligence capabilities that emerge from the
    interaction of existing system components.

    Like biological evolution:
      1. Variation: system tries new combinations of capabilities
      2. Selection: useful combinations are retained
      3. Retention: validated capabilities are integrated
    """
    def __init__(self):
        self._capabilities: dict[str, EmergentCapability] = {}
        self._events: list[EmergenceEvent] = []
        self._capability_counter = 0

    async def scan_for_emergence(self, recent_interactions: list[dict]) -> list[EmergentCapability]:
        """
        Scan recent system interactions for emergent patterns.
        Called periodically by the Evolution Engine.
        """
        new_capabilities = []

        # Pattern 1: Cross-service capability discovery
        # When service A + service B produce results that neither could alone
        service_combos = defaultdict(int)
        for interaction in recent_interactions:
            services = sorted(interaction.get("services_involved", []))
            if len(services) >= 2:
                combo_key = "+".join(services)
                service_combos[combo_key] += 1

        for combo, count in service_combos.items():
            if count >= 5:  # appeared 5+ times
                cap = await self._register_capability(
                    name=f"Cross-service: {combo}",
                    description=f"Emergent capability from combining {combo} ({count} times)",
                    emerged_from=combo.split("+"),
                    confidence=min(0.9, count / 10),
                )
                if cap:
                    new_capabilities.append(cap)

        # Pattern 2: Unexpected insight discovery
        # When the Dream Engine produces insights that no single service could
        for interaction in recent_interactions[-100:]:
            if interaction.get("source") == "dream_engine" and interaction.get("novelty", 0) > 0.7:
                cap = await self._register_capability(
                    name=f"Dream-discovered: {interaction.get('insight_type', 'unknown')}",
                    description=interaction.get("description", "")[:200],
                    emerged_from=["dream_engine", "consciousness_stream"],
                    confidence=interaction.get("confidence", 0.5),
                )
                if cap:
                    new_capabilities.append(cap)

        # Pattern 3: Neural-symbolic rule emergence
        for interaction in recent_interactions[-100:]:
            if interaction.get("source") == "neural_symbolic" and interaction.get("verified", False):
                cap = await self._register_capability(
                    name=f"Learned rule: {interaction.get('rule_text', '')[:80]}",
                    description=f"Self-learned symbolic rule: {interaction.get('rule_text', '')}",
                    emerged_from=["neural_symbolic", "memory_tiers"],
                    confidence=interaction.get("verification_score", 0.7),
                )
                if cap:
                    new_capabilities.append(cap)

        if new_capabilities:
            logger.info("🌟 EMERGENT INTELLIGENCE: %d new capabilities discovered", len(new_capabilities))
        return new_capabilities

    async def _register_capability(self, name: str, description: str,
                                    emerged_from: list[str], confidence: float) -> EmergentCapability | None:
        # Check if already exists
        for cap in self._capabilities.values():
            if cap.name == name:
                cap.applications += 1
                return None  # already known

        self._capability_counter += 1
        cid = f"emergent-cap-{self._capability_counter:04d}"
        cap = EmergentCapability(
            capability_id=cid, name=name, description=description,
            emerged_from=emerged_from, first_observed=time.time(),
            confidence=confidence, status="discovered",
        )
        self._capabilities[cid] = cap

        event = EmergenceEvent(
            event_id=f"emergence-{self._capability_counter:04d}",
            timestamp=time.time(),
            trigger="periodic_scan",
            components_involved=emerged_from,
            capability_discovered=cid,
            novelty_score=confidence,
        )
        self._events.append(event)

        logger.info("🌟 NEW CAPABILITY EMERGED: %s — %s", cid, name[:80])
        return cap

    async def evaluate_usefulness(self, capability_id: str, impact_metric: float) -> float:
        """Evaluate how useful a capability is to the enterprise."""
        cap = self._capabilities.get(capability_id)
        if not cap:
            return 0.0
        cap.usefulness = max(cap.usefulness, impact_metric)
        if cap.usefulness > 0.5 and cap.status == "discovered":
            cap.status = "testing"
        elif cap.usefulness > 0.7 and cap.status == "testing":
            cap.status = "validated"
            logger.info("✅ CAPABILITY VALIDATED: %s (usefulness: %.2f)", cap.name, cap.usefulness)
        elif cap.usefulness > 0.85 and cap.status == "validated":
            cap.status = "integrated"
            logger.info("🧠 CAPABILITY INTEGRATED INTO CIVILIZATION: %s", cap.name)
        return cap.usefulness

    def list_capabilities(self, status: str | None = None) -> list[dict]:
        caps = list(self._capabilities.values())
        if status:
            caps = [c for c in caps if c.status == status]
        return [asdict(c) for c in caps]

    def stats(self) -> dict:
        return {
            "total_capabilities": len(self._capabilities),
            "discovered": sum(1 for c in self._capabilities.values() if c.status == "discovered"),
            "testing": sum(1 for c in self._capabilities.values() if c.status == "testing"),
            "validated": sum(1 for c in self._capabilities.values() if c.status == "validated"),
            "integrated": sum(1 for c in self._capabilities.values() if c.status == "integrated"),
            "emergence_events": len(self._events),
        }

emergent_engine = EmergentIntelligenceProtocol()
__all__ = ["EmergentIntelligenceProtocol", "EmergentCapability", "EmergenceEvent", "emergent_engine"]
