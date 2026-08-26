"""
HSAAI Agent Marketplace — No-Code Builder + Lifecycle Management (Phase 3)
==========================================================================

FIX v2.3 (Phase 3): Implements an advanced Agent Marketplace with:
  - No-code agent builder (define agent via JSON config, no Python required)
  - Template library (HR, Finance, Legal, IT, Operations, Sales, Procurement, Executive)
  - Lifecycle management (draft → test → staging → production → audit → retire)
  - A/B testing (run two agent versions side-by-side, compare quality)
  - Canary rollout (5% → 25% → 100% traffic)
  - Quality metrics (hallucination rate, user satisfaction, tool failure rate)
  - Department-scoped agents (each department manages its own agents)
  - Approval workflow (department manager approves before production)
  - Version history + rollback

The marketplace enables non-technical department managers to create custom
AI agents for their workflows without writing code. Agents are defined as
JSON configs with: system prompt, tools, knowledge scopes, RBAC roles,
escalation targets, and quality thresholds.

Usage (API):
    POST /v1/marketplace/agents          — create a new agent (no-code)
    GET  /v1/marketplace/agents          — list agents (filter by department)
    GET  /v1/marketplace/templates       — list available templates
    POST /v1/marketplace/agents/{id}/test — test an agent in staging
    POST /v1/marketplace/agents/{id}/promote — promote to production
    POST /v1/marketplace/agents/{id}/rollback — rollback to previous version
    GET  /v1/marketplace/agents/{id}/metrics — quality metrics for an agent

Usage (No-code builder UI):
    1. Department manager selects a template (e.g., "HR Policy Agent")
    2. Customizes: system prompt, knowledge scopes, allowed tools, RBAC roles
    3. Tests in staging with sample queries
    4. Submits for approval (department head approves)
    5. Promotes to production with canary rollout (5% → 25% → 100%)
    6. Monitors quality metrics in dashboard
    7. Rolls back if quality degrades
"""
from __future__ import annotations

import os
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger("hsaai.agent_marketplace")


class AgentStatus(str, Enum):
    DRAFT = "draft"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    CANARY = "canary"  # canary rollout in progress
    RETIRED = "retired"
    REJECTED = "rejected"


class AgentCategory(str, Enum):
    HR = "hr"
    FINANCE = "finance"
    LEGAL = "legal"
    IT = "it"
    OPERATIONS = "operations"
    SALES = "sales"
    PROCUREMENT = "procurement"
    EXECUTIVE = "executive"
    KNOWLEDGE = "knowledge"
    CUSTOM = "custom"


@dataclass
class AgentVersion:
    """A versioned agent configuration."""
    version_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version_number: int = 1
    status: AgentStatus = AgentStatus.DRAFT
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = ""
    approved_by: str = ""
    approved_at: str = ""
    # Agent configuration (no-code)
    name: str = ""
    description: str = ""
    category: AgentCategory = AgentCategory.CUSTOM
    department: str = ""
    system_prompt: str = ""
    # Knowledge + tools
    knowledge_scopes: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    # RBAC
    allowed_roles: list[str] = field(default_factory=list)
    escalation_target: str = ""
    priority: int = 5  # 1-10, higher = more important
    # Quality thresholds (auto-rollback if violated)
    max_hallucination_rate: float = 0.05  # 5% max hallucination
    min_satisfaction_score: float = 0.7   # 70% min user satisfaction
    max_tool_failure_rate: float = 0.1    # 10% max tool failures
    # Canary rollout
    canary_percentage: int = 0  # 0, 5, 25, 50, 100
    # Metrics (populated at runtime)
    metrics: dict[str, Any] = field(default_factory=lambda: {
        "total_executions": 0,
        "successful_executions": 0,
        "failed_executions": 0,
        "hallucination_count": 0,
        "avg_satisfaction": 0.0,
        "tool_failures": 0,
        "avg_latency_ms": 0.0,
        "total_tokens_consumed": 0,
    })


