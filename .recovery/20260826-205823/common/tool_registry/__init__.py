"""
HSAAI Tool Registry & Dispatcher (v3.0)

Real tool calling mechanism for HSAAI agents. Replaces the "tool theater"
pattern (tools declared as strings but never executed) with actual dispatch.

Architecture:
  ┌─────────────────┐
  │  Agent (LLM)    │
  │  "I need to     │
  │   search HR"    │
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │  Tool Registry  │  ← tools register themselves here
  │  (dict)         │
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │  Dispatcher     │  ← routes call to correct tool
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │  Tool Handler   │  ← executes the actual logic
  │  (async func)   │
  └─────────────────┘

Available tools:
  - rag_search: search the knowledge base
  - policy_lookup: look up a specific policy document
  - summarizer: summarize a long text
  - invoice_lookup: query SAP S/4HANA for invoice details
  - budget_summary: get budget vs actual summary
  - kpi_summary: get executive KPIs
  - risk_analysis: analyze risks for a department
  - document_extract: extract text from a document
  - citation_builder: format citations from RAG results
  - employee_lookup: query SAP SuccessFactors for employee info
"""
import os
import sys
import json
import logging
import httpx
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger("hsaai.tools")

# Service URLs
RAG_ENGINE_URL = os.getenv("RAG_ENGINE_URL", "http://rag_engine:8030")
LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm_gateway:8090")
DOCUMENT_AI_URL = os.getenv("DOCUMENT_AI_URL", "http://document_ai:8060")
BACKEND_CORE_URL = os.getenv("BACKEND_CORE_URL", "http://backend:8000")


@dataclass
class ToolDefinition:
    """Definition of a callable tool."""
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable[..., Awaitable[dict]]
    category: str = "general"
    requires_auth: bool = True


# ─── Tool Registry ───

_REGISTRY: dict[str, ToolDefinition] = {}


def register_tool(tool: ToolDefinition) -> None:
    """Register a tool in the global registry."""
    _REGISTRY[tool.name] = tool
    logger.info("Registered tool: %s (%s)", tool.name, tool.category)


def get_tool(name: str) -> ToolDefinition | None:
    """Get a tool definition by name."""
    return _REGISTRY.get(name)


