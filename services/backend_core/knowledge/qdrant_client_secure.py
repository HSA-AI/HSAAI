"""
HSAAI Enterprise AI Platform — Secure Qdrant Client with Tenant Isolation (v9.0)
==================================================================================
Zero Trust Tenant Isolation for Qdrant vector operations.

This module provides SECURE versions of Qdrant operations that enforce:
  - Tenant Isolation (tenant_id from JWT claims only — never from user input)
  - Authorization (RBAC check via has_permission before any operation)
  - Audit Logging (every operation logged with actor, tenant, timestamp, result)
  - Input Validation (document_id validated for type, length, format)

DESIGN PRINCIPLE: Zero Trust — Never trust, always verify.
  - tenant_id is sourced EXCLUSIVELY from authenticated JWT claims
  - User-supplied tenant_id is IGNORED (or rejected on mismatch)
  - Every operation requires explicit permission check
  - Every operation is audit-logged

BACKWARD COMPATIBILITY: The original `delete_document_vectors` function in
`qdrant_client.py` is PRESERVED unchanged. This module adds a new
`delete_document_vectors_secure` function that should be used by all new
code. Existing code can be migrated incrementally.

Flow:
  JWT Claims → verify_authorization() → TenantContext → Secure Qdrant Operation
       ↑                                                          ↓
       └──────────────────────── User Input (REJECTED) ──────────┘

  User-supplied tenant_id is NEVER used. Only JWT tenant_id is trusted.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from backend_core.config import settings
from backend_core.knowledge.qdrant_client import QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL, QdrantDeleteError
from backend_core.security.rbac import has_permission

# ─── Audit Logger ──────────────────────────────────────────────────────
# Separate logger for audit events — forwarded to SIEM via Loki/Logstash.
audit_logger = logging.getLogger("hsaai.audit.qdrant")
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('{"timestamp":"%(asctime)s","level":"%(levelname)s","message":%(message)s}'))
    audit_logger.addHandler(handler)
    audit_logger.setLevel(logging.INFO)


# ─── Tenant Context ────────────────────────────────────────────────────
class TenantContextError(PermissionError):
    """Raised when tenant context is missing or invalid."""
    pass


class AuthorizationError(PermissionError):
    """Raised when caller lacks required permission."""
    pass


class ValidationError(ValueError):
    """Raised when input validation fails."""
    pass


def extract_tenant_context(claims: dict[str, Any]) -> dict[str, str]:
    """Extract tenant context from JWT claims.

    CRITICAL: This is the ONLY sanctioned way to obtain tenant_id.
    User-supplied tenant_id must NEVER be used.

    Args:
        claims: JWT claims dict from verify_authorization()

    Returns:
        Dict with tenant_id, workspace_id, user_id, department

    Raises:
        TenantContextError: If required fields are missing
    """
    if not claims:
        raise TenantContextError("Claims are required — cannot extract tenant context")

    tenant_id = claims.get("tenant_id") or claims.get("tenant") or claims.get("organization")
    if not tenant_id:
        raise TenantContextError("tenant_id missing from JWT claims — cannot proceed")

    workspace_id = claims.get("workspace_id") or claims.get("workspace") or "default"
    user_id = claims.get("sub") or claims.get("user_id") or "unknown"
    department = claims.get("department") or "default"

    return {
        "tenant_id": str(tenant_id),
        "workspace_id": str(workspace_id),
        "user_id": str(user_id),
        "department": str(department),
    }


def validate_document_id(document_id: str) -> None:
    """Validate document_id for type, length, and format.

    Args:
        document_id: The document ID to validate

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(document_id, str):
        raise ValidationError(
            f"document_id must be str, got {type(document_id).__name__}"
        )
    if not document_id:
        raise ValidationError("document_id must not be empty")
    if len(document_id) > 256:
        raise ValidationError(
            f"document_id exceeds maximum length of 256 characters (got {len(document_id)})"
        )
    # Allow alphanumeric, underscore, hyphen, dot, forward slash (for paths)
    if not re.match(r'^[a-zA-Z0-9_\-\.\/]+$', document_id):
        raise ValidationError(
            "document_id contains invalid characters "
            "(allowed: alphanumeric, _, -, ., /)"
        )


