# HSAAI Mutual TLS (mTLS) Configuration

## Overview

HSAAI uses mutual TLS (mTLS) for all inter-service communication to ensure:

- **Identity verification**: Each service presents a certificate signed by the HSAAI Internal CA
- **Encryption**: All traffic between services is encrypted with TLS 1.2+
- **Zero Trust**: No service can communicate without presenting a valid certificate
- **Audit trail**: Certificate CN includes service name for tracing

## Architecture

```
┌─────────┐    mTLS     ┌──────────┐    mTLS     ┌──────────┐
│ Frontend │◄───────────►│ API GW   │◄───────────►│ Backend  │
└─────────┘   (8443)    └──────────┘   (8443)    └──────────┘
                                │                         │
                          mTLS  │                    mTLS │
                         (8443) │                   (8443)│
                                ▼                         ▼
                         ┌──────────┐             ┌──────────┐
                         │  Auth    │             │   RAG    │
                         │ Service  │             │  Engine  │
                         └──────────┘             └──────────┘
```

## Quick Start

### 1. Generate certificates
```bash
./infrastructure/mtls/generate-certs.sh ./certs
```

### 2. Run with mTLS (Docker Compose)
```bash
docker compose -f docker-compose.production.yml -f infrastructure/mtls/docker-compose.mtls.yml up
```

### 3. Kubernetes with cert-manager
```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# Create CA secret
kubectl create secret tls hsaai-ca-secret --cert=./certs/ca/ca.crt --key=./certs/ca/ca.key -n hsaai

# Apply cert-manager configuration
kubectl apply -f infrastructure/kubernetes/base/cert-manager-issuer.yaml
```

## Certificate Rotation

Certificates are valid for 825 days (service) / 3650 days (CA).

### Manual rotation:
```bash
rm -rf ./certs/services
./infrastructure/mtls/generate-certs.sh ./certs
docker compose restart
```

### Automatic rotation (Kubernetes + cert-manager):
cert-manager automatically renews certificates 7 days before expiry.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MTLS_ENABLED` | `false` | Enable mTLS enforcement |
| `MTLS_CERTS_DIR` | `/certs` | Certificate directory |
| `MTLS_CA_PATH` | `/certs/ca.crt` | CA certificate path |
| `MTLS_CERT_PATH` | `/certs/tls.crt` | Service certificate path |
| `MTLS_KEY_PATH` | `/certs/tls.key` | Service private key path |
| `MTLS_STRICT` | `true` | Reject requests without valid client cert |

## Security Notes

- The CA private key (`ca.key`) must be stored securely and never committed to Git
- In production, consider using HashiCorp Vault or AWS ACM for certificate management
- All cipher suites use ECDHE key exchange for forward secrecy
- TLS 1.0 and 1.1 are explicitly disabled
