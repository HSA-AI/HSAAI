"""
HSAAI Enterprise Precognition Engine — v0.6.0

The organism SEES THE FUTURE. Not through magic — through weak signal
detection, early indicator analysis, and pattern projection.

It detects faint signals that precede major events — the enterprise
equivalent of feeling a storm coming before clouds appear.

"I'm detecting early indicators that suggest a supply disruption in
the Red Sea shipping lane within 14-21 days. Probability: 67%.
Confidence: Medium. Recommend: pre-position 2 weeks of raw material."
"""
from __future__ import annotations
import logging, time, json, random, hashlib
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.precognition")

@dataclass
class WeakSignal:
    """A faint signal that may precede a major event."""
    signal_id: str = ""
    signal_type: str = ""  # economic, geopolitical, weather, market, operational, social
    description: str = ""
    strength: float = 0.0  # 0-1, how detectable
    lead_time_hours: int = 0  # how far ahead this signal precedes the event
    source: str = ""
    confidence: float = 0.0
    detected_at: float = 0.0

@dataclass
class Precognition:
    """A prediction of a future event with associated evidence."""
    precognition_id: str = ""
    predicted_event: str = ""
    event_type: str = ""  # disruption, opportunity, risk, shift, anomaly
    probability: float = 0.0
    time_window: str = ""  # "7-14 days", "1-3 months"
    lead_signals: list[WeakSignal] = field(default_factory=list)
    potential_impact: str = ""
    recommended_preparation: str = ""
    confidence: float = 0.0
    verification_status: str = "pending"  # pending, confirmed, falsified, expired
    created_at: float = 0.0

@dataclass
class PrecognitionVerification:
    """Tracks whether a precognition was accurate."""
    precognition_id: str = ""
    event_occurred: bool = False
    timing_accurate: bool = False
    impact_accurate: bool = False
    accuracy_score: float = 0.0
    verified_at: float = 0.0


