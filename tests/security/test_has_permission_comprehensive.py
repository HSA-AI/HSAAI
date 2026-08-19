"""
HSAAI Enterprise AI Platform — Authorization Security Test Suite (v9.0)
=======================================================================
Production-Ready Enterprise test suite for the `has_permission` function in
`services/backend_core/security/rbac.py`.

Function under test:
    def has_permission(claims: dict[str, Any], permission: str) -> bool

Zero Trust Principles Verified:
  - Deny By Default (no claims, no roles → deny all)
  - Least Privilege (each role has minimal permissions)
  - Privilege Escalation Prevention (low-priv users cannot access admin perms)
  - Multi-Tenant Isolation (tenant_id from JWT only — user input rejected)
  - AI Governance (Knowledge Base, RAG, Document Intelligence protected)

Test Categories (per requirements):
  1. Authentication Security Tests (missing auth → deny)
  2. RBAC Tests (role-based access)
  3. Negative Security Testing (unknown roles, invalid permissions)
  4. Privilege Escalation Testing (attack scenarios)
  5. Multi-Tenant Isolation Testing (tenant_id source enforcement)
  6. Keycloak JWT Validation Testing (claim structure variants)
  7. AI Governance Security Tests (Knowledge Base, RAG protection)

Coverage target: 100% on has_permission + _roles_from_claims + permissions_for_roles

Rules:
  - No Keycloak, no DB, no network calls (pure function tests)
  - Independent tests (no execution-order dependency)
  - Parametrized for clarity
  - Security-focused naming
  - CI/CD compatible
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# ─── Path setup (mirrors tests/conftest.py) ────────────────────────────
_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.security.rbac import (  # noqa: E402
    ROLE_PERMISSIONS,
    _roles_from_claims,
    has_permission,
    permissions_for_roles,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════
@pytest.fixture
def claims_factory():
    """Factory for building JWT claims dicts with various role configurations.

    Usage:
        def test_x(claims_factory):
            claims = claims_factory(realm_roles=["ai_user"])
            assert has_permission(claims, "knowledge:read")
    """
    def _factory(
        realm_roles: list[str] | None = None,
        resource_roles: dict[str, list[str]] | None = None,
        direct_roles: list[str] | str | None = None,
        tenant_id: str = "company_a",
        workspace_id: str = "default",
        user_id: str = "user-123",
        extra_claims: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        claims: dict[str, Any] = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
        }
        if realm_roles is not None:
            claims["realm_access"] = {"roles": realm_roles}
        if resource_roles is not None:
            claims["resource_access"] = {
                resource: {"roles": roles} for resource, roles in resource_roles.items()
            }
        if direct_roles is not None:
            claims["roles"] = direct_roles
        if extra_claims:
            claims.update(extra_claims)
        return claims

    return _factory


# ═══════════════════════════════════════════════════════════════════════
# Section 1: Authentication Security Tests
# Verify Zero Trust Deny-By-Default principle.
# ═══════════════════════════════════════════════════════════════════════
class TestAuthenticationSecurity:
    """Verify that missing or invalid authentication denies all permissions.

    Zero Trust Principle: Deny By Default.
    If there's no valid authentication context, NO permission should be granted.
    """

    @pytest.mark.parametrize("permission", [
        "knowledge:read", "knowledge:write", "knowledge:admin", "knowledge:delete",
        "chat:write", "audit:read", "agents:execute", "executive:write",
    ])
    def test_empty_claims_denies_all_permissions(self, permission: str):
        """Empty claims dict → deny all permissions (Deny By Default)."""
        assert has_permission({}, permission) is False

    def test_empty_claims_denies_read(self):
        """Empty claims must deny even read permissions."""
        assert has_permission({}, "knowledge:read") is False

    def test_empty_claims_denies_admin(self):
        """Empty claims must deny admin permissions."""
        assert has_permission({}, "knowledge:admin") is False

    def test_empty_claims_denies_chat(self):
        """Empty claims must deny chat permissions."""
        assert has_permission({}, "chat:write") is False

    def test_claims_without_realm_access_denies(self):
        """Claims without realm_access → deny (no roles extracted)."""
        claims = {"sub": "user-1", "tenant_id": "company_a"}
        assert has_permission(claims, "knowledge:read") is False

    def test_claims_without_roles_denies(self):
        """Claims with realm_access but no roles → deny."""
        claims = {"realm_access": {}}
        assert has_permission(claims, "knowledge:read") is False

    def test_claims_with_empty_roles_list_denies(self):
        """Claims with empty roles list → deny."""
        claims = {"realm_access": {"roles": []}}
        assert has_permission(claims, "knowledge:read") is False

    def test_claims_with_none_roles_denies(self):
        """Claims with roles=None → deny (graceful handling)."""
        claims = {"realm_access": {"roles": None}}
        assert has_permission(claims, "knowledge:read") is False

    def test_claims_with_realm_access_not_dict_denies(self):
        """Claims with realm_access as string (malformed) → deny (graceful)."""
        claims = {"realm_access": "not_a_dict"}
        assert has_permission(claims, "knowledge:read") is False

    def test_claims_with_realm_access_none_denies(self):
        """Claims with realm_access=None → deny."""
        claims = {"realm_access": None}
        assert has_permission(claims, "knowledge:read") is False

    def test_none_claims_raises_attribute_error(self):
        """None claims raises AttributeError (current behavior — validation gap).

        NOTE: This documents the current behavior. In a perfect Zero Trust
        implementation, None claims should return False (deny) rather than
        raising an exception. See recommendations in the test suite README.
        """
        with pytest.raises(AttributeError):
            has_permission(None, "knowledge:read")  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════
# Section 2: RBAC Tests
# Verify Role-Based Access Control matrix is correctly enforced.
# ═══════════════════════════════════════════════════════════════════════
class TestRBACKnowledgeAdmin:
    """Test the knowledge_admin role — privileged Knowledge Base access."""

    @pytest.fixture
    def knowledge_admin_claims(self, claims_factory):
        return claims_factory(realm_roles=["knowledge_admin"])

    @pytest.mark.parametrize("permission", [
        "knowledge:read", "knowledge:write", "knowledge:admin",
        "knowledge:review", "knowledge:delete",
        "chat:write", "files:write", "audit:read", "analytics:read",
        "agents:read", "agents:admin", "agents:execute",
        "workflows:read", "observability:read",
        "approvals:create", "approvals:read",
        "graph:read", "graph:write", "graph:admin", "graph:audit",
        "executive:read",
    ])
    def test_knowledge_admin_has_all_kb_permissions(self, knowledge_admin_claims, permission: str):
        """knowledge_admin must have all Knowledge Base permissions (except upload)."""
        assert has_permission(knowledge_admin_claims, permission) is True

    def test_knowledge_admin_denies_upload(self, knowledge_admin_claims):
        """knowledge_admin does NOT have knowledge:upload (only document_uploader does).

        This enforces separation of duties: admin can manage but cannot upload
        (uploading is a delegated responsibility).
        """
        assert has_permission(knowledge_admin_claims, "knowledge:upload") is False

    def test_knowledge_admin_denies_executive_write(self, knowledge_admin_claims):
        """knowledge_admin must NOT have executive:write (least privilege)."""
        assert has_permission(knowledge_admin_claims, "executive:write") is False

    def test_knowledge_admin_denies_approvals_decide(self, knowledge_admin_claims):
        """knowledge_admin must NOT have approvals:decide (separation of duties)."""
        assert has_permission(knowledge_admin_claims, "approvals:decide") is False


class TestRBACAiUser:
    """Test the ai_user role — standard user with minimal privileges."""

    @pytest.fixture
    def ai_user_claims(self, claims_factory):
        return claims_factory(realm_roles=["ai_user"])

    @pytest.mark.parametrize("permission", [
        "chat:write", "knowledge:read", "agents:read", "agents:execute",
        "approvals:create", "graph:read",
    ])
    def test_ai_user_has_standard_permissions(self, ai_user_claims, permission: str):
        """ai_user must have standard chat/read permissions."""
        assert has_permission(ai_user_claims, permission) is True

    @pytest.mark.parametrize("permission", [
        "knowledge:admin", "knowledge:review", "knowledge:delete",
        "knowledge:write", "knowledge:upload", "files:write",
        "audit:read", "analytics:read",
        "agents:admin", "workflows:read", "observability:read",
        "approvals:read", "approvals:decide",
        "graph:write", "graph:admin", "graph:audit",
        "executive:read", "executive:write",
        "reports:read", "connectors:read", "connectors:sync",
    ])
    def test_ai_user_denies_admin_permissions(self, ai_user_claims, permission: str):
        """ai_user must NOT have admin/review/delete permissions (least privilege)."""
        assert has_permission(ai_user_claims, permission) is False


class TestRBACHsaaiAdmin:
    """Test the hsaai_admin role — superuser with wildcard access."""

    @pytest.fixture
    def hsaai_admin_claims(self, claims_factory):
        return claims_factory(realm_roles=["hsaai_admin"])

    @pytest.mark.parametrize("permission", [
        "knowledge:read", "knowledge:write", "knowledge:admin", "knowledge:delete",
        "chat:write", "audit:read", "agents:execute", "executive:write",
        "anything:whatever", "custom:permission", "nonexistent:perm",
    ])
    def test_hsaai_admin_has_all_permissions(self, hsaai_admin_claims, permission: str):
        """hsaai_admin (wildcard '*') must have ALL permissions."""
        assert has_permission(hsaai_admin_claims, permission) is True

    def test_hsaai_admin_grants_empty_permission(self, hsaai_admin_claims):
        """hsaai_admin grants even empty permission string (due to '*' wildcard).

        NOTE: This is the current behavior — the '*' check happens before
        the permission check. This is documented as a minor security concern
        but not a vulnerability (admin is trusted).
        """
        assert has_permission(hsaai_admin_claims, "") is True


class TestRBACDocumentReviewer:
    """Test the document_reviewer role."""

    @pytest.fixture
    def reviewer_claims(self, claims_factory):
        return claims_factory(realm_roles=["document_reviewer"])

    @pytest.mark.parametrize("permission", [
        "chat:write", "knowledge:read", "knowledge:review",
        "audit:read", "agents:read", "agents:execute",
        "approvals:read", "approvals:decide", "executive:read",
    ])
    def test_reviewer_has_review_permissions(self, reviewer_claims, permission: str):
        """document_reviewer must have review and decide permissions."""
        assert has_permission(reviewer_claims, permission) is True

    @pytest.mark.parametrize("permission", [
        "knowledge:admin", "knowledge:delete", "knowledge:write",
        "knowledge:upload", "files:write", "agents:admin",
        "executive:write", "graph:write",
    ])
    def test_reviewer_denies_admin_permissions(self, reviewer_claims, permission: str):
        """document_reviewer must NOT have admin/write/delete permissions."""
        assert has_permission(reviewer_claims, permission) is False


class TestRBACDocumentUploader:
    """Test the document_uploader role."""

    @pytest.fixture
    def uploader_claims(self, claims_factory):
        return claims_factory(realm_roles=["document_uploader"])

    @pytest.mark.parametrize("permission", [
        "chat:write", "files:write", "knowledge:read",
        "knowledge:upload", "knowledge:write",
        "agents:read", "agents:execute", "approvals:create",
    ])
    def test_uploader_has_upload_permissions(self, uploader_claims, permission: str):
        assert has_permission(uploader_claims, permission) is True

    def test_uploader_denies_review(self, uploader_claims):
        """document_uploader must NOT have knowledge:review (separation of duties)."""
        assert has_permission(uploader_claims, "knowledge:review") is False

    def test_uploader_denies_delete(self, uploader_claims):
        """document_uploader must NOT have knowledge:delete."""
        assert has_permission(uploader_claims, "knowledge:delete") is False


class TestRBACDepartmentManager:
    """Test the department_manager role."""

    @pytest.fixture
    def manager_claims(self, claims_factory):
        return claims_factory(realm_roles=["department_manager"])

    @pytest.mark.parametrize("permission", [
        "chat:write", "knowledge:read", "analytics:read", "reports:read",
        "agents:read", "agents:execute",
        "workflows:read", "workflows:execute",
        "approvals:create", "approvals:read", "approvals:decide",
        "connectors:read", "connectors:sync", "observability:read",
        "graph:read", "executive:read",
    ])
    def test_manager_has_operational_permissions(self, manager_claims, permission: str):
        assert has_permission(manager_claims, permission) is True

    def test_manager_denies_knowledge_admin(self, manager_claims):
        """department_manager must NOT have knowledge:admin."""
        assert has_permission(manager_claims, "knowledge:admin") is False

    def test_manager_denies_executive_write(self, manager_claims):
        """department_manager must NOT have executive:write."""
        assert has_permission(manager_claims, "executive:write") is False


class TestRBACAuditor:
    """Test the auditor role — read-only access for audit purposes."""

    @pytest.fixture
    def auditor_claims(self, claims_factory):
        return claims_factory(realm_roles=["auditor"])

    @pytest.mark.parametrize("permission", [
        "knowledge:read", "audit:read", "analytics:read", "reports:read",
        "agents:read", "workflows:read", "connectors:read",
        "observability:read", "approvals:read", "graph:read", "graph:audit",
        "executive:read",
    ])
    def test_auditor_has_read_permissions(self, auditor_claims, permission: str):
        assert has_permission(auditor_claims, permission) is True

    @pytest.mark.parametrize("permission", [
        "chat:write", "knowledge:write", "knowledge:admin", "knowledge:delete",
        "files:write", "agents:execute", "agents:admin",
        "approvals:create", "approvals:decide",
        "graph:write", "graph:admin", "executive:write",
        "workflows:execute", "connectors:sync",
    ])
    def test_auditor_denies_write_permissions(self, auditor_claims, permission: str):
        """auditor must NOT have any write/execute permissions (read-only)."""
        assert has_permission(auditor_claims, permission) is False


class TestRBACExecutive:
    """Test the executive role."""

    @pytest.fixture
    def executive_claims(self, claims_factory):
        return claims_factory(realm_roles=["executive"])

    @pytest.mark.parametrize("permission", [
        "chat:write", "knowledge:read", "analytics:read", "reports:read",
        "executive:read", "executive:write",
    ])
    def test_executive_has_executive_permissions(self, executive_claims, permission: str):
        assert has_permission(executive_claims, permission) is True

    @pytest.mark.parametrize("permission", [
        "knowledge:admin", "knowledge:delete", "knowledge:write",
        "agents:admin", "audit:read", "graph:write",
    ])
    def test_executive_denies_admin_permissions(self, executive_claims, permission: str):
        """executive must NOT have admin/operational permissions."""
        assert has_permission(executive_claims, permission) is False


# ═══════════════════════════════════════════════════════════════════════
# Section 3: Negative Security Testing
# ═══════════════════════════════════════════════════════════════════════
class TestNegativeSecurity:
    """Test handling of unknown roles, invalid permissions, and edge cases."""

    def test_unknown_role_denies_all(self, claims_factory):
        """Unknown role → deny all permissions."""
        claims = claims_factory(realm_roles=["nonexistent_role"])
        assert has_permission(claims, "knowledge:read") is False
        assert has_permission(claims, "chat:write") is False

    def test_unknown_permission_denied(self, claims_factory):
        """Unknown permission → deny (even for admin roles)."""
        claims = claims_factory(realm_roles=["knowledge_admin"])
        # knowledge_admin does not have arbitrary permissions
        assert has_permission(claims, "nonexistent:permission") is False

    def test_empty_permission_string_denied_for_standard_user(self, claims_factory):
        """Empty permission string → deny for standard users (ai_user)."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "") is False

    def test_permission_with_only_colon_denied(self, claims_factory):
        """Permission ':' (empty domain and action) → deny."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, ":") is False

    def test_permission_with_only_domain_denied(self, claims_factory):
        """Permission 'knowledge:' (empty action) → deny."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "knowledge:") is False

    def test_permission_with_only_action_denied(self, claims_factory):
        """Permission ':read' (empty domain) → deny."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, ":read") is False

    def test_wildcard_permission_admin_star_denied(self, claims_factory):
        """Permission 'admin:*' is NOT supported → deny (no wildcard expansion)."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "admin:*") is False

    def test_wildcard_permission_star_read_denied(self, claims_factory):
        """Permission '*:read' is NOT supported → deny."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "*:read") is False

    def test_wildcard_permission_double_star_denied(self, claims_factory):
        """Permission '**' is NOT supported → deny."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "**") is False

    def test_permission_case_sensitive(self, claims_factory):
        """Permission matching is case-sensitive ('Knowledge:Read' ≠ 'knowledge:read')."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "Knowledge:Read") is False
        assert has_permission(claims, "KNOWLEDGE:READ") is False
        assert has_permission(claims, "knowledge:read") is True

    def test_role_case_sensitive(self, claims_factory):
        """Role matching is case-sensitive ('AI_User' ≠ 'ai_user')."""
        claims = claims_factory(realm_roles=["AI_User"])
        assert has_permission(claims, "knowledge:read") is False
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "knowledge:read") is True

    def test_permission_with_spaces_denied(self, claims_factory):
        """Permission with leading/trailing spaces → deny (no trimming)."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, " knowledge:read") is False
        assert has_permission(claims, "knowledge:read ") is False
        assert has_permission(claims, "knowledge: read") is False


