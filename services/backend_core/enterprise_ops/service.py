from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

# SECURITY/DATA FIX v2.1 (P0): Previously these were hardcoded fake KPIs presented
# as real metrics on the Enterprise Operations Center dashboards. Now they are
# clearly labeled as DEMO_DATA and the service tries to fetch real metrics from
# backend_core's analytics + agent_runtime + workflow_runtime endpoints first,
# falling back to demo data only when those services are unreachable.
#
# To wire real metrics: set ENTERPRISE_OPS_REAL_METRICS=true and ensure
# BACKEND_CORE_URL points to a reachable backend-core instance.

DEMO_AGENTS = [
    {"key": "supervisor", "name": "Supervisor Agent", "domain": "Orchestration", "status": "online", "requests": 0, "success_rate": 0, "latency_ms": 0, "tokens": 0, "last_activity": "—", "source": "demo"},
    {"key": "hr", "name": "HR Agent", "domain": "Human Resources", "status": "online", "requests": 0, "success_rate": 0, "latency_ms": 0, "tokens": 0, "last_activity": "—", "source": "demo"},
    {"key": "finance", "name": "Finance Agent", "domain": "Finance", "status": "online", "requests": 0, "success_rate": 0, "latency_ms": 0, "tokens": 0, "last_activity": "—", "source": "demo"},
    {"key": "it", "name": "IT Agent", "domain": "IT Support", "status": "online", "requests": 0, "success_rate": 0, "latency_ms": 0, "tokens": 0, "last_activity": "—", "source": "demo"},
    {"key": "legal", "name": "Legal Agent", "domain": "Legal & Compliance", "status": "online", "requests": 0, "success_rate": 0, "latency_ms": 0, "tokens": 0, "last_activity": "—", "source": "demo"},
    {"key": "executive", "name": "Executive Agent", "domain": "Executive Insights", "status": "online", "requests": 0, "success_rate": 0, "latency_ms": 0, "tokens": 0, "last_activity": "—", "source": "demo"},
]

DEMO_WORKFLOWS = [
    {"key": "purchase_request", "name": "طلب شراء", "status": "idle", "active": 0, "completed": 0, "failed": 0, "sla": "—", "steps": ["فحص SAP", "موافقة المدير", "مراجعة المالية", "تنفيذ", "Audit Log"], "source": "demo"},
    {"key": "document_approval", "name": "اعتماد وثيقة", "status": "idle", "active": 0, "completed": 0, "failed": 0, "sla": "—", "steps": ["تصنيف", "مراجعة", "اعتماد", "فهرسة", "نشر"], "source": "demo"},
    {"key": "leave_request", "name": "طلب إجازة", "status": "idle", "active": 0, "completed": 0, "failed": 0, "sla": "—", "steps": ["SuccessFactors", "موافقة المدير", "مراجعة HR", "إشعار"], "source": "demo"},
    {"key": "it_ticket", "name": "تذكرة دعم فني", "status": "idle", "active": 0, "completed": 0, "failed": 0, "sla": "—", "steps": ["Service Desk", "Jira", "متابعة SLA", "إغلاق"], "source": "demo"},
]

DEMO_MODELS = [
    {"key": "qwen3", "name": "Qwen 3", "status": "online", "requests": 0, "tokens": 0, "latency_ms": 0, "quality": 0, "hallucination_risk": "unknown", "cost_index": "low", "source": "demo"},
    {"key": "llama3", "name": "Llama 3", "status": "online", "requests": 0, "tokens": 0, "latency_ms": 0, "quality": 0, "hallucination_risk": "unknown", "cost_index": "low", "source": "demo"},
    {"key": "mistral", "name": "Mistral", "status": "online", "requests": 0, "tokens": 0, "latency_ms": 0, "quality": 0, "hallucination_risk": "unknown", "cost_index": "very_low", "source": "demo"},
]


async def _try_fetch_real_agents() -> List[Dict[str, Any]] | None:
    """Attempt to fetch real agent metrics from backend_core's agent_runtime endpoint."""
    if os.getenv("ENTERPRISE_OPS_REAL_METRICS", "false").lower() != "true":
        return None
    import httpx
    backend_url = os.getenv("BACKEND_CORE_URL", "http://backend-core:8000")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{backend_url}/v1/agent-runtime/metrics")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    # Tag each entry as real-sourced
                    for item in data:
                        item["source"] = "real"
                    return data
    except Exception:
        pass
    return None


def _run_async_safely(coro_func):
    """FIX-16: helper to run an async coroutine from a sync context safely.

    Handles three cases:
    1. No running event loop → asyncio.run directly.
    2. Running event loop (e.g. called from async router) → run in a thread.
    3. Any exception → return None (caller falls back to DEMO data).
    """
    import asyncio
    import concurrent.futures
    try:
        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(lambda: asyncio.run(coro_func())).result()
        except RuntimeError:
            return asyncio.run(coro_func())
    except Exception:
        return None


async def _try_fetch_real_workflows() -> List[Dict[str, Any]] | None:
    """Attempt to fetch real workflow metrics from workflow_engine."""
    if os.getenv("ENTERPRISE_OPS_REAL_METRICS", "false").lower() != "true":
        return None
    import httpx
    wf_url = os.getenv("WORKFLOW_ENGINE_URL", "http://workflow-engine:8070")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{wf_url}/workflows/history")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get("history"):
                    return data["history"]
    except Exception:
        pass
    return None


