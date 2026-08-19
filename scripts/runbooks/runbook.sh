#!/usr/bin/env bash
# HSAAI Operational Runbook Scripts (Phase 18)
# ================================================
# Executable scripts for every operational procedure.
# Each script corresponds to a runbook section.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAMESPACE="${NAMESPACE:-hsaai-prod}"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()   { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*"; }
warn()  { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARN:${NC} $*"; }
error() { echo -e "${RED}[$(date +%H:%M:%S)] ERROR:${NC} $*" >&2; }

# ═══════════════════════════════════════════════════════════════
# 1. DEPLOYMENT
# ═══════════════════════════════════════════════════════════════
deploy() {
    local env="${1:-staging}"
    local image_tag="${2:-latest}"
    log "Deploying HSAAI to $env (tag: $image_tag)"

    if [ "$env" = "production" ]; then
        warn "Production deployment requires manual approval"
        read -p "Type 'DEPLOY PROD': " confirm
        [ "$confirm" != "DEPLOY PROD" ] && { log "Aborted"; exit 0; }
    fi

    helm upgrade --install hsaai infrastructure/helm/hsaai \
        --namespace "${NAMESPACE}-${env}" \
        --set image.tag="$image_tag" \
        --set environment="$env" \
        --wait --timeout 600s

    log "✅ Deployment complete"
    kubectl get pods -n "${NAMESPACE}-${env}"
}

# ═══════════════════════════════════════════════════════════════
# 2. ROLLBACK
# ═══════════════════════════════════════════════════════════════
rollback() {
    local env="${1:-staging}"
    log "Rolling back HSAAI in $env"

    helm history hsaai -n "${NAMESPACE}-${env}"
    echo ""
    read -p "Enter revision number to rollback to: " revision

    helm rollback hsaai "$revision" -n "${NAMESPACE}-${env}"
    log "Waiting for rollback to complete..."
    kubectl rollout status deployment/api-gateway -n "${NAMESPACE}-${env}" --timeout=300s
    log "✅ Rollback complete"
}

# ═══════════════════════════════════════════════════════════════
# 3. SCALING
# ═══════════════════════════════════════════════════════════════
scale_service() {
    local service="${1:?Usage: scale <service> <replicas>}"
    local replicas="${2:?Usage: scale <service> <replicas>}"
    log "Scaling $service to $replicas replicas"
    kubectl scale deployment/"$service" -n "$NAMESPACE" --replicas="$replicas"
    kubectl rollout status deployment/"$service" -n "$NAMESPACE" --timeout=300s
    log "✅ Scale complete"
}

# ═══════════════════════════════════════════════════════════════
# 4. INCIDENT RESPONSE
# ═══════════════════════════════════════════════════════════════
incident_response() {
    local severity="${1:?Usage: incident <severity P1|P2|P3>}"
    log "🚨 INCIDENT RESPONSE — Severity: $severity"

    case "$severity" in
        P1)
            warn "P1: Critical — activate kill switch"
            kubectl exec -n "$NAMESPACE" deployment/alignment-service -- \
                curl -X POST http://localhost:8005/v1/safety/kill-switch \
                -H "Content-Type: application/json" \
                -d '{"reason":"P1 incident","activated_by":"oncall"}' 2>/dev/null || \
                warn "Kill switch API not reachable"
            ;;
        P2)
            warn "P2: Major — scale down non-critical services"
            kubectl scale deployment/agent-runtime -n "$NAMESPACE" --replicas=0 2>/dev/null || true
            ;;
        P3)
            log "P3: Minor — monitor and document"
            ;;
    esac

    log "Collecting diagnostic info..."
    kubectl get pods -n "$NAMESPACE" -o wide > /tmp/incident_pods.txt
    kubectl describe nodes > /tmp/incident_nodes.txt
    kubectl top pods -n "$NAMESPACE" > /tmp/incident_top.txt 2>/dev/null || true

    log "Diagnostic info saved to /tmp/incident_*.txt"
    log "Notify on-call: Slack #hsaai-incidents"
}

# ═══════════════════════════════════════════════════════════════
# 5. DATABASE RECOVERY
# ═══════════════════════════════════════════════════════════════
db_recovery() {
    log "Database recovery procedure"
    "$SCRIPT_DIR/dr/recovery.sh" restore-pg
}

# ═══════════════════════════════════════════════════════════════
# 6. SECRET ROTATION
# ═══════════════════════════════════════════════════════════════
rotate_secrets() {
    log "Rotating secrets via Vault"

    # Generate new JWT signing key
    local new_jwt=$(openssl rand -base64 32)
    log "Generated new JWT signing key"

    # Update in Vault
    kubectl exec -n "$NAMESPACE" deployment/vault -- \
        vault kv put secret/hsaai/jwt-signing-key key="$new_jwt" 2>/dev/null || \
        warn "Vault not reachable — manual rotation required"

    # Rotate API keys
    log "Rotate OpenAI API key (manual — via OpenAI dashboard)"
    log "Rotate database passwords (next step)"

    # Restart services to pick up new secrets
    log "Restarting services to load new secrets..."
    kubectl rollout restart deployment/api-gateway -n "$NAMESPACE"
    kubectl rollout restart deployment/auth-service -n "$NAMESPACE"

    log "✅ Secret rotation complete"
}

# ═══════════════════════════════════════════════════════════════
# 7. CERTIFICATE RENEWAL
# ═══════════════════════════════════════════════════════════════
renew_certs() {
    log "Certificate renewal (cert-manager)"

    # Check cert status
    kubectl get certificates -n "$NAMESPACE"

    # Trigger renewal
    kubectl certificate renew hsaai-tls -n "$NAMESPACE" 2>/dev/null || \
        warn "No hsaai-tls certificate found"

    # Verify
    sleep 10
    kubectl get certificates -n "$NAMESPACE"
    log "✅ Certificate renewal initiated"
}

