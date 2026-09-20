"""HSAAI Agent Civilization — v0.2.0

Upgrades multi_agents from isolated agents to a civilized agent society.
12 enterprise agents with identity, purpose, skills, memory, authority,
relationships, and evolution. Managed by Chief Intelligence Supervisor.
"""
from __future__ import annotations
import asyncio, logging, time
from dataclasses import dataclass, field, asdict
from typing import Any
logger = logging.getLogger("hsaai.agent_civilization")

@dataclass
class AgentIdentity:
    agent_id: str
    name: str
    purpose: str
    department: str
    skills: list[str] = field(default_factory=list)
    authority_level: str = "standard"  # standard, elevated, restricted
    version: str = "0.2.0"
    created_at: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    evolution_stage: str = "stable"  # learning, stable, expert

@dataclass
class CivilizationTask:
    task_id: str
    description: str
    assigned_agents: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, failed
    results: list[dict] = field(default_factory=list)
    created_at: float = 0.0

# 12 Enterprise Agents
AGENT_REGISTRY: dict[str, AgentIdentity] = {
    "hr_agent": AgentIdentity(
        agent_id="hr_agent", name="HR Agent", department="HR",
        purpose="Manage employee relations, policies, and workforce analytics",
        skills=["policy_lookup", "employee_search", "leave_calc", "payroll_query", "workforce_analytics"],
    ),
    "finance_agent": AgentIdentity(
        agent_id="finance_agent", name="Finance Agent", department="Finance",
        purpose="Financial intelligence, budget management, and cost optimization",
        skills=["budget_check", "invoice_lookup", "cost_analysis", "payment_status", "financial_forecast"],
        authority_level="elevated",
    ),
    "procurement_agent": AgentIdentity(
        agent_id="procurement_agent", name="Procurement Agent", department="Procurement",
        purpose="Supplier management, contract analysis, and sourcing strategy",
        skills=["supplier_search", "contract_review", "po_create", "rfq_generate", "supplier_risk_assess"],
    ),
    "operations_agent": AgentIdentity(
        agent_id="operations_agent", name="Operations Agent", department="Operations",
        purpose="Production monitoring, quality control, and capacity planning",
        skills=["production_status", "inventory_check", "quality_query", "maintenance_schedule", "capacity_plan"],
    ),
    "legal_agent": AgentIdentity(
        agent_id="legal_agent", name="Legal Agent", department="Legal",
        purpose="Contract analysis, compliance checking, and risk assessment",
        skills=["contract_analyze", "compliance_check", "risk_assess", "clause_extract", "litigation_track"],
        authority_level="elevated",
    ),
    "executive_agent": AgentIdentity(
        agent_id="executive_agent", name="Executive Agent", department="Office of CEO",
        purpose="Strategic decision support and executive intelligence",
        skills=["kpi_dashboard", "strategic_query", "market_brief", "decision_support", "board_prep"],
        authority_level="elevated",
    ),
    "it_agent": AgentIdentity(
        agent_id="it_agent", name="IT Agent", department="IT",
        purpose="System health, access management, and incident response",
        skills=["ticket_create", "asset_query", "access_request", "incident_report", "system_health"],
    ),
    "sales_agent": AgentIdentity(
        agent_id="sales_agent", name="Sales Agent", department="Sales",
        purpose="Customer intelligence, pipeline management, and revenue forecasting",
        skills=["customer_lookup", "pipeline_query", "forecast_generate", "opportunity_score", "churn_predict"],
    ),
    "document_agent": AgentIdentity(
        agent_id="document_agent", name="Document Agent", department="Knowledge",
        purpose="Document intelligence, knowledge extraction, and semantic search",
        skills=["doc_search", "summarize", "extract_entities", "classify", "knowledge_graph_update"],
    ),
    "governance_agent": AgentIdentity(
        agent_id="governance_agent", name="Governance Agent", department="Audit",
        purpose="Policy enforcement, audit, and compliance monitoring",
        skills=["policy_enforce", "audit_query", "risk_score", "compliance_report", "constitutional_check"],
        authority_level="elevated",
    ),
    "research_agent": AgentIdentity(
        agent_id="research_agent", name="Research Agent", department="R&D",
        purpose="Market research, technology scanning, and innovation ideation",
        skills=["trend_analysis", "market_research", "technology_scan", "innovation_ideate", "competitive_intel"],
    ),
    "crisis_agent": AgentIdentity(
        agent_id="crisis_agent", name="Crisis Agent", department="Emergency",
        purpose="Incident response, escalation management, and recovery planning",
        skills=["incident_response", "escalation", "communication_draft", "recovery_plan", "impact_assess"],
        authority_level="elevated",
    ),
}

