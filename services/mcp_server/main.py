"""
HSAAI MCP Server (v3.0)

Model Context Protocol (MCP) server implementation for HSAAI.
Allows external MCP-compatible clients (Claude Desktop, Cursor, Cline, etc.)
to access HSAAI's knowledge base, agents, and tools.

Implements the MCP 2024-11-05 specification:
  - Tools: callable functions exposed to LLMs
  - Resources: readable data sources
  - Prompts: reusable prompt templates

Architecture:
  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
  │  Claude /   │  MCP    │  HSAAI MCP  │  HTTP   │  HSAAI      │
  │  Cursor /   │◄───────►│  Server     │◄───────►│  Services   │
  │  Cline      │  JSON   │  :8094      │         │  (RAG, LLM, │
  └─────────────┘  -RPC   └─────────────┘         │  Agents)    │
                                                └─────────────┘

Usage:
    # Start the MCP server
    cd services/mcp_server
    uvicorn main:app --host 0.0.0.0 --port 8094

    # Configure in Claude Desktop (claude_desktop_config.json):
    {
      "mcpServers": {
        "hsaai": {
          "url": "http://localhost:8094/mcp"
        }
      }
    }
"""
import os
import sys
import json
import logging
from typing import Any
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add packages/ for shared auth
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
    _AUTH_AVAILABLE = True
except ImportError as _e:
    _AUTH_AVAILABLE = False
    _AUTH_LOAD_ERROR = str(_e)
    async def _auth_dep():  # type: ignore
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Authentication module unavailable. Service cannot accept requests.")

# FIX S-16: Import prompt injection scanner. The hsaai_llm_generate tool was
# forwarding raw, un-scanned user prompts straight to the LLM gateway — a
# prompt-injection / prompt-leakage vector. scan_prompt() enforces a max
# length cap, detects injection patterns, neutralizes instruction markers,
# and returns a verdict we can convert into an HTTP 400.
try:
    from common.prompt_security import scan_prompt as _scan_prompt
    _PROMPT_SECURITY_AVAILABLE = True
except ImportError as _e:  # pragma: no cover - import guard
    _PROMPT_SECURITY_AVAILABLE = False
    _PROMPT_SECURITY_LOAD_ERROR = str(_e)
    _scan_prompt = None  # type: ignore

# FIX S-16: Hard cap on prompt length forwarded to the LLM gateway.
_PROMPT_MAX_LENGTH = int(os.getenv("MCP_PROMPT_MAX_LENGTH", "8000"))

logger = logging.getLogger("hsaai.mcp")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="HSAAI MCP Server",
    version="4.0.0",
    description="Model Context Protocol server — exposes HSAAI tools/resources to external AI clients",
)

# Service URLs (internal)
RAG_ENGINE_URL = os.getenv("RAG_ENGINE_URL", "http://rag_engine:8030")
LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm_gateway:8090")
AI_ORCHESTRATOR_URL = os.getenv("AI_ORCHESTRATOR_URL", "http://ai_orchestrator:8020")
MULTI_AGENTS_URL = os.getenv("MULTI_AGENTS_URL", "http://multi_agents:8040")
WORKFLOW_ENGINE_URL = os.getenv("WORKFLOW_ENGINE_URL", "http://workflow_engine:8050")


# ─── MCP Protocol Types ───

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str
    method: str
    params: dict | None = None


class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    result: dict | None = None
    error: dict | None = None


# ─── MCP Tools (callable functions exposed to LLMs) ───

