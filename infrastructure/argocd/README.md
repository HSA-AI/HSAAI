# HSAAI ArgoCD GitOps (Phase 2 — Modernize)

Fixed in v2.2: Replaces push-based `helm upgrade` from GitHub Actions with
pull-based GitOps via ArgoCD.

## Quick Start

### 1. Install ArgoCD in your cluster

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ArgoCD server to be ready:
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s

# Get the admin password:
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Port-forward to access the UI:
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Open https://localhost:8080
```

### 2. Create the HSAAI namespace

```bash
kubectl create namespace hsaai
kubectl create namespace hsaai-staging
```

### 3. Apply the root Application (App-of-Apps pattern)

```bash
kubectl apply -f infrastructure/argocd/app-of-apps.yaml
```

This creates:
- `hsaai-staging` Application → deploys to `hsaai-staging` namespace
- `hsaai-production` Application → deploys to `hsaai` namespace (manual sync)

### 4. Configure the Git repo credential (if private)

```bash
kubectl create secret generic hsaai-repo-cred \
  --from-literal=type=git \
  --from-literal=url=https://github.com/hsaai/hsaai \
  --from-literal=username=hsaai-bot \
  --from-literal=password=$GITHUB_TOKEN \
  -n argocd

kubectl annotate secret hsaai-repo-cred -n argocd \
  argocd.argoproj.io/secret-type=repository
```

### 5. Configure secrets via External Secrets Operator

ArgoCD does NOT manage secrets (they should not be in Git). Use
External Secrets Operator + Vault:

```bash
# Install External Secrets Operator
kubectl apply -f https://raw.githubusercontent.com/external-secrets/external-secrets/main/deploy/crds/bundle.yaml

# Create a SecretStore that points to Vault
cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: hsaai-vault-store
  namespace: hsaai
spec:
  provider:
    vault:
      server: https://vault:8200
      path: secret
      auth:
        appRole:
          path: approle
          roleId: "$VAULT_ROLE_ID"
          secretRef:
            name: vault-secret-id
            key: secret-id
EOF
```

### 6. Sync the applications

**Staging** syncs automatically (any push to `main` triggers a deploy).

**Production** requires manual sync:
```bash
argocd app sync hsaai-production
# Or click "Sync" in the ArgoCD UI
```

## Architecture

```
Git Repository (main branch)
       │
       ▼
┌─────────────────┐
│  ArgoCD Server  │  ← polls Git every 3 minutes
│  (in cluster)   │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────────┐
│staging │ │ production  │
│  auto  │ │  manual     │
│ sync   │ │  sync       │
└────────┘ └────────────┘
    │              │
    ▼              ▼
 hsaai-staging   hsaai
 namespace       namespace
```

## Benefits over push-based CI/CD

| Aspect | Push-based (before) | ArgoCD GitOps (after) |
|--------|---------------------|----------------------|
| Kubeconfig | Long-lived GitHub secret | None — ArgoCD runs in-cluster |
| Drift detection | None | Automatic (every 3 min) |
| Self-healing | None | Manual edits auto-reverted |
| Audit trail | CI logs only | Git history + ArgoCD events |
| Rollback | Re-run CI with old commit | `argocd app rollback` |
| Multi-env | Separate CI jobs | App-of-Apps pattern |
| Secret management | `--set` (shell history) | External Secrets + Vault |

## CI/CD changes

The GitHub Actions workflow (`.github/workflows/ci-cd.yml`) has been updated to:
1. Build + sign container images (cosign)
2. Run all tests + security scans (blocking)
3. **NO `helm upgrade` step** — ArgoCD handles deployment
4. The only deploy action is updating the image tag in `values.yaml` and
   committing to Git — ArgoCD picks up the change automatically.

## Disaster Recovery

If the cluster is lost:
1. Provision a new cluster
2. Install ArgoCD
3. Apply `app-of-apps.yaml`
4. ArgoCD restores the entire platform state from Git
5. Restore data from WAL-G backups in MinIO
