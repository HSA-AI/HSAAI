# FINAL_TEST_SUMMARY

Date: 2026-09-14. Current source release: 4.0.0-rc.2. Package: HSAAI_v1.zip. Classification: **B – PRODUCTION CANDIDATE – BLOCKERS REMAIN**.

| Check | Result |
|---|---|
| Backend | 598 PASS / 0 FAIL / 0 SKIPPED |
| Frontend | 38 PASS / 0 FAIL / 0 SKIPPED |
| E2E | 2 PASS / 0 FAIL / 11 SKIPPED (public UI only) |
| Coverage | 41.92% → 54.78% — gate FAIL |
| PDF clauses | 5 / 1482 PASS; 864 PARTIAL; 510 FAIL; 103 BLOCKED; 58 context rows outside denominator |
| Docker build/runtime | BLOCKED / BLOCKED |
| Containers healthy | 0 / 33 observed; 22 optional services; 2 one-shot jobs |
| Database | PARTIAL: SQLite + 9 native Redis checks; production engines blocked |
| AI layer | PARTIAL: execution/error logic tested; real model/vector chain unverified |
| Frontend ↔ Backend | BLOCKED: actual identity/backend unavailable |
| Monitoring | NOT TESTED at runtime |
| Security | NOT APPROVED: observed Critical 0 / High 1 / Medium 55 / Low 57 |
| Kubernetes | Helm/static PASS; real deployment NOT AVAILABLE |
| Production health check | NOT TESTED |
| Final classification | B – PRODUCTION CANDIDATE – BLOCKERS REMAIN |


Backend includes 1 passing test under `tests/integration`, which is a local service contract; it is a subset of 598, not an extra live integration count. Real full-stack Integration: 0 passed / 0 failed / NOT TESTED. Public E2E: 2 passed / 0 failed / 11 skipped. Native Redis: 9 additional acceptance checks, separate from pytest.

Whole pytest: **600 PASS / 0 FAIL / 11 SKIPPED**, command exit 1 due only to 54.78% <80 coverage. Frontend: 38 PASS / 0 FAIL / 0 SKIPPED, all install/lint/type-check/build commands exit 0. Security observed counts include the explicit manual findings; no complete security PASS is claimed. Docker Build and Runtime are BLOCKED rather than fabricated PASS/FAIL image diagnoses. Kubernetes static validation PASS; server validation BLOCKED and real deployment NOT AVAILABLE.

Authoritative raw evidence: `evidence/backend-tests-final.xml`, `backend-tests-final.log`, `coverage-final.json`, `frontend-tests.json`, `final-validation.json`, `browser-visual-validation.json`, `redis-native-final.json`, `bandit-final.json`, `manual-security-findings.json`, `python-dependencies-final.json`, `runtime-attempts.json`, `helm-lint-final.log`. Older evidence is preserved as history and does not override these results.
