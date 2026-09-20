# SECURITY_VALIDATION_REPORT

2026-09-19: **NOT APPROVED**. No severity suppression or formal exception.

| Scope | Critical | High | Medium | Low |
|---|---|---|---|---|
| Bandit --ignore-nosec | Not a scanner category | 0 | 52 | 57 |
| Open / partly mitigated manual findings | 0 observed | 3 | 1 | 0 |
| Combined observed | 0 | 3 | 53 | 57 |

Bandit scanned40989LOC, zero parse errors; raw evidence preserved in bandit-20260919.json. These counts do not certify unscanned images, GPU dependencies, runtime or DAST. Previous npm/pip audits remain dated2026-09-14 and are not new scan results.

| ID | Severity | Status | Evidence / action |
|---|---|---|---|
| MAN-H01 | High | PARTIAL | CoE/FinOps ownership and queries repaired,34 new tests pass. Migration0009 adds7 table scopes, indexes and PostgreSQL RLS; workspace context propagated. Real PostgreSQL upgrade/RLS and provenance-based legacy default/default reassignment still require acceptance. |
| MAN-H02 | High | OPEN | rag_engine/main.py upload_document: PII block raises HTTPException inside a broad except Exception that continues indexing. Reject before storage/indexing; fail closed on required PII service failure; propagate authentication and validate provider decision. |
| MAN-H03 | High | OPEN | rag_engine/main.py get_document omits ACL; delete_document filters tenant but omits workspace and mutation permission, swallows provider errors and returns deleted. Enforce scope/ACL/RBAC, verified mutation and honest failures. |
| MAN-M01 | Medium | CLOSED IN CODE / LOCAL VALIDATION | Bounded HTTP rate limiter; fail closed; atomic Redis admission. Actual loopback Redis concurrency/outage/recovery passed. Production image/HA behavior still unvalidated. |
| MAN-M02 | Medium | CLOSED IN CODE / UNIT VALIDATION | Ten Phase5 connectors sanitize errors/logs, bound retries, restore circuit state;48 new HTTP transport tests passed. Real provider credentials not used. |
| MAN-M03 | Medium | OPEN | Images/model provenance not all pinned to validated immutable digests; complete image SBOM/scans/signing on build host. |

Increased manual High count reflects additional review findings, not removal of previous fixes. All prior findings and scans remain in history. No claim of complete penetration testing, compliance certification, or production security approval.
