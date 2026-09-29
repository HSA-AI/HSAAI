#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

CLUSTER="${HSAAI_KIND_CLUSTER:-hsaai-runtime}"
NAMESPACE="${HSAAI_NAMESPACE:-hsaai}"
IMAGE_TAG="${HSAAI_IMAGE_TAG:?HSAAI_IMAGE_TAG is required}"

EVIDENCE="${ROOT}/.artifacts/kubernetes-runtime"

mkdir -p "${EVIDENCE}"

collect_evidence() {
    set +e

    kubectl get nodes -o wide \
        > "${EVIDENCE}/nodes.txt" 2>&1

    kubectl get all -A -o wide \
        > "${EVIDENCE}/all-resources.txt" 2>&1

    kubectl get pods -n "${NAMESPACE}" -o wide \
        > "${EVIDENCE}/application-pods.txt" 2>&1

    kubectl get pods -n hsaai-data -o wide \
        > "${EVIDENCE}/data-plane-pods.txt" 2>&1

    kubectl get events -A \
        --sort-by='.lastTimestamp' \
        > "${EVIDENCE}/events.txt" 2>&1

    kubectl describe pods -n "${NAMESPACE}" \
        > "${EVIDENCE}/application-describe.txt" 2>&1

    kubectl logs \
        -n "${NAMESPACE}" \
        -l app.kubernetes.io/part-of=hsaai \
        --all-containers=true \
        --prefix=true \
        --tail=300 \
        > "${EVIDENCE}/application-logs.txt" 2>&1

    helm status hsaai \
        -n "${NAMESPACE}" \
        > "${EVIDENCE}/helm-status.txt" 2>&1
}

trap collect_evidence EXIT

echo "============================================================"
echo " HSAAI Kubernetes Runtime Acceptance"
echo "============================================================"
echo "Cluster:   ${CLUSTER}"
echo "Namespace: ${NAMESPACE}"
echo "Image tag: ${IMAGE_TAG}"
echo

command -v docker >/dev/null
command -v kind >/dev/null
command -v kubectl >/dev/null
command -v helm >/dev/null
command -v jq >/dev/null

echo "[1/9] Cluster validation"

kubectl cluster-info
kubectl get nodes -o wide

echo
echo "[2/9] Create namespaces and runtime storage"

kubectl create namespace "${NAMESPACE}" \
    --dry-run=client \
    -o yaml \
    | kubectl apply -f -

cat <<'YAML' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolume
metadata:
  name: hsaai-documents-ci
spec:
  capacity:
    storage: 2Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Delete
  storageClassName: manual
  hostPath:
    path: /var/local/hsaai-documents
    type: DirectoryOrCreate

---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: hsaai-models-ci
spec:
  capacity:
    storage: 1Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Delete
  storageClassName: manual
  hostPath:
    path: /var/local/hsaai-models
    type: DirectoryOrCreate

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: documents-data
  namespace: hsaai
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: manual
  volumeName: hsaai-documents-ci
  resources:
    requests:
      storage: 2Gi

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: embedding-models
  namespace: hsaai
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: manual
  volumeName: hsaai-models-ci
  resources:
    requests:
      storage: 1Gi
YAML

kubectl wait \
    --for=jsonpath='{.status.phase}'=Bound \
    pvc/documents-data \
    -n "${NAMESPACE}" \
    --timeout=60s

kubectl wait \
    --for=jsonpath='{.status.phase}'=Bound \
    pvc/embedding-models \
    -n "${NAMESPACE}" \
    --timeout=60s

echo
echo "[3/9] Deploy CI data plane"

kubectl apply \
    -f "${ROOT}/infrastructure/kubernetes/ci/runtime-dependencies.yaml"

for deployment in \
    postgres \
    redis \
    qdrant \
    keycloak \
    ollama \
    otel-collector
do
    echo "Waiting for data-plane deployment: ${deployment}"

    kubectl rollout status \
        "deployment/${deployment}" \
        -n hsaai-data \
        --timeout=240s
done

echo
echo "[4/9] Pull immutable HSAAI production images"

test -n "${GHCR_USERNAME:-}" || {
    echo "ERROR: GHCR_USERNAME not set"
    exit 1
}

test -n "${GHCR_TOKEN:-}" || {
    echo "ERROR: GHCR_TOKEN not set"
    exit 1
}

printf '%s' "${GHCR_TOKEN}" \
    | docker login ghcr.io \
        --username "${GHCR_USERNAME}" \
        --password-stdin

images=(
    hsaai-api-gateway
    hsaai-auth-service
    hsaai-backend-core
    hsaai-rag-service
    hsaai-llm-gateway
    hsaai-agent-runtime
    hsaai-workflow-engine
    hsaai-alignment-service
    hsaai-governance-service
    hsaai-mcp-server
    hsaai-pii-detector
    hsaai-frontend
)

for name in "${images[@]}"
do
    image="ghcr.io/hsa-ai/${name}:${IMAGE_TAG}"

    echo
    echo "Pulling ${image}"

    docker pull "${image}"

    kind load docker-image \
        --name "${CLUSTER}" \
        "${image}"

    docker image rm "${image}" || true
done

docker logout ghcr.io || true

echo
echo "[5/9] Helm runtime validation"

