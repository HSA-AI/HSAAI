"""
HSAAI Cognitive Narrative Engine — v0.5.0
The organism understands and constructs STORIES — not just data points.
Every decision, event, and insight is placed in a narrative context.
"""
from __future__ import annotations
import logging, time, json
from dataclasses import dataclass, field, asdict
from typing import Any
logger = logging.getLogger("hsaai.narrative")

@dataclass
class EnterpriseNarrative:
    narrative_id: str = ""
    title: str = ""
    arc: str = ""  # rising, peak, falling, resolution
    actors: list[str] = field(default_factory=list)
    setting: str = ""  # organizational context
    conflict: str = ""  # the challenge
    resolution: str = ""  # how it was/will be resolved
    lessons: list[str] = field(default_factory=list)
    emotional_tone: str = ""  # triumphant, cautionary, tragic, hopeful
    created_at: float = 0.0

class CognitiveNarrativeEngine:
    """Constructs and understands enterprise narratives."""
    def __init__(self):
        self._narratives: list[EnterpriseNarrative] = []
        self._counter = 0

    async def construct_narrative(self, events: list[dict], context: dict) -> EnterpriseNarrative:
        self._counter += 1
        actors = list(set(e.get("actor", "system") for e in events))
        conflict = next((e.get("description", "") for e in events if e.get("type") == "challenge"), "Multiple challenges faced")
        resolution = next((e.get("outcome", "") for e in reversed(events) if e.get("outcome")), "Pending")
        tone = "triumphant" if "success" in resolution.lower() else "cautionary" if "failure" in resolution.lower() else "hopeful"
        narrative = EnterpriseNarrative(
            narrative_id=f"narrative-{self._counter:04d}",
            title=f"The Story of {context.get('topic', 'Enterprise Event')}",
            arc="resolution" if resolution != "Pending" else "rising",
            actors=actors[:5],
            setting=context.get("organizational_context", "HSA Group"),
            conflict=conflict[:300],
            resolution=resolution[:300],
            lessons=[e.get("lesson", "") for e in events if e.get("lesson")][:5],
            emotional_tone=tone,
            created_at=time.time(),
        )
        self._narratives.append(narrative)
        logger.info("📖 NARRATIVE: '%s' (%s arc, %s tone)", narrative.title, narrative.arc, tone)
        return narrative

    def get_narratives(self, limit: int = 20) -> list[dict]:
        return [asdict(n) for n in self._narratives[-limit:]]
    def stats(self) -> dict:
        return {"narratives_constructed": len(self._narratives)}

narrative_engine = CognitiveNarrativeEngine()
__all__ = ["CognitiveNarrativeEngine", "EnterpriseNarrative", "narrative_engine"]
