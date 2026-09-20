# HSAAI RBAC with Keycloak Roles

HSAAI uses Keycloak JWT Access Tokens as the authoritative identity source.

## Extracted roles
The backend extracts roles from:
- `realm_access.roles`
- `resource_access.<client>.roles`
- legacy `roles` / `role` claims for compatibility

## Enterprise roles
| Role | Access |
|---|---|
| hsaai_admin | Full system access |
| knowledge_admin | Knowledge Base administration, review, delete, analytics |
| document_reviewer | Approve/reject/archive documents and read audit |
| document_uploader | Register/upload documents |
| department_manager | Department-level documents and reports |
| ai_user | Chat and knowledge search |
| auditor | Read-only logs, analytics, reports |

## Environment
```env
KEYCLOAK_ISSUER=http://keycloak:8080/realms/hsaai
KEYCLOAK_AUDIENCE=hsaai-api
KEYCLOAK_CLIENT_ID=hsaai-web
VERIFY_KEYCLOAK_AUDIENCE=false
```

Set `VERIFY_KEYCLOAK_AUDIENCE=true` when the Keycloak client audience is fully configured.