MCP_TOOLS = [
    {
        "name": "hsaai_knowledge_search",
        "description": "Search the HSAAI enterprise knowledge base. Returns relevant document chunks with citations. Use this to answer questions about company policies, procedures, documents, and internal knowledge.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (can be in Arabic or English)",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5, max: 20)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "hsaai_ask_agent",
        "description": "Ask a specific HSAAI department agent (HR, Finance, IT, Legal, Executive) a question. The agent will use the knowledge base to provide a grounded answer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "enum": ["hr", "finance", "it", "legal", "executive", "general"],
                    "description": "The department agent to route the question to",
                },
                "query": {
                    "type": "string",
                    "description": "The question to ask",
                },
            },
            "required": ["agent", "query"],
        },
    },
    {
        "name": "hsaai_llm_generate",
        "description": "Generate text using the HSAAI local LLM (Ollama qwen3:8b). Use for general-purpose text generation, summarization, or translation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The prompt to generate from"},
                "system": {"type": "string", "description": "System prompt", "default": ""},
                "max_tokens": {"type": "integer", "default": 1024},
                "temperature": {"type": "number", "default": 0.7},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "hsaai_workflow_start",
        "description": "Start an HSAAI workflow by its template key. Available templates: purchase_request, document_approval, leave_request, it_ticket.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_key": {
                    "type": "string",
                    "enum": ["purchase_request", "document_approval", "leave_request", "it_ticket"],
                    "description": "The workflow template to start",
                },
                "inputs": {
                    "type": "object",
                    "description": "Input parameters for the workflow",
                },
            },
            "required": ["workflow_key"],
        },
    },
    {
        "name": "hsaai_compliance_report",
        "description": "Generate a compliance report (SOX, GDPR, NDMO, PDPL) for a specified period. Only available to auditor/admin roles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "framework": {
                    "type": "string",
                    "enum": ["SOX", "GDPR", "NDMO", "PDPL"],
                    "description": "The compliance framework",
                },
                "start_date": {"type": "string", "description": "ISO date: YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "ISO date: YYYY-MM-DD"},
            },
            "required": ["framework", "start_date", "end_date"],
        },
    },
]


# ─── MCP Resources (readable data sources) ───

MCP_RESOURCES = [
    {
        "uri": "hsaai://knowledge/stats",
        "name": "Knowledge Base Statistics",
        "description": "Statistics about the HSAAI knowledge base (document count, chunk count, etc.)",
        "mimeType": "application/json",
    },
    {
        "uri": "hsaai://agents/list",
        "name": "Available Department Agents",
        "description": "List of HSAAI department agents and their capabilities",
        "mimeType": "application/json",
    },
    {
        "uri": "hsaai://workflow/templates",
        "name": "Workflow Templates",
        "description": "List of available workflow templates",
        "mimeType": "application/json",
    },
    {
        "uri": "hsaai://models/list",
        "name": "Available LLM Models",
        "description": "List of LLM models available via the HSAAI LLM Gateway",
        "mimeType": "application/json",
    },
]


# ─── Health ───

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "mcp_server",
        "version": "3.0.0",
        "protocol_version": "2024-11-05",
        "tools_count": len(MCP_TOOLS),
        "resources_count": len(MCP_RESOURCES),
    }


# ─── MCP JSON-RPC Endpoint ───

@app.post("/mcp")
async def mcp_handle(request: MCPRequest, claims: dict = Depends(_auth_dep)):
    """Handle MCP JSON-RPC requests.

    Supports methods:
      - initialize: handshake
      - tools/list: list available tools
      - tools/call: invoke a tool
      - resources/list: list available resources
      - resources/read: read a resource
      - prompts/list: list prompt templates
    """
    method = request.method
    params = request.params or {}

    if method == "initialize":
        return _ok(request.id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False, "subscribe": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": "hsaai-mcp-server",
                "version": "3.0.0",
            },
        })

    elif method == "tools/list":
        return _ok(request.id, {"tools": MCP_TOOLS})

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        return await _call_tool(request.id, tool_name, tool_args, claims)

    elif method == "resources/list":
        return _ok(request.id, {"resources": MCP_RESOURCES})

    elif method == "resources/read":
        uri = params.get("uri", "")
        return await _read_resource(request.id, uri, claims)

    elif method == "prompts/list":
        return _ok(request.id, {"prompts": []})

    else:
        return _error(request.id, -32601, f"Method not found: {method}")


# ─── Tool Implementation ───

