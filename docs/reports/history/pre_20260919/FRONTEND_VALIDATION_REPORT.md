# FRONTEND_VALIDATION_REPORT

**PASS for the measured frontend build and tests.** A fresh copy of `apps/web` received `npm ci`, lint, `type-check`, Vitest tests, a production build and npm audit. All exited 0; 38 tests passed. See `evidence/final-validation.json` and the frontend logs/JSON. Dependencies/build output are excluded from the delivery; the source and lockfile are retained. The production build took 82.82 seconds in this environment; this is not an installation SLA.

Real Chromium visited the built Next.js app at 390×844, 768×1024 and 1440×960. Login returned HTTP 200, RTL was enabled, fonts loaded locally, no horizontal overflow or page JavaScript errors were observed. PNG evidence: `evidence/login-390.png`, `login-768.png`, `login-1440.png` and `browser-visual-validation.json`. Two public E2E checks passed. No screenshot is a substitute for authenticated business testing or a WCAG audit.

An earlier standalone visual attempt timed out waiting for network idle while backend auth requests were unavailable (`browser-visual.log`). A fresh-server retest used the same network-idle condition and passed; actual 500 responses for `/v1/keycloak/config` and `/v1/auth/me` are retained in the final browser evidence. The application/backend identity integration therefore remains **BLOCKED**, not PASS. Authenticated pages, upload→RAG→model→response and admin workflows require the real stack and test accounts.

30 real local `/api/health` HTTP requests: mean 5.320 ms; p95 10.008 ms. This measures a local frontend health route only. Browser tests do not measure frontend source coverage; Python coverage must not be described as combined JS/Python coverage.
