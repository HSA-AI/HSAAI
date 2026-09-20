"""
HSAAI Enterprise Consciousness Stream — v0.2.0

Continuous enterprise awareness via event ingestion.
The enterprise "sees" everything happening in real-time.
"""
from __future__ import annotations
import asyncio, logging, time, hashlib, json
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.consciousness")

@dataclass
class EnterpriseEvent:
    event_id: str = ""
    event_type: str = ""
    source: str = ""
    timestamp: float = 0.0
    entities: list[dict] = field(default_factory=list)
    payload: dict = field(default_factory=dict)
    severity: str = "info"
    tenant_id: str = "default"

@dataclass
class SalienceScore:
    score: float = 0.0
    factors: dict = field(default_factory=dict)
    recommendation: str = ""

class ConsciousnessStream:
    """Continuous stream of enterprise events — the 'eyes' of the cognitive organism."""
    def __init__(self):
        self._events: list[EnterpriseEvent] = []
        self._subscribers: dict[str, list] = defaultdict(list)
        self._event_count = 0

    async def ingest(self, event: EnterpriseEvent) -> dict:
        """Ingest an enterprise event and propagate to subscribers."""
        if not event.event_id:
            event.event_id = hashlib.sha256(
                f"{event.source}:{event.event_type}:{time.time()}".encode()
            ).hexdigest()[:16]
        if not event.timestamp:
            event.timestamp = time.time()
        self._event_count += 1
        self._events.append(event)
        if len(self._events) > 10000:
            self._events = self._events[-5000:]  # keep last 5K

        salience = await self._score_salience(event)
        result = {"event_id": event.event_id, "salience": salience.score, "processed": True}
        if salience.score > 0.7:
            result["proactive_alert"] = True
            result["recommendation"] = salience.recommendation
            logger.info("HIGH SALIENCE EVENT [%s]: %s (score: %.2f) — %s",
                       event.event_id, event.event_type, salience.score, salience.recommendation)
        return result

    async def _score_salience(self, event: EnterpriseEvent) -> SalienceScore:
        score = 0.0
        factors = {}
        if event.severity in ("critical", "error"): score += 0.4; factors["severity"] = 0.4
        elif event.severity == "warning": score += 0.2; factors["severity"] = 0.2
        if event.event_type in ("supplier_delay", "contract_breach", "regulatory_change",
                                "market_shift", "security_incident"):
            score += 0.3; factors["event_type"] = 0.3
        if len(event.entities) > 3: score += 0.15; factors["entity_count"] = 0.15
        if event.payload.get("financial_impact", 0) > 100000:
            score += 0.25; factors["financial_impact"] = 0.25
        recommendation = ""
        if score > 0.7:
            recommendation = f"Proactive alert recommended for {event.event_type} from {event.source}."
        return SalienceScore(score=min(score, 1.0), factors=factors, recommendation=recommendation)

    def subscribe(self, event_type: str, callback):
        self._subscribers[event_type].append(callback)

    def stats(self) -> dict:
        return {"total_events": self._event_count, "buffered": len(self._events),
                "subscriber_types": list(self._subscribers.keys())}

consciousness_stream = ConsciousnessStream()
__all__ = ["ConsciousnessStream", "EnterpriseEvent", "SalienceScore", "consciousness_stream"]
