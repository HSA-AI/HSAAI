"""
HSAAI Enterprise Digital Twin — v0.2.0

A living simulation of the enterprise. Allows "What happens if?" questions
before any real decision is made.
"""
from __future__ import annotations
import logging, time, random, asyncio
from dataclasses import dataclass, field, asdict
from typing import Any
logger = logging.getLogger("hsaai.twin")

@dataclass
class SimulationResult:
    scenario: str = ""
    success_probability: float = 0.0
    p10_outcome: float = 0.0
    p50_outcome: float = 0.0
    p90_outcome: float = 0.0
    iterations: int = 0
    critical_risks: list[str] = field(default_factory=list)
    recommendation: str = ""
    computation_time_ms: int = 0

class EnterpriseDigitalTwin:
    """Simulates the enterprise across 3 time dimensions: current, historical, future."""
    def __init__(self):
        self._snapshots: dict[str, dict] = {}
        self._simulation_count = 0

    async def snapshot(self, label: str = "current") -> dict:
        """Take a snapshot of enterprise state."""
        snap = {"label": label, "timestamp": time.time(), "entities": {}, "metrics": {}}
        self._snapshots[label] = snap
        return snap

    async def simulate(self, scenario: str, variables: dict | None = None,
                       horizon_months: int = 12, iterations: int = 1000) -> SimulationResult:
        """Monte Carlo simulation of a scenario."""
        start = time.time()
        self._simulation_count += 1
        variables = variables or {}
        results = []
        for _ in range(iterations):
            # Simple Monte Carlo: random walk with drift
            base = variables.get("base_value", 1000000)
            drift = variables.get("annual_drift", 0.05) / 12
            volatility = variables.get("volatility", 0.15) / (12 ** 0.5)
            value = base
            for month in range(horizon_months):
                shock = random.gauss(0, volatility)
                value *= (1 + drift + shock)
            results.append(value)
        results.sort()
        n = len(results)
        p10 = results[int(n * 0.1)]
        p50 = results[int(n * 0.5)]
        p90 = results[int(n * 0.9)]
        success_prob = sum(1 for r in results if r > 0) / n
        risks = []
        if variables.get("currency_risk"):
            risks.append(f"Currency devaluation ({variables['currency_risk']*100:.0f}%)")
        if variables.get("regulatory_risk"):
            risks.append(f"Regulatory delay ({variables['regulatory_risk']*100:.0f}%)")
        latency = int((time.time() - start) * 1000)
        recommendation = ""
        if success_prob > 0.7 and p50 > 0:
            recommendation = f"Proceed with scenario. Expected outcome: {p50:,.0f}."
        elif success_prob > 0.5:
            recommendation = f"Proceed with caution. P10 downside: {p10:,.0f}."
        else:
            recommendation = f"Do not proceed without mitigation. Success probability too low."
        return SimulationResult(
            scenario=scenario, success_probability=success_prob,
            p10_outcome=p10, p50_outcome=p50, p90_outcome=p90,
            iterations=iterations, critical_risks=risks,
            recommendation=recommendation, computation_time_ms=latency,
        )

    def list_snapshots(self) -> list[str]:
        return list(self._snapshots.keys())

digital_twin = EnterpriseDigitalTwin()
__all__ = ["EnterpriseDigitalTwin", "SimulationResult", "digital_twin"]
