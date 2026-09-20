# HSAAI ABAC Engine — Open Policy Agent (v3.0)

This directory contains OPA policies for Attribute-Based Access Control (ABAC)
across HSAAI services.

## Architecture

```
                    ┌──────────────────┐
                    │   HSAAI Service  │
                    │  (FastAPI route) │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  abac.py helper  │
                    │  (check_policy)  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   OPA Sidecar    │
                    │  :8181/v1/data   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   policies/      │
                    │  - rbac.rego     │
                    │  - abac.rego     │
                    │  - tenant.rego   │
                    │  - data_class.rego│
                    └──────────────────┘
```

## Policies

### `rbac.rego` — Role-Based Access Control (baseline)
Maps roles to permissions (same as Python RBAC, but enforced in OPA).

### `abac.rego` — Attribute-Based Access Control
Evaluates dynamic policies based on:
- User attributes (department, role, location, time-of-day)
- Resource attributes (classification, owner, tenant, sensitivity)
- Action (read, write, delete, approve, export)
- Environment (IP, device, MFA status)

### `tenant.rego` — Tenant Isolation
Ensures users can only access their tenant's resources (unless hsaai_admin).

### `data_class.rego` — Data Classification
Restricts access to Confidential/Restricted data based on user clearance.

## Usage

### Check policy from Python
```python
from packages.common.abac.client import check_access

allowed = check_access(
    user={"sub": "user-123", "roles": ["ai_user"], "department": "HR", "tenant_id": "default"},
    action="documents:read",
    resource={"type": "document", "classification": "confidential", "tenant_id": "default", "owner": "user-456"},
)
if not allowed:
    raise HTTPException(403, "Access denied by ABAC policy")
```

### Deploy OPA
```bash
docker compose -f infrastructure/opa/docker-compose.opa.yml up -d
```

### Test a policy
```bash
curl -X POST http://opa:8181/v1/data/hsaai/abac/allow \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "user": {"roles": ["ai_user"], "department": "HR", "tenant_id": "default"},
      "action": "documents:read",
      "resource": {"type": "document", "classification": "internal", "tenant_id": "default"}
    }
  }'
```
