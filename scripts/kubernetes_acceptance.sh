#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

CHART="${ROOT}/infrastructure/helm"
VALUES="${CHART}/values.yaml"
PRODUCTION_VALUES="${CHART}/values-production.yaml"

NAMESPACE="${HSAAI_K8S_NAMESPACE:-hsaai}"
RELEASE="${HSAAI_HELM_RELEASE:-hsaai}"

EVIDENCE_DIR="${HSAAI_ACCEPTANCE_EVIDENCE_DIR:-${ROOT}/.artifacts/kubernetes-acceptance}"
RENDERED="${EVIDENCE_DIR}/helm-rendered.yaml"
DRYRUN_OUTPUT="${EVIDENCE_DIR}/server-dry-run.txt"
IMAGE_OUTPUT="${EVIDENCE_DIR}/images.txt"

mkdir -p "${EVIDENCE_DIR}"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

echo "============================================================"
echo " HSAAI Kubernetes Production Acceptance"
echo "============================================================"
echo

echo "[1/9] Required commands"
command -v helm >/dev/null 2>&1 || fail "helm is required"
command -v kubectl >/dev/null 2>&1 || fail "kubectl is required"

helm version
kubectl version --client

echo
echo "[2/9] Required files"

test -f "${CHART}/Chart.yaml" ||
    fail "Chart.yaml missing"

test -f "${VALUES}" ||
    fail "values.yaml missing"

test -f "${PRODUCTION_VALUES}" ||
    fail "values-production.yaml missing"

echo
echo "[3/9] Reject unresolved production image placeholders"

if grep -Rni \
    'REPLACE_ORGANIZATION' \
    "${CHART}" \
    "${ROOT}/infrastructure/kubernetes" \
    > "${EVIDENCE_DIR}/unresolved-placeholders.txt"
then
    cat "${EVIDENCE_DIR}/unresolved-placeholders.txt"
    fail "unresolved REPLACE_ORGANIZATION references found"
fi

echo "No unresolved organization placeholders."

echo
echo "[4/9] Helm lint"

helm lint "${CHART}" \
    -f "${VALUES}" \
    -f "${PRODUCTION_VALUES}" \
    --strict

echo
echo "[5/9] Render production Helm release"

helm template "${RELEASE}" "${CHART}" \
    --namespace "${NAMESPACE}" \
    --include-crds \
    -f "${VALUES}" \
    -f "${PRODUCTION_VALUES}" \
    > "${RENDERED}"

test -s "${RENDERED}" ||
    fail "Helm produced an empty manifest"

echo "Rendered manifest:"
wc -l "${RENDERED}"

echo
echo "[6/9] Validate required workload types"

grep -q '^kind: Deployment$' "${RENDERED}" ||
    fail "no Deployment rendered"

grep -q '^kind: Service$' "${RENDERED}" ||
    fail "no Service rendered"

DEPLOYMENTS="$(
    grep -c '^kind: Deployment$' "${RENDERED}" || true
)"

SERVICES="$(
    grep -c '^kind: Service$' "${RENDERED}" || true
)"

echo "Deployments: ${DEPLOYMENTS}"
echo "Services:    ${SERVICES}"

echo
echo "[7/9] Validate rendered container image references"

grep -E '^[[:space:]]+image:' "${RENDERED}" \
    | sed 's/^[[:space:]]*//' \
    | sort -u \
    | tee "${IMAGE_OUTPUT}"

if grep -q 'REPLACE_ORGANIZATION' "${RENDERED}"; then
    fail "rendered Helm output still contains REPLACE_ORGANIZATION"
fi

echo
echo "[8/9] Kubernetes API server validation"

kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1 ||
    kubectl create namespace "${NAMESPACE}"

kubectl apply \
    --dry-run=server \
    -f "${RENDERED}" \
    > "${DRYRUN_OUTPUT}"

cat "${DRYRUN_OUTPUT}"

echo
echo "[9/9] Acceptance summary"

cat <<SUMMARY
============================================================
 HSAAI KUBERNETES ACCEPTANCE: PASS
============================================================
Namespace:        ${NAMESPACE}
Helm release:     ${RELEASE}
Deployments:      ${DEPLOYMENTS}
Services:         ${SERVICES}
Rendered file:    ${RENDERED}
API validation:   PASS
Placeholders:     NONE
============================================================
SUMMARY
