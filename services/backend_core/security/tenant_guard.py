import logging
from dataclasses import dataclass
from typing import Iterable


_logger = logging.getLogger("hsaai.tenant_guard")


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    organization_id: str
    workspace_id: str
    user_id: str
    roles: tuple[str, ...]


class TenantAccessError(PermissionError):
    pass


# FIX S-14: Removed undocumented 'system_admin' magic role.
# 'system_admin' was never defined in the Keycloak realm, never documented in
# docs/security/RBAC_KEYCLOAK_ROLES.md, and provided an undocumented backdoor
# that bypassed every tenant-isolation check. Cross-workspace / cross-tenant
# access is now gated on BOTH:
#   (a) the caller carries the 'hsaai_admin' realm role, AND
#   (b) the caller has been explicitly granted the 'tenant:cross' permission
#       (e.g. via the per-tenant permissions table / RBAC policy).
# Neither condition alone is sufficient. This matches the documented access
# matrix in docs/security/ACCESS_CONTROL_MATRIX.md.

CROSS_TENANT_PERMISSION = "tenant:cross"
ADMIN_ROLE = "hsaai_admin"


def require_workspace_access(
    context: TenantContext,
    workspace_id: str,
    granted_permissions: Iterable[str] = (),
) -> None:
    """Raise TenantAccessError unless the caller may access `workspace_id`.

    FIX S-14: Same-workspace access is always allowed. Cross-workspace access
    requires (a) hsaai_admin role AND (b) explicit 'tenant:cross' permission.
    """
    if context.workspace_id == workspace_id:
        return
    granted = set(granted_permissions)
    if ADMIN_ROLE in context.roles and CROSS_TENANT_PERMISSION in granted:
        _logger.info(
            "cross-workspace access granted: user=%s target_workspace=%s (hsaai_admin + tenant:cross)",
            context.user_id, workspace_id,
        )
        return
    raise TenantAccessError(
        "cross-workspace access denied: requires hsaai_admin role AND explicit 'tenant:cross' permission"
    )


def build_qdrant_filter(context: TenantContext) -> dict:
    return {
        "must": [
            {"key": "tenant_id", "match": {"value": context.tenant_id}},
            {"key": "organization_id", "match": {"value": context.organization_id}},
            {"key": "workspace_id", "match": {"value": context.workspace_id}},
        ]
    }


def can(context: TenantContext, permission: str, granted_permissions: Iterable[str]) -> bool:
    """Return True iff `permission` is granted to the caller.

    FIX S-14: Removed the 'system_admin' bypass. The 'tenant:cross' permission
    additionally requires the 'hsaai_admin' realm role (defense in depth —
    a misconfigured permission grant alone cannot enable cross-tenant access).
    """
    granted = set(granted_permissions)
    if permission == CROSS_TENANT_PERMISSION:
        return ADMIN_ROLE in context.roles and CROSS_TENANT_PERMISSION in granted
    return permission in granted