async def _call_tool(req_id, name: str, args: dict, claims: dict) -> MCPResponse:
    """Execute an MCP tool call."""
    tenant_id = claims.get("tenant_id", "default")
    workspace_id = claims.get("workspace_id", "default")

    try:
        if name == "hsaai_knowledge_search":
            query = args.get("query", "")
            top_k = min(args.get("top_k", 5), 20)
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{RAG_ENGINE_URL}/v1/search",
                    json={
                        "query": query,
                        "tenant_id": tenant_id,
                        "workspace_id": workspace_id,
                        "top_k": top_k,
                        "mode": "hybrid",
                    },
                )
                if resp.status_code >= 400:
                    return _error(req_id, -32603, f"RAG search failed: HTTP {resp.status_code}")
                data = resp.json()
                results = data.get("results", [])
                text_result = "\n\n".join([
                    f"[{i+1}] {r.get('filename', 'unknown')} (chunk {r.get('chunk_index', '?')}):\n{r.get('text', '')[:500]}"
                    for i, r in enumerate(results)
                ])
                return _ok(req_id, {
                    "content": [{"type": "text", "text": text_result or "No results found."}],
                    "isError": False,
                })

        elif name == "hsaai_ask_agent":
            agent = args.get("agent", "general")
            query = args.get("query", "")
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{MULTI_AGENTS_URL}/v1/run",
                    json={
                        "message": query,
                        "preferred_agent": agent,
                        "tenant_id": tenant_id,
                        "workspace_id": workspace_id,
                    },
                )
                if resp.status_code >= 400:
                    return _error(req_id, -32603, f"Agent run failed: HTTP {resp.status_code}")
                data = resp.json()
                answer = data.get("answer", "No answer generated.")
                return _ok(req_id, {
                    "content": [{"type": "text", "text": answer}],
                    "isError": False,
                })

        elif name == "hsaai_llm_generate":
            prompt = args.get("prompt", "")
            system = args.get("system", "You are HSAAI, a private enterprise AI assistant.")
            max_tokens = args.get("max_tokens", 1024)
            temperature = args.get("temperature", 0.7)

            # FIX S-16: Scan the prompt BEFORE forwarding to the LLM gateway.
            # Reject (HTTP 400) if the prompt is too long or matches injection
            # patterns. Always log the submission for auditability.
            caller_sub = claims.get("sub", "unknown")
            if not _PROMPT_SECURITY_AVAILABLE:
                logger.error(
                    "hsaai_llm_generate blocked: prompt_security module unavailable "
                    "(import error: %s) — refusing to forward un-scanned prompt",
                    _PROMPT_SECURITY_LOAD_ERROR,
                )
                raise HTTPException(
                    status_code=503,
                    detail="Prompt security scanner unavailable — refusing to forward un-scanned prompt",
                )

            scan_result = _scan_prompt(prompt, max_length=_PROMPT_MAX_LENGTH)
            logger.info(
                "hsaai_llm_generate prompt submitted: tenant=%s user=%s "
                "prompt_len=%d sanitized_len=%d risk=%.2f blocked=%s reason=%s",
                tenant_id, caller_sub, len(prompt), len(scan_result.sanitized),
                scan_result.risk_score, scan_result.blocked, scan_result.reason or "none",
            )
            if scan_result.blocked:
                # FIX S-16: surface as HTTP 400 so the MCP client sees a clear
                # rejection rather than a silent LLM-side filter or an MCP error.
                raise HTTPException(
                    status_code=400,
                    detail=f"Prompt rejected by security scan: {scan_result.reason}",
                )
            prompt = scan_result.sanitized

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{LLM_GATEWAY_URL}/v1/generate",
                    json={
                        "prompt": prompt,
                        "system": system,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "tenant_id": tenant_id,
                    },
                )
                if resp.status_code >= 400:
                    return _error(req_id, -32603, f"LLM generation failed: HTTP {resp.status_code}")
                data = resp.json()
                text = data.get("text", "")
                return _ok(req_id, {
                    "content": [{"type": "text", "text": text}],
                    "isError": False,
                })

        elif name == "hsaai_workflow_start":
            workflow_key = args.get("workflow_key", "")
            inputs = args.get("inputs", {})
            async with httpx.AsyncClient(timeout=30) as client:
                # FIX v2.1 (P0): workflow_engine exposes /workflows/run, not /workflows/start.
                # The previous path was a contract drift bug that broke the MCP tool at runtime.
                resp = await client.post(
                    f"{WORKFLOW_ENGINE_URL}/workflows/run",
                    json={
                        "workflow_key": workflow_key,
                        "inputs": inputs,
                        "tenant_id": tenant_id,
                        "workspace_id": workspace_id,
                    },
                )
                if resp.status_code >= 400:
                    return _error(req_id, -32603, f"Workflow start failed: HTTP {resp.status_code}")
                data = resp.json()
                return _ok(req_id, {
                    "content": [{"type": "text", "text": json.dumps(data, indent=2)}],
                    "isError": False,
                })

        elif name == "hsaai_compliance_report":
            framework = args.get("framework", "GDPR")
            start_date = args.get("start_date", "")
            end_date = args.get("end_date", "")
            # FIX v2.1 (P0): compliance_reports service was never deployed (only a sub-module
            # of backend_core per CONSOLIDATION_LOG.md). Route the request to backend_core's
            # compliance endpoint instead, which exists and is deployed.
            BACKEND_CORE_URL = os.getenv("BACKEND_CORE_URL", "http://backend-core:8000")
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{BACKEND_CORE_URL}/v1/compliance/generate",
                    json={
                        "framework": framework,
                        "start_date": start_date,
                        "end_date": end_date,
                        "tenant_id": tenant_id,
                    },
                )
                if resp.status_code >= 400:
                    return _error(req_id, -32603, f"Compliance report failed: HTTP {resp.status_code}")
                data = resp.json()
                return _ok(req_id, {
                    "content": [{"type": "text", "text": json.dumps(data, indent=2, default=str)}],
                    "isError": False,
                })

        else:
            return _error(req_id, -32602, f"Unknown tool: {name}")

    except httpx.HTTPError as exc:
        logger.exception("Tool call HTTP error")
        return _error(req_id, -32603, f"Network error: {exc}")
    except HTTPException:
        # FIX S-16: re-raise so FastAPI converts it to the proper HTTP status
        # (e.g. 400 for a blocked prompt). The bare `except Exception` below
        # would otherwise swallow it and turn it into an MCP -32603 error.
        raise
    except Exception as exc:
        logger.exception("Tool call error")
        return _error(req_id, -32603, f"Internal error: {exc}")


