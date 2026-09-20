"""
HSAAI Proactive Intelligence — v0.2.0

The cognitive organism doesn't wait for questions — it proactively
discovers anomalies, opportunities, and risks.
"""
from __future__ import annotations
import logging, time, asyncio
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.proactive")

@dataclass
class ProactiveAlert:
    alert_id: str = ""
    alert_type: str = ""  # anomaly, opportunity, risk
    title: str = ""
    description: str = ""
    severity: str = "info"
    confidence: float = 0.0
    recommended_action: str = ""
    expected_impact: str = ""
    created_at: float = 0.0
    stakeholders: list[str] = field(default_factory=list)

class ProactiveIntelligenceEngine:
    """Discovers anomalies, opportunities, and risks before humans ask."""
    def __init__(self):
        self._alerts: list[ProactiveAlert] = []
        self._alert_counter = 0

    async def detect_anomalies(self, metrics: dict) -> list[ProactiveAlert]:
        """Detect anomalous patterns in enterprise metrics."""
        alerts = []
        for metric_name, values in metrics.items():
            if not values or len(values) < 5:
                continue
            recent = values[-5:]
            historical_avg = sum(values[:-5]) / max(len(values) - 5, 1)
            recent_avg = sum(recent) / len(recent)
            if historical_avg > 0:
                deviation = abs(recent_avg - historical_avg) / historical_avg
                if deviation > 0.3:
                    self._alert_counter += 1
                    alert = ProactiveAlert(
                        alert_id=f"alert-{self._alert_counter:04d}",
                        alert_type="anomaly",
                        title=f"Anomalous {metric_name} detected",
                        description=f"{metric_name} deviated {deviation*100:.0f}% from historical average.",
                        severity="warning" if deviation < 0.5 else "critical",
                        confidence=min(0.9, deviation),
                        recommended_action=f"Investigate root cause of {metric_name} anomaly.",
                        expected_impact=f"Potential {'positive' if recent_avg > historical_avg else 'negative'} impact.",
                        created_at=time.time(),
                    )
                    alerts.append(alert)
                    self._alerts.append(alert)
                    logger.info("ANOMALY DETECTED: %s (%.0f%% deviation)", metric_name, deviation*100)
        return alerts

    async def discover_opportunities(self, data: dict) -> list[ProactiveAlert]:
        """Discover opportunities humans haven't asked about."""
        opportunities = []
        if data.get("supplier_price_drop"):
            self._alert_counter += 1
            opp = ProactiveAlert(
                alert_id=f"alert-{self._alert_counter:04d}",
                alert_type="opportunity",
                title="Supplier price drop detected",
                description=f"Supplier {data['supplier_price_drop'].get('supplier', '')} "
                           f"reduced prices by {data['supplier_price_drop'].get('reduction', 0)*100:.0f}%.",
                severity="info",
                confidence=0.8,
                recommended_action="Consider forward contract or volume increase.",
                expected_impact=f"Potential savings: ${data['supplier_price_drop'].get('potential_savings', 0):,.0f}",
                created_at=time.time(),
                stakeholders=["procurement", "finance"],
            )
            opportunities.append(opp)
            self._alerts.append(opp)
        return opportunities

    async def predict_risks(self, indicators: dict) -> list[ProactiveAlert]:
        """Predict risks before they materialize."""
        risks = []
        if indicators.get("supplier_delay_count", 0) >= 3:
            self._alert_counter += 1
            risk = ProactiveAlert(
                alert_id=f"alert-{self._alert_counter:04d}",
                alert_type="risk",
                title="Supplier reliability degrading",
                description=f"Supplier has delayed {indicators['supplier_delay_count']} times in 30 days.",
                severity="warning",
                confidence=0.75,
                recommended_action="Activate backup supplier and review contract terms.",
                expected_impact=f"Production disruption risk: {indicators.get('disruption_probability', 0.2)*100:.0f}%",
                created_at=time.time(),
                stakeholders=["procurement", "operations"],
            )
            risks.append(risk)
            self._alerts.append(risk)
        return risks

    def list_alerts(self, alert_type: str | None = None, limit: int = 50) -> list[ProactiveAlert]:
        alerts = self._alerts
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)[:limit]

proactive_engine = ProactiveIntelligenceEngine()
__all__ = ["ProactiveIntelligenceEngine", "ProactiveAlert", "proactive_engine"]
