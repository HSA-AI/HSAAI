# Recovery checkpoint — 2026-09-13

Current baseline matches all 1,437 files of the prior rc.1 ZIP. A complete local backup was made before changes. The scratch environment reset removed the last validation round; its isolated test results are historical and must not be counted as current verification.

Recovered changes: scoped workflow execution/resumption; persistent two-person approval and additive migration 0007; scoped approval API; embedding validation/cache identity; connector OAuth audience, sender and retry headers; bounded streaming timeout/error sanitization; SHA-256 noncredential identifiers; trusted rate-limit identity; real-credential E2E configuration and per-test browser lifecycle.

Current regression and coverage: PENDING. Docker/Kubernetes runtime remains unavailable until independently proven otherwise. Never mark this checkpoint Production Ready. No source was removed.
