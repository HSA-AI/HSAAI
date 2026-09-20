"""
HSAAI Causal Time Travel — v0.4.0

The ability to "replay" historical enterprise states and test alternative
decisions against them. Not just counterfactual reasoning — actual
state reconstruction + alternative path simulation.

"What would have happened if we made a different decision on 2024-03-15?"
"""
from __future__ import annotations
import logging, time, json, copy
from dataclasses import dataclass, field, asdict
from typing import Any
logger = logging.getLogger("hsaai.time_travel")

@dataclass
class HistoricalState:
    """A reconstructed snapshot of the enterprise at a point in time."""
    timestamp: float = 0.0
    label: str = ""
    entities: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    decisions_made: list[dict] = field(default_factory=list)
    active_risks: list[dict] = field(default_factory=list)
    financial_state: dict = field(default_factory=dict)

@dataclass
class AlternativeTimeline:
    """Result of testing an alternative decision in the past."""
    original_timeline: str = ""
    alternative_decision: str = ""
    divergence_point: float = 0.0
    original_outcome: dict = field(default_factory=dict)
    alternative_outcome: dict = field(default_factory=dict)
    differences: list[str] = field(default_factory=list)
    confidence: float = 0.0
    lesson: str = ""


class CausalTimeTravel:
    """
    Reconstructs historical enterprise states and simulates alternative
    decisions against them — "rewinding" the enterprise to a past moment
    and playing it forward with a different choice.
    """
    def __init__(self):
        self._snapshots: dict[float, HistoricalState] = {}
        self._timelines: list[AlternativeTimeline] = []

    def record_snapshot(self, state: HistoricalState):
        """Record a point-in-time enterprise state."""
        self._snapshots[state.timestamp] = state
        if len(self._snapshots) > 365:  # keep 1 year of daily snapshots
            oldest = min(self._snapshots.keys())
            del self._snapshots[oldest]

    def get_snapshot(self, timestamp: float) -> HistoricalState | None:
        """Retrieve the closest snapshot to a timestamp."""
        if not self._snapshots:
            return None
        closest = min(self._snapshots.keys(), key=lambda t: abs(t - timestamp))
        return self._snapshots[closest]

    async def replay_with_alternative(
        self,
        timestamp: float,
        original_decision: str,
        alternative_decision: str,
        original_outcome: dict,
        horizon_months: int = 6,
    ) -> AlternativeTimeline:
        """
        Replay history from `timestamp` with an alternative decision.

        "What would have happened if we chose differently on date X?"
        """
        snapshot = self.get_snapshot(timestamp)
        if not snapshot:
            return AlternativeTimeline(
                original_timeline=original_decision,
                alternative_decision=alternative_decision,
                lesson="No historical snapshot available for this timestamp.",
            )

        # Simulate the alternative path
        # In production: use the Digital Twin to replay with modified inputs
        alt_metrics = copy.deepcopy(snapshot.metrics)

        # Apply alternative decision effects (simplified)
        if "renew" in alternative_decision.lower() and "diversif" in alternative_decision.lower():
            # Alternative: diversify suppliers instead of renew
            for key in alt_metrics:
                if "concentration" in key:
                    alt_metrics[key] *= 0.65  # reduce concentration by 35%
                if "risk" in key:
                    alt_metrics[key] *= 0.7  # reduce risk by 30%
                if "cost" in key and "savings" not in key:
                    alt_metrics[key] *= 1.08  # 8% cost increase from dual-source

        # Calculate differences
        differences = []
        for key in alt_metrics:
            orig = original_outcome.get(key, snapshot.metrics.get(key, 0))
            alt = alt_metrics[key]
            if isinstance(orig, (int, float)) and isinstance(alt, (int, float)) and orig != 0:
                change = (alt - orig) / abs(orig) * 100
                if abs(change) > 1:
                    differences.append(f"{key}: {change:+.1f}% (original: {orig:.2f}, alternative: {alt:.2f})")

        # Generate lesson
        lesson = ""
        if differences:
            positive = [d for d in differences if "+" in d and "cost" not in d.lower()]
            negative = [d for d in differences if "-" in d or "cost" in d.lower()]
            lesson = (f"Alternative decision '{alternative_decision}' would have resulted in "
                     f"{len(positive)} improvements and {len(negative)} trade-offs. "
                     f"Key insight: {differences[0] if differences else 'minimal impact'}.")
        else:
            lesson = "Alternative decision would have had minimal impact on measured outcomes."

        timeline = AlternativeTimeline(
            original_timeline=original_decision,
            alternative_decision=alternative_decision,
            divergence_point=timestamp,
            original_outcome=original_outcome,
            alternative_outcome=alt_metrics,
            differences=differences,
            confidence=0.65,  # medium confidence — simplified simulation
            lesson=lesson,
        )
        self._timelines.append(timeline)
        logger.info("⏰ TIME TRAVEL: Replayed %s → %s at %s",
                   original_decision, alternative_decision, time.ctime(timestamp))
        return timeline

    def list_timelines(self, limit: int = 20) -> list[dict]:
        return [asdict(t) for t in self._timelines[-limit:]]

    def stats(self) -> dict:
        return {
            "snapshots_stored": len(self._snapshots),
            "timelines_explored": len(self._timelines),
            "earliest_snapshot": min(self._snapshots.keys()) if self._snapshots else 0,
            "latest_snapshot": max(self._snapshots.keys()) if self._snapshots else 0,
        }

time_travel_engine = CausalTimeTravel()
__all__ = ["CausalTimeTravel", "HistoricalState", "AlternativeTimeline", "time_travel_engine"]
