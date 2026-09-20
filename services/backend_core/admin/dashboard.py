"""
HSAAI Admin Dashboard Stats — Production Grade (v5.0)

FIX v5.0 (P0): Replaced hardcoded fake metrics with real database queries.
Previously returned {users: 10, messages: 500} — fabricated numbers
presented as real platform stats on the /admin endpoint.
"""
import os
import logging
from typing import Any

logger = logging.getLogger("hsaai.admin")


def stats() -> dict[str, Any]:
    """Get real platform statistics from the database.

    Queries the actual tables for user count, message count, and document count.
    Falls back to zeros if the database is unavailable (e.g., during startup).
    """
    try:
        from backend_core.db.database import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            # Query real counts from the database.
            result = db.execute(text("SELECT COUNT(*) FROM messages")).scalar()
            messages_count = int(result) if result else 0

            # Try to get document count from knowledge_documents.
            try:
                doc_result = db.execute(text("SELECT COUNT(*) FROM knowledge_documents")).scalar()
                rag_documents = int(doc_result) if doc_result else 0
            except Exception:
                rag_documents = 0

            # Try to get workspace count from knowledge_spaces.
            try:
                ws_result = db.execute(text("SELECT COUNT(*) FROM knowledge_spaces")).scalar()
                workspaces = int(ws_result) if ws_result else 0
            except Exception:
                workspaces = 0

            # Users are managed by Keycloak — we can't query them directly.
            # Return 0 and let the frontend query Keycloak admin API.
            users = 0

            return {
                "platform": "HSAAI",
                "health": "operational",
                "active_agents": ["HR", "Finance", "Executive", "Knowledge", "General"],
                "metrics": {
                    "users": users,
                    "messages": messages_count,
                    "rag_documents": rag_documents,
                    "workspaces": workspaces,
                },
                "data_source": "database",
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning("Failed to query database for stats: %s — returning zeros", e)
        return {
            "platform": "HSAAI",
            "health": "degraded",
            "active_agents": [],
            "metrics": {"users": 0, "messages": 0, "rag_documents": 0, "workspaces": 0},
            "data_source": "unavailable",
            "error": str(e)[:200],
        }
