"""
HSAAI Intelligence Economy Engine — v0.2.0

Measures the value of intelligence as a financial asset.
6 dimensions: Knowledge, Decision, Agent, Automation, Prediction, Learning value.
"""
from __future__ import annotations
import logging, time
from dataclasses import dataclass, field, asdict
from typing import Any
logger = logging.getLogger("hsaai.economy")

@dataclass
class IntelligenceBalanceSheet:
    period: str = ""
    knowledge_assets_value: float = 0.0
    decision_assets_value: float = 0.0
    agent_assets_value: float = 0.0
    prediction_assets_value: float = 0.0
    automation_assets_value: float = 0.0
    learning_assets_value: float = 0.0
    total_costs: float = 0.0
    roi: float = 0.0
    generated_at: float = 0.0

    @property
    def total_assets(self) -> float:
        return (self.knowledge_assets_value + self.decision_assets_value +
                self.agent_assets_value + self.prediction_assets_value +
                self.automation_assets_value + self.learning_assets_value)

    @property
    def net_value(self) -> float:
        return self.total_assets - self.total_costs

class IntelligenceEconomyEngine:
    """Measures intelligence as a financial asset."""
    def __init__(self):
        self._decision_count = 0
        self._hours_saved = 0
        self._loss_avoided = 0.0
        self._opportunities_captured = 0.0

    def record_decision(self, outcome_value: float = 0.0):
        self._decision_count += 1
        if outcome_value > 0:
            self._opportunities_captured += outcome_value

    def record_automation(self, hours_saved: int, hourly_rate: float = 50.0):
        self._hours_saved += hours_saved
        self._opportunities_captured += hours_saved * hourly_rate

    def record_loss_avoided(self, amount: float):
        self._loss_avoided += amount

    def generate_balance_sheet(self, period: str = "monthly",
                               costs: float = 195000.0) -> IntelligenceBalanceSheet:
        knowledge_value = self._loss_avoided * 0.3 + 500000  # wisdom crystals + failure memory
        decision_value = self._decision_count * 350  # avg value per decision
        agent_value = self._hours_saved * 50  # labor equivalent
        prediction_value = self._loss_avoided * 0.7
        automation_value = self._hours_saved * 35  # efficiency gain
        learning_value = self._decision_count * 20  # compound learning
        total_assets = (knowledge_value + decision_value + agent_value +
                       prediction_value + automation_value + learning_value)
        roi = (total_assets - costs) / costs if costs > 0 else 0
        return IntelligenceBalanceSheet(
            period=period,
            knowledge_assets_value=knowledge_value,
            decision_assets_value=decision_value,
            agent_assets_value=agent_value,
            prediction_assets_value=prediction_value,
            automation_assets_value=automation_value,
            learning_assets_value=learning_value,
            total_costs=costs,
            roi=roi,
            generated_at=time.time(),
        )

intelligence_economy = IntelligenceEconomyEngine()
__all__ = ["IntelligenceEconomyEngine", "IntelligenceBalanceSheet", "intelligence_economy"]
