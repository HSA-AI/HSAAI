"""
HSAAI Enterprise AI Platform — Secure Qdrant Tenant Isolation Test Suite (v9.0)
===============================================================================
Production-Ready Enterprise tests for Zero Trust Tenant Isolation in
`services/backend_core/knowledge/qdrant_client_secure.py`.

Functions under test:
  - extract_tenant_context() — tenant context from JWT claims only
  - validate_document_id() — input validation
  - build_tenant_scoped_filter() — Qdrant filter with tenant isolation
  - reject_user_supplied_tenant_id() — cross-tenant access prevention
  - delete_document_vectors_secure() — secure deletion with full Zero Trust
  - search_vectors_secure() — secure search with tenant scoping

Zero Trust Principles Verified:
  - tenant_id sourced EXCLUSIVELY from JWT claims
  - User-supplied tenant_id REJECTED on mismatch
  - Authorization required before any operation
  - Input validation enforced
  - Audit logging for every operation
  - Cross-tenant access blocked

Test Categories:
  1. Tenant Context Extraction Tests
  2. Input Validation Tests
  3. Tenant-Scoped Filter Tests
  4. Cross-Tenant Access Rejection Tests
  5. Authorization Enforcement Tests
  6. Audit Logging Tests
  7. Secure Deletion Tests (delete_document_vectors_secure)
  8. Secure Search Tests (search_vectors_secure)
  9. Error Handling Tests
  10. Async Quality Tests

Rules:
  - No real Qdrant (all HTTP mocked)
  - No real Keycloak (claims passed directly)
  - pytest-asyncio with proper await
  - Independent tests
"""
from __future__ import annotations

import json
import sys
import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import httpx