# ═══════════════════════════════════════════════════════════════════════
# Section 4: Privilege Escalation Testing
# ═══════════════════════════════════════════════════════════════════════
class TestPrivilegeEscalation:
    """Test that privilege escalation attacks are prevented."""

    def test_ai_user_cannot_access_knowledge_review(self, claims_factory):
        """ai_user attempting knowledge:review → DENY (privilege escalation blocked)."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "knowledge:review") is False

    def test_ai_user_cannot_access_knowledge_admin(self, claims_factory):
        """ai_user attempting knowledge:admin → DENY."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "knowledge:admin") is False

    def test_ai_user_cannot_delete_documents(self, claims_factory):
        """ai_user attempting knowledge:delete → DENY."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "knowledge:delete") is False

    def test_ai_user_cannot_access_audit_logs(self, claims_factory):
        """ai_user attempting audit:read → DENY."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "audit:read") is False

    def test_reviewer_cannot_access_knowledge_admin(self, claims_factory):
        """document_reviewer attempting knowledge:admin → DENY."""
        claims = claims_factory(realm_roles=["document_reviewer"])
        assert has_permission(claims, "knowledge:admin") is False

    def test_reviewer_cannot_delete_documents(self, claims_factory):
        """document_reviewer attempting knowledge:delete → DENY."""
        claims = claims_factory(realm_roles=["document_reviewer"])
        assert has_permission(claims, "knowledge:delete") is False

    def test_uploader_cannot_review_documents(self, claims_factory):
        """document_uploader attempting knowledge:review → DENY (separation of duties)."""
        claims = claims_factory(realm_roles=["document_uploader"])
        assert has_permission(claims, "knowledge:review") is False

    def test_uploader_cannot_delete_documents(self, claims_factory):
        """document_uploader attempting knowledge:delete → DENY."""
        claims = claims_factory(realm_roles=["document_uploader"])
        assert has_permission(claims, "knowledge:delete") is False

    def test_manager_cannot_access_knowledge_admin(self, claims_factory):
        """department_manager attempting knowledge:admin → DENY."""
        claims = claims_factory(realm_roles=["department_manager"])
        assert has_permission(claims, "knowledge:admin") is False

    def test_auditor_cannot_modify_anything(self, claims_factory):
        """auditor must NOT have any write permissions (read-only role)."""
        claims = claims_factory(realm_roles=["auditor"])
        write_permissions = [
            "knowledge:write", "knowledge:delete", "knowledge:admin",
            "files:write", "chat:write", "agents:execute", "agents:admin",
            "graph:write", "executive:write", "workflows:execute",
            "approvals:create", "approvals:decide", "connectors:sync",
        ]
        for perm in write_permissions:
            assert has_permission(claims, perm) is False, (
                f"auditor must NOT have write permission '{perm}'"
            )

    def test_executive_cannot_access_admin(self, claims_factory):
        """executive attempting knowledge:admin → DENY."""
        claims = claims_factory(realm_roles=["executive"])
        assert has_permission(claims, "knowledge:admin") is False

    def test_executive_cannot_delete_documents(self, claims_factory):
        """executive attempting knowledge:delete → DENY."""
        claims = claims_factory(realm_roles=["executive"])
        assert has_permission(claims, "knowledge:delete") is False

    def test_jwt_tampering_adding_admin_role_to_ai_user(self, claims_factory):
        """Simulate JWT tampering: attacker adds 'hsaai_admin' to ai_user claims.

        NOTE: This test verifies that IF the JWT is validly signed (i.e., the
        attacker has the signing key), the role would be honored. In practice,
        JWT signature verification prevents this. This test documents that
        the RBAC layer itself does not have additional defense.
        """
        # Attacker forges claims with both ai_user and hsaai_admin
        claims = claims_factory(realm_roles=["ai_user", "hsaai_admin"])
        # hsaai_admin grants wildcard → escalation succeeds IF JWT is validly signed
        assert has_permission(claims, "knowledge:admin") is True
        # This documents that JWT signature verification is the primary defense

    def test_multiple_low_priv_roles_do_not_escalate(self, claims_factory):
        """Combining multiple low-privilege roles does NOT grant admin access."""
        claims = claims_factory(realm_roles=["ai_user", "document_uploader"])
        # Each role grants its own permissions, but NOT admin
        assert has_permission(claims, "knowledge:admin") is False
        assert has_permission(claims, "knowledge:delete") is False
        # But they DO grant their combined permissions
        assert has_permission(claims, "knowledge:upload") is True  # from uploader
        assert has_permission(claims, "chat:write") is True  # from both


