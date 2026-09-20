from typing import Any


def format_citations(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations = []
    for item in results:
        payload = item.get("payload", item)
        citations.append({
            "document_id": payload.get("document_id"),
            "filename": payload.get("filename"),
            "chunk_id": payload.get("chunk_id"),
            "page": payload.get("page"),
            "score": item.get("score"),
        })
    return citations


def enforce_cited_answer(answer: str, citations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "answer": answer,
        "citations": citations,
        "citation_required": True,
        "policy": "Enterprise RAG answers must include source citations when generated from documents.",
    }


def require_citations(answer: str, sources: list[dict[str, Any]]) -> str:
    """Return a human-readable answer that keeps citation policy explicit.

    This helper is intentionally lightweight so the core chat path can enforce
    a visible source section without changing the existing API contract.
    """
    if not sources:
        return answer
    if "المصادر" in answer or "Sources" in answer:
        return answer
    lines = []
    for idx, source in enumerate(sources, start=1):
        filename = source.get("filename") or "unknown"
        chunk = source.get("chunk_index", source.get("chunk_id", 0))
        lines.append(f"[{idx}] {filename}#chunk-{chunk}")
    return f"{answer}\n\nالمصادر:\n" + "\n".join(lines)