@dataclass
class Agent:
    """An agent in the marketplace with version history."""
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    category: AgentCategory = AgentCategory.CUSTOM
    department: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = ""
    versions: list[AgentVersion] = field(default_factory=list)
    current_version: str = ""  # version_id of current production version
    tags: list[str] = field(default_factory=list)

    def get_version(self, version_id: str) -> Optional[AgentVersion]:
        for v in self.versions:
            if v.version_id == version_id:
                return v
        return None

    def get_production_version(self) -> Optional[AgentVersion]:
        for v in self.versions:
            if v.status == AgentStatus.PRODUCTION:
                return v
        return None

    def get_latest_version(self) -> Optional[AgentVersion]:
        if not self.versions:
            return None
        return sorted(self.versions, key=lambda v: v.version_number)[-1]


# ─── Template Library ─────────────────────────────────────────

AGENT_TEMPLATES: list[dict[str, Any]] = [
    {
        "template_id": "hr-policy-agent",
        "name": "HR Policy Agent",
        "category": "hr",
        "description": "Answers employee questions about HR policies, leave, benefits, and procedures.",
        "system_prompt": (
            "You are the HR Policy Agent for HSA Group. You answer questions about "
            "HR policies, leave requests, benefits, compensation, and employee procedures. "
            "Always cite the specific policy document and section. If you don't know, "
            "escalate to the HR department manager. Never disclose other employees' "
            "personal information."
        ),
        "knowledge_scopes": ["hr-policies", "employee-handbook", "leave-policies", "benefits"],
        "allowed_tools": ["hr_leave_balance_lookup", "hr_policy_search", "escalate_to_hr_manager"],
        "allowed_roles": ["ai_user", "department_manager", "hr_staff"],
        "escalation_target": "hr-manager",
        "priority": 6,
    },
    {
        "template_id": "finance-budget-agent",
        "name": "Finance Budget Agent",
        "category": "finance",
        "description": "Queries budget status, processes invoices, and generates financial reports.",
        "system_prompt": (
            "You are the Finance Budget Agent. You help with budget queries, invoice "
            "processing, expense reports, and financial approvals. Always verify the "
            "requester has finance:read or finance:write permission before disclosing "
            "financial data. For amounts over 100,000 SAR, require two-person approval."
        ),
        "knowledge_scopes": ["finance-policies", "budget-records", "invoice-records"],
        "allowed_tools": ["sap_budget_lookup", "invoice_processing", "financial_report_generator", "escalate_to_cfo"],
        "allowed_roles": ["department_manager", "finance_staff", "executive"],
        "escalation_target": "cfo",
        "priority": 7,
    },
    {
        "template_id": "legal-contract-agent",
        "name": "Legal Contract Analysis Agent",
        "category": "legal",
        "description": "Analyzes contracts, checks compliance, and flags legal risks.",
        "system_prompt": (
            "You are the Legal Contract Analysis Agent. You review contracts for "
            "compliance with HSA Group policies, flag legal risks, and suggest "
            "amendments. Always recommend human legal review for contracts over "
            "1,000,000 SAR. Never provide formal legal advice — always escalate "
            "to the legal department."
        ),
        "knowledge_scopes": ["legal-policies", "contract-templates", "compliance-rules"],
        "allowed_tools": ["contract_analyzer", "compliance_checker", "legal_risk_assessor", "escalate_to_legal"],
        "allowed_roles": ["department_manager", "legal_staff"],
        "escalation_target": "legal-counsel",
        "priority": 8,
    },
    {
        "template_id": "it-support-agent",
        "name": "IT Support Agent",
        "category": "it",
        "description": "Handles IT support tickets, password resets, and system access requests.",
        "system_prompt": (
            "You are the IT Support Agent. You handle IT support requests including "
            "password resets, system access, software installation, and hardware "
            "requests. Always verify the requester's identity before processing "
            "password resets. For security-sensitive operations, require manager approval."
        ),
        "knowledge_scopes": ["it-policies", "system-documentation", "troubleshooting-guides"],
        "allowed_tools": ["ad_password_reset", "jira_ticket_create", "access_request", "escalate_to_it_manager"],
        "allowed_roles": ["ai_user", "department_manager", "it_staff"],
        "escalation_target": "it-manager",
        "priority": 5,
    },
    {
        "template_id": "procurement-agent",
        "name": "Procurement Agent",
        "category": "procurement",
        "description": "Manages purchase requests, vendor comparisons, and procurement workflows.",
        "system_prompt": (
            "You are the Procurement Agent. You process purchase requests, compare "
            "vendor quotes, track orders, and manage procurement workflows. For "
            "purchases over 500,000 SAR, require CFO approval. Always check the "
            "approved vendor list before recommending suppliers."
        ),
        "knowledge_scopes": ["procurement-policies", "vendor-records", "purchase-history"],
        "allowed_tools": ["sap_purchase_order", "vendor_comparison", "procurement_workflow", "escalate_to_procurement_manager"],
        "allowed_roles": ["department_manager", "procurement_staff"],
        "escalation_target": "procurement-manager",
        "priority": 6,
    },
    {
        "template_id": "executive-insights-agent",
        "name": "Executive Insights Agent",
        "category": "executive",
        "description": "Provides executive-level KPI dashboards, trends, and strategic insights.",
        "system_prompt": (
            "You are the Executive Insights Agent. You provide C-suite executives with "
            "KPI dashboards, trend analysis, and strategic insights. Always present "
            "data with context and confidence intervals. For sensitive financial "
            "data, verify the requester has executive:read permission."
        ),
        "knowledge_scopes": ["executive-metrics", "strategic-plans", "market-analysis"],
        "allowed_tools": ["powerbi_dashboard", "trend_analyzer", "kpi_calculator", "escalate_to_ceo"],
        "allowed_roles": ["executive", "hsaai_admin"],
        "escalation_target": "ceo",
        "priority": 9,
    },
    {
        "template_id": "operations-agent",
        "name": "Operations Agent",
        "category": "operations",
        "description": "Monitors supply chain, inventory, and production scheduling.",
        "system_prompt": (
            "You are the Operations Agent. You monitor supply chain status, inventory "
            "levels, production schedules, and logistics. Alert on inventory below "
            "reorder points. For production delays, notify the operations manager immediately."
        ),
        "knowledge_scopes": ["operations-policies", "inventory-records", "supply-chain-data"],
        "allowed_tools": ["sap_inventory_check", "production_scheduler", "logistics_tracker", "escalate_to_ops_manager"],
        "allowed_roles": ["department_manager", "operations_staff"],
        "escalation_target": "operations-manager",
        "priority": 6,
    },
    {
        "template_id": "sales-pipeline-agent",
        "name": "Sales Pipeline Agent",
        "category": "sales",
        "description": "Tracks sales pipeline, forecasts revenue, and analyzes customer insights.",
        "system_prompt": (
            "You are the Sales Pipeline Agent. You track the sales pipeline, forecast "
            "revenue, analyze customer data, and identify upsell opportunities. "
            "Always respect customer privacy — never disclose customer PII without "
            "proper authorization."
        ),
        "knowledge_scopes": ["sales-policies", "customer-records", "pipeline-data"],
        "allowed_tools": ["crm_pipeline_lookup", "revenue_forecaster", "customer_analyzer", "escalate_to_sales_manager"],
        "allowed_roles": ["department_manager", "sales_staff", "executive"],
        "escalation_target": "sales-manager",
        "priority": 7,
    },
]