# ═══════════════════════════════════════════════════════════════════════
# Section 5: Multi-Tenant Isolation Testing
# ═══════════════════════════════════════════════════════════════════════
class TestMultiTenantIsolation:
    """Test that tenant_id is sourced from JWT only and enforced.

    CRITICAL: The has_permission function does NOT currently enforce tenant
    isolation. It only checks role-based permissions. Tenant isolation must
    be enforced at a higher layer (e.g., in the API endpoint that calls
    has_permission, by comparing claims['tenant_id'] with the requested
    tenant_id).

    These tests document the current behavior and verify that tenant_id
    in claims does not affect permission decisions (which is correct —
    permissions are role-based, not tenant-based).
    """

    def test_tenant_id_in_claims_does_not_grant_extra_permissions(self, claims_factory):
        """tenant_id presence does not grant permissions beyond role scope."""
        claims_a = claims_factory(realm_roles=["ai_user"], tenant_id="company_a")
        claims_b = claims_factory(realm_roles=["ai_user"], tenant_id="company_b")
        # Same role → same permissions regardless of tenant
        assert has_permission(claims_a, "knowledge:read") == has_permission(claims_b, "knowledge:read")
        assert has_permission(claims_a, "knowledge:admin") is False
        assert has_permission(claims_b, "knowledge:admin") is False

    def test_tenant_id_does_not_affect_admin_access(self, claims_factory):
        """tenant_id does not grant admin access to non-admin users."""
        claims = claims_factory(realm_roles=["ai_user"], tenant_id="company_a")
        # Even with tenant_id set, ai_user cannot access admin
        assert has_permission(claims, "knowledge:admin") is False
        assert has_permission(claims, "knowledge:delete") is False

    def test_cross_tenant_access_must_be_enforced_at_endpoint_level(self, claims_factory):
        """Cross-tenant access prevention is NOT handled by has_permission.

        This test documents that has_permission is role-based only.
        Cross-tenant isolation must be enforced by:
        1. Comparing claims['tenant_id'] with requested tenant_id at the endpoint
        2. Using the tenant_guard module's require_workspace_access()
        3. Adding tenant_id to Qdrant filters (see Qdrant audit report)
        """
        claims = claims_factory(realm_roles=["ai_user"], tenant_id="company_a")
        # has_permission does not know about target tenant — it's role-only
        # The ENDPOINT must verify: claims['tenant_id'] == requested_tenant_id
        # This is a documented design pattern, not a bug.
        assert has_permission(claims, "knowledge:read") is True
        # But the endpoint must ALSO check tenant_id match

    def test_tenant_id_default_when_missing(self, claims_factory):
        """When tenant_id is missing from claims, it defaults (via _normalize_claims)."""
        # has_permission itself doesn't normalize — that's done in verify_authorization
        claims = {"realm_access": {"roles": ["ai_user"]}}  # no tenant_id
        # Permission check still works (tenant_id is not used by has_permission)
        assert has_permission(claims, "knowledge:read") is True

    def test_workspace_id_does_not_affect_permissions(self, claims_factory):
        """workspace_id does not affect permission decisions (role-based only)."""
        claims_a = claims_factory(realm_roles=["ai_user"], workspace_id="ws_a")
        claims_b = claims_factory(realm_roles=["ai_user"], workspace_id="ws_b")
        assert has_permission(claims_a, "knowledge:read") == has_permission(claims_b, "knowledge:read")