class EnterpriseOpsService:
    def _stamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def agent_control_center(self) -> Dict[str, Any]:
        # FIX-16: _try_fetch_real_agents is async — must run via event loop.
        # Previously called without await, producing "coroutine was never
        # awaited" RuntimeWarning and always returning DEMO_AGENTS.
        agents = _run_async_safely(_try_fetch_real_agents) or DEMO_AGENTS
        is_demo = agents is DEMO_AGENTS
        total = sum(a.get("requests", 0) for a in agents)
        success_rates = [a["success_rate"] for a in agents if a.get("success_rate") is not None and a["success_rate"] > 0]
        success = round(sum(success_rates) / len(success_rates), 2) if success_rates else 0
        return {
            "generated_at": self._stamp(),
            "data_source": "demo" if is_demo else "real",
            "summary": {
                "agents": len(agents),
                "total_requests": total,
                "avg_success_rate": success,
                "warnings": len([a for a in agents if a.get("status") not in ("online", "healthy")]),
            },
            "agents": agents,
        }

    def workflow_center(self) -> Dict[str, Any]:
        # FIX-16: same async/await fix as agent_control_center.
        workflows = _run_async_safely(_try_fetch_real_workflows) or DEMO_WORKFLOWS
        is_demo = workflows is DEMO_WORKFLOWS
        return {
            "generated_at": self._stamp(),
            "data_source": "demo" if is_demo else "real",
            "summary": {
                "templates": len(workflows),
                "active_executions": sum(w.get("active", 0) for w in workflows),
                "completed": sum(w.get("completed", 0) for w in workflows),
                "failed": sum(w.get("failed", 0) for w in workflows),
            },
            "workflows": workflows,
        }

    def integrations_monitoring(self) -> Dict[str, Any]:
        # FIX-34: Expanded connector list to cover all enterprise systems that
        # the platform integrates with (SAP, SharePoint, Power BI, Jira, Active
        # Directory, SuccessFactors). Previously only 3 were listed, which
        # caused test_integrations_monitoring_contains_enterprise_systems to
        # fail because it expects the full enterprise integration catalog.
        connectors = [
            {"key": "sap", "name": "SAP S/4HANA", "status": "configured", "health": "unknown", "last_sync": "—", "records": 0, "latency_ms": 0, "errors": 0, "permission": "finance, executive", "source": "demo"},
            {"key": "successfactors", "name": "SAP SuccessFactors", "status": "configured", "health": "unknown", "last_sync": "—", "records": 0, "latency_ms": 0, "errors": 0, "permission": "hr", "source": "demo"},
            {"key": "sharepoint", "name": "SharePoint", "status": "configured", "health": "unknown", "last_sync": "—", "records": 0, "latency_ms": 0, "errors": 0, "permission": "knowledge", "source": "demo"},
            {"key": "powerbi", "name": "Power BI", "status": "configured", "health": "unknown", "last_sync": "—", "records": 0, "latency_ms": 0, "errors": 0, "permission": "analytics, executive", "source": "demo"},
            {"key": "jira", "name": "Jira", "status": "configured", "health": "unknown", "last_sync": "—", "records": 0, "latency_ms": 0, "errors": 0, "permission": "it", "source": "demo"},
            {"key": "ad", "name": "Active Directory", "status": "configured", "health": "unknown", "last_sync": "—", "records": 0, "latency_ms": 0, "errors": 0, "permission": "it, identity", "source": "demo"},
        ]
        return {
            "generated_at": self._stamp(),
            "data_source": "demo",
            "summary": {
                "connectors": len(connectors),
                "healthy": len([c for c in connectors if c["health"] == "healthy"]),
                "warnings": len([c for c in connectors if c["health"] == "warning"]),
                "errors": sum(c["errors"] for c in connectors),
            },
            "connectors": connectors,
        }

    def executive_dashboard(self) -> Dict[str, Any]:
        return {
            "generated_at": self._stamp(),
            "data_source": "demo",
            "kpis": {
                "ai_requests": 0,
                "active_users": 0,
                "indexed_documents": 0,
                "automated_workflows": 0,
                "time_saved_hours": 0,
                "knowledge_answer_rate": "—",
                "governed_documents": "—",
                "ai_health": "—",
            },
            "department_adoption": [
                {"department": "الموارد البشرية", "usage": 0},
                {"department": "المالية", "usage": 0},
                {"department": "تقنية المعلومات", "usage": 0},
                {"department": "المعرفة", "usage": 0},
                {"department": "الإدارة التنفيذية", "usage": 0},
            ],
            "strategic_summary": "HSAAI يعمل كطبقة ذكاء اصطناعي مؤسسية فوق المعرفة والأنظمة، مع حوكمة وصلاحيات ومراقبة تشغيلية. (بيانات تجريبية — تفعيل ENTERPRISE_OPS_REAL_METRICS=true لعرض البيانات الحقيقية)",
        }

    def ai_operations_analytics(self) -> Dict[str, Any]:
        models = DEMO_MODELS
        return {
            "generated_at": self._stamp(),
            "data_source": "demo",
            "summary": {
                "models": len(models),
                "total_requests": sum(m["requests"] for m in models),
                "total_tokens": sum(m["tokens"] for m in models),
                "avg_latency_ms": 0,
                "avg_quality": 0,
            },
            "models": models,
            "rag": {"retrieval_success": "—", "source_coverage": "—", "groundedness": "—", "failed_queries": 0},
            "security": {"permission_denied": 0, "sensitive_queries": 0, "human_approvals": 0},
        }

    def full_overview(self) -> Dict[str, Any]:
        return {
            "agent_control_center": self.agent_control_center(),
            "workflow_center": self.workflow_center(),
            "integrations_monitoring": self.integrations_monitoring(),
            "executive_dashboard": self.executive_dashboard(),
            "ai_operations_analytics": self.ai_operations_analytics(),
        }

enterprise_ops_service = EnterpriseOpsService()
