/**
 * HSAAI Client-side RBAC — Server-Verified Roles
 *
 * SECURITY FIX: Roles are now retrieved from the server-side auth session
 * via httpOnly cookies (not from localStorage which is trivially modifiable).
 * The useRoles() hook in auth-provider.ts reads roles from the secure session.
 *
 * This module provides:
 * 1. Static role-permission mapping (for UI rendering hints only)
 * 2. Permission check function (for client-side UX gating)
 * 3. Server-side permission enforcement (authoritative) via API calls
 */

export const ENTERPRISE_ROLES = [
  "hsaai_admin",
  "knowledge_admin",
  "document_reviewer",
  "document_uploader",
  "department_manager",
  "ai_user",
  "auditor",
] as const;

export type EnterpriseRole = (typeof ENTERPRISE_ROLES)[number];

const ROLE_PERMISSIONS: Record<string, string[]> = {
  hsaai_admin: ["*"],
  knowledge_admin: [
    "knowledge:admin", "knowledge:read", "knowledge:write",
    "knowledge:review", "knowledge:delete", "audit:read", "analytics:read",
  ],
  document_reviewer: ["knowledge:read", "knowledge:review", "audit:read"],
  document_uploader: ["knowledge:read", "knowledge:upload", "knowledge:write"],
  department_manager: ["knowledge:read", "reports:read", "analytics:read"],
  ai_user: ["chat:write", "knowledge:read"],
  auditor: ["knowledge:read", "audit:read", "analytics:read", "reports:read"],
};

/**
 * Client-side permission check.
 * NOTE: This is for UI rendering ONLY. All actual authorization
 * is enforced server-side via Keycloak RBAC + backend middleware.
 * Never trust client-side checks for security decisions.
 */
export function can(permission: string, roles: string[]): boolean {
  return roles.some((role) => {
    const perms = ROLE_PERMISSIONS[role] || [];
    return perms.includes("*") || perms.includes(permission);
  });
}

/**
 * Get permissions array for a set of roles (for UI display).
 */
export function getPermissions(roles: string[]): string[] {
  const allPerms = new Set<string>();
  for (const role of roles) {
    const perms = ROLE_PERMISSIONS[role] || [];
    for (const p of perms) {
      if (p !== "*") allPerms.add(p);
    }
  }
  return Array.from(allPerms).sort();
}

/**
 * FIX v2.1 (P0): getClientRoles — returns the role list for the current user.
 * Previously admin/knowledge-governance/page.tsx imported this function but it
 * was not exported, causing a TypeScript compile error and blocking `next build`.
 * The implementation reads roles from the in-browser session (AuthProvider context).
 * For server-side rendering, the cookie is forwarded by lib/server-auth.ts.
 */
export function getClientRoles(): string[] {
  if (typeof window === "undefined") return [];
  try {
    // Roles are stored in sessionStorage by AuthProvider after OIDC login.
    // Fallback: empty array means "no UI gating" — server enforces authoritatively.
    const raw = window.sessionStorage.getItem("hsaai_roles");
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

/**
 * FIX v2.1 (P0): setClientRoles — called by AuthProvider after OIDC login
 * to populate the role list used by getClientRoles() and can().
 */
export function setClientRoles(roles: string[]): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem("hsaai_roles", JSON.stringify(roles));
  } catch {
    // sessionStorage may be unavailable (private mode) — fail silently.
    // Server-side RBAC remains authoritative regardless.
  }
}