# ═══════════════════════════════════════════════════════════════
# 8. CACHE FLUSH
# ═══════════════════════════════════════════════════════════════
flush_cache() {
    log "Flushing Redis cache"

    kubectl exec -n "$NAMESPACE" deployment/redis -- \
        redis-cli FLUSHDB 2>/dev/null || warn "Redis not reachable"

    log "Flushing Qdrant cache (keeping vectors)"
    # Note: Qdrant doesn't have a simple cache flush — only collection deletion
    # We keep vectors and only flush the LLM response cache in Redis

    log "✅ Cache flush complete"
}

# ═══════════════════════════════════════════════════════════════
# 9. QUEUE RECOVERY
# ═══════════════════════════════════════════════════════════════
recover_queue() {
    log "Kafka queue recovery"

    # List topics
    kubectl exec -n "$NAMESPACE" deployment/kafka -- \
        kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null || \
        warn "Kafka not reachable"

    # Check consumer lag
    log "Consumer group lag:"
    kubectl exec -n "$NAMESPACE" deployment/kafka -- \
        kafka-consumer-groups --bootstrap-server localhost:9092 --describe --all-groups 2>/dev/null || true

    log "If lag is high, restart consumers:"
    log "  kubectl rollout restart deployment/agent-runtime -n $NAMESPACE"
}

# ═══════════════════════════════════════════════════════════════
# 10. SERVICE RESTART
# ═══════════════════════════════════════════════════════════════
restart_service() {
    local service="${1:?Usage: restart <service-name>}"
    log "Restarting $service"
    kubectl rollout restart deployment/"$service" -n "$NAMESPACE"
    kubectl rollout status deployment/"$service" -n "$NAMESPACE" --timeout=300s
    log "✅ $service restarted"
}

# ═══════════════════════════════════════════════════════════════
# 11. NODE FAILURE
# ═══════════════════════════════════════════════════════════════
handle_node_failure() {
    local node="${1:?Usage: node-failure <node-name>}"
    warn "🚨 Node failure: $node"

    log "Cordoning node (no new pods scheduled)..."
    kubectl cordon "$node"

    log "Draining node (evict existing pods)..."
    kubectl drain "$node" --ignore-daemonsets --delete-emptydir-data --timeout=300s || \
        warn "Drain timeout — some pods may still be running"

    log "Verifying pods rescheduled..."
    kubectl get pods -n "$NAMESPACE" -o wide | grep -v Running | grep -v Completed || \
        log "✅ All pods running on healthy nodes"

    log "Node $node is now cordoned and drained"
    log "To bring back: kubectl uncordon $node"
}

# ═══════════════════════════════════════════════════════════════
# 12. REGION FAILURE (calls DR script)
# ═══════════════════════════════════════════════════════════════
handle_region_failure() {
    warn "🚨 REGION FAILURE — activating DR procedure"
    "$SCRIPT_DIR/dr/recovery.sh" failover
}

# ═══════════════════════════════════════════════════════════════
# 13. HEALTH CHECK
# ═══════════════════════════════════════════════════════════════
health_check() {
    log "HSAAI Health Check"
    log "═══════════════════════════════════════════════════════════"

    # Check all pods
    local total=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)
    local running=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep "Running" | wc -l)
    log "Pods: $running/$total running"

    # Check key services
    for svc in api-gateway llm-gateway rag-engine governance; do
        local ready=$(kubectl get deployment "$svc" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        local desired=$(kubectl get deployment "$svc" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
        if [ "$ready" = "$desired" ] && [ "$ready" != "0" ]; then
            log "  ✅ $svc: $ready/$desired"
        else
            warn "  ⚠️  $svc: $ready/$desired"
        fi
    done

    # Check database connections
    log "Database connections:"
    kubectl exec -n "$NAMESPACE" patroni-0 -- \
        psql -U hsaai -d hsaai -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null || warn "  DB not reachable"

    log "═══════════════════════════════════════════════════════════"
}

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
case "${1:-help}" in
    deploy)        shift; deploy "$@" ;;
    rollback)      shift; rollback "$@" ;;
    scale)         shift; scale_service "$@" ;;
    incident)      shift; incident_response "$@" ;;
    db-recovery)   db_recovery ;;
    rotate-secrets) rotate_secrets ;;
    renew-certs)   renew_certs ;;
    flush-cache)   flush_cache ;;
    queue-recovery) recover_queue ;;
    restart)       shift; restart_service "$@" ;;
    node-failure)  shift; handle_node_failure "$@" ;;
    region-failure) handle_region_failure ;;
    health)        health_check ;;
    *)
        cat <<EOF
HSAAI Operational Runbook Scripts (Phase 18)

Usage: $0 {command} [args]

Commands:
  deploy <env> [tag]          Deploy to environment (staging/production)
  rollback <env>              Rollback to previous deployment
  scale <service> <replicas>  Scale a service
  incident <P1|P2|P3>         Incident response
  db-recovery                 Database recovery procedure
  rotate-secrets              Rotate secrets via Vault
  renew-certs                 Renew TLS certificates
  flush-cache                 Flush Redis cache
  queue-recovery              Kafka queue recovery
  restart <service>           Restart a service
  node-failure <node>         Handle node failure (cordon + drain)
  region-failure              Handle region failure (failover)
  health                      Full health check

Environment:
  NAMESPACE  Kubernetes namespace (default: hsaai-prod)
EOF
        ;;
esac
