# HSAAI 2.1.0 Enterprise Repository Reordered

This release restructures HSAAI into a production-oriented enterprise repository layout suitable for internal AI platform development, technical review, staging deployment, and executive presentation.

## Included
- Web application moved to `apps/web`.
- Backend services moved to `services/*`.
- Shared common, integrations, and governance packages added under `packages/*`.
- Docker/Kubernetes/Helm/Keycloak/Monitoring moved to `infrastructure/*`.
- Documentation reorganized by architecture, operations, integration, governance, security, UI, API, and deliverables.
- CI/CD workflow templates added.

## Runtime Note
Use the compose files in `infrastructure/docker/`. The original service code is preserved; only paths were reorganized.
