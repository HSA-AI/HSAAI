"""
HSAAI Temporal Intelligence — v0.6.0

The organism understands TIME as a dimension of intelligence. It sees
the past (memory), present (consciousness), and future (precognition)
simultaneously — and understands how they connect.

Past → Present → Future is not a line — it's a FIELD.
"""
from __future__ import annotations
import logging, time, json
from dataclasses import dataclass, field, asdict
from typing import Any
logger = logging.getLogger("hsaai.temporal")

@dataclass
class TemporalField:
    """A temporal field — past/present/future seen as one."""
    entity: str = ""
    past_pattern: str = ""  # what happened before
    present_state: str = ""  # what's happening now
    future_projection: str = ""  # what will likely happen
    temporal_resonance: float = 0.0  # how strongly past→present→future connect
    cycle_detected: bool = False  # is this a repeating pattern?
    cycle_period: str = ""  # if cyclic, what's the period?
    insight: str = ""  # what the temporal view reveals

class TemporalIntelligenceEngine:
    """Understands time as a connected field, not a linear sequence."""
    def __init__(self):
        self._fields: list[TemporalField] = []
        self._cycle_patterns: dict[str, list[float]] = {}  # pattern → timestamps

    async def construct_field(self, entity: str, past_events: list[dict],
                               present_signals: list[dict],
                               future_predictions: list[dict]) -> TemporalField:
        """Construct a temporal field for an entity."""
        # Analyze past patterns
        past_pattern = "stable" if len(past_events) < 5 else "cyclic" if self._detect_cycle(past_events) else "trending"
        present_state = "normal" if not present_signals else "alerting" if any(s.get("severity") == "critical" for s in present_signals) else "monitoring"
        future_projection = "continuation" if past_pattern == "stable" else "disruption_likely" if present_state == "alerting" else "shift_imminent"

        # Check for cycles
        cycle = past_pattern == "cyclic"
        cycle_period = ""
        if cycle:
            timestamps = [e.get("timestamp", 0) for e in past_events if e.get("timestamp")]
            if len(timestamps) > 3:
                intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
                avg_interval = sum(intervals) / len(intervals)
                cycle_period = f"~{avg_interval/86400:.0f} days"

        # Generate temporal insight
        insight = ""
        if cycle and present_state == "alerting":
            insight = f"Temporal cycle detected ({cycle_period}). Current alert aligns with historical cycle peak. Expect resolution within 1 cycle period."
        elif past_pattern == "trending" and future_projection == "disruption_likely":
            insight = f"Trend analysis shows deterioration. Past trajectory + present signals indicate disruption within 2-4 weeks."
        elif past_pattern == "stable" and present_state == "normal":
            insight = "Temporally stable. Past, present, and projected future are consistent. No action needed."
        else:
            insight = f"Temporal mismatch: past={past_pattern}, present={present_state}, future={future_projection}. Investigate divergence."

        field_obj = TemporalField(
            entity=entity, past_pattern=past_pattern,
            present_state=present_state, future_projection=future_projection,
            temporal_resonance=0.7 if cycle else 0.5,
            cycle_detected=cycle, cycle_period=cycle_period,
            insight=insight,
        )
        self._fields.append(field_obj)
        logger.info("⏳ TEMPORAL FIELD for '%s': %s → %s → %s (insight: %s)",
                   entity, past_pattern, present_state, future_projection, insight[:80])
        return field_obj

    def _detect_cycle(self, events: list[dict]) -> bool:
        """Detect if events follow a cyclic pattern."""
        if len(events) < 5:
            return False
        timestamps = sorted([e.get("timestamp", 0) for e in events if e.get("timestamp")])
        if len(timestamps) < 5:
            return False
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        if not intervals:
            return False
        avg = sum(intervals) / len(intervals)
        if avg == 0:
            return False
        variance = sum((i - avg) ** 2 for i in intervals) / len(intervals)
        cv = (variance ** 0.5) / avg  # coefficient of variation
        return cv < 0.3  # low variance → cyclic

    def get_fields(self, limit: int = 20) -> list[dict]:
        return [asdict(f) for f in self._fields[-limit:]]
    def stats(self) -> dict:
        return {"temporal_fields": len(self._fields),
                "cycles_detected": sum(1 for f in self._fields if f.cycle_detected)}

temporal_engine = TemporalIntelligenceEngine()
__all__ = ["TemporalIntelligenceEngine", "TemporalField", "temporal_engine"]