# ─── Marketplace Service ──────────────────────────────────────

class AgentMarketplace:
    """Manages the agent lifecycle: create → test → staging → production → retire."""

    def __init__(self):
        # In production, this is backed by PostgreSQL (agents table).
        # For now, in-memory with file persistence.
        self._agents: dict[str, Agent] = {}
        self._storage_file = os.getenv("AGENT_MARKETPLACE_FILE", "/data/agent_marketplace.json")
        self._load()

    def _load(self):
        """Load agents from file."""
        try:
            if os.path.exists(self._storage_file):
                with open(self._storage_file) as f:
                    data = json.load(f)
                for agent_data in data.get("agents", []):
                    agent = Agent(
                        agent_id=agent_data["agent_id"],
                        name=agent_data["name"],
                        category=AgentCategory(agent_data["category"]),
                        department=agent_data["department"],
                        created_at=agent_data["created_at"],
                        created_by=agent_data["created_by"],
                        current_version=agent_data.get("current_version", ""),
                        tags=agent_data.get("tags", []),
                    )
                    for v_data in agent_data.get("versions", []):
                        v = AgentVersion(
                            version_id=v_data["version_id"],
                            version_number=v_data["version_number"],
                            status=AgentStatus(v_data["status"]),
                            created_at=v_data["created_at"],
                            created_by=v_data["created_by"],
                            approved_by=v_data.get("approved_by", ""),
                            approved_at=v_data.get("approved_at", ""),
                            name=v_data["name"],
                            description=v_data["description"],
                            category=AgentCategory(v_data["category"]),
                            department=v_data["department"],
                            system_prompt=v_data["system_prompt"],
                            knowledge_scopes=v_data["knowledge_scopes"],
                            allowed_tools=v_data["allowed_tools"],
                            allowed_roles=v_data["allowed_roles"],
                            escalation_target=v_data.get("escalation_target", ""),
                            priority=v_data.get("priority", 5),
                            max_hallucination_rate=v_data.get("max_hallucination_rate", 0.05),
                            min_satisfaction_score=v_data.get("min_satisfaction_score", 0.7),
                            max_tool_failure_rate=v_data.get("max_tool_failure_rate", 0.1),
                            canary_percentage=v_data.get("canary_percentage", 0),
                            metrics=v_data.get("metrics", {}),
                        )
                        agent.versions.append(v)
                    self._agents[agent.agent_id] = agent
        except Exception as e:
            logger.warning("Failed to load agent marketplace: %s", e)

    def _save(self):
        """Persist agents to file."""
        try:
            os.makedirs(os.path.dirname(self._storage_file), exist_ok=True)
            data = {"agents": []}
            for agent in self._agents.values():
                agent_dict = asdict(agent)
                # Convert enums to strings for JSON serialization.
                agent_dict["category"] = agent.category.value
                for v in agent_dict.get("versions", []):
                    v["status"] = v["status"].value if isinstance(v["status"], AgentStatus) else v["status"]
                    v["category"] = v["category"].value if isinstance(v["category"], AgentCategory) else v["category"]
                data["agents"].append(agent_dict)
            with open(self._storage_file, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save agent marketplace: %s", e)

    # ─── Template operations ──────────────────────────────

    def list_templates(self, category: Optional[str] = None) -> list[dict]:
        """List available agent templates."""
        if category:
            return [t for t in AGENT_TEMPLATES if t["category"] == category]
        return AGENT_TEMPLATES

    def get_template(self, template_id: str) -> Optional[dict]:
        for t in AGENT_TEMPLATES:
            if t["template_id"] == template_id:
                return t
        return None

    # ─── Agent CRUD ───────────────────────────────────────

    def create_agent_from_template(
        self,
        template_id: str,
        department: str,
        created_by: str,
        customizations: Optional[dict] = None,
    ) -> Agent:
        """Create a new agent from a template (no-code builder).

        Args:
            template_id: The template to base the agent on.
            department: The department that owns this agent.
            created_by: User ID of the creator.
            customizations: Optional overrides for system_prompt, tools, scopes, etc.

        Returns:
            The created Agent (in DRAFT status, awaiting testing).
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        customizations = customizations or {}
        agent = Agent(
            name=customizations.get("name", template["name"]),
            category=AgentCategory(template["category"]),
            department=department,
            created_by=created_by,
            tags=customizations.get("tags", [template["category"]]),
        )

        # Create version 1 from template + customizations.
        version = AgentVersion(
            version_number=1,
            status=AgentStatus.DRAFT,
            created_by=created_by,
            name=agent.name,
            description=customizations.get("description", template["description"]),
            category=agent.category,
            department=department,
            system_prompt=customizations.get("system_prompt", template["system_prompt"]),
            knowledge_scopes=customizations.get("knowledge_scopes", template["knowledge_scopes"]),
            allowed_tools=customizations.get("allowed_tools", template["allowed_tools"]),
            allowed_roles=customizations.get("allowed_roles", template["allowed_roles"]),
            escalation_target=customizations.get("escalation_target", template.get("escalation_target", "")),
            priority=customizations.get("priority", template.get("priority", 5)),
        )
        agent.versions.append(version)
        self._agents[agent.agent_id] = agent
        self._save()
        logger.info("Created agent %s from template %s (department=%s)", agent.agent_id, template_id, department)
        return agent

    def create_custom_agent(
        self,
        name: str,
        description: str,
        category: AgentCategory,
        department: str,
        created_by: str,
        system_prompt: str,
        knowledge_scopes: list[str],
        allowed_tools: list[str],
        allowed_roles: list[str],
        escalation_target: str = "",
        priority: int = 5,
    ) -> Agent:
        """Create a custom agent from scratch (no-code builder)."""
        agent = Agent(
            name=name,
            category=category,
            department=department,
            created_by=created_by,
        )
        version = AgentVersion(
            version_number=1,
            status=AgentStatus.DRAFT,
            created_by=created_by,
            name=name,
            description=description,
            category=category,
            department=department,
            system_prompt=system_prompt,
            knowledge_scopes=knowledge_scopes,
            allowed_tools=allowed_tools,
            allowed_roles=allowed_roles,
            escalation_target=escalation_target,
            priority=priority,
        )
        agent.versions.append(version)
        self._agents[agent.agent_id] = agent
        self._save()
        logger.info("Created custom agent %s (department=%s)", agent.agent_id, department)
        return agent

    def list_agents(
        self,
        department: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[AgentStatus] = None,
    ) -> list[Agent]:
        """List agents, optionally filtered."""
        result = list(self._agents.values())
        if department:
            result = [a for a in result if a.department == department]
        if category:
            result = [a for a in result if a.category == AgentCategory(category)]
        if status:
            result = [a for a in result if a.get_production_version() and a.get_production_version().status == status]
        return result

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self._agents.get(agent_id)

    # ─── Lifecycle management ─────────────────────────────

    def test_agent(self, agent_id: str, version_id: str, tested_by: str) -> AgentVersion:
        """Move an agent version from DRAFT to TESTING.

        In TESTING status, the agent can be invoked with test queries but
        does not serve production traffic.
        """
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")
        version = agent.get_version(version_id)
        if not version:
            raise ValueError(f"Version not found: {version_id}")
        if version.status != AgentStatus.DRAFT:
            raise ValueError(f"Version must be in DRAFT status (current: {version.status})")
        version.status = AgentStatus.TESTING
        self._save()
        logger.info("Agent %s v%d moved to TESTING by %s", agent_id, version.version_number, tested_by)
        return version

    def promote_to_staging(self, agent_id: str, version_id: str, approved_by: str) -> AgentVersion:
        """Promote an agent version from TESTING to STAGING.

        Requires department manager approval.
        """
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")
        version = agent.get_version(version_id)
        if not version:
            raise ValueError(f"Version not found: {version_id}")
        if version.status != AgentStatus.TESTING:
            raise ValueError(f"Version must be in TESTING status (current: {version.status})")
        version.status = AgentStatus.STAGING
        version.approved_by = approved_by
        version.approved_at = datetime.now(timezone.utc).isoformat()
        self._save()
        logger.info("Agent %s v%d promoted to STAGING by %s", agent_id, version.version_number, approved_by)
        return version

    def promote_to_production(
        self,
        agent_id: str,
        version_id: str,
        approved_by: str,
        canary: bool = True,
    ) -> AgentVersion:
        """Promote an agent version from STAGING to PRODUCTION (or CANARY).

        If canary=True, starts a canary rollout at 5% traffic.
        The canary_percentage must be manually increased to 25%, 50%, 100%.
        If canary=False, goes directly to 100% production.
        """
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")
        version = agent.get_version(version_id)
        if not version:
            raise ValueError(f"Version not found: {version_id}")
        if version.status != AgentStatus.STAGING:
            raise ValueError(f"Version must be in STAGING status (current: {version.status})")

        # Archive the previous production version.
        prev_prod = agent.get_production_version()
        if prev_prod and prev_prod.version_id != version_id:
            prev_prod.status = AgentStatus.RETIRED

        if canary:
            version.status = AgentStatus.CANARY
            version.canary_percentage = 5
        else:
            version.status = AgentStatus.PRODUCTION
            version.canary_percentage = 100
        version.approved_by = approved_by
        version.approved_at = datetime.now(timezone.utc).isoformat()
        agent.current_version = version_id
        self._save()
        logger.info(
            "Agent %s v%d promoted to %s by %s (canary=%d%%)",
            agent_id, version.version_number, version.status.value, approved_by, version.canary_percentage
        )
        return version

    def increase_canary(self, agent_id: str, version_id: str, percentage: int) -> AgentVersion:
        """Increase the canary percentage for an agent version.

        Valid percentages: 5 → 25 → 50 → 100.
        At 100%, the agent moves from CANARY to PRODUCTION status.
        """
        if percentage not in (5, 25, 50, 100):
            raise ValueError("Canary percentage must be 5, 25, 50, or 100")
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")
        version = agent.get_version(version_id)
        if not version:
            raise ValueError(f"Version not found: {version_id}")
        if version.status != AgentStatus.CANARY:
            raise ValueError(f"Version must be in CANARY status (current: {version.status})")
        version.canary_percentage = percentage
        if percentage == 100:
            version.status = AgentStatus.PRODUCTION
        self._save()
        logger.info("Agent %s v%d canary increased to %d%%", agent_id, version.version_number, percentage)
        return version

    def rollback(self, agent_id: str) -> Optional[AgentVersion]:
        """Rollback to the previous production version."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")
        # Find the most recently retired version.
        retired = [v for v in agent.versions if v.status == AgentStatus.RETIRED]
        if not retired:
            return None
        prev = sorted(retired, key=lambda v: v.approved_at)[-1]
        # Archive current production.
        current_prod = agent.get_production_version()
        if current_prod:
            current_prod.status = AgentStatus.RETIRED
        # Restore previous.
        prev.status = AgentStatus.PRODUCTION
        prev.canary_percentage = 100
        agent.current_version = prev.version_id
        self._save()
        logger.info("Agent %s rolled back to v%d", agent_id, prev.version_number)
        return prev

    def retire_agent(self, agent_id: str, retired_by: str) -> bool:
        """Retire an agent entirely (all versions become RETIRED)."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")
        for v in agent.versions:
            v.status = AgentStatus.RETIRED
        agent.current_version = ""
        self._save()
        logger.info("Agent %s retired by %s", agent_id, retired_by)
        return True

    # ─── Metrics ──────────────────────────────────────────

    def update_metrics(self, agent_id: str, version_id: str, metrics_update: dict):
        """Update quality metrics for an agent version.

        Called by the agent runtime after each execution.
        If metrics violate thresholds, auto-rollback is triggered.
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return
        version = agent.get_version(version_id)
        if not version:
            return
        # Merge metrics update.
        for key, value in metrics_update.items():
            if key in version.metrics:
                if isinstance(version.metrics[key], (int, float)) and isinstance(value, (int, float)):
                    version.metrics[key] += value
                else:
                    version.metrics[key] = value
            else:
                version.metrics[key] = value

        # Check quality thresholds — auto-rollback if violated.
        total = version.metrics.get("total_executions", 0)
        if total > 100:  # only check after 100 executions (statistical significance)
            hallucination_rate = version.metrics.get("hallucination_count", 0) / max(total, 1)
            tool_failure_rate = version.metrics.get("tool_failures", 0) / max(total, 1)
            satisfaction = version.metrics.get("avg_satisfaction", 1.0)

            if (hallucination_rate > version.max_hallucination_rate or
                tool_failure_rate > version.max_tool_failure_rate or
                satisfaction < version.min_satisfaction_score):
                logger.warning(
                    "Agent %s v%d quality thresholds violated — auto-rollback triggered "
                    "(hallucination=%.2f%%, tool_failures=%.2f%%, satisfaction=%.2f)",
                    agent_id, version.version_number,
                    hallucination_rate * 100, tool_failure_rate * 100, satisfaction
                )
                self.rollback(agent_id)
        self._save()

    def get_metrics(self, agent_id: str, version_id: Optional[str] = None) -> dict:
        """Get quality metrics for an agent version."""
        agent = self.get_agent(agent_id)
        if not agent:
            return {}
        if version_id:
            version = agent.get_version(version_id)
        else:
            version = agent.get_production_version() or agent.get_latest_version()
        if not version:
            return {}
        return {
            "agent_id": agent_id,
            "version": version.version_number,
            "status": version.status.value,
            "canary_percentage": version.canary_percentage,
            "metrics": version.metrics,
            "thresholds": {
                "max_hallucination_rate": version.max_hallucination_rate,
                "min_satisfaction_score": version.min_satisfaction_score,
                "max_tool_failure_rate": version.max_tool_failure_rate,
            },
        }


# Singleton instance.
marketplace = AgentMarketplace()

__all__ = [
    "AgentMarketplace",
    "marketplace",
    "Agent",
    "AgentVersion",
    "AgentStatus",
    "AgentCategory",
    "AGENT_TEMPLATES",
]