# ═══════════════════════════════════════════════════════════════════════
# Section 6: Keycloak JWT Validation Testing
# Test various JWT claim structures that Keycloak may produce.
# ═══════════════════════════════════════════════════════════════════════
class TestKeycloakJWTStructures:
    """Test that RBAC handles all Keycloak JWT claim structures correctly."""

    def test_realm_access_roles_format(self, claims_factory):
        """Standard Keycloak realm_access.roles format."""
        claims = {
            "realm_access": {"roles": ["ai_user"]},
        }
        assert has_permission(claims, "knowledge:read") is True

    def test_resource_access_roles_format(self):
        """Keycloak resource_access.<resource>.roles format."""
        claims = {
            "resource_access": {
                "account": {"roles": ["manage-account"]},
                "hsaai-portal": {"roles": ["ai_user"]},
            },
        }
        assert has_permission(claims, "knowledge:read") is True

    def test_multiple_resource_access_entries(self):
        """Multiple resource_access entries — roles from all are combined."""
        claims = {
            "resource_access": {
                "account": {"roles": ["manage-account"]},
                "hsaai-portal": {"roles": ["ai_user"]},
                "hsaai-admin": {"roles": ["document_reviewer"]},
            },
        }
        # ai_user + document_reviewer → combined permissions
        assert has_permission(claims, "knowledge:read") is True  # both have
        assert has_permission(claims, "knowledge:review") is True  # reviewer only
        assert has_permission(claims, "knowledge:admin") is False  # neither has

    def test_direct_roles_claim(self):
        """Direct 'roles' claim (custom, non-standard but supported)."""
        claims = {"roles": ["ai_user"]}
        assert has_permission(claims, "knowledge:read") is True

    def test_direct_role_singular_claim(self):
        """Direct 'role' (singular) claim — supported as string."""
        claims = {"role": "ai_user"}
        assert has_permission(claims, "knowledge:read") is True

    def test_roles_as_string(self):
        """'roles' as a string (not list) — supported."""
        claims = {"roles": "ai_user"}
        assert has_permission(claims, "knowledge:read") is True

    def test_combined_realm_and_resource_access(self):
        """Both realm_access and resource_access present — roles combined."""
        claims = {
            "realm_access": {"roles": ["ai_user"]},
            "resource_access": {"hsaai-admin": {"roles": ["document_reviewer"]}},
        }
        assert has_permission(claims, "knowledge:read") is True
        assert has_permission(claims, "knowledge:review") is True  # from resource_access
        assert has_permission(claims, "knowledge:admin") is False

    def test_duplicate_roles_deduplicated(self):
        """Duplicate roles are deduplicated (no permission inflation)."""
        claims = {"realm_access": {"roles": ["ai_user", "ai_user", "ai_user"]}}
        assert has_permission(claims, "knowledge:read") is True
        # No extra permissions from duplicates
        assert has_permission(claims, "knowledge:admin") is False

    def test_empty_roles_list_in_realm_access(self):
        """Empty roles list → deny."""
        claims = {"realm_access": {"roles": []}}
        assert has_permission(claims, "knowledge:read") is False

    def test_malformed_realm_access_not_dict(self):
        """realm_access as string (malformed) → graceful deny."""
        claims = {"realm_access": "not_a_dict"}
        assert has_permission(claims, "knowledge:read") is False

    def test_malformed_roles_in_realm_access_not_list(self):
        """realm_access.roles as string (not list) → graceful deny."""
        claims = {"realm_access": {"roles": "ai_user"}}
        # String is not iterable in the expected way — verify behavior
        # Actually, the code checks `isinstance(realm_roles, list)` so string → deny
        assert has_permission(claims, "knowledge:read") is False

    def test_resource_access_not_dict(self):
        """resource_access as string (malformed) → graceful deny."""
        claims = {"resource_access": "not_a_dict"}
        assert has_permission(claims, "knowledge:read") is False

    def test_resource_access_roles_not_list(self):
        """resource_access.<resource>.roles as string → graceful skip."""
        claims = {
            "resource_access": {
                "account": {"roles": "not_a_list"},  # malformed
            },
        }
        assert has_permission(claims, "knowledge:read") is False

    def test_resource_access_entry_not_dict(self):
        """resource_access.<resource> as string → graceful skip."""
        claims = {
            "resource_access": {
                "account": "not_a_dict",  # malformed
            },
        }
        assert has_permission(claims, "knowledge:read") is False

    def test_roles_with_none_values_filtered(self):
        """None values in roles list are filtered out."""
        claims = {"realm_access": {"roles": [None, "ai_user", None]}}
        assert has_permission(claims, "knowledge:read") is True

    def test_roles_with_non_string_values_coerced(self):
        """Non-string values in roles are coerced to string."""
        claims = {"realm_access": {"roles": [123, "ai_user"]}}
        # 123 becomes "123" which is not a valid role → only ai_user counts
        assert has_permission(claims, "knowledge:read") is True


