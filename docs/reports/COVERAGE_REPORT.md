# COVERAGE_REPORT

**Original41.92%; prior candidate54.78%; current56.56%; target≥80%: FAIL.**
Current covered9656/17071; missing7415; at least4001 more covered statements needed at this denominator.

Existing --cov=services --cov=packages --cov-fail-under=80 preserved. No new exclusion or no-cover pragma. Statement coverage, not branch/GPU/runtime/JS coverage. New measurement excludes the E2E test directory from execution; it does not omit any production package from the coverage scope.

| Component | Covered | Statements | Coverage |
|---|---|---|---|
| services/backend_core/enterprise_os/router.py | 520 | 607 | 85.67% |
| services/backend_core/enterprise_integrations/phase5_connectors.py | 349 | 389 | 89.72% |
| packages/common/security/rate_limit.py | 115 | 119 | 96.64% |
| services/workflow_engine/main.py | 208 | 229 | 90.83% |
| services/backend_core/knowledge/service.py | 177 | 192 | 92.19% |
| services/rag_engine/main.py | 152 | 546 | 27.84% |
| services/backend_core/security/encryption.py | 66 | 69 | 95.65% |

Remaining uncovered production modules and exact missing statements are in evidence/coverage-20260919.json. More genuine core tests are required; providing a Docker host alone does not close this gap.
