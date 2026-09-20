# CHANGES_AND_ROOT_CAUSES

Source files/features and prior fixes were preserved. Baseline 351 backend PASS increased to 598; 38 frontend tests remain passing. Final package name follows the owner request; the code is not reverted to v1.

| Area | Root cause | Correction | Evidence/limit |
|---|---|---|---|
| Workflow | Some paths failed to await steps, used body identity/token or lost history/continuation | Verified scope/auth, correct awaits/failure state/approval resume, bounded step definitions and no stored body token | test_workflow_execution.py; process-local state still needs durable storage |
| Approvals | Critical multi-person/SLA fields not persisted consistently | Additive migration 0007; independent reviewers; tenant/workspace checks, row-lock intent, notification await | test_approval_persistence.py; SQLite passed, PostgreSQL locking untested |
| Embedding | Wrong environment lookup, malformed or zero vectors/cross-model cache | Model/revision-sensitive locked cache, dimension/finite/nonzero validation, failed-batch atomic publication | test_embedding_integrity.py; actual weight load untested |
| Connector/LLM | Wrong OAuth scope/audience use, app-only /me misuse, CSRF token lost and raw provider errors | Scope-aware cache, Power BI scope, Outlook sender, SAP CSRF retained, bounded timeouts and sanitized primary errors | test_connector_http_contracts.py + test_llm_gateway_behavior.py |
| Rate-limit identity | Client-supplied identity/forwarded headers could select counters | Use verified identity/peer address; Redis timeout/unique members and stronger 429 assertions | test_rate_limit_identity.py; remaining fail-open path listed separately |
| Phase 5 | Fallback strings and fixed statuses claimed success while providers failed | Actual failure statuses, empty failed answers, scoped telemetry, verified forwarding; unimplemented workflow integration reports failure | test_phase5_failure_semantics.py |
| OAuth role boundary | Roles from unrelated OAuth clients were trusted | Allow only configured HSAAI client roles; preserve legitimate realm/direct roles | test_role_client_boundary.py |
| Marketplace | Canary activation replaced stable pointer too early; stale metrics could roll back new production | Keep stable until full rollout, safe rollback/current version, cumulative weighted counters | test_marketplace_rollout.py; real traffic/tenant ownership still open |
| Knowledge | ORM registration used obsolete JSON field names; vector cleanup failures were swallowed; permission rows unscoped | Correct JSON model fields, scoped services/routes, guarded cleanup and soft deletion retaining audit/version FKs, migration 0008 | test_knowledge_lifecycle.py + original backend tests |
| Encryption | Encoded Fernet key was decoded twice; concurrent salt creation returned different/empty salts | Preserve validated encoded key; atomically publish complete private persistent salt; refuse corrupt salt/tampering | 15 encryption cases, real crypto; retain key+salt for restore |
| Legacy Enterprise OS | JSON fields mismatched models; agents/approvals/graph/search crossed scopes; any one reviewer could declare execution | Correct persisted fields/audit tenant, scoped queries/default agents, independent review chain, prevent risk downgrade, truthful routed/pending-executor statuses | 14 SQLite tests; CoE/FinOps global ownership remains High |
| Test fixtures | Broad exception handlers could swallow schema/import failures as skips | Failures now surface; authenticated test prerequisites explicitly classified | Full regression; 11 remaining credential-dependent E2E |
| Production config | Encryption key generation/injection missing; metadata claimed stable production | Generate private key/config, required Compose key/persistent salt/DEBUG=false, candidate metadata and aligned manifest tags | config-generator-validation.json; Docker runtime still unavailable |
| Documentation | Placeholder PKCE runbook and old candidate status/partial PDF traceability | Complete Arabic handover runbook, root evidence/report precedence, 100-page lossless-clause matrix and explicit blockers | Current reports + history retained |


Hash-based new seed/A-B identifiers use SHA-256. Existing stored IDs/data are not mass-rewritten; new assignments may differ and require upgrade review. Legacy default-scope database rows are retained and need deliberate ownership migration. No real company email/notification was sent and no external business-system data was modified.