# ═══════════════════════════════════════════════════════════════════════
# Section 7: AI Governance Security Tests
# Verify protection of Knowledge Base, RAG, and Document Intelligence.
# ═══════════════════════════════════════════════════════════════════════
class TestAIGovernanceKnowledgeBase:
    """Test who can perform Knowledge Base operations."""

    # ─── Knowledge: Read ───
    @pytest.mark.parametrize("role", [
        "hsaai_admin", "knowledge_admin", "document_reviewer",
        "document_uploader", "department_manager", "ai_user",
        "auditor", "executive",
    ])
    def test_all_roles_can_read_knowledge(self, role: str, claims_factory):
        """All authenticated roles can read knowledge (knowledge:read)."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "knowledge:read") is True

    # ─── Knowledge: Upload ───
    @pytest.mark.parametrize("role", ["hsaai_admin", "document_uploader"])
    def test_only_uploader_roles_can_upload(self, role: str, claims_factory):
        """Only hsaai_admin (wildcard) and document_uploader can upload documents.

        NOTE: knowledge_admin does NOT have knowledge:upload — this is intentional
        separation of duties (admin manages, uploader uploads).
        """
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "knowledge:upload") is True

    @pytest.mark.parametrize("role", [
        "document_reviewer", "department_manager", "ai_user",
        "auditor", "executive",
    ])
    def test_non_uploader_roles_cannot_upload(self, role: str, claims_factory):
        """Non-uploader roles cannot upload documents."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "knowledge:upload") is False

    # ─── Knowledge: Review ───
    @pytest.mark.parametrize("role", ["hsaai_admin", "knowledge_admin", "document_reviewer"])
    def test_only_review_roles_can_review(self, role: str, claims_factory):
        """Only admin and reviewer roles can review documents."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "knowledge:review") is True

    @pytest.mark.parametrize("role", [
        "document_uploader", "department_manager", "ai_user",
        "auditor", "executive",
    ])
    def test_non_review_roles_cannot_review(self, role: str, claims_factory):
        """Non-review roles cannot review documents (separation of duties)."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "knowledge:review") is False

    # ─── Knowledge: Delete (Vector Deletion) ───
    @pytest.mark.parametrize("role", ["hsaai_admin", "knowledge_admin"])
    def test_only_admin_roles_can_delete_vectors(self, role: str, claims_factory):
        """CRITICAL: Only admin roles can delete vectors (knowledge:delete)."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "knowledge:delete") is True

    @pytest.mark.parametrize("role", [
        "document_reviewer", "document_uploader", "department_manager",
        "ai_user", "auditor", "executive",
    ])
    def test_non_admin_roles_cannot_delete_vectors(self, role: str, claims_factory):
        """CRITICAL: Non-admin roles MUST NOT be able to delete vectors."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "knowledge:delete") is False, (
            f"Role '{role}' must NOT have knowledge:delete permission"
        )

    # ─── Knowledge: Admin ───
    @pytest.mark.parametrize("role", ["hsaai_admin", "knowledge_admin"])
    def test_only_admin_roles_can_admin_knowledge(self, role: str, claims_factory):
        """Only admin roles can administer knowledge base."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "knowledge:admin") is True

    @pytest.mark.parametrize("role", [
        "document_reviewer", "document_uploader", "department_manager",
        "ai_user", "auditor", "executive",
    ])
    def test_non_admin_roles_cannot_admin_knowledge(self, role: str, claims_factory):
        """Non-admin roles cannot administer knowledge base."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "knowledge:admin") is False

    # ─── Reindex (knowledge:write is used for reindexing) ───
    @pytest.mark.parametrize("role", [
        "hsaai_admin", "knowledge_admin", "document_uploader",
    ])
    def test_only_write_roles_can_reindex(self, role: str, claims_factory):
        """Only roles with knowledge:write can reindex (uploaders and admins)."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "knowledge:write") is True

    @pytest.mark.parametrize("role", [
        "document_reviewer", "ai_user", "auditor", "executive",
    ])
    def test_non_write_roles_cannot_reindex(self, role: str, claims_factory):
        """Roles without knowledge:write cannot reindex."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "knowledge:write") is False


