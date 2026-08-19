# Backup, Restore, and Disaster Recovery

## Backup targets

- PostgreSQL database.
- Qdrant collections.
- Local uploads.
- Local models metadata.
- Keycloak realm/export.
- Audit logs.
- Helm values and Kubernetes secrets.

## Suggested backup schedule

| Asset | Frequency | Retention |
|---|---:|---:|
| PostgreSQL | Every 6 hours | 30 days |
| Qdrant snapshots | Daily | 30 days |
| Upload storage | Daily incremental | 90 days |
| Keycloak realm | On every change | 180 days |
| Audit logs | Continuous archival | 1 year or policy-driven |

## Restore order

1. Restore Kubernetes namespace and secrets.
2. Restore PostgreSQL.
3. Restore Qdrant collections/snapshots.
4. Restore local uploads.
5. Restore Keycloak realm.
6. Restart backend services.
7. Run smoke tests.
8. Run RAG consistency check.
9. Run admin login check.

## DR objectives

- RPO: configurable, recommended 6 hours.
- RTO: configurable, recommended 2–4 hours for single-cluster deployment.
- For higher availability, use multi-node PostgreSQL, replicated object storage, and multi-node Qdrant.