_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.knowledge.qdrant_client_secure import (  # noqa: E402
    AuthorizationError,
    TenantContextError,
    ValidationError,
    build_tenant_scoped_filter,
    delete_document_vectors_secure,
    extract_tenant_context,
    reject_user_supplied_tenant_id,
    search_vectors_secure,
    validate_document_id,
)
from backend_core.knowledge.qdrant_client import QdrantDeleteError  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════
# Dummy HTTP Client (mocked httpx.AsyncClient)
# ═══════════════════════════════════════════════════════════════════════
class DummyResponse:
    def __init__(self, status_code: int = 200, json_data: Any = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {"status": "ok"}
        self.text = text or json.dumps(self._json_data)

    def json(self) -> Any:
        return self._json_data


class DummyAsyncClient:
    def __init__(self, *args: Any, response: DummyResponse | None = None,
                 exception: Exception | None = None, **kwargs: Any) -> None:
        self.response = response or DummyResponse(200, {"status": "ok"})
        self.exception = exception
        self.url: str | None = None
        self.payload: dict | None = None
        self.method: str | None = None
        self.kwargs = kwargs

    async def __aenter__(self) -> "DummyAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def post(self, url: str, json: dict | None = None, **kwargs: Any) -> DummyResponse:
        self.url = url
        self.payload = json
        self.method = "POST"
        if self.exception is not None:
            raise self.exception
        return self.response


@pytest.fixture
def patch_async_client(monkeypatch):
    """Patch httpx.AsyncClient in the secure module."""
    state: dict[str, Any] = {"client": None}

    def _patch(response: DummyResponse | None = None, exception: Exception | None = None):
        client = DummyAsyncClient(response=response, exception=exception)
        state["client"] = client

        def _factory(*args: Any, **kwargs: Any) -> DummyAsyncClient:
            client.kwargs = kwargs
            return client

        import backend_core.knowledge.qdrant_client_secure as secure_module
        monkeypatch.setattr(secure_module.httpx, "AsyncClient", _factory)
        return client

    return _patch


@pytest.fixture
def clean_qdrant_config(monkeypatch):
    """Reset Qdrant config to known defaults."""
    import backend_core.knowledge.qdrant_client_secure as secure_module
    monkeypatch.setattr(secure_module, "QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setattr(secure_module, "QDRANT_COLLECTION", "hsaai_knowledge")
    monkeypatch.setattr(secure_module, "QDRANT_API_KEY", None)


@pytest.fixture
def admin_claims():
    """JWT claims for hsaai_admin (full access)."""
    return {
        "sub": "admin-user-123",
        "tenant_id": "company_a",
        "workspace_id": "ws_default",
        "department": "it",
        "realm_access": {"roles": ["hsaai_admin"]},
    }


@pytest.fixture
def ai_user_claims():
    """JWT claims for ai_user (standard user)."""
    return {
        "sub": "user-456",
        "tenant_id": "company_a",
        "workspace_id": "ws_default",
        "department": "finance",
        "realm_access": {"roles": ["ai_user"]},
    }


@pytest.fixture
def knowledge_admin_claims():
    """JWT claims for knowledge_admin."""
    return {
        "sub": "kb-admin-789",
        "tenant_id": "company_a",
        "workspace_id": "ws_default",
        "department": "knowledge",
        "realm_access": {"roles": ["knowledge_admin"]},
    }


@pytest.fixture
def tenant_b_claims():
    """JWT claims for a user in Tenant B (different tenant)."""
    return {
        "sub": "user-tenant-b",
        "tenant_id": "company_b",
        "workspace_id": "ws_default",
        "department": "finance",
        "realm_access": {"roles": ["hsaai_admin"]},
    }


# ═══════════════════════════════════════════════════════════════════════
# Section 1: Tenant Context Extraction Tests
# ═══════════════════════════════════════════════════════════════════════
class TestExtractTenantContext:
    """Test tenant context extraction from JWT claims."""

    def test_extracts_tenant_id_from_claims(self, admin_claims):
        ctx = extract_tenant_context(admin_claims)
        assert ctx["tenant_id"] == "company_a"

    def test_extracts_workspace_id_from_claims(self, admin_claims):
        ctx = extract_tenant_context(admin_claims)
        assert ctx["workspace_id"] == "ws_default"

    def test_extracts_user_id_from_sub(self, admin_claims):
        ctx = extract_tenant_context(admin_claims)
        assert ctx["user_id"] == "admin-user-123"

    def test_extracts_department_from_claims(self, admin_claims):
        ctx = extract_tenant_context(admin_claims)
        assert ctx["department"] == "it"

    def test_tenant_id_from_tenant_field(self):
        """Claims with 'tenant' (not 'tenant_id') — supported."""
        claims = {"sub": "u1", "tenant": "company_c"}
        ctx = extract_tenant_context(claims)
        assert ctx["tenant_id"] == "company_c"

    def test_tenant_id_from_organization_field(self):
        """Claims with 'organization' — supported."""
        claims = {"sub": "u1", "organization": "company_d"}
        ctx = extract_tenant_context(claims)
        assert ctx["tenant_id"] == "company_d"

    def test_workspace_defaults_to_default_when_missing(self):
        claims = {"sub": "u1", "tenant_id": "t1"}
        ctx = extract_tenant_context(claims)
        assert ctx["workspace_id"] == "default"

    def test_user_id_defaults_to_unknown_when_missing(self):
        claims = {"tenant_id": "t1"}
        ctx = extract_tenant_context(claims)
        assert ctx["user_id"] == "unknown"

    def test_department_defaults_to_default_when_missing(self):
        claims = {"sub": "u1", "tenant_id": "t1"}
        ctx = extract_tenant_context(claims)
        assert ctx["department"] == "default"

    def test_none_claims_raises(self):
        with pytest.raises(TenantContextError, match="Claims are required"):
            extract_tenant_context(None)  # type: ignore[arg-type]

    def test_empty_claims_raises(self):
        with pytest.raises(TenantContextError, match="Claims are required"):
            extract_tenant_context({})

    def test_missing_tenant_id_raises(self):
        with pytest.raises(TenantContextError, match="tenant_id missing"):
            extract_tenant_context({"sub": "u1"})

    def test_empty_tenant_id_raises(self):
        with pytest.raises(TenantContextError, match="tenant_id missing"):
            extract_tenant_context({"sub": "u1", "tenant_id": ""})

    def test_returns_string_types(self, admin_claims):
        ctx = extract_tenant_context(admin_claims)
        assert isinstance(ctx["tenant_id"], str)
        assert isinstance(ctx["workspace_id"], str)
        assert isinstance(ctx["user_id"], str)
        assert isinstance(ctx["department"], str)


# ═══════════════════════════════════════════════════════════════════════
# Section 2: Input Validation Tests
# ═══════════════════════════════════════════════════════════════════════
class TestValidateDocumentId:
    """Test document_id input validation."""

    def test_valid_document_id_accepted(self):
        validate_document_id("doc_123")

    def test_valid_with_hyphen(self):
        validate_document_id("doc-123")

    def test_valid_with_dot(self):
        validate_document_id("doc.123")

    def test_valid_with_slash(self):
        validate_document_id("path/to/doc")

    def test_valid_alphanumeric_only(self):
        validate_document_id("ABC123")

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_document_id("")

    def test_none_rejected(self):
        with pytest.raises(ValidationError, match="must be str"):
            validate_document_id(None)  # type: ignore[arg-type]

    def test_int_rejected(self):
        with pytest.raises(ValidationError, match="must be str"):
            validate_document_id(12345)  # type: ignore[arg-type]

    def test_dict_rejected(self):
        with pytest.raises(ValidationError, match="must be str"):
            validate_document_id({"$ne": ""})  # type: ignore[arg-type]

    def test_too_long_rejected(self):
        with pytest.raises(ValidationError, match="maximum length"):
            validate_document_id("x" * 257)

    def test_exactly_256_chars_accepted(self):
        validate_document_id("x" * 256)

    def test_special_characters_rejected(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_document_id("doc@123")

    def test_spaces_rejected(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_document_id("doc 123")

    def test_newlines_rejected(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_document_id("doc\n123")

    def test_unicode_rejected(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_document_id("doc_🌍")

    def test_arabic_rejected(self):
        """Arabic characters are NOT allowed in document_id (security)."""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_document_id("مستند_123")


# ═══════════════════════════════════════════════════════════════════════
# Section 3: Tenant-Scoped Filter Tests
# ═══════════════════════════════════════════════════════════════════════
class TestBuildTenantScopedFilter:
    """Test the tenant-scoped Qdrant filter builder."""

    def test_filter_contains_document_id(self, admin_claims):
        ctx = extract_tenant_context(admin_claims)
        f = build_tenant_scoped_filter("doc_123", ctx)
        keys = [c["key"] for c in f["filter"]["must"]]
        assert "document_id" in keys

    def test_filter_contains_tenant_id(self, admin_claims):
        ctx = extract_tenant_context(admin_claims)
        f = build_tenant_scoped_filter("doc_123", ctx)
        keys = [c["key"] for c in f["filter"]["must"]]
        assert "tenant_id" in keys

    def test_filter_contains_workspace_id(self, admin_claims):
        ctx = extract_tenant_context(admin_claims)
        f = build_tenant_scoped_filter("doc_123", ctx)
        keys = [c["key"] for c in f["filter"]["must"]]
        assert "workspace_id" in keys

    def test_filter_tenant_id_value_from_claims(self, admin_claims):
        ctx = extract_tenant_context(admin_claims)
        f = build_tenant_scoped_filter("doc_123", ctx)
        tenant_condition = next(c for c in f["filter"]["must"] if c["key"] == "tenant_id")
        assert tenant_condition["match"]["value"] == "company_a"

    def test_filter_workspace_id_value_from_claims(self, admin_claims):
        ctx = extract_tenant_context(admin_claims)
        f = build_tenant_scoped_filter("doc_123", ctx)
        ws_condition = next(c for c in f["filter"]["must"] if c["key"] == "workspace_id")
        assert ws_condition["match"]["value"] == "ws_default"

    def test_filter_document_id_value_from_param(self, admin_claims):
        ctx = extract_tenant_context(admin_claims)
        f = build_tenant_scoped_filter("doc_unique_456", ctx)
        doc_condition = next(c for c in f["filter"]["must"] if c["key"] == "document_id")
        assert doc_condition["match"]["value"] == "doc_unique_456"

    def test_filter_has_exactly_three_conditions(self, admin_claims):
        ctx = extract_tenant_context(admin_claims)
        f = build_tenant_scoped_filter("doc_123", ctx)
        assert len(f["filter"]["must"]) == 3

    def test_filter_tenant_differs_for_different_tenants(self, admin_claims, tenant_b_claims):
        ctx_a = extract_tenant_context(admin_claims)
        ctx_b = extract_tenant_context(tenant_b_claims)
        f_a = build_tenant_scoped_filter("doc_123", ctx_a)
        f_b = build_tenant_scoped_filter("doc_123", ctx_b)
        tenant_a = next(c for c in f_a["filter"]["must"] if c["key"] == "tenant_id")["match"]["value"]
        tenant_b = next(c for c in f_b["filter"]["must"] if c["key"] == "tenant_id")["match"]["value"]
        assert tenant_a == "company_a"
        assert tenant_b == "company_b"
        assert tenant_a != tenant_b


# ═══════════════════════════════════════════════════════════════════════
# Section 4: Cross-Tenant Access Rejection Tests
# ═══════════════════════════════════════════════════════════════════════
class TestRejectUserSuppliedTenantId:
    """Test that user-supplied tenant_id is rejected when it mismatches JWT."""

    def test_matching_tenant_id_accepted(self):
        """User-supplied tenant_id matching JWT → accepted."""
        reject_user_supplied_tenant_id("company_a", "company_a")  # No exception

    def test_mismatching_tenant_id_rejected(self):
        """User-supplied tenant_id different from JWT → REJECTED."""
        with pytest.raises(TenantContextError, match="Tenant ID mismatch"):
            reject_user_supplied_tenant_id("company_a", "company_b")

    def test_none_user_supplied_tenant_id_accepted(self):
        """No user-supplied tenant_id → accepted (OK to omit)."""
        reject_user_supplied_tenant_id("company_a", None)  # No exception

    def test_empty_user_supplied_tenant_id_rejected(self):
        """Empty string user-supplied tenant_id ≠ JWT tenant → rejected."""
        with pytest.raises(TenantContextError, match="Tenant ID mismatch"):
            reject_user_supplied_tenant_id("company_a", "")

    def test_cross_tenant_attack_blocked(self):
        """SECURITY: Attacker from Tenant A cannot access Tenant B by specifying tenant_id in request."""
        # Attacker's JWT says tenant_id=company_a
        # Attacker sends request with tenant_id=company_b in body
        with pytest.raises(TenantContextError, match="Cross-tenant access is forbidden"):
            reject_user_supplied_tenant_id("company_a", "company_b")

    def test_case_sensitive_tenant_id(self):
        """Tenant ID matching is case-sensitive."""
        with pytest.raises(TenantContextError, match="Tenant ID mismatch"):
            reject_user_supplied_tenant_id("company_a", "Company_A")


# ═══════════════════════════════════════════════════════════════════════
# Section 5: Authorization Enforcement Tests
# ═══════════════════════════════════════════════════════════════════════
class TestAuthorizationEnforcement:
    """Test that authorization is enforced before any Qdrant operation."""

    @pytest.mark.asyncio
    async def test_admin_can_delete(self, admin_claims, patch_async_client, clean_qdrant_config):
        """hsaai_admin can delete (has wildcard permission)."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        result = await delete_document_vectors_secure("doc_123", admin_claims)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_knowledge_admin_can_delete(self, knowledge_admin_claims, patch_async_client, clean_qdrant_config):
        """knowledge_admin can delete (has explicit knowledge:delete)."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        result = await delete_document_vectors_secure("doc_123", knowledge_admin_claims)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_ai_user_cannot_delete(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """ai_user CANNOT delete (lacks knowledge:delete permission)."""
        patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        with pytest.raises(AuthorizationError, match="lacks 'knowledge:delete'"):
            await delete_document_vectors_secure("doc_123", ai_user_claims)

    @pytest.mark.asyncio
    async def test_ai_user_can_search(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """ai_user CAN search (has knowledge:read permission)."""
        patch_async_client(response=DummyResponse(200, {"results": []}))
        result = await search_vectors_secure([0.1, 0.2, 0.3], ai_user_claims)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_unauthorized_user_blocked_before_qdrant_call(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """Unauthorized user is blocked BEFORE any Qdrant HTTP call is made."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        with pytest.raises(AuthorizationError):
            await delete_document_vectors_secure("doc_123", ai_user_claims)
        # Verify Qdrant was NOT called
        assert client.url is None
        assert client.payload is None

    @pytest.mark.asyncio
    async def test_custom_permission_requirement(self, admin_claims, patch_async_client, clean_qdrant_config):
        """Custom permission can be specified."""
        patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        # hsaai_admin has wildcard — any permission passes
        result = await delete_document_vectors_secure(
            "doc_123", admin_claims, require_permission="custom:permission"
        )
        assert result["status"] == "ok"


# ═══════════════════════════════════════════════════════════════════════
# Section 6: Audit Logging Tests
# ═══════════════════════════════════════════════════════════════════════
class TestAuditLogging:
    """Test that audit logging is performed for every operation."""

    @pytest.mark.asyncio
    async def test_successful_deletion_logged(self, admin_claims, patch_async_client, clean_qdrant_config, caplog):
        """Successful deletion must be audit-logged."""
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.qdrant"):
            patch_async_client(response=DummyResponse(200, {"status": "ok"}))
            await delete_document_vectors_secure("doc_123", admin_claims)

        audit_entries = [r for r in caplog.records if r.name == "hsaai.audit.qdrant"]
        assert len(audit_entries) >= 1
        # Verify the audit entry contains required fields
        entry = json.loads(audit_entries[-1].message)
        assert entry["event"] == "qdrant.delete_document_vectors"
        assert entry["actor"] == "admin-user-123"
        assert entry["tenant_id"] == "company_a"
        assert entry["document_id"] == "doc_123"
        assert entry["result"] == "success"
        assert "timestamp" in entry
        assert "latency_ms" in entry

    @pytest.mark.asyncio
    async def test_failed_deletion_logged(self, admin_claims, patch_async_client, clean_qdrant_config, caplog):
        """Failed deletion (HTTP error) must be audit-logged."""
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.qdrant"):
            patch_async_client(response=DummyResponse(500, text="Server Error"))
            with pytest.raises(QdrantDeleteError):
                await delete_document_vectors_secure("doc_123", admin_claims)

        audit_entries = [r for r in caplog.records if r.name == "hsaai.audit.qdrant"]
        assert len(audit_entries) >= 1
        entry = json.loads(audit_entries[-1].message)
        assert entry["result"] == "failed"
        assert "500" in entry["error"]

    @pytest.mark.asyncio
    async def test_authorization_denial_logged(self, ai_user_claims, patch_async_client, clean_qdrant_config, caplog):
        """Authorization denial must be audit-logged."""
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.qdrant"):
            patch_async_client(response=DummyResponse(200, {"status": "ok"}))
            with pytest.raises(AuthorizationError):
                await delete_document_vectors_secure("doc_123", ai_user_claims)

        audit_entries = [r for r in caplog.records if r.name == "hsaai.audit.qdrant"]
        assert len(audit_entries) >= 1
        entry = json.loads(audit_entries[-1].message)
        assert entry["result"] == "denied"
        assert "AuthorizationError" in entry["error"]

    @pytest.mark.asyncio
    async def test_validation_failure_logged(self, admin_claims, patch_async_client, clean_qdrant_config, caplog):
        """Validation failure must be audit-logged."""
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.qdrant"):
            patch_async_client(response=DummyResponse(200, {"status": "ok"}))
            with pytest.raises(ValidationError):
                await delete_document_vectors_secure("", admin_claims)

        audit_entries = [r for r in caplog.records if r.name == "hsaai.audit.qdrant"]
        assert len(audit_entries) >= 1
        entry = json.loads(audit_entries[-1].message)
        assert entry["result"] == "failed"
        assert "ValidationError" in entry["error"]

    @pytest.mark.asyncio
    async def test_audit_entry_includes_request_id(self, admin_claims, patch_async_client, clean_qdrant_config, caplog):
        """Audit entry must include a request_id for traceability."""
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.qdrant"):
            patch_async_client(response=DummyResponse(200, {"status": "ok"}))
            await delete_document_vectors_secure("doc_123", admin_claims)

        audit_entries = [r for r in caplog.records if r.name == "hsaai.audit.qdrant"]
        entry = json.loads(audit_entries[-1].message)
        assert "request_id" in entry
        assert len(entry["request_id"]) > 0

    @pytest.mark.asyncio
    async def test_audit_entry_includes_timestamp(self, admin_claims, patch_async_client, clean_qdrant_config, caplog):
        """Audit entry must include UTC timestamp."""
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.qdrant"):
            patch_async_client(response=DummyResponse(200, {"status": "ok"}))
            await delete_document_vectors_secure("doc_123", admin_claims)

        audit_entries = [r for r in caplog.records if r.name == "hsaai.audit.qdrant"]
        entry = json.loads(audit_entries[-1].message)
        assert "timestamp" in entry
        # ISO format with timezone
        assert "T" in entry["timestamp"]


# ═══════════════════════════════════════════════════════════════════════
# Section 7: Secure Deletion Tests (delete_document_vectors_secure)
# ═══════════════════════════════════════════════════════════════════════
class TestDeleteDocumentVectorsSecure:
    """Test the secure deletion function."""

    @pytest.mark.asyncio
    async def test_successful_deletion(self, admin_claims, patch_async_client, clean_qdrant_config):
        """Successful deletion returns Qdrant response."""
        patch_async_client(response=DummyResponse(200, {"operation_id": 123, "status": "completed"}))
        result = await delete_document_vectors_secure("doc_123", admin_claims)
        assert result["operation_id"] == 123

    @pytest.mark.asyncio
    async def test_payload_includes_tenant_id(self, admin_claims, patch_async_client, clean_qdrant_config):
        """CRITICAL: Payload must include tenant_id for isolation."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors_secure("doc_123", admin_claims)
        keys = [c["key"] for c in client.payload["filter"]["must"]]
        assert "tenant_id" in keys

    @pytest.mark.asyncio
    async def test_payload_includes_workspace_id(self, admin_claims, patch_async_client, clean_qdrant_config):
        """CRITICAL: Payload must include workspace_id for isolation."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors_secure("doc_123", admin_claims)
        keys = [c["key"] for c in client.payload["filter"]["must"]]
        assert "workspace_id" in keys

    @pytest.mark.asyncio
    async def test_payload_tenant_id_from_jwt_not_user_input(self, admin_claims, patch_async_client, clean_qdrant_config):
        """CRITICAL: tenant_id in payload comes from JWT, not user input."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        # Even if someone tries to pass tenant_id in document_id, it's ignored
        await delete_document_vectors_secure("doc_123", admin_claims)
        tenant_cond = next(c for c in client.payload["filter"]["must"] if c["key"] == "tenant_id")
        assert tenant_cond["match"]["value"] == "company_a"  # From JWT

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_delete_tenant_b_vectors(self, admin_claims, tenant_b_claims, patch_async_client, clean_qdrant_config):
        """SECURITY: Tenant A's admin cannot delete Tenant B's vectors.

        Even though both are hsaai_admin, the filter includes tenant_id from JWT.
        Tenant A's filter: tenant_id=company_a → only deletes Tenant A's vectors.
        """
        # Tenant A admin tries to delete "tenant_b_doc"
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors_secure("tenant_b_doc", admin_claims)
        # Verify the filter STILL says tenant_id=company_a (not company_b)
        tenant_cond = next(c for c in client.payload["filter"]["must"] if c["key"] == "tenant_id")
        assert tenant_cond["match"]["value"] == "company_a"
        # The document_id is "tenant_b_doc" but the filter restricts to company_a
        # → Qdrant will NOT delete Tenant B's vectors (filter won't match)

    @pytest.mark.asyncio
    async def test_http_error_raises_qdrant_delete_error(self, admin_claims, patch_async_client, clean_qdrant_config):
        """HTTP error raises QdrantDeleteError."""
        patch_async_client(response=DummyResponse(500, text="Internal Error"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors_secure("doc_123", admin_claims)

    @pytest.mark.asyncio
    async def test_network_error_raises_qdrant_delete_error(self, admin_claims, patch_async_client, clean_qdrant_config):
        """Network error raises QdrantDeleteError."""
        patch_async_client(exception=httpx.ConnectError("Connection refused"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors_secure("doc_123", admin_claims)

    @pytest.mark.asyncio
    async def test_invalid_json_raises_qdrant_delete_error(self, admin_claims, patch_async_client, clean_qdrant_config):
        """Invalid JSON response raises QdrantDeleteError (not JSONDecodeError)."""

        class BadJsonResponse(DummyResponse):
            def json(self):
                raise json.JSONDecodeError("Expecting value", "not json", 0)

        patch_async_client(response=BadJsonResponse(200, text="not json"))
        with pytest.raises(QdrantDeleteError, match="invalid JSON"):
            await delete_document_vectors_secure("doc_123", admin_claims)

    @pytest.mark.asyncio
    async def test_missing_tenant_id_raises(self, patch_async_client, clean_qdrant_config):
        """Missing tenant_id in claims raises TenantContextError."""
        patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        with pytest.raises(TenantContextError):
            await delete_document_vectors_secure("doc_123", {"sub": "u1"})

    @pytest.mark.asyncio
    async def test_none_claims_raises(self, patch_async_client, clean_qdrant_config):
        """None claims raises TenantContextError."""
        patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        with pytest.raises(TenantContextError):
            await delete_document_vectors_secure("doc_123", None)  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════
# Section 8: Secure Search Tests (search_vectors_secure)
# ═══════════════════════════════════════════════════════════════════════
class TestSearchVectorsSecure:
    """Test the secure search function."""

    @pytest.mark.asyncio
    async def test_successful_search(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """Successful search returns Qdrant response."""
        patch_async_client(response=DummyResponse(200, {"results": [{"id": 1, "score": 0.9}]}))
        result = await search_vectors_secure([0.1, 0.2, 0.3], ai_user_claims)
        assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_search_filter_includes_tenant_id(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """CRITICAL: Search filter must include tenant_id."""
        client = patch_async_client(response=DummyResponse(200, {"results": []}))
        await search_vectors_secure([0.1, 0.2], ai_user_claims)
        keys = [c["key"] for c in client.payload["filter"]["must"]]
        assert "tenant_id" in keys

    @pytest.mark.asyncio
    async def test_search_filter_includes_workspace_id(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """CRITICAL: Search filter must include workspace_id."""
        client = patch_async_client(response=DummyResponse(200, {"results": []}))
        await search_vectors_secure([0.1, 0.2], ai_user_claims)
        keys = [c["key"] for c in client.payload["filter"]["must"]]
        assert "workspace_id" in keys

    @pytest.mark.asyncio
    async def test_search_tenant_isolation(self, admin_claims, tenant_b_claims, patch_async_client, clean_qdrant_config):
        """SECURITY: Tenant A's search does NOT return Tenant B's vectors."""
        # Tenant A searches
        client_a = patch_async_client(response=DummyResponse(200, {"results": []}))
        await search_vectors_secure([0.1, 0.2], admin_claims)
        tenant_a_filter = next(c for c in client_a.payload["filter"]["must"] if c["key"] == "tenant_id")
        assert tenant_a_filter["match"]["value"] == "company_a"

        # Tenant B searches
        client_b = patch_async_client(response=DummyResponse(200, {"results": []}))
        await search_vectors_secure([0.1, 0.2], tenant_b_claims)
        tenant_b_filter = next(c for c in client_b.payload["filter"]["must"] if c["key"] == "tenant_id")
        assert tenant_b_filter["match"]["value"] == "company_b"

        # Tenants are isolated
        assert tenant_a_filter["match"]["value"] != tenant_b_filter["match"]["value"]

    @pytest.mark.asyncio
    async def test_search_unauthorized_user_blocked(self, patch_async_client, clean_qdrant_config):
        """User without knowledge:read cannot search."""
        claims = {
            "sub": "u1",
            "tenant_id": "company_a",
            "realm_access": {"roles": ["unknown_role"]},
        }
        patch_async_client(response=DummyResponse(200, {"results": []}))
        with pytest.raises(AuthorizationError):
            await search_vectors_secure([0.1, 0.2], claims)

    @pytest.mark.asyncio
    async def test_search_with_score_threshold(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """Score threshold is passed to Qdrant."""
        client = patch_async_client(response=DummyResponse(200, {"results": []}))
        await search_vectors_secure([0.1, 0.2], ai_user_claims, score_threshold=0.7)
        assert client.payload.get("score_threshold") == 0.7

    @pytest.mark.asyncio
    async def test_search_with_custom_limit(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """Custom limit is passed to Qdrant."""
        client = patch_async_client(response=DummyResponse(200, {"results": []}))
        await search_vectors_secure([0.1, 0.2], ai_user_claims, limit=5)
        assert client.payload.get("limit") == 5

    @pytest.mark.asyncio
    async def test_search_http_error_raises_qdrant_delete_error(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """Search HTTP error raises QdrantDeleteError."""
        patch_async_client(response=DummyResponse(500, text="Server Error"))
        with pytest.raises(QdrantDeleteError, match="search failed"):
            await search_vectors_secure([0.1, 0.2], ai_user_claims)

    @pytest.mark.asyncio
    async def test_search_network_error_raises_qdrant_delete_error(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """Search network error raises QdrantDeleteError."""
        patch_async_client(exception=httpx.ConnectError("Connection refused"))
        with pytest.raises(QdrantDeleteError, match="search request failed"):
            await search_vectors_secure([0.1, 0.2], ai_user_claims)

    @pytest.mark.asyncio
    async def test_search_timeout_raises_qdrant_delete_error(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """Search timeout raises QdrantDeleteError."""
        patch_async_client(exception=httpx.TimeoutException("Timeout"))
        with pytest.raises(QdrantDeleteError, match="search request failed"):
            await search_vectors_secure([0.1, 0.2], ai_user_claims)

    @pytest.mark.asyncio
    async def test_search_invalid_json_raises_qdrant_delete_error(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """Search invalid JSON response raises QdrantDeleteError."""

        class BadJsonResponse(DummyResponse):
            def json(self):
                raise json.JSONDecodeError("Expecting value", "not json", 0)

        patch_async_client(response=BadJsonResponse(200, text="not json"))
        with pytest.raises(QdrantDeleteError, match="invalid JSON"):
            await search_vectors_secure([0.1, 0.2], ai_user_claims)

    @pytest.mark.asyncio
    async def test_search_http_400_raises(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """Search HTTP 400 raises QdrantDeleteError."""
        patch_async_client(response=DummyResponse(400, text="Bad Request"))
        with pytest.raises(QdrantDeleteError):
            await search_vectors_secure([0.1, 0.2], ai_user_claims)

    @pytest.mark.asyncio
    async def test_search_http_404_raises(self, ai_user_claims, patch_async_client, clean_qdrant_config):
        """Search HTTP 404 raises QdrantDeleteError."""
        patch_async_client(response=DummyResponse(404, text="Not Found"))
        with pytest.raises(QdrantDeleteError):
            await search_vectors_secure([0.1, 0.2], ai_user_claims)

    @pytest.mark.asyncio
    async def test_search_missing_tenant_raises(self, patch_async_client, clean_qdrant_config):
        """Search with missing tenant_id raises TenantContextError."""
        patch_async_client(response=DummyResponse(200, {"results": []}))
        with pytest.raises(TenantContextError):
            await search_vectors_secure([0.1, 0.2], {"sub": "u1"})


# ═══════════════════════════════════════════════════════════════════════
# Section 9: Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════
class TestErrorHandling:
    """Test comprehensive error handling."""

    @pytest.mark.asyncio
    async def test_http_400_raises_qdrant_delete_error(self, admin_claims, patch_async_client, clean_qdrant_config):
        patch_async_client(response=DummyResponse(400, text="Bad Request"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors_secure("doc_123", admin_claims)

    @pytest.mark.asyncio
    async def test_http_404_raises_qdrant_delete_error(self, admin_claims, patch_async_client, clean_qdrant_config):
        patch_async_client(response=DummyResponse(404, text="Not Found"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors_secure("doc_123", admin_claims)

    @pytest.mark.asyncio
    async def test_timeout_raises_qdrant_delete_error(self, admin_claims, patch_async_client, clean_qdrant_config):
        patch_async_client(exception=httpx.TimeoutException("Timeout"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors_secure("doc_123", admin_claims)

    @pytest.mark.asyncio
    async def test_connect_error_raises_qdrant_delete_error(self, admin_claims, patch_async_client, clean_qdrant_config):
        patch_async_client(exception=httpx.ConnectError("Connection refused"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors_secure("doc_123", admin_claims)

    @pytest.mark.asyncio
    async def test_error_message_does_not_leak_full_response(self, admin_claims, patch_async_client, clean_qdrant_config, caplog):
        """Error message should be truncated (500 chars max)."""
        import logging
        long_text = "x" * 1000
        with caplog.at_level(logging.INFO, logger="hsaai.audit.qdrant"):
            patch_async_client(response=DummyResponse(500, text=long_text))
            with pytest.raises(QdrantDeleteError) as exc_info:
                await delete_document_vectors_secure("doc_123", admin_claims)
        # Error message should not contain the full 1000-char response
        assert "x" * 600 not in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════
# Section 10: Async Quality Tests
# ═══════════════════════════════════════════════════════════════════════
class TestAsyncQuality:
    """Verify async quality — no unawaited coroutines, no RuntimeWarnings."""

    @pytest.mark.asyncio
    async def test_no_runtime_warning_on_success(self, admin_claims, patch_async_client, clean_qdrant_config, recwarn):
        patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors_secure("doc_123", admin_claims)
        runtime_warnings = [w for w in recwarn.list if issubclass(w.category, RuntimeWarning)]
        assert len(runtime_warnings) == 0

    @pytest.mark.asyncio
    async def test_no_runtime_warning_on_error(self, admin_claims, patch_async_client, clean_qdrant_config, recwarn):
        patch_async_client(response=DummyResponse(500, text="Error"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors_secure("doc_123", admin_claims)
        runtime_warnings = [w for w in recwarn.list if issubclass(w.category, RuntimeWarning)]
        assert len(runtime_warnings) == 0

    @pytest.mark.asyncio
    async def test_returns_awaitable(self, admin_claims, patch_async_client, clean_qdrant_config):
        patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        coro = delete_document_vectors_secure("doc_123", admin_claims)
        assert asyncio.iscoroutine(coro)
        await coro


# ═══════════════════════════════════════════════════════════════════════
# Section 11: Integration-style End-to-End Tests
# ═══════════════════════════════════════════════════════════════════════
class TestEndToEndSecureFlow:
    """End-to-end secure flow tests."""

    @pytest.mark.asyncio
    async def test_complete_secure_deletion_flow(self, knowledge_admin_claims, patch_async_client, clean_qdrant_config, caplog):
        """Verify complete secure flow: auth → tenant → validate → delete → audit."""
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.qdrant"):
            client = patch_async_client(response=DummyResponse(200, {
                "operation_id": 999,
                "status": "completed",
            }))
            result = await delete_document_vectors_secure("doc_abc", knowledge_admin_claims)

        # Verify result
        assert result["operation_id"] == 999

        # Verify URL
        assert "/collections/hsaai_knowledge/points/delete" in client.url

        # Verify payload has tenant isolation
        keys = [c["key"] for c in client.payload["filter"]["must"]]
        assert "document_id" in keys
        assert "tenant_id" in keys
        assert "workspace_id" in keys

        # Verify tenant_id from JWT (not user input)
        tenant_cond = next(c for c in client.payload["filter"]["must"] if c["key"] == "tenant_id")
        assert tenant_cond["match"]["value"] == "company_a"

        # Verify audit log
        audit_entries = [r for r in caplog.records if r.name == "hsaai.audit.qdrant"]
        assert len(audit_entries) >= 1
        entry = json.loads(audit_entries[-1].message)
        assert entry["result"] == "success"
        assert entry["actor"] == "kb-admin-789"
        assert entry["tenant_id"] == "company_a"

    @pytest.mark.asyncio
    async def test_cross_tenant_attack_blocked_end_to_end(self, admin_claims, patch_async_client, clean_qdrant_config, caplog):
        """SECURITY: Cross-tenant attack is blocked end-to-end.

        Scenario: Admin from Tenant A tries to delete Tenant B's document.
        Expected: Deletion proceeds but ONLY affects Tenant A's vectors
                  (filter includes tenant_id=company_a, so Tenant B's
                  vectors with tenant_id=company_b are NOT matched).
        """
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.qdrant"):
            client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
            # Admin from company_a tries to delete "company_b_doc"
            await delete_document_vectors_secure("company_b_doc", admin_claims)

        # Verify the filter STILL has tenant_id=company_a (from JWT)
        tenant_cond = next(c for c in client.payload["filter"]["must"] if c["key"] == "tenant_id")
        assert tenant_cond["match"]["value"] == "company_a"
        # The document_id is "company_b_doc" but the filter is scoped to company_a
        # Qdrant will not find/delete Tenant B's vectors because the filter
        # requires tenant_id=company_a AND document_id=company_b_doc (no match)
        doc_cond = next(c for c in client.payload["filter"]["must"] if c["key"] == "document_id")
        assert doc_cond["match"]["value"] == "company_b_doc"
        # Audit log records the attempt
        audit_entries = [r for r in caplog.records if r.name == "hsaai.audit.qdrant"]
        entry = json.loads(audit_entries[-1].message)
        assert entry["tenant_id"] == "company_a"  # From JWT
        assert entry["document_id"] == "company_b_doc"  # Requested