class ChiefIntelligenceSupervisor:
    """Manages the Agent Civilization — decomposes tasks, selects agents,
    orchestrates execution, resolves conflicts, synthesizes results."""

    async def decompose(self, task: str) -> list[dict]:
        """Decompose a complex task into subtasks for different agents."""
        subtasks = []
        task_lower = task.lower()
        if any(w in task_lower for w in ["budget", "cost", "financial", "revenue", "margin"]):
            subtasks.append({"agent": "finance_agent", "subtask": f"Analyze financial aspects: {task}"})
        if any(w in task_lower for w in ["supplier", "procurement", "contract", "purchase"]):
            subtasks.append({"agent": "procurement_agent", "subtask": f"Analyze procurement aspects: {task}"})
        if any(w in task_lower for w in ["employee", "staff", "hr", "payroll", "leave"]):
            subtasks.append({"agent": "hr_agent", "subtask": f"Analyze HR aspects: {task}"})
        if any(w in task_lower for w in ["legal", "compliance", "regulatory", "contract"]):
            subtasks.append({"agent": "legal_agent", "subtask": f"Analyze legal aspects: {task}"})
        if any(w in task_lower for w in ["risk", "exposure", "concentration"]):
            subtasks.append({"agent": "governance_agent", "subtask": f"Assess risk: {task}"})
        if any(w in task_lower for w in ["market", "competitor", "customer", "trend"]):
            subtasks.append({"agent": "research_agent", "subtask": f"Research market aspects: {task}"})
        if any(w in task_lower for w in ["production", "inventory", "quality", "capacity"]):
            subtasks.append({"agent": "operations_agent", "subtask": f"Analyze operations: {task}"})
        if not subtasks:
            subtasks.append({"agent": "executive_agent", "subtask": task})
        return subtasks

    async def select_agents(self, subtasks: list[dict]) -> list[dict]:
        """Select the best agent for each subtask."""
        selected = []
        for st in subtasks:
            agent_id = st["agent"]
            if agent_id in AGENT_REGISTRY:
                selected.append({**st, "agent_identity": AGENT_REGISTRY[agent_id]})
        return selected

    async def resolve_conflicts(self, results: list[dict]) -> list[dict]:
        """Resolve conflicts between agent results."""
        if len(results) <= 1:
            return results
        # Simple conflict detection: if agents disagree on recommendation
        recommendations = [r.get("recommendation", "") for r in results]
        if len(set(recommendations)) > 1:
            logger.info("Conflict detected between %d agents — applying majority vote", len(results))
            # Majority vote
            from collections import Counter
            most_common = Counter(recommendations).most_common(1)
            if most_common and most_common[0][1] > 1:
                winner = most_common[0][0]
                for r in results:
                    r["conflict_resolved"] = r.get("recommendation") == winner
        return results

    async def synthesize(self, results: list[dict]) -> dict:
        """Synthesize multiple agent results into a unified intelligence package."""
        if not results:
            return {"synthesis": "No results to synthesize.", "confidence": 0.0}
        synthesis_parts = []
        total_confidence = 0
        for r in results:
            agent_name = r.get("agent", "unknown")
            answer = r.get("answer", r.get("result", ""))
            confidence = r.get("confidence", 0.5)
            synthesis_parts.append(f"[{agent_name}] (confidence: {confidence:.0%}): {answer}")
            total_confidence += confidence
        avg_confidence = total_confidence / len(results)
        return {
            "synthesis": "\n\n".join(synthesis_parts),
            "confidence": avg_confidence,
            "agents_contributed": len(results),
            "agent_names": [r.get("agent", "unknown") for r in results],
        }

supervisor = ChiefIntelligenceSupervisor()
__all__ = ["AgentIdentity", "CivilizationTask", "AGENT_REGISTRY", "ChiefIntelligenceSupervisor", "supervisor"]
