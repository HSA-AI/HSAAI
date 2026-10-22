# HSAAI Current Release Status

**Authoritative software release status**

## Current Published Release — v4.1.0

- Release: `v4.1.0`
- Name: **HSAAI v4.1.0 — Enterprise RAG Local Runtime**
- Published: **2026-10-22**
- Classification: **Published stable software release**
- Release commit: `23c45bb066497d31bbd135bafddc0e3ef5194a91`
- Pull request: **#29 — 45/45 successful checks**
- Main branch workflows: **6/6 successful**

Official release:
https://github.com/HSA-AI/HSAAI/releases/tag/v4.1.0

### Validated CI Workflows

- Continuous Integration: PASS
- Docker Build Validation: PASS
- Kubernetes Production Acceptance: PASS
- RAG Document End-to-End: PASS
- Live LLM Answer Quality: PASS
- Production Image Supply Chain: PASS

These results apply to the repository validation environment.

They do not independently establish successful deployment
to an external production Kubernetes cluster.

### Kubernetes Runtime Acceptance — Verified CI Evidence

| Verification | Result |
| --- | --- |
| Kubernetes Runtime Acceptance (Kind CI) | ✅ PASS |
| Kubernetes Version | v1.32.2 |
| Kubernetes Nodes | 1/1 Ready |
| Helm Runtime Deployment | PASS |
| Application Deployments | 12/12 Available |
| Application Pods | 12/12 Ready |
| Data Plane Pods | 6/6 Ready |
| Total Application and Data Plane Pods | 18/18 Running |
| Container Restarts | 0 |
| Internal Service Readiness Probes | PASS |
| Tested Container Image Tag | `sha-33ff3f81702c` |
| GitHub Actions Run | [39791353596](https://github.com/HSA-AI/HSAAI/actions/runs/39791353596) |
| Test Date | 2026-10-22 |
| External Kubernetes Deployment | PENDING |
| v4.1.0 Image-Specific Runtime Acceptance | Not established by this run |

This test deployed HSAAI to an ephemeral Kind Kubernetes cluster
inside GitHub Actions. All 12 application deployments became
Available, all 18 application and data-plane Pods were Ready,
and the recorded container restart count was zero.

Transient startup readiness warnings were observed for some
components; subsequent readiness checks passed.

The tested images used tag `sha-33ff3f81702c`.
This evidence must not be represented as runtime validation
of the v4.1.0 release images or as external production
Kubernetes acceptance.

## Previous Release Evidence — v4.0.0

The following results belong to the previous production release
and must not be represented as newly measured v4.1.0 results.

- Release: `v4.0.0`
- Classification: **Production Release**
- Release commit: `80b7806`
- Published artifact: `HSAAI_v4.0.0.zip`
- Backend coverage: **80.43%**
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

### Historical Artifact Integrity

SHA-256 for `HSAAI_v4.0.0.zip`:

`4e8e69695537adccbc969c4f7a3047ffd844cc46439d3cc86d055da9b6e9c2d2`

Previous release:
https://github.com/HSA-AI/HSAAI/releases/tag/v4.0.0

## Kubernetes Scope

Repository-level Kubernetes validation and CI acceptance
have passed for the documented workflows.

Real external Kubernetes deployment remains an
environment-specific operator acceptance gate.

Production secrets, TLS, persistent storage, networking,
backup/restore, capacity, failover, and customer
infrastructure require separate operational verification.

## Historical Reports

Reports referring to `4.0.0-rc.2`, `HSAAI_v1.zip`,
or `Production Candidate` represent earlier engineering
snapshots retained for traceability.

## Source of Truth

For the current published release, use:

1. GitHub Release `v4.1.0`
2. `README.md`
3. `docs/reports/CURRENT_RELEASE_STATUS.md`
4. The corresponding GitHub Actions workflow runs

Historical metrics must remain associated with their
original release commits and evaluation environments.
