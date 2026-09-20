# HSAAI Service Mesh (Istio) — Setup Guide (Phase 3 — Scale)

## Quick Start

### 1. Install Istio with production profile

```bash
# Download Istio 1.24+
curl -L https://istio.io/downloadIstio | sh -
cd istio-*
export PATH=$PWD/bin:$PATH

# Install with production profile (includes Prometheus, Kiali, Jaeger)
istioctl install --set profile=production \
  --set meshConfig.accessLogFile=/dev/stdout \
  --set meshConfig.accessLogEncoding=JSON \
  --set meshConfig.defaultConfig.tracing.sampling=10.0 \
  --set values.global.proxy.resources.requests.cpu=100m \
  --set values.global.proxy.resources.requests.memory=128Mi \
  --set values.global.proxy.resources.limits.cpu=500m \
  --set values.global.proxy.resources.limits.memory=256Mi \
  --set values.pilot.resources.requests.cpu=250m \
  --set values.pilot.resources.requests.memory=512Mi
```

### 2. Enable mesh injection for the hsaai namespace

```bash
kubectl label namespace hsaai istio-injection=enabled
kubectl label namespace hsaai-staging istio-injection=enabled
```

### 3. Apply the HSAAI mesh configuration

```bash
kubectl apply -f infrastructure/service-mesh/istio-config.yaml
```

### 4. Install Kiali (mesh observability UI)

```bash
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.24/samples/addons/kiali.yaml
kubectl port-forward svc/kiali -n istio-system 20001:20001
# Open http://localhost:20001
```

### 5. Install Jaeger (distributed tracing)

```bash
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.24/samples/addons/jaeger.yaml
kubectl port-forward svc/tracing -n istio-system 16686:16686
# Open http://localhost:16686
```

## What the mesh provides

| Capability | Before (Phase 2) | After (Phase 3 Istio) |
|------------|-------------------|----------------------|
| mTLS | Per-service uvicorn certs | Automatic, mesh-level |
| Traffic routing | Kubernetes Service only | Canary, A/B, weighted |
| Circuit breaking | None | Per-service with outlier detection |
| Tracing | OpenTelemetry manual | Automatic (10% sampling) |
| Metrics | Per-app Prometheus | Mesh-level + per-app |
| Authorization | Per-app RBAC | Mesh-level NetworkPolicy + AuthPolicy |

## Canary rollout example

```bash
# Deploy canary version (5% traffic)
kubectl set image deployment/backend backend=ghcr.io/hsaai/backend:4.3.0-canary
kubectl label pods -l app=backend version=canary --overwrite

# Monitor canary metrics in Kiali
# If healthy, increase to 25%, 50%, 100%
kubectl patch virtualservice backend-canary -n hsaai --type='json' \
  -p='[{"op":"replace","path":"/spec/http/1/route/0/weight","value":75},{"op":"replace","path":"/spec/http/1/route/1/weight","value":25}]'

# If unhealthy, rollback to 100% stable
kubectl patch virtualservice backend-canary -n hsaai --type='json' \
  -p='[{"op":"replace","path":"/spec/http/1/route/0/weight","value":100},{"op":"replace","path":"/spec/http/1/route/1/weight","value":0}]'
```