def list_tools() -> list[dict]:
    """List all registered tools (for agent discovery)."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
            "category": t.category,
        }
        for t in _REGISTRY.values()
    ]


async def dispatch_tool(name: str, args: dict[str, Any], context: dict) -> dict:
    """Execute a tool by name with the given arguments.

    Args:
        name: The tool name (must be registered).
        args: Tool arguments (validated against the tool's JSON Schema).
        context: Execution context (tenant_id, workspace_id, user_id, roles).

    Returns:
        Tool execution result dict.

    Raises:
        ValueError: If the tool is not found.
        Exception: If the tool handler raises.
    """
    tool = get_tool(name)
    if tool is None:
        # FIX-25: Return an error dict instead of raising ValueError.
        # Raising forces every caller to wrap dispatch_tool in try/except,
        # and a stray raise in an async dispatcher can crash the event loop.
        # Returning a structured error is the safer, more composable pattern
        # and matches what callers (and tests) expect.
        logger.warning("Unknown tool requested: %s", name)
        return {
            "success": False,
            "error": f"Unknown tool: {name}",
            "available": list(_REGISTRY.keys()),
        }

    # Inject context into args (tools can use tenant_id, user_id, etc.)
    args_with_context = {**args, "_context": context}

    try:
        result = await tool.handler(**args_with_context)
        logger.info("Tool %s executed successfully (tenant=%s)", name, context.get("tenant_id"))
        return result
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return {"error": str(exc), "tool": name, "success": False}


# ─── Tool Handlers ───

async def _rag_search(query: str, top_k: int = 5, _context: dict = None, **kwargs) -> dict:
    """Search the RAG knowledge base."""
    ctx = _context or {}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{RAG_ENGINE_URL}/v1/search",
            json={
                "query": query,
                "tenant_id": ctx.get("tenant_id", "default"),
                "workspace_id": ctx.get("workspace_id", "default"),
                "top_k": top_k,
                "mode": "hybrid",
            },
        )
        if resp.status_code >= 400:
            return {"error": f"RAG search failed: HTTP {resp.status_code}", "success": False}
        data = resp.json()
        return {
            "results": data.get("results", [])[:top_k],
            "count": data.get("count", 0),
            "success": True,
        }


async def _policy_lookup(policy_name: str, _context: dict = None, **kwargs) -> dict:
    """Look up a specific policy document by name."""
    ctx = _context or {}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{RAG_ENGINE_URL}/v1/search",
            json={
                "query": f"policy {policy_name}",
                "tenant_id": ctx.get("tenant_id", "default"),
                "workspace_id": ctx.get("workspace_id", "default"),
                "top_k": 3,
                "mode": "hybrid",
            },
        )
        if resp.status_code >= 400:
            return {"error": f"Policy lookup failed: HTTP {resp.status_code}", "success": False}
        data = resp.json()
        results = data.get("results", [])
        return {
            "policy": results[0] if results else None,
            "alternatives": results[1:] if len(results) > 1 else [],
            "success": True,
        }


async def _summarizer(text: str, max_length: int = 500, _context: dict = None, **kwargs) -> dict:
    """Summarize a long text using the LLM."""
    ctx = _context or {}
    if not text or len(text) < 100:
        return {"summary": text, "success": True, "note": "Text too short to summarize."}

    prompt = f"Summarize the following text in no more than {max_length} characters. Preserve key facts and figures.\n\nText:\n{text[:10000]}\n\nSummary:"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{LLM_GATEWAY_URL}/v1/generate",
            json={
                "prompt": prompt,
                "system": "You are a precise summarization assistant. Summarize faithfully without adding information.",
                "max_tokens": 500,
                "temperature": 0.3,
                "tenant_id": ctx.get("tenant_id", "default"),
            },
        )
        if resp.status_code >= 400:
            return {"error": f"Summarization failed: HTTP {resp.status_code}", "success": False}
        data = resp.json()
        summary = data.get("text", "").strip()
        return {"summary": summary, "original_length": len(text), "summary_length": len(summary), "success": True}


async def _invoice_lookup(invoice_id: str, _context: dict = None, **kwargs) -> dict:
    """Look up invoice details from SAP S/4HANA via the enterprise connector."""
    ctx = _context or {}
    tenant_id = ctx.get("tenant_id", "default")
    BACKEND_CORE_URL = os.getenv("BACKEND_CORE_URL", "http://backend_core:8000")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BACKEND_CORE_URL}/v1/connectors/sap/invoices/{invoice_id}",
                headers={"Authorization": f"Bearer {ctx.get('token', '')}",
                         "X-Tenant-Id": tenant_id},
            )
            if resp.status_code < 400:
                data = resp.json()
                return {
                    "invoice_id": invoice_id,
                    "status": "ok",
                    "fields": {
                        "vendor": data.get("vendor", ""),
                        "amount": data.get("amount", 0.0),
                        "currency": data.get("currency", "SAR"),
                        "due_date": data.get("due_date"),
                        "status": data.get("status", "unknown"),
                    },
                    "source": "sap_s4hana",
                    "success": True,
                }
            return {
                "invoice_id": invoice_id,
                "status": "error",
                "error": f"SAP returned HTTP {resp.status_code}",
                "success": False,
            }
    except Exception as e:
        return {
            "invoice_id": invoice_id,
            "status": "unavailable",
            "error": f"SAP connector unreachable: {str(e)[:100]}",
            "success": False,
        }


async def _budget_summary(department: str = "all", _context: dict = None, **kwargs) -> dict:
    """Get budget vs actual summary for a department from SAP S/4HANA."""
    ctx = _context or {}
    tenant_id = ctx.get("tenant_id", "default")
    BACKEND_CORE_URL = os.getenv("BACKEND_CORE_URL", "http://backend_core:8000")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BACKEND_CORE_URL}/v1/connectors/sap/budget",
                params={"department": department},
                headers={"Authorization": f"Bearer {ctx.get('token', '')}",
                         "X-Tenant-Id": tenant_id},
            )
            if resp.status_code < 400:
                data = resp.json()
                return {
                    "department": department,
                    "period": data.get("period", "current_quarter"),
                    "budget": data.get("budget", 0),
                    "actual": data.get("actual", 0),
                    "variance": data.get("variance", 0),
                    "utilization_pct": data.get("utilization_pct", 0),
                    "source": "sap_s4hana",
                    "success": True,
                }
            return {
                "department": department,
                "status": "error",
                "error": f"SAP returned HTTP {resp.status_code}",
                "success": False,
            }
    except Exception as e:
        return {
            "department": department,
            "status": "unavailable",
            "error": f"SAP connector unreachable: {str(e)[:100]}",
            "success": False,
        }


async def _kpi_summary(department: str = "all", _context: dict = None, **kwargs) -> dict:
    """Get executive KPIs."""
    ctx = _context or {}
    # Query the analytics service for real KPIs
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "http://analytics:8070/metrics/ai",
                headers={"Authorization": f"Bearer {ctx.get('token', '')}"},
            )
            if resp.status_code < 400:
                data = resp.json()
                return {
                    "kpis": {
                        "ai_requests_today": data.get("tokens_today", 0),
                        "active_agents": data.get("active_agents", 0),
                        "avg_latency_ms": data.get("avg_latency_ms", 0),
                    },
                    "department": department,
                    "success": True,
                }
    except Exception:
        pass
    return {"kpis": {}, "department": department, "success": False, "error": "Analytics service unavailable"}


async def _risk_analysis(department: str, _context: dict = None, **kwargs) -> dict:
    """Analyze risks for a department."""
    # Query the knowledge graph for risk entities
    ctx = _context or {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{BACKEND_CORE_URL}/v1/knowledge-graph/search",
                json={
                    "query": f"risk {department}",
                    "entity_type": "Risk",
                    "tenant_id": ctx.get("tenant_id", "default"),
                    "workspace_id": ctx.get("workspace_id", "default"),
                },
            )
            if resp.status_code < 400:
                data = resp.json()
                risks = data.get("entities", [])
                return {
                    "department": department,
                    "risks_identified": len(risks),
                    "risks": risks[:10],
                    "success": True,
                }
    except Exception:
        pass
    return {"department": department, "risks_identified": 0, "risks": [], "success": False}


async def _document_extract(doc_id: str, _context: dict = None, **kwargs) -> dict:
    """Extract text from a document by ID."""
    ctx = _context or {}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{RAG_ENGINE_URL}/v1/documents/list",
            json={
                "tenant_id": ctx.get("tenant_id", "default"),
                "workspace_id": ctx.get("workspace_id", "default"),
                "doc_id": doc_id,
            },
        )
        if resp.status_code < 400:
            data = resp.json()
            docs = data.get("documents", [])
            if docs:
                return {"document": docs[0], "success": True}
        return {"error": "Document not found", "doc_id": doc_id, "success": False}


async def _citation_builder(results: list[dict], _context: dict = None, **kwargs) -> dict:
    """Format citations from RAG results."""
    citations = []
    for i, r in enumerate(results, start=1):
        citations.append({
            "index": i,
            "doc_id": r.get("doc_id", "unknown"),
            "filename": r.get("filename", "unknown"),
            "chunk_index": r.get("chunk_index"),
            "page": r.get("page"),
            "score": r.get("score", 0),
            "quote": (r.get("text") or "")[:200],
        })
    return {"citations": citations, "count": len(citations), "success": True}


async def _employee_lookup(employee_id: str, _context: dict = None, **kwargs) -> dict:
    """Look up employee info from SAP SuccessFactors via the enterprise connector."""
    ctx = _context or {}
    tenant_id = ctx.get("tenant_id", "default")
    BACKEND_CORE_URL = os.getenv("BACKEND_CORE_URL", "http://backend_core:8000")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BACKEND_CORE_URL}/v1/connectors/successfactors/employees/{employee_id}",
                headers={"Authorization": f"Bearer {ctx.get('token', '')}",
                         "X-Tenant-Id": tenant_id},
            )
            if resp.status_code < 400:
                data = resp.json()
                return {
                    "employee_id": employee_id,
                    "status": "ok",
                    "fields": {
                        "name": data.get("name", ""),
                        "department": data.get("department", ""),
                        "position": data.get("position", ""),
                        "manager": data.get("manager", ""),
                        "email": data.get("email", ""),
                    },
                    "source": "sap_successfactors",
                    "success": True,
                }
            return {
                "employee_id": employee_id,
                "status": "error",
                "error": f"HR system returned HTTP {resp.status_code}",
                "success": False,
            }
    except Exception as e:
        return {
            "employee_id": employee_id,
            "status": "unavailable",
            "error": f"HR connector unreachable: {str(e)[:100]}",
            "success": False,
        }


# ─── Register All Tools ───

def _register_all_tools():
    """Register all built-in tools. Called on module import."""
    register_tool(ToolDefinition(
        name="rag_search",
        description="Search the enterprise knowledge base. Returns relevant document chunks with citations.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "top_k": {"type": "integer", "description": "Number of results (default 5)", "default": 5},
            },
            "required": ["query"],
        },
        handler=_rag_search,
        category="knowledge",
    ))

    register_tool(ToolDefinition(
        name="policy_lookup",
        description="Look up a specific policy document by name.",
        parameters={
            "type": "object",
            "properties": {
                "policy_name": {"type": "string", "description": "The policy name or keyword"},
            },
            "required": ["policy_name"],
        },
        handler=_policy_lookup,
        category="knowledge",
    ))

    register_tool(ToolDefinition(
        name="summarizer",
        description="Summarize a long text using the LLM.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to summarize"},
                "max_length": {"type": "integer", "default": 500},
            },
            "required": ["text"],
        },
        handler=_summarizer,
        category="ai",
    ))

    register_tool(ToolDefinition(
        name="invoice_lookup",
        description="Look up invoice details from SAP.",
        parameters={
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "The invoice ID"},
            },
            "required": ["invoice_id"],
        },
        handler=_invoice_lookup,
        category="finance",
    ))

    register_tool(ToolDefinition(
        name="budget_summary",
        description="Get budget vs actual summary for a department.",
        parameters={
            "type": "object",
            "properties": {
                "department": {"type": "string", "default": "all"},
            },
        },
        handler=_budget_summary,
        category="finance",
    ))

    register_tool(ToolDefinition(
        name="kpi_summary",
        description="Get executive KPIs (AI usage, active agents, latency).",
        parameters={
            "type": "object",
            "properties": {
                "department": {"type": "string", "default": "all"},
            },
        },
        handler=_kpi_summary,
        category="executive",
    ))

    register_tool(ToolDefinition(
        name="risk_analysis",
        description="Analyze risks for a department using the knowledge graph.",
        parameters={
            "type": "object",
            "properties": {
                "department": {"type": "string", "description": "The department to analyze"},
            },
            "required": ["department"],
        },
        handler=_risk_analysis,
        category="risk",
    ))

    register_tool(ToolDefinition(
        name="document_extract",
        description="Extract text from a document by ID.",
        parameters={
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "The document ID"},
            },
            "required": ["doc_id"],
        },
        handler=_document_extract,
        category="knowledge",
    ))

    register_tool(ToolDefinition(
        name="citation_builder",
        description="Format citations from RAG search results.",
        parameters={
            "type": "object",
            "properties": {
                "results": {"type": "array", "description": "RAG search results"},
            },
            "required": ["results"],
        },
        handler=_citation_builder,
        category="knowledge",
    ))

    register_tool(ToolDefinition(
        name="employee_lookup",
        description="Look up employee info from HR system.",
        parameters={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "The employee ID"},
            },
            "required": ["employee_id"],
        },
        handler=_employee_lookup,
        category="hr",
    ))


# Register on import
_register_all_tools()


__all__ = [
    "ToolDefinition",
    "register_tool",
    "get_tool",
    "list_tools",
    "dispatch_tool",
]
