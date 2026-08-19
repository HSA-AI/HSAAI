"""
HSAAI Governance common package.

Public API:
    - risk_engine: AI action risk scoring (0-100, low/medium/high/critical)
    - policy_engine: Policy-as-code (YAML, deny-by-default, versioned)
    - explainability: Decision audit + XAI + lineage

These modules are importable from any service via:
    from packages.common.governance.risk_engine import RiskEngine, RiskContext
    from packages.common.governance.policy_engine import PolicyEngine, Request
    from packages.common.governance.explainability import ExplainabilityEngine, DecisionRecord
"""
from packages.common.governance.risk_engine import (
    RiskEngine, RiskContext, RiskResult, RiskLevel, risk_level_for_score,
)
from packages.common.governance.policy_engine import (
    PolicyEngine, Policy, PolicyDecision, Request, Effect,
)
from packages.common.governance.explainability import (
    ExplainabilityEngine, DecisionRecord, LineageGraph,
)

__all__ = [
    "RiskEngine", "RiskContext", "RiskResult", "RiskLevel", "risk_level_for_score",
    "PolicyEngine", "Policy", "PolicyDecision", "Request", "Effect",
    "ExplainabilityEngine", "DecisionRecord", "LineageGraph",
]
