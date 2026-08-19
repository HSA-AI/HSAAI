#!/bin/bash
# ============================================================
# HSAAI mTLS Certificate Generation
# ============================================================
# Generates a private CA and per-service certificates for
# mutual TLS authentication between HSAAI microservices.
#
# Usage: ./generate-certs.sh [output-dir]
# Default output: ./certs
# ============================================================

set -euo pipefail

CERTS_DIR="${1:-./certs}"
mkdir -p "$CERTS_DIR/ca" "$CERTS_DIR/services"

CA_KEY="$CERTS_DIR/ca/ca.key"
CA_CERT="$CERTS_DIR/ca/ca.crt"
CA_SERIAL="$CERTS_DIR/ca/ca.serial"
DAYS=3650  # 10 years for internal CA

# Service list for certificate generation
SERVICES=(
  "backend_core"
  "api_gateway"
  "auth_service"
  "rag_engine"
  "llm_gateway"
  "ai_orchestrator"
  "multi_agents"
  "workflow_engine"
  "agent_studio"
  "analytics"
  "document_ai"
  "voice_ai"
  "frontend"
)

echo "🔐 Generating HSAAI mTLS certificates..."
echo "   Output directory: $CERTS_DIR"

# ── Step 1: Generate Root CA ─────────────────────────
echo ""
echo "📋 Step 1: Generating Root CA..."

if [ ! -f "$CA_KEY" ]; then
    openssl genrsa -out "$CA_KEY" 4096
    echo "   ✅ CA private key generated"
else
    echo "   ⏭️  CA private key already exists, skipping"
fi

if [ ! -f "$CA_CERT" ]; then
    openssl req -new -x509 \
        -key "$CA_KEY" \
        -out "$CA_CERT" \
        -days "$DAYS" \
        -subj "/C=YE/ST=Aden/L=Aden/O=Hayel Saeed Anam Group/OU=HSAAI Infrastructure/CN=HSAAI Internal CA" \
        -addext "basicConstraints=critical,CA:TRUE" \
        -addext "keyUsage=critical,cRLSign,keyCertSign" \
        -addext "subjectKeyIdentifier=hash"
    echo "   ✅ CA certificate generated"
else
    echo "   ⏭️  CA certificate already exists, skipping"
fi

# Initialize serial
echo "01" > "$CA_SERIAL"

# ── Step 2: Generate per-service certificates ─────────
echo ""
echo "📋 Step 2: Generating service certificates..."

for SERVICE in "${SERVICES[@]}"; do
    SVC_DIR="$CERTS_DIR/services/$SERVICE"
    mkdir -p "$SVC_DIR"

    SVC_KEY="$SVC_DIR/tls.key"
    SVC_CSR="$SVC_DIR/tls.csr"
    SVC_CERT="$SVC_DIR/tls.crt"

    # Skip if certificate already exists and is valid
    if [ -f "$SVC_CERT" ] && openssl verify -CAfile "$CA_CERT" "$SVC_CERT" &>/dev/null; then
        echo "   ⏭️  $SERVICE: certificate already valid, skipping"
        continue
    fi

    # Generate private key
    openssl genrsa -out "$SVC_KEY" 2048 2>/dev/null

    # Generate CSR with SANs
    cat > "$SVC_DIR/openssl.cnf" <<EOF
[req]
distinguished_name = req_dn
req_extensions = v3_req
prompt = no

[req_dn]
C = YE
ST = Aden
L = Aden
O = Hayel Saeed Anam Group
OU = HSAAI Platform
CN = $SERVICE.hsaai.internal

[v3_req]
basicConstraints = CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth,clientAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = $SERVICE
DNS.2 = $SERVICE.hsaai.internal
DNS.3 = $SERVICE.default.svc.cluster.local
DNS.4 = localhost
IP.1 = 127.0.0.1
EOF

    openssl req -new \
        -key "$SVC_KEY" \
        -out "$SVC_CSR" \
        -config "$SVC_DIR/openssl.cnf"

    # Sign with CA
    openssl x509 -req \
        -in "$SVC_CSR" \
        -CA "$CA_CERT" \
        -CAkey "$CA_KEY" \
        -CAcreateserial \
        -CAserial "$CA_SERIAL" \
        -out "$SVC_CERT" \
        -days 825 \
        -sha256 \
        -extfile "$SVC_DIR/openssl.cnf" \
        -extensions v3_req

    # Cleanup CSR
    rm -f "$SVC_CSR"

    echo "   ✅ $SERVICE: certificate generated"
done

# ── Step 3: Create combined trust bundle ──────────────
echo ""
echo "📋 Step 3: Creating trust bundle..."
cat "$CA_CERT" > "$CERTS_DIR/ca/trust-bundle.crt"
echo "   ✅ Trust bundle created: $CERTS_DIR/ca/trust-bundle.crt"

# ── Step 4: Create Kubernetes secrets manifest ────────
echo ""
echo "📋 Step 4: Generating Kubernetes TLS secrets..."

for SERVICE in "${SERVICES[@]}"; do
    SVC_DIR="$CERTS_DIR/services/$SERVICE"
    kubectl create secret generic "$SERVICE-mtls-certs" \
        --from-file=tls.crt="$SVC_DIR/tls.crt" \
        --from-file=tls.key="$SVC_DIR/tls.key" \
        --from-file=ca.crt="$CERTS_DIR/ca/trust-bundle.crt" \
        --dry-run=client -o yaml \
        > "$SVC_DIR/k8s-secret.yaml" 2>/dev/null || true
    echo "   ✅ $SERVICE: K8s secret manifest generated"
done

echo ""
echo "🎉 mTLS certificate generation complete!"
echo "   CA certificate: $CA_CERT"
echo "   Trust bundle:   $CERTS_DIR/ca/trust-bundle.crt"
echo "   Service certs:  $CERTS_DIR/services/<name>/"
echo ""
echo "⚠️  IMPORTANT:"
echo "   - Store ca.key securely (offline, air-gapped)"
echo "   - Add certs/ to .gitignore"
echo "   - Rotate certificates annually"
echo "   - Use cert-manager in production Kubernetes"
