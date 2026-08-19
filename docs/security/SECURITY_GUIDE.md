# Security Guide

- Use Keycloak OIDC for SSO.
- Enforce RBAC on every API and page.
- Enable MFA in Keycloak for admins and sensitive roles.
- Use tenant_id/workspace_id/department filters in all data queries.
- Sensitive actions must create approval requests.
- Secrets must be injected through environment variables or Kubernetes secrets.
- Enable secure headers, rate limiting, audit logs, and internal-only mode.
- Classify data as Public, Internal, Confidential, Restricted, Highly Restricted.