class EnterprisePrecognitionEngine:
    """
    Predicts future enterprise events through weak signal detection.

    Sources of precognition:
      1. Weak economic signals (currency, commodity, rate changes)
      2. Geopolitical indicators (tensions, regulatory shifts)
      3. Weather/climate patterns (monsoon, drought, extreme events)
      4. Market micro-structure changes (order flow, sentiment shifts)
      5. Operational early warnings (quality drift, delay clusters)
      6. Social signals (employee sentiment, customer complaints)
      7. Dream Engine insights (subconscious pattern recognition)
    """
    def __init__(self):
        self._signals: list[WeakSignal] = []
        self._precognitions: list[Precognition] = []
        self._verifications: list[PrecognitionVerification] = []
        self._signal_counter = 0
        self._precog_counter = 0
        self._accuracy_history: list[float] = []

        # Known signal-event correlations (learned over time)
        self._signal_patterns = {
            "currency_volatility_increase": {
                "leads_to": "price_disruption",
                "lead_time_hours": 72,
                "probability_boost": 0.15,
            },
            "supplier_response_time_slowing": {
                "leads_to": "supply_disruption",
                "lead_time_hours": 168,
                "probability_boost": 0.25,
            },
            "customer_complaint_volume_rising": {
                "leads_to": "churn_event",
                "lead_time_hours": 336,
                "probability_boost": 0.20,
            },
            "regulatory_consultation_published": {
                "leads_to": "regulatory_change",
                "lead_time_hours": 720,
                "probability_boost": 0.30,
            },
            "competator_price_reduction": {
                "leads_to": "market_share_loss",
                "lead_time_hours": 48,
                "probability_boost": 0.18,
            },
            "weather_anomaly_detected": {
                "leads_to": "supply_chain_disruption",
                "lead_time_hours": 120,
                "probability_boost": 0.22,
            },
            "employee_sentiment_declining": {
                "leads_to": "talent_loss",
                "lead_time_hours": 504,
                "probability_boost": 0.15,
            },
            "quality_metrics_drifting": {
                "leads_to": "product_recall_risk",
                "lead_time_hours": 240,
                "probability_boost": 0.28,
            },
        }

    async def ingest_signal(self, signal_type: str, description: str,
                             strength: float, source: str = "monitor") -> WeakSignal:
        """Ingest a weak signal that may precede a future event."""
        self._signal_counter += 1
        sid = f"signal-{self._signal_counter:04d}"

        # Check if this signal type is a known precursor
        pattern = self._signal_patterns.get(signal_type, {})
        lead_time = pattern.get("lead_time_hours", 72)
        confidence = pattern.get("probability_boost", 0.1) * strength

        signal = WeakSignal(
            signal_id=sid, signal_type=signal_type,
            description=description, strength=strength,
            lead_time_hours=lead_time, source=source,
            confidence=confidence, detected_at=time.time(),
        )
        self._signals.append(signal)

        # If signal is strong enough, generate a precognition
        if strength > 0.4 and pattern:
            precog = await self._generate_precognition(signal, pattern)
            if precog:
                self._precognitions.append(precog)
                logger.warning("🔮 PRECOGNITION: %s (probability: %.0f%%, window: %s) — %s",
                              precog.predicted_event, precog.probability*100,
                              precog.time_window, precog.recommended_preparation[:80])

        return signal

    async def _generate_precognition(self, signal: WeakSignal, pattern: dict) -> Precognition:
        """Generate a precognition from a strong weak signal."""
        self._precog_counter += 1
        pid = f"precog-{self._precog_counter:04d}"

        leads_to = pattern["leads_to"]
        prob_boost = pattern["probability_boost"]
        lead_hours = pattern["lead_time_hours"]

        # Calculate probability
        base_prob = 0.3
        probability = min(0.95, base_prob + prob_boost * signal.strength)

        # Calculate time window
        if lead_hours < 72:
            window = f"{lead_hours//24}-{lead_hours//24+1} days"
        elif lead_hours < 168:
            window = f"{lead_hours//24}-{lead_hours//24+3} days"
        elif lead_hours < 720:
            window = f"{lead_hours//168}-{lead_hours//168+1} weeks"
        else:
            window = f"{lead_hours//720}-{lead_hours//720+1} months"

        # Generate recommendation
        recommendations = {
            "price_disruption": "Lock in forward contracts for 90 days. Hedge 60% of exposure.",
            "supply_disruption": f"Pre-position {lead_hours//24} days of raw material. Activate backup suppliers.",
            "churn_event": "Launch retention campaign for top 20 at-risk customers within 7 days.",
            "regulatory_change": "Begin compliance assessment. Engage legal team for impact analysis.",
            "market_share_loss": "Accelerate product differentiation. Review pricing strategy.",
            "supply_chain_disruption": "Reroute logistics. Increase safety stock by 30%.",
            "talent_loss": "Schedule retention conversations. Review compensation competitiveness.",
            "product_recall_risk": "Increase quality inspections. Review batch testing protocols.",
        }

        return Precognition(
            precognition_id=pid,
            predicted_event=leads_to.replace("_", " ").title(),
            event_type="risk" if "disruption" in leads_to or "loss" in leads_to else "opportunity",
            probability=probability,
            time_window=window,
            lead_signals=[signal],
            potential_impact=f"Potential {'negative' if probability > 0.5 else 'minor'} impact on operations.",
            recommended_preparation=recommendations.get(leads_to, "Monitor situation closely."),
            confidence=signal.confidence,
            created_at=time.time(),
        )

    async def scan_all_signals(self) -> list[Precognition]:
        """Scan all recent signals for emerging precognition patterns."""
        recent = [s for s in self._signals if time.time() - s.detected_at < 86400 * 7]
        # Check for signal clusters (multiple signals pointing to same event)
        signal_clusters = defaultdict(list)
        for s in recent:
            pattern = self._signal_patterns.get(s.signal_type)
            if pattern:
                signal_clusters[pattern["leads_to"]].append(s)

        new_precogs = []
        for event_type, signals in signal_clusters.items():
            if len(signals) >= 2:
                # Multiple signals → higher confidence
                combined_strength = min(1.0, sum(s.strength for s in signals) / len(signals) + 0.2)
                precog = await self._generate_precognition(
                    WeakSignal(signal_type="cluster", strength=combined_strength,
                              description=f"Cluster of {len(signals)} signals"),
                    self._signal_patterns.get(signals[0].signal_type, {"leads_to": event_type,
                                                                       "lead_time_hours": 72,
                                                                       "probability_boost": 0.3})
                )
                if precog:
                    precog.lead_signals = signals
                    precog.confidence = min(0.9, combined_strength + 0.15)
                    self._precognitions.append(precog)
                    new_precogs.append(precog)
                    logger.warning("🔮 CLUSTER PRECOGNITION: %d signals → %s (prob: %.0f%%)",
                                  len(signals), event_type, precog.probability*100)

        return new_precogs

    async def verify(self, precognition_id: str, event_occurred: bool,
                      timing_accurate: bool, impact_accurate: bool):
        """Verify whether a precognition was accurate."""
        verification = PrecognitionVerification(
            precognition_id=precognition_id,
            event_occurred=event_occurred,
            timing_accurate=timing_accurate,
            impact_accurate=impact_accurate,
            accuracy_score=sum([event_occurred, timing_accurate, impact_accurate]) / 3,
            verified_at=time.time(),
        )
        self._verifications.append(verification)
        self._accuracy_history.append(verification.accuracy_score)
        # Update precognition status
        for p in self._precognitions:
            if p.precognition_id == precognition_id:
                p.verification_status = "confirmed" if event_occurred else "falsified"
                break
        logger.info("🔮 VERIFICATION: %s → %s (accuracy: %.0f%%)",
                   precognition_id, "CONFIRMED" if event_occurred else "FALSIFIED",
                   verification.accuracy_score*100)

    def get_precognitions(self, status: str | None = None, limit: int = 20) -> list[dict]:
        precogs = self._precognitions
        if status:
            precogs = [p for p in precogs if p.verification_status == status]
        result = []
        for p in precogs[-limit:]:
            d = asdict(p)
            d["lead_signals"] = [asdict(s) for s in p.lead_signals]
            result.append(d)
        return result

    def stats(self) -> dict:
        avg_accuracy = sum(self._accuracy_history) / max(len(self._accuracy_history), 1)
        return {
            "signals_detected": len(self._signals),
            "precognitions_generated": len(self._precognitions),
            "precognitions_confirmed": sum(1 for p in self._precognitions if p.verification_status == "confirmed"),
            "precognitions_falsified": sum(1 for p in self._precognitions if p.verification_status == "falsified"),
            "prediction_accuracy": avg_accuracy,
            "known_patterns": len(self._signal_patterns),
        }

precognition_engine = EnterprisePrecognitionEngine()
__all__ = ["EnterprisePrecognitionEngine", "Precognition", "WeakSignal", "PrecognitionVerification", "precognition_engine"]
