# COVERAGE_REPORT

**Previous: 41.92%. Final: 54.78%. Required: ≥80%. Result: FAIL.** Improvement: 12.86 percentage points. Final coverage: 9319 covered / 17013 executable statements; 7694 missing. At the current denominator, at least **4292 additional statements** need meaningful coverage to reach 80%. Fixes can change the denominator.

The actual whole-suite command uses the existing `--cov=services --cov=packages --cov-fail-under=80` in pytest.ini. No gate was lowered and no additional production exclusion was introduced. Existing configuration exclusions (including deprecated paths, migrations in coverage's omit pattern, `__repr__`, TYPE_CHECKING and existing no-cover pragmas) are retained and explicitly visible in pyproject.toml; 75 excluded statements are reported. This is measured Python line coverage, not branch coverage, GPU validation, migration execution coverage or frontend JS coverage. Do not infer 90% critical-path assurance from aggregate coverage.

| Critical component | Covered | Statements | Coverage |
|---|---|---|---|
| services/workflow_engine/main.py | 208 | 229 | 90.83% |
| services/backend_core/approvals/service.py | 185 | 229 | 80.79% |
| services/backend_core/knowledge/service.py | 177 | 192 | 92.19% |
| services/backend_core/enterprise_os/router.py | 479 | 593 | 80.78% |
| services/rag_engine/embedding.py | 169 | 217 | 77.88% |
| services/llm_gateway/main.py | 217 | 362 | 59.94% |
| packages/common/auth/service_auth.py | 60 | 90 | 66.67% |
| services/backend_core/security/encryption.py | 66 | 69 | 95.65% |


Largest remaining gaps:

| File | Missing statements | Current coverage |
|---|---|---|
| services/rag_engine/main.py | 394 | 27.84% |
| services/model_training/finetune_pipeline_v2.py | 344 | 13.13% |
| services/governance/main.py | 292 | 52.44% |
| services/multi_agents/agents.py | 258 | 0.00% |
| services/backend_core/enterprise_integrations/phase5_connectors.py | 249 | 31.97% |
| services/api_gateway/main.py | 200 | 37.50% |
| packages/common/ai/advanced_rag.py | 168 | 24.66% |
| services/backend_core/ai_quality/eval_pipeline.py | 162 | 0.00% |
| services/backend_core/knowledge_graph/neo4j_repository.py | 162 | 0.00% |
| services/auth_service/main.py | 148 | 45.99% |
| services/llm_gateway/main.py | 145 | 59.94% |
| packages/common/governance/policy_engine.py | 138 | 31.68% |
| packages/common/governance/explainability.py | 131 | 35.15% |
| packages/common/governance/risk_engine.py | 131 | 34.83% |
| services/model_training/model_registry.py | 121 | 45.74% |
| services/multi_agents/main.py | 121 | 0.00% |
| packages/common/security/vault_client.py | 120 | 54.72% |
| services/backend_core/enterprise_os/router.py | 114 | 80.78% |


New meaningful checks cover actual crypto, real SQLite writes/constraints/audit, provider/timeout errors, cached vector integrity, authorization and scope isolation, workflow continuation and rollout state. Explicit HTTP/embedding fakes isolate unit boundaries; no live model claim is made. Evidence: `evidence/coverage-final.json`, `tests/coverage.xml`, `evidence/backend-tests-final.log`. Coverage improvement remains engineering work and is a release blocker, even if a Docker host becomes available.
