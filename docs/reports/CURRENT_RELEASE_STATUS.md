# HSAAI Current Release Status

**Authoritative software release status**

- Release: `v4.0.0`
- Classification: **Production Release**
- Published release artifact: `HSAAI_v4.0.0.zip`
- Release commit: `80b7806`
- Backend test coverage: **80.43%**
- Final release validation: **32/32 successful**
- Package hygiene: **Passed**
- Dependency validation: **Passed**
- Security validation: **Passed**
- Docker build validation: **Passed**
- Enterprise runtime acceptance: **Passed**
- Authenticated Enterprise E2E: **Passed**
- Production runtime parity: **Passed**
- Kubernetes CI acceptance: **Passed**
- Production image supply chain: **Passed**
- Artifact integrity: **SHA-256 published**

## Release Artifact Integrity

SHA-256:

`4e8e69695537adccbc969c4f7a3047ffd844cc46439d3cc86d055da9b6e9c2d2`

## Kubernetes Scope

Repository-level Kubernetes validation and CI acceptance have passed.

Real external Kubernetes deployment remains an environment-specific
operator acceptance gate because production secrets, TLS, storage,
networking, backup/restore, capacity, failover, and customer infrastructure
cannot be validated solely by repository CI.

This does not change the software classification of HSAAI v4.0.0 as the
published Production Release.

## Historical Reports

Reports referring to `4.0.0-rc.2`, `HSAAI_v1.zip`, or
`Production Candidate` represent earlier engineering snapshots and are
retained for traceability only.

They must not be interpreted as the current release status.

## Source of Truth

For current repository status, use:

1. `README.md`
2. `docs/reports/CURRENT_RELEASE_STATUS.md`
3. GitHub Release `v4.0.0`

Older validation reports and evidence remain historical engineering records.
