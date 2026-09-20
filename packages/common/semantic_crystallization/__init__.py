"""
HSAAI Semantic Memory Crystallization — v0.5.0
Transforms raw semantic data into crystallized knowledge structures.
Not just storing facts — building INTERCONNECTED KNOWLEDGE CRYSTALS
that grow and strengthen with each new experience.
"""
from __future__ import annotations
import logging, time, hashlib, json
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.semantic_cryst")

@dataclass
class KnowledgeCrystal:
    crystal_id: str = ""
    concept: str = ""
    facets: list[str] = field(default_factory=list)  # different aspects understood
    connections: dict = field(default_factory=dict)  # connected concepts → strength
    confidence: float = 0.0
    times_accessed: int = 0
    times_validated: int = 0
    times_refuted: int = 0
    maturity: str = "forming"  # forming, stable, mature, crystallized
    created_at: float = 0.0
    last_reinforced: float = 0.0

class SemanticCrystallizationEngine:
    """Crystallizes semantic knowledge into growing interconnected structures."""
    def __init__(self):
        self._crystals: dict[str, KnowledgeCrystal] = {}
        self._counter = 0

    def ingest(self, concept: str, facet: str, connections: dict | None = None):
        """Ingest a new semantic observation."""
        key = concept.lower().strip()
        if key not in self._crystals:
            self._counter += 1
            self._crystals[key] = KnowledgeCrystal(
                crystal_id=f"crystal-{self._counter:04d}",
                concept=concept, facets=[facet],
                connections=connections or {},
                confidence=0.3, created_at=time.time(), last_reinforced=time.time(),
            )
        else:
            crystal = self._crystals[key]
            if facet not in crystal.facets:
                crystal.facets.append(facet)
            if connections:
                for k, v in connections.items():
                    if k in crystal.connections:
                        crystal.connections[k] = max(crystal.connections[k], v)
                    else:
                        crystal.connections[k] = v
            crystal.confidence = min(1.0, crystal.confidence + 0.1)
            crystal.last_reinforced = time.time()
            # Update maturity
            if crystal.confidence > 0.8 and len(crystal.facets) > 5:
                crystal.maturity = "crystallized"
            elif crystal.confidence > 0.6:
                crystal.maturity = "mature"
            elif crystal.confidence > 0.4:
                crystal.maturity = "stable"

    def access(self, concept: str) -> dict | None:
        crystal = self._crystals.get(concept.lower().strip())
        if crystal:
            crystal.times_accessed += 1
            return asdict(crystal)
        return None

    def validate(self, concept: str, correct: bool):
        crystal = self._crystals.get(concept.lower().strip())
        if crystal:
            if correct:
                crystal.times_validated += 1
                crystal.confidence = min(1.0, crystal.confidence + 0.05)
            else:
                crystal.times_refuted += 1
                crystal.confidence = max(0.1, crystal.confidence - 0.1)

    def list_crystals(self, maturity: str | None = None, limit: int = 50) -> list[dict]:
        crystals = list(self._crystals.values())
        if maturity:
            crystals = [c for c in crystals if c.maturity == maturity]
        crystals.sort(key=lambda c: c.confidence, reverse=True)
        return [asdict(c) for c in crystals[:limit]]

    def stats(self) -> dict:
        return {
            "total_crystals": len(self._crystals),
            "crystallized": sum(1 for c in self._crystals.values() if c.maturity == "crystallized"),
            "mature": sum(1 for c in self._crystals.values() if c.maturity == "mature"),
            "avg_confidence": sum(c.confidence for c in self._crystals.values()) / max(len(self._crystals), 1),
        }

semantic_crystallization_engine = SemanticCrystallizationEngine()
__all__ = ["SemanticCrystallizationEngine", "KnowledgeCrystal", "semantic_crystallization_engine"]
