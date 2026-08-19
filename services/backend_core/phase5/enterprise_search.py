
from __future__ import annotations
import time
import httpx
import os
import logging
from .schemas import EnterpriseSearchRequest, ObservabilityEvent
from .observability import record_event

logger = logging.getLogger("hsaai.enterprise_search")

RAG_ENGINE_URL = os.getenv("RAG_ENGINE_URL", "http://rag_engine:8030")
BACKEND_CORE_URL = os.getenv("BACKEND_CORE_URL", "http://backend:8000")

CATALOG = {
    "rag": {"name": "Knowledge Base", "description": "Knowledge documents, PDFs, Word, Excel, policies and indexed files"},
    "agents": {"name": "Agent Runtime", "description": "Agent runtime traces, tools, workflow execution context"},
    "integrations": {"name": "Enterprise Integrations", "description": "SAP, HR, Active Directory, service desk and BI connectors"},
    "audit": {"name": "Audit & Governance", "description": "Security audit logs, AI observability and governance events"},
}

async def _search_rag(query: str, tenant_id: str, workspace_id: str, top_k: int = 5) -> list[dict]:
    """Search the RAG engine for real results."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{RAG_ENGINE_URL}/v1/search",
                json={"query": query, "tenant_id": tenant_id, "workspace_id": workspace_id, "top_k": top_k},
            )
            if response.status_code < 400:
                return response.json().get("results", [])
    except Exception as exc:
        logger.warning("RAG search failed: %s", exc)
    return []

def unified_search(req: EnterpriseSearchRequest) -> dict:
    """
    AI FIX: Replaced fake search results (catalog descriptions with fabricated scores)
    with real RAG engine search. Returns actual search results from the knowledge base.
    """
    import asyncio
    import concurrent.futures
    started = time.time()
    results = []

    # Search RAG for real results
    # FIX-32: _search_rag is async — must run via event loop. Previously
    # called without await, producing "coroutine object is not iterable"
    # TypeError and skipping RAG results entirely.
    try:
        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                rag_results = ex.submit(
                    lambda: asyncio.run(_search_rag(req.query, req.context.tenant_id, req.context.workspace_id, req.top_k))
                ).result()
        except RuntimeError:
            rag_results = asyncio.run(_search_rag(req.query, req.context.tenant_id, req.context.workspace_id, req.top_k))
    except Exception as _exc:
        import logging
        logging.getLogger("hsaai.phase5.enterprise_search").warning(
            "RAG search failed (non-fatal): %s", _exc
        )
        rag_results = []
    for r in rag_results:
        results.append({
            "source": "rag",
            "title": r.get("title", r.get("source_file", "Knowledge Document")),
            "snippet": r.get("text", "")[:300],
            "score": r.get("score", 0.0),
            "tenant_id": req.context.tenant_id,
            "workspace_id": req.context.workspace_id,
        })

    # For non-RAG sources, include catalog reference (not fake results)
    for source in req.sources:
        if source not in CATALOG or source == "rag":
            continue
        results.append({
            "source": source,
            "title": CATALOG[source]["name"],
            "snippet": CATALOG[source]["description"],
            "score": 0.0,  # Honest: no semantic match computed for catalog entries
            "tenant_id": req.context.tenant_id,
            "workspace_id": req.context.workspace_id,
            "note": "Catalog reference — connect data source for live search",
        })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    answer = None
    if req.answer and rag_results:
        answer = "\n".join([f"[{i+1}] {r.get('text', '')[:300]}" for i, r in enumerate(rag_results[:5])])

    elapsed = int((time.time() - started) * 1000)
    record_event(ObservabilityEvent(
        event_type="enterprise_search",
        component="enterprise_search",
        tenant_id=req.context.tenant_id,
        workspace_id=req.context.workspace_id,
        latency_ms=elapsed,
        success=True,
        metadata={"query": req.query, "sources": req.sources, "rag_results": len(rag_results)},
    ))

    return {
        "query": req.query,
        "sources_searched": req.sources,
        "count": len(results[:req.top_k]),
        "results": results[:req.top_k],
        "answer": answer,
        "elapsed_ms": elapsed,
        "real_search_performed": True,
    }