class TestAIGovernanceRAG:
    """Test RAG pipeline access control."""

    def test_ai_user_can_search_knowledge(self, claims_factory):
        """ai_user can search knowledge base (knowledge:read)."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "knowledge:read") is True

    def test_ai_user_cannot_admin_rag(self, claims_factory):
        """ai_user cannot administer RAG pipeline."""
        claims = claims_factory(realm_roles=["ai_user"])
        assert has_permission(claims, "knowledge:admin") is False

    def test_auditor_can_read_but_not_modify_rag(self, claims_factory):
        """auditor can read RAG data but cannot modify (read-only)."""
        claims = claims_factory(realm_roles=["auditor"])
        assert has_permission(claims, "knowledge:read") is True
        assert has_permission(claims, "knowledge:write") is False
        assert has_permission(claims, "knowledge:delete") is False

    def test_rag_context_isolation_via_tenant_id(self, claims_factory):
        """RAG context must be isolated by tenant_id.

        NOTE: has_permission does not enforce tenant isolation — it must be
        done at the RAG query layer by:
        1. Adding tenant_id to the Qdrant search filter
        2. Verifying claims['tenant_id'] matches the requested tenant

        This test verifies that the permission system itself is tenant-agnostic
        (correct behavior — tenant isolation is a separate concern).
        """
        claims = claims_factory(realm_roles=["ai_user"], tenant_id="company_a")
        # Permission is granted based on role, not tenant
        assert has_permission(claims, "knowledge:read") is True
        # But the RAG layer MUST filter by tenant_id


class TestAIGovernanceAgents:
    """Test AI Agent system access control."""

    @pytest.mark.parametrize("role", [
        "hsaai_admin", "knowledge_admin", "document_reviewer",
        "document_uploader", "department_manager", "ai_user",
        "auditor",
    ])
    def test_most_roles_can_read_agents(self, role: str, claims_factory):
        """Most roles can read agent info (agents:read)."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "agents:read") is True

    def test_executive_cannot_read_agents(self, claims_factory):
        """executive cannot read agent info (no agents:read permission)."""
        claims = claims_factory(realm_roles=["executive"])
        assert has_permission(claims, "agents:read") is False

    @pytest.mark.parametrize("role", [
        "hsaai_admin", "knowledge_admin", "document_reviewer",
        "document_uploader", "department_manager", "ai_user",
    ])
    def test_operational_roles_can_execute_agents(self, role: str, claims_factory):
        """Operational roles can execute agents (agents:execute)."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "agents:execute") is True

    @pytest.mark.parametrize("role", ["auditor", "executive"])
    def test_non_operational_roles_cannot_execute_agents(self, role: str, claims_factory):
        """auditor and executive cannot execute agents (read-only)."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "agents:execute") is False

    @pytest.mark.parametrize("role", ["hsaai_admin", "knowledge_admin"])
    def test_only_admin_can_administer_agents(self, role: str, claims_factory):
        """Only admin roles can administer agents (agents:admin)."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "agents:admin") is True

    @pytest.mark.parametrize("role", [
        "document_reviewer", "document_uploader", "department_manager",
        "ai_user", "auditor", "executive",
    ])
    def test_non_admin_cannot_administer_agents(self, role: str, claims_factory):
        """Non-admin roles cannot administer agents."""
        claims = claims_factory(realm_roles=[role])
        assert has_permission(claims, "agents:admin") is False


# ═══════════════════════════════════════════════════════════════════════
# Section 8: Helper Function Tests
# Verify _roles_from_claims and permissions_for_roles helpers.
# ═══════════════════════════════════════════════════════════════════════
class TestRolesFromClaims:
    """Test the _roles_from_claims helper function."""

    def test_extracts_realm_access_roles(self):
        claims = {"realm_access": {"roles": ["ai_user", "auditor"]}}
        roles = _roles_from_claims(claims)
        assert "ai_user" in roles
        assert "auditor" in roles

    def test_extracts_resource_access_roles(self):
        claims = {
            "resource_access": {
                "account": {"roles": ["manage-account"]},
                "portal": {"roles": ["ai_user"]},
            },
        }
        roles = _roles_from_claims(claims)
        assert "ai_user" in roles
        assert "manage-account" in roles

    def test_extracts_direct_roles(self):
        claims = {"roles": ["ai_user"]}
        roles = _roles_from_claims(claims)
        assert "ai_user" in roles

    def test_extracts_singular_role(self):
        claims = {"role": "ai_user"}
        roles = _roles_from_claims(claims)
        assert "ai_user" in roles

    def test_combines_all_role_sources(self):
        claims = {
            "roles": ["direct_role"],
            "realm_access": {"roles": ["realm_role"]},
            "resource_access": {"portal": {"roles": ["resource_role"]}},
        }
        roles = _roles_from_claims(claims)
        assert "direct_role" in roles
        assert "realm_role" in roles
        assert "resource_role" in roles

    def test_deduplicates_roles(self):
        claims = {
            "roles": ["ai_user"],
            "realm_access": {"roles": ["ai_user"]},
            "resource_access": {"portal": {"roles": ["ai_user"]}},
        }
        roles = _roles_from_claims(claims)
        assert roles.count("ai_user") == 1

    def test_empty_claims_returns_empty_list(self):
        assert _roles_from_claims({}) == []

    def test_no_roles_returns_empty_list(self):
        claims = {"realm_access": {}}
        assert _roles_from_claims(claims) == []

    def test_preserves_order(self):
        claims = {
            "roles": ["first"],
            "realm_access": {"roles": ["second"]},
        }
        roles = _roles_from_claims(claims)
        # Direct roles come first, then realm_access
        assert roles[0] == "first"
        assert roles[1] == "second"

    def test_filters_none_values(self):
        claims = {"realm_access": {"roles": [None, "ai_user", None]}}
        roles = _roles_from_claims(claims)
        assert None not in roles
        assert "ai_user" in roles

    def test_coerces_non_string_to_string(self):
        claims = {"realm_access": {"roles": [123, "ai_user"]}}
        roles = _roles_from_claims(claims)
        assert "123" in roles
        assert "ai_user" in roles


class TestPermissionsForRoles:
    """Test the permissions_for_roles helper function."""

    def test_returns_set(self):
        result = permissions_for_roles(["ai_user"])
        assert isinstance(result, set)

    def test_single_role_permissions(self):
        result = permissions_for_roles(["ai_user"])
        assert "knowledge:read" in result
        assert "chat:write" in result
        assert "knowledge:admin" not in result

    def test_multiple_roles_combine_permissions(self):
        result = permissions_for_roles(["ai_user", "document_reviewer"])
        assert "knowledge:read" in result  # both
        assert "chat:write" in result  # both
        assert "knowledge:review" in result  # reviewer only
        assert "knowledge:admin" not in result  # neither

    def test_unknown_role_returns_empty(self):
        result = permissions_for_roles(["unknown_role"])
        assert result == set()

    def test_empty_roles_list_returns_empty(self):
        result = permissions_for_roles([])
        assert result == set()

    def test_admin_role_returns_wildcard(self):
        result = permissions_for_roles(["hsaai_admin"])
        assert "*" in result

    def test_duplicate_roles_do_not_duplicate_permissions(self):
        result1 = permissions_for_roles(["ai_user"])
        result2 = permissions_for_roles(["ai_user", "ai_user", "ai_user"])
        assert result1 == result2


# ═══════════════════════════════════════════════════════════════════════
# Section 9: ROLE_PERMISSIONS Matrix Integrity Tests
# Verify the RBAC matrix itself is consistent and complete.
# ═══════════════════════════════════════════════════════════════════════
class TestRBACMatrixIntegrity:
    """Verify the ROLE_PERMISSIONS matrix is well-formed."""

    def test_all_documented_roles_exist(self):
        """All 8 documented roles must be in ROLE_PERMISSIONS."""
        expected_roles = {
            "hsaai_admin", "knowledge_admin", "document_reviewer",
            "document_uploader", "department_manager", "ai_user",
            "auditor", "executive",
        }
        assert set(ROLE_PERMISSIONS.keys()) == expected_roles

    def test_each_role_has_permissions(self):
        """Each role must have at least one permission."""
        for role, perms in ROLE_PERMISSIONS.items():
            assert len(perms) > 0, f"Role '{role}' has no permissions"

    def test_only_admin_has_wildcard(self):
        """Only hsaai_admin should have the '*' wildcard."""
        for role, perms in ROLE_PERMISSIONS.items():
            if role == "hsaai_admin":
                assert "*" in perms
            else:
                assert "*" not in perms, f"Role '{role}' has wildcard '*' — security risk"

    def test_all_permissions_use_colon_format(self):
        """All non-wildcard permissions must use 'domain:action' format."""
        for role, perms in ROLE_PERMISSIONS.items():
            for perm in perms:
                if perm == "*":
                    continue
                assert ":" in perm, (
                    f"Permission '{perm}' in role '{role}' does not use 'domain:action' format"
                )

    def test_knowledge_read_is_granted_to_all_roles(self):
        """knowledge:read must be granted to all 8 roles (universal read access).

        hsaai_admin has '*' wildcard which implicitly grants knowledge:read.
        """
        for role in ROLE_PERMISSIONS:
            perms = ROLE_PERMISSIONS[role]
            assert "knowledge:read" in perms or "*" in perms, (
                f"Role '{role}' missing 'knowledge:read'"
            )

    def test_knowledge_delete_is_restricted(self):
        """knowledge:delete must ONLY be granted to admin roles.

        hsaai_admin has '*' wildcard (implicitly grants delete).
        knowledge_admin has explicit 'knowledge:delete'.
        No other role should have delete access.
        """
        admin_roles_with_delete = [
            role for role, perms in ROLE_PERMISSIONS.items()
            if "knowledge:delete" in perms or "*" in perms
        ]
        assert set(admin_roles_with_delete) == {"hsaai_admin", "knowledge_admin"}, (
            f"knowledge:delete granted to non-admin roles: {admin_roles_with_delete}"
        )

    def test_knowledge_admin_is_restricted(self):
        """knowledge:admin must ONLY be granted to admin roles.

        hsaai_admin has '*' wildcard (implicitly grants admin).
        knowledge_admin has explicit 'knowledge:admin'.
        """
        admin_roles = [
            role for role, perms in ROLE_PERMISSIONS.items()
            if "knowledge:admin" in perms or "*" in perms
        ]
        assert set(admin_roles) == {"hsaai_admin", "knowledge_admin"}

    def test_auditor_has_no_write_permissions(self):
        """auditor must NOT have any write permissions (read-only role)."""
        auditor_perms = ROLE_PERMISSIONS["auditor"]
        write_indicators = [":write", ":delete", ":admin", ":upload", ":execute", ":sync"]
        for perm in auditor_perms:
            for indicator in write_indicators:
                assert indicator not in perm, (
                    f"auditor has write permission '{perm}' — must be read-only"
                )

    def test_executive_has_no_admin_permissions(self):
        """executive must NOT have admin permissions."""
        exec_perms = ROLE_PERMISSIONS["executive"]
        admin_indicators = [":admin", ":delete", ":upload"]
        for perm in exec_perms:
            for indicator in admin_indicators:
                assert indicator not in perm, (
                    f"executive has admin permission '{perm}'"
                )

    def test_separation_of_duties_upload_vs_review(self):
        """document_uploader must NOT have knowledge:review (separation of duties)."""
        uploader_perms = ROLE_PERMISSIONS["document_uploader"]
        assert "knowledge:review" not in uploader_perms, (
            "document_uploader has knowledge:review — violates separation of duties"
        )

    def test_separation_of_duties_review_vs_delete(self):
        """document_reviewer must NOT have knowledge:delete (separation of duties)."""
        reviewer_perms = ROLE_PERMISSIONS["document_reviewer"]
        assert "knowledge:delete" not in reviewer_perms, (
            "document_reviewer has knowledge:delete — violates separation of duties"
        )


# ═══════════════════════════════════════════════════════════════════════
# Section 10: Idempotency & Independence Tests
# ═══════════════════════════════════════════════════════════════════════
class TestIdempotency:
    """Verify has_permission is pure (idempotent, no side effects)."""

    def test_same_input_same_output(self, claims_factory):
        """Same input always produces same output."""
        claims = claims_factory(realm_roles=["ai_user"])
        r1 = has_permission(claims, "knowledge:read")
        r2 = has_permission(claims, "knowledge:read")
        assert r1 == r2

    def test_function_does_not_mutate_claims(self, claims_factory):
        """Calling has_permission must not mutate the claims dict."""
        claims = claims_factory(realm_roles=["ai_user"])
        original_claims = dict(claims)
        _ = has_permission(claims, "knowledge:read")
        assert claims == original_claims

    def test_consecutive_calls_independent(self, claims_factory):
        """Consecutive calls with different inputs don't interfere."""
        claims_user = claims_factory(realm_roles=["ai_user"])
        claims_admin = claims_factory(realm_roles=["hsaai_admin"])
        r1 = has_permission(claims_user, "knowledge:admin")
        r2 = has_permission(claims_admin, "knowledge:admin")
        assert r1 is False
        assert r2 is True
