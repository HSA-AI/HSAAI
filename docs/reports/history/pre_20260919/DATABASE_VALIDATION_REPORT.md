# DATABASE_VALIDATION_REPORT

**Overall: PARTIAL.** Actual local SQLite relational tests and isolated native Redis acceptance pass. Production database acceptance remains BLOCKED.

| Engine/store | Executed evidence | Remaining |
|---|---|---|
| SQLite | Knowledge versions/audit/FK retention, scoped document/permission lifecycle, durable approval fields, legacy agent/graph CRUD and review chains in real temporary databases | SQLite is a test engine; it does not prove PostgreSQL RLS/row-lock/role semantics. |
| Redis 6.2.14 native | 9/9 checks PASS: connect, R/W, TTL, transaction, 200 concurrent increments, RDB snapshot, controlled outage, restart persistence, separate backup restore (7.707 s) | Production Redis image/version, ACL/TLS, Sentinel/cluster and app connection/recovery not tested. |
| PostgreSQL | Schema/model/migration code and static constraints reviewed | Empty upgrade, upgrade from real old schema, indexes/roles/RLS, seeds, app R/W, restart, backup/restore and recovery need live PostgreSQL. |
| Qdrant | Transport-boundary scope/deletion/error tests; wait=true cleanup request | Live embedding/vector indexing/search, storage, snapshots/restore and restart required. |
| Neo4j / MinIO / MLflow / Keycloak database | Definitions/source preserved | Actual connections, storage, data integrity, backup/restore and recovery not tested. |


Alembic revisions are preserved through 0008. Revision 0006 adds a frozen complete schema snapshot; 0007 persists multi-person/SLA approval state; 0008 adds tenant/workspace ownership to knowledge permissions. Historical default-scope rows remain default-scope and require deliberate ownership migration by the company. No guessed company ownership or production seed users were inserted.

Knowledge approval no longer falsely marks a document vector-indexed. Archive/delete checks vector cleanup before state changes; failed cleanup returns an explicit retryable error and retains the record. Soft deletion retains audit/version foreign keys while hiding deleted content. Actual distributed DB/vector atomicity, concurrent reviewers on PostgreSQL and reconciliation after a crash still need fault injection.

Native Redis evidence: `evidence/redis-native-final.json`; reproducible runner `scripts/validation/redis_native_acceptance.py`. No production data was touched. The native server is Redis 6.2.14, not a certification of the declared container image.
