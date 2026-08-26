"""
HSAAI Enterprise Connector Framework — AI Integration Layer (PHASE 5)
======================================================================
Wires all connectors into the AI stack:
  - AI Chat (Tool Calling)
  - Agents (per-department connectors)
  - RAG (federated search across connectors)
  - Knowledge Graph (entity extraction from connector data)
  - Workflow Engine (trigger connector actions from workflows)
  - Analytics (aggregate metrics across connectors)
  - Document Intelligence (extract from documents fetched via connectors)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .base import BaseConnector, ConnectorError
from .registry import ConnectorRegistry as registry

logger = logging.getLogger(__name__)


class ConnectorToolRegistry:
    """
    Maps AI tool names to connector actions.
    Used by the AI Chat (Tool Calling) to expose connector capabilities
    to the LLM as callable tools.
    """

    _tools: dict[str, dict] = {}

    @classmethod
    def register_tool(cls, tool_name: str, connector_name: str, action: str,
                      description: str, param_schema: dict | None = None) -> None:
        """Register a connector action as an AI-callable tool."""
        cls._tools[tool_name] = {
            "connector": connector_name,
            "action": action,
            "description": description,
            "param_schema": param_schema or {},
        }
        logger.debug(f"Registered AI tool: {tool_name} → {connector_name}.{action}")

    @classmethod
    def get_tool(cls, tool_name: str) -> dict | None:
        return cls._tools.get(tool_name)

    @classmethod
    def list_tools(cls) -> list[dict]:
        """List all registered tools (for LLM function-calling schema)."""
        return [
            {"name": name, **info}
            for name, info in sorted(cls._tools.items())
        ]

    @classmethod
    async def call_tool(cls, tool_name: str, **kwargs) -> dict:
        """Execute a tool by name (called by the AI Chat tool-calling loop)."""
        tool = cls._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")
        instance = registry.get_instance(tool["connector"])
        if not instance:
            raise ConnectorError(f"Connector '{tool['connector']}' not running")
        return await instance.call(tool["action"], **kwargs)

    @classmethod
    def auto_register_from_connectors(cls) -> int:
        """
        Auto-discover connector actions and register them as AI tools.
        Tool naming: {connector}_{action} (e.g. 'sap_s4hana_get_sales_orders').
        """
        count = 0
        for conn_info in registry.list_instances():
            conn = registry.get_instance(conn_info["name"])
            if not conn:
                continue
            meta = conn.metadata()
            for action in meta.get("actions", []):
                tool_name = f"{conn_info['name']}_{action}"
                cls.register_tool(
                    tool_name=tool_name,
                    connector_name=conn_info["name"],
                    action=action,
                    description=meta.get("action_descriptions", {}).get(action, f"{action} on {conn_info['name']}"),
                )
                count += 1
        logger.info(f"Auto-registered {count} AI tools from connectors")
        return count


class FederatedSearch:
    """
    Federated search across ALL connectors simultaneously.
    Used by the RAG engine to search across SAP, SharePoint, AD, etc. in one call.
    """

    @staticmethod
    async def search_all(query: str, limit_per_connector: int = 5,
                         categories: list[str] | None = None) -> dict[str, list[dict]]:
        """
        Search all connected connectors in parallel.
        Returns a dict mapping connector name → results.
        """
        import asyncio
        results: dict[str, list[dict]] = {}
        tasks = []
        for conn_info in registry.list_instances():
            if categories and conn_info["category"] not in categories:
                continue
            if conn_info["state"] != "connected":
                continue
            conn = registry.get_instance(conn_info["name"])
            if not conn:
                continue
            tasks.append(FederatedSearch._search_one(conn, query, limit_per_connector))
        # Run all searches in parallel
        search_results = await asyncio.gather(*tasks, return_exceptions=True)
        for conn_info, result in zip(registry.list_instances(), search_results):
            if isinstance(result, Exception):
                logger.warning(f"Federated search failed for '{conn_info['name']}': {result}")
                results[conn_info["name"]] = []
            else:
                results[conn_info["name"]] = result
        return results

    @staticmethod
    async def _search_one(connector: BaseConnector, query: str, limit: int) -> list[dict]:
        try:
            return await connector.search(query, limit=limit)
        except Exception:
            return []


class ConnectorWorkflowIntegration:
    """
    Integration with the Workflow Engine.
    Allows workflow steps to call connector actions.
    """

    @staticmethod
    async def execute_step(connector_name: str, action: str, params: dict,
                           user: str | None = None) -> dict:
        """Execute a connector action as a workflow step."""
        conn = registry.get_instance(connector_name)
        if not conn:
            raise ConnectorError(f"Connector '{connector_name}' not found")
        return await conn.call(action, user=user, **params)


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 6: Security — Auth strategies + RBAC/ABAC
# ═══════════════════════════════════════════════════════════════════════════
class ConnectorPermissionChecker:
    """
    RBAC/ABAC permission checker for connectors.
    Integrates with OPA (Open Policy Agent) in production.
    """

    # Permission matrix: role → allowed connector categories
    _ROLE_MATRIX = {
        "ai_admin": ["*"],  # all categories
        "executive": ["BI", "ERP", "HR"],
        "department_manager": ["ERP", "HR", "Documents", "ITSM"],
        "ai_user": ["Documents", "Collaboration"],
    }

    @classmethod
    def check(cls, user_role: str, connector_name: str, action: str) -> bool:
        """Check if a user role can execute an action on a connector."""
        # Get connector category
        conn = registry.get_instance(connector_name)
        if not conn:
            return False
        category = conn.config.category
        # Admin can do everything
        if user_role in cls._ROLE_MATRIX and "*" in cls._ROLE_MATRIX[user_role]:
            return True
        # Check role matrix
        allowed_categories = cls._ROLE_MATRIX.get(user_role, [])
        return category in allowed_categories

    @classmethod
    async def check_opa(cls, user: str, role: str, connector: str, action: str) -> bool:
        """Check via OPA (in production). Falls back to local matrix if OPA unavailable."""
        # TODO: implement OPA HTTP query
        # POST http://opa:8181/v1/data/hsaai/allow
        # {"input": {"user": user, "role": role, "connector": connector, "action": action}}
        return cls.check(role, connector, action)


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 7: Observability — Structured logs, metrics, tracing
# ═══════════════════════════════════════════════════════════════════════════
class ConnectorObservability:
    """
    Observability aggregator: structured logs, Prometheus metrics, OpenTelemetry tracing.
    """

    @staticmethod
    def export_prometheus() -> str:
        """Export all connector metrics in Prometheus format."""
        lines = [
            "# HELP hsaai_connector_calls_total Total calls per connector",
            "# TYPE hsaai_connector_calls_total counter",
            "# HELP hsaai_connector_latency_ms_avg Average latency in ms",
            "# TYPE hsaai_connector_latency_ms_avg gauge",
            "# HELP hsaai_connector_cache_hits_total Cache hits",
            "# TYPE hsaai_connector_cache_hits_total counter",
            "# HELP hsaai_connector_circuit_breaker_state CB state (0=closed, 1=open, 2=half_open)",
            "# TYPE hsaai_connector_circuit_breaker_state gauge",
        ]
        for name, m in registry.metrics_all().items():
            labels = f'connector="{name}"'
            lines.append(f'hsaai_connector_calls_total{{{labels},result="success"}} {m.successful_calls}')
            lines.append(f'hsaai_connector_calls_total{{{labels},result="failure"}} {m.failed_calls}')
            lines.append(f'hsaai_connector_latency_ms_avg{{{labels}}} {m.avg_latency_ms}')
            lines.append(f'hsaai_connector_cache_hits_total{{{labels}}} {m.cache_hits}')
            cb_state = {"closed": 0, "open": 1, "half_open": 2}.get(m.circuit_breaker_state.value, 0)
            lines.append(f'hsaai_connector_circuit_breaker_state{{{labels}}} {cb_state}')
        return "\n".join(lines) + "\n"

    @staticmethod
    def export_health_summary() -> dict:
        """Export a health summary for the admin dashboard."""
        return registry.health_all()


__all__ = [
    "ConnectorToolRegistry",
    "FederatedSearch",
    "ConnectorWorkflowIntegration",
    "ConnectorPermissionChecker",
    "ConnectorObservability",
]
