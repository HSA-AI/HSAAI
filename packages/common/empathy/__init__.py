"""
HSAAI Enterprise Empathy Engine — v0.4.0

The cognitive organism doesn't just process data — it FEELS the
organizational climate. It senses employee sentiment, customer
frustration, stakeholder confidence, and organizational stress.

This is emotional intelligence for the enterprise.
"""
from __future__ import annotations
import logging, time, json
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.empathy")

@dataclass
class EmotionalState:
    """The emotional state of an entity (person, team, org)."""
    entity_id: str = ""
    entity_type: str = ""  # person, team, department, organization
    sentiment: float = 0.0  # -1.0 (very negative) to +1.0 (very positive)
    stress_level: float = 0.0  # 0.0 (calm) to 1.0 (critical stress)
    confidence: float = 0.0  # 0.0 (low) to 1.0 (high)
    engagement: float = 0.5  # 0.0 (disengaged) to 1.0 (highly engaged)
    frustration_indicators: list[str] = field(default_factory=list)
    satisfaction_indicators: list[str] = field(default_factory=list)
    assessed_at: float = 0.0

@dataclass
class OrganizationalClimate:
    """The overall emotional climate of the organization."""
    overall_sentiment: float = 0.0
    overall_stress: float = 0.0
    overall_engagement: float = 0.5
    departments_at_risk: list[str] = field(default_factory=list)
    positive_signals: list[str] = field(default_factory=list)
    negative_signals: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    assessed_at: float = 0.0


class EnterpriseEmpathyEngine:
    """
    Senses the emotional state of the organization through multi-modal analysis:
      - Communication tone (email, chat, tickets)
      - Behavioral patterns (response time, work hours, interaction frequency)
      - Feedback signals (surveys, reviews, exit interviews)
      - System signals (error rates, complaint volumes, support escalations)
    """
    def __init__(self):
        self._entity_states: dict[str, EmotionalState] = {}
        self._climate_history: list[OrganizationalClimate] = []

    async def assess_entity(self, entity_id: str, entity_type: str,
                            signals: dict) -> EmotionalState:
        """Assess the emotional state of an entity from signals."""
        sentiment = 0.0
        stress = 0.0
        engagement = 0.5
        frustration = []
        satisfaction = []

        # Communication tone analysis
        comm_tone = signals.get("communication_tone", {})
        if comm_tone:
            sentiment += comm_tone.get("positivity", 0) * 0.3
            if comm_tone.get("anger_indicators", 0) > 0.3:
                frustration.append("elevated anger in communications")
                stress += 0.2
            if comm_tone.get("gratitude_indicators", 0) > 0.3:
                satisfaction.append("gratitude expressions detected")

        # Behavioral patterns
        behavior = signals.get("behavioral_patterns", {})
        if behavior:
            response_time = behavior.get("avg_response_time_hours", 4)
            if response_time > 8:
                stress += 0.2
                frustration.append(f"slow response time ({response_time:.0f}h avg)")
            elif response_time < 2:
                engagement += 0.15

            work_hours = behavior.get("avg_work_hours", 8)
            if work_hours > 10:
                stress += 0.25
                frustration.append(f"extended work hours ({work_hours:.0f}h avg)")
            elif work_hours < 6:
                engagement -= 0.1

        # System signals
        system = signals.get("system_signals", {})
        if system:
            error_rate = system.get("error_rate", 0)
            if error_rate > 0.05:
                stress += 0.15
                frustration.append(f"high system error rate ({error_rate*100:.1f}%)")

            complaint_volume = system.get("complaint_volume", 0)
            if complaint_volume > 10:
                stress += 0.1
                frustration.append(f"elevated complaints ({complaint_volume})")

        # Feedback signals
        feedback = signals.get("feedback", {})
        if feedback:
            survey_score = feedback.get("satisfaction_score", 0.5)
            sentiment += (survey_score - 0.5) * 0.4
            engagement = (engagement + survey_score) / 2

        state = EmotionalState(
            entity_id=entity_id, entity_type=entity_type,
            sentiment=max(-1.0, min(1.0, sentiment)),
            stress=min(1.0, stress),
            confidence=0.6,
            engagement=max(0.0, min(1.0, engagement)),
            frustration_indicators=frustration,
            satisfaction_indicators=satisfaction,
            assessed_at=time.time(),
        )
        self._entity_states[entity_id] = state
        return state

    async def assess_organizational_climate(self) -> OrganizationalClimate:
        """Assess the overall emotional climate of the organization."""
        if not self._entity_states:
            return OrganizationalClimate(assessed_at=time.time())

        sentiments = [s.sentiment for s in self._entity_states.values()]
        stresses = [s.stress_level for s in self._entity_states.values()]
        engagements = [s.engagement for s in self._entity_states.values()]

        overall_sentiment = sum(sentiments) / len(sentiments)
        overall_stress = sum(stresses) / len(stresses)
        overall_engagement = sum(engagements) / len(engagements)

        at_risk = []
        for eid, state in self._entity_states.items():
            if state.stress_level > 0.6 or state.sentiment < -0.3:
                at_risk.append(eid)

        positive = []
        negative = []
        for state in self._entity_states.values():
            positive.extend(state.satisfaction_indicators[:2])
            negative.extend(state.frustration_indicators[:2])

        recommendations = []
        if overall_stress > 0.5:
            recommendations.append("Organizational stress is elevated — consider workload review and wellness initiatives.")
        if overall_engagement < 0.4:
            recommendations.append("Engagement is low — consider recognition programs and career development conversations.")
        if at_risk:
            recommendations.append(f"{len(at_risk)} entities show risk indicators — schedule check-ins.")
        if overall_sentiment > 0.3:
            recommendations.append("Positive sentiment detected — leverage momentum for innovation initiatives.")

        climate = OrganizationalClimate(
            overall_sentiment=overall_sentiment,
            overall_stress=overall_stress,
            overall_engagement=overall_engagement,
            departments_at_risk=at_risk[:10],
            positive_signals=list(set(positive))[:5],
            negative_signals=list(set(negative))[:5],
            recommendations=recommendations,
            assessed_at=time.time(),
        )
        self._climate_history.append(climate)
        if len(self._climate_history) > 90:
            self._climate_history = self._climate_history[-30:]
        return climate

    def get_entity_state(self, entity_id: str) -> dict | None:
        state = self._entity_states.get(entity_id)
        return asdict(state) if state else None

    def climate_trend(self, days: int = 30) -> dict:
        """Get climate trend over the last N days."""
        if not self._climate_history:
            return {"trend": "no_data"}
        recent = self._climate_history[-days:]
        return {
            "sentiment_trend": [c.overall_sentiment for c in recent],
            "stress_trend": [c.overall_stress for c in recent],
            "engagement_trend": [c.overall_engagement for c in recent],
            "data_points": len(recent),
        }

    def stats(self) -> dict:
        return {
            "entities_tracked": len(self._entity_states),
            "climate_assessments": len(self._climate_history),
            "at_risk_count": sum(1 for s in self._entity_states.values() if s.stress_level > 0.6),
        }

empathy_engine = EnterpriseEmpathyEngine()
__all__ = ["EnterpriseEmpathyEngine", "EmotionalState", "OrganizationalClimate", "empathy_engine"]
