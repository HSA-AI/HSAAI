# HSAAI ABAC Policy (v3.0)
# Attribute-Based Access Control — evaluates dynamic policies based on
# user, resource, action, and environment attributes.

package hsaai.abac

import data.hsaai.rbac

# Default deny
default allow := false

# ─── Main allow rule ───
# A request is allowed if:
#   1. RBAC permits the action (baseline), AND
#   2. ABAC rules don't deny it (e.g., tenant isolation, classification, time)

allow {
    rbac.has_permission(input.user.roles, input.action)
    not deny
}

# ─── Deny rules (higher priority) ───

# Deny: cross-tenant access (unless hsaai_admin)
deny {
    input.user.tenant_id != input.resource.tenant_id
    not "hsaai_admin" in input.user.roles
}

# Deny: accessing confidential data without clearance
deny {
    input.resource.classification == "confidential"
    not user_has_clearance(input.user, "confidential")
}

# Deny: accessing restricted data without explicit clearance
deny {
    input.resource.classification == "restricted"
    not user_has_clearance(input.user, "restricted")
}

# Deny: write actions outside business hours for non-admins
# (Business hours: 6am-8pm UTC, Sunday-Thursday)
deny {
    input.action in {"write", "delete", "approve"}
    not "hsaai_admin" in input.user.roles
    not is_business_hours(input.env.time)
}

# Deny: access from outside corporate network for sensitive actions
deny {
    input.action in {"export", "delete", "admin_change"}
    not is_corporate_network(input.env.ip)
    not "hsaai_admin" in input.user.roles
}

# Deny: MFA not verified for admin actions
deny {
    input.action in {"admin_change", "budget_override", "external_write"}
    not input.user.mfa_verified
}

# ─── Helper functions ───

user_has_clearance(user, required_level) {
    clearance_levels := {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
    user_clearance := clearance_levels[user.clearance]
    required := clearance_levels[required_level]
    user_clearance >= required
}

is_business_hours(time) {
    # time is RFC3339 format: "2026-06-24T14:30:00Z"
    hour := parse_int(split(split(time, "T")[1], ":")[0])
    hour >= 6
    hour < 20
    # Day of week: 0=Sunday, 6=Saturday
    day := dayofweek(time)
    day >= 0
    day <= 4
}

is_corporate_network(ip) {
    # Private CIDR ranges
    startswith(ip, "10.")
} {
    startswith(ip, "172.")
    octets := split(ip, ".")
    second := parse_int(octets[1])
    second >= 16
    second <= 31
} {
    startswith(ip, "192.168.")
}

# ─── Decision metadata (for audit logging) ───
decision := {
    "allow": allow,
    "reason": reason,
    "user_roles": input.user.roles,
    "action": input.action,
    "resource_type": input.resource.type,
    "resource_tenant": input.resource.tenant_id,
    "user_tenant": input.user.tenant_id,
}

reason := "rbac_permitted_abac_no_deny" {
    allow
}

reason := "cross_tenant_access" {
    input.user.tenant_id != input.resource.tenant_id
    not "hsaai_admin" in input.user.roles
}

reason := "insufficient_clearance" {
    input.resource.classification in {"confidential", "restricted"}
    not user_has_clearance(input.user, input.resource.classification)
}

reason := "outside_business_hours" {
    input.action in {"write", "delete", "approve"}
    not is_business_hours(input.env.time)
    not "hsaai_admin" in input.user.roles
}

reason := "non_corporate_ip" {
    input.action in {"export", "delete", "admin_change"}
    not is_corporate_network(input.env.ip)
    not "hsaai_admin" in input.user.roles
}

reason := "mfa_not_verified" {
    input.action in {"admin_change", "budget_override", "external_write"}
    not input.user.mfa_verified
}

reason := "rbac_denied" {
    not rbac.has_permission(input.user.roles, input.action)
}
