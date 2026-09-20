# Environment Variables

Critical variables are listed in `.env.production.example`.

## Mandatory production variables
- `APP_ENV=production`
- `DATABASE_URL`, `DIRECT_URL`
- `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`, `KEYCLOAK_ISSUER`
- `QDRANT_URL`, `QDRANT_COLLECTION`, optional `QDRANT_API_KEY`
- `DOMAIN_NAME`, `SSL_EMAIL`
- `CORS_ALLOW_ORIGINS`

## Enterprise connectors
Use these exact prefixes:
- SAP: `SAP_BASE_URL`, `SAP_CLIENT_ID`, `SAP_CLIENT_SECRET`, `SAP_USERNAME`, `SAP_PASSWORD`, `SAP_SYSTEM_ID`
- SharePoint: `SHAREPOINT_TENANT_ID`, `SHAREPOINT_CLIENT_ID`, `SHAREPOINT_CLIENT_SECRET`, `SHAREPOINT_SITE_ID`, `SHAREPOINT_DRIVE_ID`
- Active Directory: `AD_URL`, `AD_DOMAIN`, `AD_BIND_DN`, `AD_BIND_PASSWORD`, `AD_BASE_DN`

Secrets must never be committed to Git. Use `.env.production` locally or a real secret manager in deployment.
