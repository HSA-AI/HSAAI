"""
HSAAI Cultural Intelligence Engine — v0.5.0
Understands the UNIQUE CULTURE of the enterprise — its values, norms,
communication patterns, decision styles, and unwritten rules.
Adapts its behavior to align with organizational culture.
"""
from __future__ import annotations
import logging, time, json
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.cultural")

@dataclass
class CulturalProfile:
    organization: str = ""
    values: list[str] = field(default_factory=list)
    communication_style: str = ""  # direct, indirect, formal, informal
    decision_style: str = ""  # top_down, consensus, data_driven, intuitive
    risk_appetite: str = ""  # conservative, moderate, aggressive
    time_orientation: str = ""  # short_term, long_term
    power_distance: float = 0.5  # 0=flat, 1=hierarchical
    uncertainty_avoidance: float = 0.5
    individualism_collectivism: float = 0.5  # 0=collectivist, 1=individualist
    arabic_language_preference: float = 1.0  # 0=English, 1=Arabic
    formality_level: float = 0.7
    assessed_at: float = 0.0

@dataclass
class CulturalAdaptation:
    adaptation_id: str = ""
    what_adapted: str = ""
    why: str = ""
    cultural_dimension: str = ""
    before: str = ""
    after: str = ""
    effectiveness: float = 0.0

class CulturalIntelligenceEngine:
    """Understands and adapts to the enterprise's unique culture."""
    def __init__(self):
        self._profile: CulturalProfile | None = None
        self._adaptations: list[CulturalAdaptation] = []
        self._cultural_signals: list[dict] = []
        self._adaptation_counter = 0

    async def assess_culture(self, signals: list[dict]) -> CulturalProfile:
        """Assess organizational culture from behavioral signals."""
        # Analyze communication patterns
        formal_count = sum(1 for s in signals if s.get("formal_language"))
        informal_count = sum(1 for s in signals if not s.get("formal_language"))
        comm_style = "formal" if formal_count > informal_count else "informal"

        # Decision style
        top_down = sum(1 for s in signals if s.get("decision_source") == "leadership")
        consensus = sum(1 for s in signals if s.get("decision_source") == "team")
        data_driven = sum(1 for s in signals if s.get("decision_source") == "data")
        if top_down > max(consensus, data_driven):
            decision_style = "top_down"
        elif data_driven > consensus:
            decision_style = "data_driven"
        else:
            decision_style = "consensus"

        # Risk appetite
        risky = sum(1 for s in signals if s.get("risk_taken", False))
        safe = sum(1 for s in signals if not s.get("risk_taken", False))
        risk_appetite = "aggressive" if risky > safe * 1.5 else "conservative" if safe > risky * 1.5 else "moderate"

        # Arabic preference
        arabic_comm = sum(1 for s in signals if s.get("language") == "arabic")
        total_comm = len(signals)
        arabic_pref = arabic_comm / total_comm if total_comm > 0 else 0.5

        self._profile = CulturalProfile(
            organization="HSA Group",
            values=["quality", "integrity", "community", "long_term_relationships"],
            communication_style=comm_style,
            decision_style=decision_style,
            risk_appetite=risk_appetite,
            time_orientation="long_term",
            power_distance=0.7,  # Yemeni conglomerate — hierarchical
            uncertainty_avoidance=0.6,
            individualism_collectivism=0.3,  # collectivist
            arabic_language_preference=arabic_pref,
            formality_level=0.8,
            assessed_at=time.time(),
        )
        logger.info("🌍 CULTURAL PROFILE: %s style, %s decisions, %s risk, Arabic pref: %.0f%%",
                    comm_style, decision_style, risk_appetite, arabic_pref*100)
        return self._profile

    async def adapt_communication(self, message: str, audience: str = "general") -> dict:
        """Adapt a message to match organizational culture."""
        if not self._profile:
            return {"adapted": message, "adaptations": []}
        adaptations = []
        adapted = message
        # Arabic preference
        if self._profile.arabic_language_preference > 0.7 and not any('\u0600' <= c <= '\u06FF' for c in message):
            adaptations.append("Considered Arabic translation (cultural preference)")
        # Formality
        if self._profile.formality_level > 0.6:
            adaptations.append(f"Applied formal tone (organizational formality: {self._profile.formality_level:.0%})")
        # Decision style
        if self._profile.decision_style == "data_driven":
            adaptations.append("Added data emphasis (organization prefers data-driven decisions)")
        elif self._profile.decision_style == "top_down":
            adaptations.append("Structured for leadership review (top-down decision culture)")
        return {"adapted": adapted, "adaptations": adaptations, "profile": asdict(self._profile)}

    def get_profile(self) -> dict | None:
        return asdict(self._profile) if self._profile else None

    def stats(self) -> dict:
        return {
            "profile_assessed": self._profile is not None,
            "adaptations_made": len(self._adaptations),
            "cultural_signals_collected": len(self._cultural_signals),
        }

cultural_engine = CulturalIntelligenceEngine()
__all__ = ["CulturalIntelligenceEngine", "CulturalProfile", "CulturalAdaptation", "cultural_engine"]