helm lint \
    "${ROOT}/infrastructure/helm" \
    -f "${ROOT}/infrastructure/helm/values.yaml" \
    -f "${ROOT}/infrastructure/helm/values-runtime-ci.yaml" \
    --strict

TAG_ARGS=()

for service in \
    api-gateway \
    auth-service \
    backend-core \
    rag-service \
    llm-gateway \
    agent-runtime \
    workflow-engine \
    alignment-service \
    governance-service \
    mcp-server \
    pii-detector \
    frontend
do
    TAG_ARGS+=(
        --set-string
        "services.${service}.image.tag=${IMAGE_TAG}"
    )
done

helm template \
    hsaai \
    "${ROOT}/infrastructure/helm" \
    --namespace "${NAMESPACE}" \
    -f "${ROOT}/infrastructure/helm/values.yaml" \
    -f "${ROOT}/infrastructure/helm/values-runtime-ci.yaml" \
    "${TAG_ARGS[@]}" \
    > "${EVIDENCE}/helm-rendered-runtime.yaml"

echo
echo "[6/9] Install HSAAI application plane"

helm upgrade \
    --install \
    hsaai \
    "${ROOT}/infrastructure/helm" \
    --namespace "${NAMESPACE}" \
    -f "${ROOT}/infrastructure/helm/values.yaml" \
    -f "${ROOT}/infrastructure/helm/values-runtime-ci.yaml" \
    "${TAG_ARGS[@]}"

echo
echo "[7/9] Wait for all HSAAI deployments"

EXPECTED_DEPLOYMENTS=12

ACTUAL_DEPLOYMENTS="$(
    kubectl get deployments \
        -n "${NAMESPACE}" \
        -l app.kubernetes.io/part-of=hsaai \
        -o name \
        | wc -l \
        | tr -d ' '
)"

echo "Expected deployments: ${EXPECTED_DEPLOYMENTS}"
echo "Actual deployments:   ${ACTUAL_DEPLOYMENTS}"

test "${ACTUAL_DEPLOYMENTS}" -eq "${EXPECTED_DEPLOYMENTS}" || {
    echo "ERROR: unexpected deployment count"
    exit 1
}

kubectl wait \
    --for=condition=Available \
    deployment \
    --all \
    -n "${NAMESPACE}" \
    --timeout=600s

kubectl wait \
    --for=condition=Ready \
    pod \
    -l app.kubernetes.io/part-of=hsaai \
    -n "${NAMESPACE}" \
    --timeout=300s

echo
echo "[8/9] Check restarts and in-cluster service connectivity"

RESTARTS="$(
    kubectl get pods \
        -n "${NAMESPACE}" \
        -l app.kubernetes.io/part-of=hsaai \
        -o json \
    | jq '
        [
          .items[]
          | .status.containerStatuses[]?
          | .restartCount
        ]
        | add // 0
      '
)"

echo "Container restarts: ${RESTARTS}"

test "${RESTARTS}" -eq 0 || {
    echo "ERROR: application containers restarted during acceptance"
    exit 1
}

kubectl run hsaai-runtime-probe \
    -n "${NAMESPACE}" \
    --image=curlimages/curl:8.10.1 \
    --restart=Never \
    --command \
    -- sleep 600

kubectl wait \
    --for=condition=Ready \
    pod/hsaai-runtime-probe \
    -n "${NAMESPACE}" \
    --timeout=120s

checks=(
    "api-gateway:8000:/ready"
    "auth-service:8010:/ready"
    "backend-core:8000:/ready"
    "rag-service:8030:/ready"
    "llm-gateway:8090:/ready"
    "agent-runtime:8040:/health"
    "workflow-engine:8070:/health"
    "alignment-service:8005:/health"
    "governance-service:8011:/health"
    "mcp-server:8094:/health"
    "pii-detector:8092:/health"
    "frontend:3000:/api/health"
)

for entry in "${checks[@]}"
do
    IFS=: read -r service port path <<< "${entry}"

    url="http://${service}.${NAMESPACE}.svc.cluster.local:${port}${path}"

    echo "Checking ${url}"

    kubectl exec \
        -n "${NAMESPACE}" \
        hsaai-runtime-probe \
        -- curl \
            --fail \
            --silent \
            --show-error \
            --max-time 15 \
            "${url}" \
            >/dev/null
done

kubectl delete pod \
    hsaai-runtime-probe \
    -n "${NAMESPACE}" \
    --wait=true

echo
echo "[9/9] Final runtime evidence"

kubectl get deployments \
    -n "${NAMESPACE}" \
    -o wide

kubectl get pods \
    -n "${NAMESPACE}" \
    -o wide

kubectl get services \
    -n "${NAMESPACE}"

echo
echo "============================================================"
echo " HSAAI KUBERNETES RUNTIME ACCEPTANCE: PASS"
echo "============================================================"
echo "Image tag:       ${IMAGE_TAG}"
echo "Deployments:     ${ACTUAL_DEPLOYMENTS}/${EXPECTED_DEPLOYMENTS}"
echo "Container restarts: ${RESTARTS}"
echo "Data plane:      PASS"
echo "Pods Ready:      PASS"
echo "Service probes:  PASS"
echo "============================================================"
