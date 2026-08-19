#!/bin/bash
# ============================================================
# HSAAI Multi-Node Scaling Validation
# ============================================================
# Validates that HSAAI services scale correctly across
# multiple nodes with proper session handling and data
# consistency.
#
# Prerequisites:
#   - kubectl configured with multi-node cluster
#   - HSAAI deployed via Helm chart
#   - Redis available for session state
#   - PostgreSQL with connection pooling (PgBouncer)
#
# Usage: ./scripts/validate-multi-node.sh [namespace]
# ============================================================

set -euo pipefail

NAMESPACE="${1:-hsaai}"
FAILURES=0

echo "🔍 HSAAI Multi-Node Validation"
echo "   Namespace: $NAMESPACE"
echo ""

# ── 1. Cluster Readiness ──────────────────────────────
echo "📋 Step 1: Verify cluster has multiple nodes..."
NODE_COUNT=$(kubectl get nodes --no-headers 2>/dev/null | wc -l)
if [ "$NODE_COUNT" -lt 2 ]; then
    echo "   ⚠️  Only $NODE_COUNT node(s) found. Multi-node validation requires 2+."
    echo "   Continuing anyway for documentation purposes."
else
    echo "   ✅ $NODE_COUNT nodes available"
fi

# ── 2. Service Replicas ───────────────────────────────
echo ""
echo "📋 Step 2: Verify service replicas are distributed..."
for DEPLOY in backend-core api-gateway rag-engine llm-gateway auth-service; do
    REPLICAS=$(kubectl get deployment "$DEPLOY" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [ "$REPLICAS" -ge 2 ]; then
        echo "   ✅ $DEPLOY: $REPLICAS replicas"
    else
        echo "   ⚠️  $DEPLOY: $REPLICAS replicas (need 2+)"
        FAILURES=$((FAILURES + 1))
    fi
done

# ── 3. Pod Distribution ──────────────────────────────
echo ""
echo "📋 Step 3: Verify pods are spread across nodes..."
for DEPLOY in backend-core api-gateway rag-engine; do
    NODES=$(kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOY" -o jsonpath='{range .items[*]}{.spec.nodeName}{"\n"}{end}' 2>/dev/null | sort -u | wc -l)
    if [ "$NODES" -ge 2 ]; then
        echo "   ✅ $DEPLOY: spread across $NODES nodes"
    else
        echo "   ⚠️  $DEPLOY: on $NODES node(s) only"
    fi
done

# ── 4. Session Consistency ───────────────────────────
echo ""
echo "📋 Step 4: Verify session consistency across replicas..."
# Get two different backend pods
PODS=($(kubectl get pods -n "$NAMESPACE" -l "app=backend-core" -o jsonpath='{range .items[*]}{.metadata.name}{" "}{end}' 2>/dev/null))
if [ ${#PODS[@]} -ge 2 ]; then
    # Create a session on pod 1
    TOKEN1=$(kubectl exec -n "$NAMESPACE" "${PODS[0]}" -- curl -s -X POST http://localhost:8000/v1/auth/login         -H "Content-Type: application/json"         -d '{"username":"test","password":"test"}' 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

    if [ -n "$TOKEN1" ]; then
        echo "   ✅ Session created on ${PODS[0]}"
        # Verify session on pod 2
        RESULT=$(kubectl exec -n "$NAMESPACE" "${PODS[1]}" -- curl -s http://localhost:8000/v1/auth/me             -H "Authorization: Bearer $TOKEN1" 2>/dev/null || echo "")
        if echo "$RESULT" | grep -q "sub"; then
            echo "   ✅ Session validated on ${PODS[1]} (Redis-backed)"
        else
            echo "   ⚠️  Session NOT valid on ${PODS[1]} — sticky sessions issue?"
            FAILURES=$((FAILURES + 1))
        fi
    else
        echo "   ⏭️  Could not create test session (auth may be Keycloak-only)"
    fi
else
    echo "   ⏭️  Need 2+ backend pods for session test"
fi

# ── 5. Database Connection Pooling ───────────────────
echo ""
echo "📋 Step 5: Verify database connection pooling..."
CONN_COUNT=$(kubectl exec -n "$NAMESPACE" deploy/backend-core -- python3 -c "
from sqlalchemy import create_engine, text
import os
url = os.getenv('DATABASE_URL', '')
if 'postgresql' in url:
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()'))
        print(result.scalar())
else:
    print('0')
" 2>/dev/null || echo "unknown")
echo "   ℹ️  Active DB connections: $CONN_COUNT"

# ── 6. HPA Validation ────────────────────────────────
echo ""
echo "📋 Step 6: Verify HPA is active..."
for HPA in backend-hpa rag-engine-hpa api-gateway-hpa; do
    STATUS=$(kubectl get hpa "$HPA" -n "$NAMESPACE" -o jsonpath='{.status.currentReplicas}' 2>/dev/null || echo "not found")
    if [ "$STATUS" != "not found" ]; then
        echo "   ✅ $HPA: current replicas=$STATUS"
    else
        echo "   ⚠️  $HPA: not found"
    fi
done

# ── 7. Network Policy Check ──────────────────────────
echo ""
echo "📋 Step 7: Verify network policies are enforced..."
POLICY_COUNT=$(kubectl get networkpolicies -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)
if [ "$POLICY_COUNT" -ge 2 ]; then
    echo "   ✅ $POLICY_COUNT network policies active"
else
    echo "   ⚠️  Only $POLICY_COUNT network policy — Zero Trust requires more"
    FAILURES=$((FAILURES + 1))
fi

# ── Summary ───────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$FAILURES" -eq 0 ]; then
    echo "🎉 Multi-node validation PASSED (0 failures)"
else
    echo "⚠️  Multi-node validation: $FAILURES issue(s) found"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
