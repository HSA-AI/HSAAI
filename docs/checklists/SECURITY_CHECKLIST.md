# Security Checklist

- [ ] Replace every `CHANGE_ME` in `.env.production`.
- [ ] Set `ALLOW_DEV_RBAC=false` in production.
- [ ] Confirm Keycloak JWT validation with the real issuer.
- [ ] Configure roles and role mappings in Keycloak.
- [ ] Restrict `CORS_ALLOW_ORIGINS` to the real HTTPS domain only.
- [ ] Confirm uploads block executable/script extensions.
- [ ] Confirm Nginx HTTPS, HSTS, X-Frame-Options, and X-Content-Type-Options.
- [ ] Confirm audit logging for login, upload, delete, approval, integration access, admin changes, and LLM requests.
- [ ] Confirm connector UI/API never returns client secrets or passwords.
- [ ] Confirm database and Qdrant volumes are backed up.
