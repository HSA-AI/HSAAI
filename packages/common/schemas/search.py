"""
HSAAI canonical SearchRequest schema.

FIX FIX-MEDIUM-QUALITY (Issue 5): single source of truth for the search
request payload. Previously three divergent copies lived in:
  - services/rag_engine/main.py
  - services/backend_core/enterprise_os/router.py
  - services/backend_core/enterprise_search/router.py

Per-service extensions (sources/search_type, department/classification/space_id,
user_id/user_roles/top_k/mode) are added by subclassing this canonical model,
preserving the exact wire-shape of each existing endpoint.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Canonical HSAAI search request.

    Only `query` is universally required. Services that need tenant scoping,
    ACL fields, top_k, mode, filters, etc. should subclass and add them so
    the canonical model stays backward-compatible with every existing caller.
    """
    query: str = Field(..., min_length=1)
