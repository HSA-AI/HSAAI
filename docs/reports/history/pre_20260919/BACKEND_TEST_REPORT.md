# BACKEND_TEST_REPORT

Final: **598 passed, 0 failed, 0 skipped** outside the browser E2E directory. Baseline: 351 passed. Added net 247 passing backend checks. The same full pytest invocation also contains 2 public browser PASS and 11 authenticated browser SKIP, for **600 passed / 0 failed / 11 skipped** in JUnit. These categories must not be added twice.

`python -m pytest tests -q --cov-report=json:docs/reports/evidence/coverage-final.json --junitxml=docs/reports/evidence/backend-tests-final.xml` was actually executed against the final Python source. Exit code **1** is caused by the unchanged 80% coverage gate, not a failed assertion. Evidence: `backend-tests-final.xml`, `backend-tests-final.log`, `final-validation.json`.

| Suite directory | Passed |
|---|---|
| backend | 4 |
| contract | 10 |
| department_agents | 4 |
| docker | 1 |
| enterprise_integrations | 4 |
| enterprise_ops | 4 |
| enterprise_os | 9 |
| enterprise_upgrade | 2 |
| integration | 1 |
| knowledge_graph | 1 |
| maturity_upgrade | 5 |
| phase11 | 36 |
| phase12 | 8 |
| release | 280 |
| security | 182 |
| unit | 47 |


Tests include signed JWT validation/expired and invalid tokens, trusted OAuth role clients, rate-limit identity spoofing, workflow execution and approval resume, independent reviewers, tenant/workspace scoping, RAG request propagation, embedding dimensions/NaN/cache invalidation, provider outages, retries, failed phases, marketplace rollouts and real SQLite lifecycle/FK checks. Real encryption tests check Arabic/text roundtrips, encoded Fernet keys, tampering, wrong keys, concurrent salt publication and corrupt-salt refusal.

`tests/release/test_enterprise_os_persistence.py` exercises actual SQLite models and the legacy router's handlers, not a fake database. ASGI and HTTP transports in other tests are explicitly local unit/contract boundaries. They do not establish live Keycloak/PostgreSQL/Qdrant/model integration. No old test was removed. Fixture-wide exception handlers that previously swallowed schema failures or converted import failures to skips were removed; failures now surface.