# ─── Resource Reading ───

async def _read_resource(req_id, uri: str, claims: dict) -> MCPResponse:
    """Read an MCP resource by URI."""
    try:
        if uri == "hsaai://knowledge/stats":
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(f"{RAG_ENGINE_URL}/v1/analytics", json={
                    "tenant_id": claims.get("tenant_id", "default"),
                    "workspace_id": claims.get("workspace_id", "default"),
                })
                data = resp.json() if resp.status_code < 400 else {"error": "unavailable"}
            return _ok(req_id, {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(data, indent=2)}]})

        elif uri == "hsaai://agents/list":
            agents = [
                {"name": "HR Agent", "key": "hr", "description": "Human Resources policies, leave, payroll"},
                {"name": "Finance Agent", "key": "finance", "description": "Budgets, invoices, financial reports"},
                {"name": "IT Agent", "key": "it", "description": "IT support, tickets, technical issues"},
                {"name": "Legal Agent", "key": "legal", "description": "Legal documents, compliance, contracts"},
                {"name": "Executive Agent", "key": "executive", "description": "Strategic KPIs, executive summaries"},
                {"name": "General Agent", "key": "general", "description": "General-purpose assistant"},
            ]
            return _ok(req_id, {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(agents, indent=2)}]})

        elif uri == "hsaai://workflow/templates":
            templates = [
                {"key": "purchase_request", "name": "Purchase Request", "steps": ["SAP check", "Manager approval", "Finance review"]},
                {"key": "document_approval", "name": "Document Approval", "steps": ["Classify", "Review", "Approve", "Publish"]},
                {"key": "leave_request", "name": "Leave Request", "steps": ["SuccessFactors", "Manager approval", "HR review"]},
                {"key": "it_ticket", "name": "IT Support Ticket", "steps": ["Service Desk", "Jira", "SLA tracking"]},
            ]
            return _ok(req_id, {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(templates, indent=2)}]})

        elif uri == "hsaai://models/list":
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{LLM_GATEWAY_URL}/v1/models")
                data = resp.json() if resp.status_code < 400 else {"models": []}
            return _ok(req_id, {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(data, indent=2)}]})

        else:
            return _error(req_id, -32602, f"Unknown resource URI: {uri}")

    except Exception as exc:
        logger.exception("Resource read error")
        return _error(req_id, -32603, f"Internal error: {exc}")


# ─── Helpers ───

def _ok(req_id, result: dict) -> MCPResponse:
    return MCPResponse(jsonrpc="2.0", id=req_id, result=result)


def _error(req_id, code: int, message: str) -> MCPResponse:
    return MCPResponse(jsonrpc="2.0", id=req_id, error={"code": code, "message": message})


if __name__ == "__main__":
    # FIX v2.2 (Phase 2): mTLS support via shared helper.
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..', 'packages'))
    try:
        from common.security.mtls_server import run_with_mtls
        run_with_mtls("mcp_server.main:app", host="0.0.0.0", port=8094)
    except ImportError:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8094)
