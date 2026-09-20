# FINAL_TEST_SUMMARY

Latest source snapshot: 2026-09-19. Package HSAAI_v1.zip; source release4.0.0-rc.2.

| Check | Result |
|---|---|
| Backend (2026-09-19) | 690 PASS / 0 FAIL / 0 SKIPPED |
| Frontend (2026-09-14; unchanged source) | 38 PASS / 0 FAIL / 0 SKIPPED; production build PASS |
| E2E (2026-09-14; not rerun) | 2 PASS / 0 FAIL / 11 SKIPPED; public UI only |
| Python coverage (2026-09-19) | 41.92% → 54.78% → 56.56%; target80% FAIL |
| Focused security regression | 209 PASS; subset of backend total |
| PDF clauses | 5/1482 PASS;864 PARTIAL;510 FAIL;103 BLOCKED;58 context rows |
| Docker build/runtime | BLOCKED / BLOCKED |
| Containers healthy | 0/33 observed;22 optional;2 jobs |
| Database / AI full chain | PARTIAL / NOT VALIDATED in production |
| Frontend ↔ Backend / Monitoring | NOT TESTED as a complete runtime |
| Security | NOT APPROVED; observed C0/H3/M53/L57 |
| Kubernetes | Static previous PASS; real deployment NOT AVAILABLE |
| Production health check | NOT TESTED |
| Release | B – PRODUCTION CANDIDATE – BLOCKERS REMAIN |

Actual backend command: `python -m pytest tests --ignore=tests/e2e -q --cov-report=json:docs/reports/evidence/coverage-20260919.json --junitxml=docs/reports/evidence/backend-20260919.xml`. It finished with690 passes and exit1 solely because coverage56.56% is below80%; no tests were disabled or exclusions added. Backend includes the existing local integration contract and one new actual Redis concurrency/recovery test; these are not extra counts. Full-stack integration remains NOT TESTED (0 observed passes/0 failures).

The unchanged frontend and prior public E2E evidence are dated2026-09-14, not relabeled as new runs. No new whole-suite/E2E/clean-Docker PASS is claimed. Historical full-suite600/11skips is preserved in history and raw evidence.

New raw evidence: backend-20260919.xml/log,coverage-20260919.json,continuation-security.xml/log,bandit-20260919.json,static-20260919-rerun.log,ruff-critical-20260919.log,runtime-attempts-20260919.json. Existing frontend/browsers/Redis backup evidence remains intact.