def build_tenant_scoped_filter(
    document_id: str,
    tenant_context: dict[str, str],
) -> dict[str, Any]:
    """Build a Qdrant filter that includes tenant isolation.

    The filter matches:
      - document_id == <document_id>
      - tenant_id == <tenant_id from JWT>
      - workspace_id == <workspace_id from JWT>

    This ensures a user can ONLY delete vectors that belong to their
    own tenant and workspace.

    Args:
        document_id: The document ID to delete
        tenant_context: Tenant context from extract_tenant_context()

    Returns:
        Qdrant filter dict with tenant isolation
    """
    return {
        "filter": {
            "must": [
                {"key": "document_id", "match": {"value": document_id}},
                {"key": "tenant_id", "match": {"value": tenant_context["tenant_id"]}},
                {"key": "workspace_id", "match": {"value": tenant_context["workspace_id"]}},
            ]
        }
    }


def _audit_log(
    event: str,
    tenant_context: dict[str, str],
    document_id: str,
    result: str,
    error: str | None = None,
    latency_ms: int = 0,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Create and log an audit entry.

    Args:
        event: Event type (e.g., "qdrant.delete_document_vectors")
        tenant_context: Tenant context with actor info
        document_id: The document ID affected
        result: "success" or "failed"
        error: Error message if failed
        latency_ms: Operation latency in milliseconds
        request_id: Optional request correlation ID

    Returns:
        The audit entry dict
    """
    entry = {
        "event": event,
        "actor": tenant_context["user_id"],
        "tenant_id": tenant_context["tenant_id"],
        "workspace_id": tenant_context["workspace_id"],
        "department": tenant_context["department"],
        "document_id": document_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "latency_ms": latency_ms,
        "request_id": request_id or str(uuid.uuid4()),
    }
    if error:
        entry["error"] = error[:500]

    # Log to audit logger (forwarded to SIEM)
    audit_logger.info(json.dumps(entry, ensure_ascii=False))
    return entry


def _headers() -> dict[str, str]:
    """Build Qdrant API headers with API key if configured."""
    return {"api-key": QDRANT_API_KEY} if QDRANT_API_KEY else {}


async def delete_document_vectors_secure(
    document_id: str,
    claims: dict[str, Any],
    *,
    require_permission: str = "knowledge:delete",
) -> dict[str, Any]:
    """SECURE version of delete_document_vectors with Zero Trust Tenant Isolation.

    This function enforces:
      1. Authorization: Caller must have 'knowledge:delete' permission
      2. Tenant Isolation: tenant_id sourced from JWT claims ONLY
      3. Input Validation: document_id validated for type/length/format
      4. Audit Logging: Every attempt logged with full context
      5. Error Handling: All errors caught, logged, and wrapped

    CRITICAL: The `claims` parameter must come from `verify_authorization()`.
    User-supplied tenant_id is NEVER used — only JWT tenant_id is trusted.

    Args:
        document_id: The document ID whose vectors should be deleted
        claims: JWT claims dict from verify_authorization()
        require_permission: Permission required (default: 'knowledge:delete')

    Returns:
        Qdrant response dict

    Raises:
        AuthorizationError: Caller lacks required permission
        TenantContextError: Tenant context missing from claims
        ValidationError: document_id validation failed
        QdrantDeleteError: Qdrant operation failed

    Usage:
        # In a FastAPI endpoint:
        @router.delete("/documents/{document_id}/vectors")
        async def delete_vectors(
            document_id: str,
            claims: dict = Depends(require_permission("knowledge:delete")),
        ):
            return await delete_document_vectors_secure(document_id, claims)
    """
    started = time.time()

    # ─── Step 1: Extract tenant context from JWT claims ───
    try:
        tenant_context = extract_tenant_context(claims)
    except TenantContextError as exc:
        _audit_log(
            event="qdrant.delete_document_vectors",
            tenant_context={"user_id": "unknown", "tenant_id": "unknown",
                           "workspace_id": "unknown", "department": "unknown"},
            document_id=str(document_id),
            result="failed",
            error=f"TenantContextError: {exc}",
            latency_ms=int((time.time() - started) * 1000),
        )
        raise

    # ─── Step 2: Authorization check (Zero Trust) ───
    if not has_permission(claims, require_permission):
        _audit_log(
            event="qdrant.delete_document_vectors",
            tenant_context=tenant_context,
            document_id=document_id,
            result="denied",
            error=f"AuthorizationError: caller lacks '{require_permission}' permission",
            latency_ms=int((time.time() - started) * 1000),
        )
        raise AuthorizationError(
            f"Caller '{tenant_context['user_id']}' lacks '{require_permission}' permission"
        )

    # ─── Step 3: Input validation ───
    try:
        validate_document_id(document_id)
    except ValidationError as exc:
        _audit_log(
            event="qdrant.delete_document_vectors",
            tenant_context=tenant_context,
            document_id=str(document_id),
            result="failed",
            error=f"ValidationError: {exc}",
            latency_ms=int((time.time() - started) * 1000),
        )
        raise

    # ─── Step 4: Build tenant-scoped filter ───
    payload = build_tenant_scoped_filter(document_id, tenant_context)
    url = f"{QDRANT_URL.rstrip('/')}/collections/{QDRANT_COLLECTION}/points/delete"

    # ─── Step 5: Execute Qdrant deletion ───
    try:
        async with httpx.AsyncClient(timeout=30, headers=_headers()) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        error_msg = f"Qdrant delete request failed: {exc}"
        _audit_log(
            event="qdrant.delete_document_vectors",
            tenant_context=tenant_context,
            document_id=document_id,
            result="failed",
            error=error_msg,
            latency_ms=int((time.time() - started) * 1000),
        )
        raise QdrantDeleteError(error_msg) from exc

    # ─── Step 6: Handle HTTP errors ───
    if response.status_code >= 400:
        error_msg = f"Qdrant delete failed: {response.status_code} {response.text[:500]}"
        _audit_log(
            event="qdrant.delete_document_vectors",
            tenant_context=tenant_context,
            document_id=document_id,
            result="failed",
            error=error_msg,
            latency_ms=int((time.time() - started) * 1000),
        )
        raise QdrantDeleteError(error_msg)

    # ─── Step 7: Parse response ───
    try:
        result = response.json()
    except json.JSONDecodeError as exc:
        error_msg = f"Qdrant returned invalid JSON: {exc}"
        _audit_log(
            event="qdrant.delete_document_vectors",
            tenant_context=tenant_context,
            document_id=document_id,
            result="failed",
            error=error_msg,
            latency_ms=int((time.time() - started) * 1000),
        )
        raise QdrantDeleteError(error_msg) from exc

    # ─── Step 8: Audit log success ───
    _audit_log(
        event="qdrant.delete_document_vectors",
        tenant_context=tenant_context,
        document_id=document_id,
        result="success",
        latency_ms=int((time.time() - started) * 1000),
    )

    return result


async def search_vectors_secure(
    query_vector: list[float],
    claims: dict[str, Any],
    *,
    limit: int = 10,
    score_threshold: float | None = None,
    require_permission: str = "knowledge:read",
) -> dict[str, Any]:
    """SECURE vector search with tenant isolation.

    Ensures search results are scoped to the caller's tenant and workspace.
    A user from Tenant A can NEVER retrieve vectors from Tenant B.

    Args:
        query_vector: The query embedding vector
        claims: JWT claims dict from verify_authorization()
        limit: Maximum number of results
        score_threshold: Optional minimum score threshold
        require_permission: Permission required (default: 'knowledge:read')

    Returns:
        Qdrant search response dict

    Raises:
        AuthorizationError: Caller lacks required permission
        TenantContextError: Tenant context missing from claims
        QdrantDeleteError: Qdrant operation failed
    """
    started = time.time()

    # Step 1: Extract tenant context
    tenant_context = extract_tenant_context(claims)

    # Step 2: Authorization check
    if not has_permission(claims, require_permission):
        _audit_log(
            event="qdrant.search_vectors",
            tenant_context=tenant_context,
            document_id="(search)",
            result="denied",
            error=f"AuthorizationError: caller lacks '{require_permission}' permission",
            latency_ms=int((time.time() - started) * 1000),
        )
        raise AuthorizationError(
            f"Caller '{tenant_context['user_id']}' lacks '{require_permission}' permission"
        )

    # Step 3: Build tenant-scoped search filter
    search_filter = {
        "must": [
            {"key": "tenant_id", "match": {"value": tenant_context["tenant_id"]}},
            {"key": "workspace_id", "match": {"value": tenant_context["workspace_id"]}},
        ]
    }

    payload: dict[str, Any] = {
        "vector": query_vector,
        "filter": search_filter,
        "limit": limit,
    }
    if score_threshold is not None:
        payload["score_threshold"] = score_threshold

    url = f"{QDRANT_URL.rstrip('/')}/collections/{QDRANT_COLLECTION}/points/search"

    # Step 4: Execute search
    try:
        async with httpx.AsyncClient(timeout=30, headers=_headers()) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        error_msg = f"Qdrant search request failed: {exc}"
        _audit_log(
            event="qdrant.search_vectors",
            tenant_context=tenant_context,
            document_id="(search)",
            result="failed",
            error=error_msg,
            latency_ms=int((time.time() - started) * 1000),
        )
        raise QdrantDeleteError(error_msg) from exc

    if response.status_code >= 400:
        error_msg = f"Qdrant search failed: {response.status_code} {response.text[:500]}"
        _audit_log(
            event="qdrant.search_vectors",
            tenant_context=tenant_context,
            document_id="(search)",
            result="failed",
            error=error_msg,
            latency_ms=int((time.time() - started) * 1000),
        )
        raise QdrantDeleteError(error_msg)

    try:
        result = response.json()
    except json.JSONDecodeError as exc:
        raise QdrantDeleteError(f"Qdrant returned invalid JSON: {exc}") from exc

    _audit_log(
        event="qdrant.search_vectors",
        tenant_context=tenant_context,
        document_id="(search)",
        result="success",
        latency_ms=int((time.time() - started) * 1000),
    )

    return result


def reject_user_supplied_tenant_id(
    claims_tenant_id: str,
    user_supplied_tenant_id: str | None,
) -> None:
    """Reject requests where user-supplied tenant_id mismatches JWT tenant_id.

    CRITICAL SECURITY: This function enforces that tenant_id comes ONLY from
    JWT claims. If a user attempts to specify a different tenant_id in the
    request body, query params, or headers, the request is rejected.

    Args:
        claims_tenant_id: tenant_id from JWT claims (trusted)
        user_supplied_tenant_id: tenant_id from user input (untrusted)

    Raises:
        TenantContextError: If user_supplied_tenant_id doesn't match claims
    """
    if user_supplied_tenant_id is None:
        return  # No user-supplied tenant_id — OK

    if user_supplied_tenant_id != claims_tenant_id:
        raise TenantContextError(
            f"Tenant ID mismatch: JWT claims tenant_id='{claims_tenant_id}' "
            f"but request specified tenant_id='{user_supplied_tenant_id}'. "
            f"Cross-tenant access is forbidden."
        )
