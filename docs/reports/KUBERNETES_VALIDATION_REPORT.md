# KUBERNETES_VALIDATION_REPORT


> **Historical Validation Snapshot**
>
> This document records an earlier HSAAI validation state associated with
> the `v4.0.0-rc.2` release-candidate period.
>
> It is retained for engineering traceability and historical evidence only.
> It is **not** the authoritative current release status.
>
> Current authoritative software release:
> **HSAAI v4.0.0 — Production Release**
>
> Refer to `README.md` and `docs/reports/CURRENT_RELEASE_STATUS.md`
> for the current validated release state.


**Static/Helm: PASS within tested scope. Server validation: BLOCKED. Real deployment: NOT AVAILABLE.** No cluster/kubeconfig/kubectl was available. Server-side dry-run and get pods/services/deployments/events were attempted and recorded in `evidence/runtime-attempts.json`. A real apply was not performed; no rollout success is claimed.

`helm lint infrastructure/helm` passed (1 chart, 0 failed); `helm template` rendered successfully. Canonical source/static validation covers the release manifest's 53 resources and service/deployment port alignment. Evidence: `helm-lint-final.log`, `helm-rendered.yaml`, `static-release-final.log`. Templates/images are aligned with candidate 4.0.0-rc.2; the images still must be built and supplied to a registry.

Namespace, Deployments, Services, ingress, ConfigMaps, external Secret references, PVC/storage, resource requests/limits, startup/readiness/liveness probes, replicas, service accounts/RBAC, network policies, PDB and HPA declarations are present for the reviewed configuration. The chart expects `existingSecret: hsaai-secrets`; example values are not real credentials. Static declarations do not prove secret resolution, scheduling, storage binding, GPU admission, autoscaling, HA or network reachability.

Production prerequisites include cluster-specific StorageClass/Ingress/TLS, image registry access, secrets, databases/Keycloak/model dependencies and GPU nodes if required. The default canonical manifest does not demonstrate operation of every one of the 57 Compose entries. Full required-service parity must be reviewed against the production deployment scope. Apply one canonical path (Kustomize or Helm) to the acceptance cluster; validate slow startup, dependency outage, probes, restart and persistence. All runtime requirements in the mandatory PDF remain open until evidenced.
