# HSAAI Vault Configuration (v4.1)
# HashiCorp Vault for centralized secrets management.
#
# SECURITY FIX v2.1 (P0):
#   - TLS enabled (was tls_disable=1)
#   - Audit logging enabled (was commented out)
#   - Raft storage for HA (was single-node file storage)
#   - Removed circular transit auto-unseal (was pointing to itself)
#   - Production mode (no dev root token)

server {
  ui = true
  api_addr = "https://vault:8200"
  cluster_addr = "https://vault:8201"

  # Raft storage for HA — survives node failure.
  # In production, deploy 3+ Vault nodes for quorum.
  storage "raft" {
    path    = "/vault/data"
    node_id = "vault_node_1"
    # For multi-node: add retry_join entries:
    # retry_join {
    #   leader_api_addr = "https://vault-2:8200"
    # }
    # retry_join {
    #   leader_api_addr = "https://vault-3:8200"
    # }
  }

  # TLS listener — no plaintext HTTP.
  # Certs are mounted via infrastructure/mtls/ and rotated by cert-manager.
  listener "tcp" {
    address       = "0.0.0.0:8200"
    tls_cert_file = "/vault/tls/tls.crt"
    tls_key_file  = "/vault/tls/tls.key"
    tls_min_version = "tls12"
  }

  # Shamir's Secret Sharing for unseal — production-grade.
  # In a 3-node HA setup, use auto-unseal via a *separate* transit Vault
  # (not this one — the previous config was circular).
  # seal "transit" {
  #   address       = "https://vault-unseal:8200"
  #   disable_renewal = "false"
  #   key_name      = "autounseal"
  #   mount_path    = "transit/"
  #   tls_ca_cert   = "/vault/tls/ca.crt"
  # }
}

# Audit logging — write all Vault access to file.
# Required for ISO 27001 A.8.15 (Logging) and SOC 2 CC7.2.
audit "file" {
  file_path = "/vault/audit/audit.log"
  # Log all request/response details for forensic analysis.
  log_raw = false
  hmac_accessor = true
  format = "json"
}

# Keep mlock enabled in production (prevents secrets from being swapped to disk).
# Only disable in dev/CI environments where capabilities cannot be granted.
disable_mlock = false
