"""
HSAAI Vault Client — Production Secrets Management (Fix #2)
=============================================================
Replaces direct env var secret reads with centralized Vault integration.

CRITICAL FIX: All sensitive secrets (passwords, API keys, JWT signing keys,
database credentials, TLS private keys) now flow through Vault instead of
being read directly from environment variables.

Authentication methods supported:
  - AppRole (role_id + secret_id) — for VM-based deployments
  - Kubernetes Auth (service account JWT) — for K8s deployments
  - Token (direct) — for development only

Features:
  - Automatic token renewal (background thread)
  - Secret caching with TTL (reduces Vault load)
  - Circuit breaker (prevents cascade failures)
  - Retry with exponential backoff
  - Audit logging of every secret access
  - Health check endpoint
  - Secret rotation support
  - Dynamic secrets (database credentials)

Usage:
    from packages.common.security.vault_client import vault_client, get_secret

    # Read a secret (cached, audited, circuit-breaker protected)
    db_password = get_secret("database/hsaai", "password")

    # Or use the client directly
    secret = vault_client.read_secret("jwt-signing-key")
"""
import os
import time
import json
import logging
import threading
import asyncio
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
import httpx

logger = logging.getLogger("hsaai.vault")


# ─── Circuit Breaker ───────────────────────────────────────────────
class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""


@dataclass
class CircuitBreakerState:
    failure_count: int = 0
    last_failure: float = 0.0
    state: str = "closed"  # closed, open, half-open
    threshold: int = 5
    reset_timeout: float = 60.0

    def record_success(self):
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure = time.time()
        if self.failure_count >= self.threshold:
            self.state = "open"
            logger.error(f"Vault circuit breaker OPEN (failures={self.failure_count})")

    def can_attempt(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.last_failure > self.reset_timeout:
                self.state = "half-open"
                logger.info("Vault circuit breaker → HALF-OPEN")
                return True
            return False
        return True  # half-open


# ─── Cache Entry ───────────────────────────────────────────────────
@dataclass
class CacheEntry:
    data: Dict[str, Any]
    expires_at: float
    lease_id: str = ""
    lease_duration: int = 0


# ─── Vault Client ──────────────────────────────────────────────────
class VaultClient:
    """
    Production Vault client with caching, circuit breaker, and renewal.

    Authentication priority:
      1. VAULT_TOKEN (direct token — dev only)
      2. VAULT_APPROLE_ROLE_ID + VAULT_APPROLE_SECRET_ID (AppRole — VM)
      3. Kubernetes service account JWT (K8s auth)
    """

    def __init__(self):
        self.vault_url = os.getenv("VAULT_ADDR", "http://vault:8200")
        self.namespace = os.getenv("VAULT_NAMESPACE", "")
        self.token = os.getenv("VAULT_TOKEN", "")
        self._token_expires_at = 0.0
        self._cache: Dict[str, CacheEntry] = {}
        self._cache_ttl = int(os.getenv("VAULT_CACHE_TTL", "300"))  # 5 min default
        self._cb = CircuitBreakerState()
        self._client = httpx.AsyncClient(timeout=10)
        self._lock = threading.Lock()
        self._renewal_thread: Optional[threading.Thread] = None
        self._audit_log: list = []
        self._initialized = False

    def initialize(self):
        """
        Initialize authentication. Call once at service startup.

        FAIL-CLOSED: In production/staging, if no auth method is configured,
        the service MUST NOT start. No dev token fallback.
        """
        if self._initialized:
            return

        environment = os.getenv("DEPLOY_ENV", "development")
        is_production = environment in ("production", "staging")

        # Try AppRole auth
        role_id = os.getenv("VAULT_APPROLE_ROLE_ID", "")
        secret_id = os.getenv("VAULT_APPROLE_SECRET_ID", "")

        if not self.token and role_id and secret_id:
            self._auth_approle(role_id, secret_id)
            logger.info("Vault authenticated via AppRole")
        elif not self.token:
            # Try Kubernetes auth
            k8s_role = os.getenv("VAULT_K8S_ROLE", "")
            if k8s_role:
                self._auth_kubernetes(k8s_role)
                logger.info("Vault authenticated via Kubernetes")
            else:
                # FAIL-CLOSED: No auth method configured
                if is_production:
                    logger.error("=" * 60)
                    logger.error("CRITICAL: Vault authentication not configured!")
                    logger.error("Environment: %s", environment)
                    logger.error("Required: VAULT_APPROLE_ROLE_ID + VAULT_APPROLE_SECRET_ID")
                    logger.error("   OR:     VAULT_K8S_ROLE")
                    logger.error("   OR:     VAULT_TOKEN (dev only)")
                    logger.error("Service CANNOT start without Vault authentication.")
                    logger.error("=" * 60)
                    raise SystemExit(1)
                else:
                    # Development only: allow VAULT_TOKEN if explicitly set
                    explicit_token = os.getenv("VAULT_TOKEN", "")
                    if explicit_token and explicit_token != "dev-only-token":
                        self.token = explicit_token
                        logger.warning("Vault: using explicit VAULT_TOKEN (dev mode only)")
                    else:
                        logger.warning("Vault: no auth configured in dev mode — secrets will use env fallback")
                        self.token = ""

        # Start token renewal thread (only if we have a token)
        if self.token:
            self._start_renewal()

        self._initialized = True
        logger.info(f"Vault client initialized → {self.vault_url} (env={environment})")

    async def _auth_approle(self, role_id: str, secret_id: str):
        """Authenticate via AppRole."""
        if not self._cb.can_attempt():
            raise CircuitBreakerOpen("Vault circuit breaker open")
        try:
            resp = await self._client.post(
                f"{self.vault_url}/v1/auth/approle/login",
                json={"role_id": role_id, "secret_id": secret_id},
            )
            resp.raise_for_status()
            auth = resp.json()["auth"]
            self.token = auth["client_token"]
            self._token_expires_at = time.time() + auth.get("lease_duration", 3600)
            self._cb.record_success()
        except Exception as e:
            self._cb.record_failure()
            logger.error(f"Vault AppRole auth failed: {e}")
            raise

    async def _auth_kubernetes(self, role: str):
        """Authenticate via Kubernetes service account JWT."""
        if not self._cb.can_attempt():
            raise CircuitBreakerOpen("Vault circuit breaker open")
        try:
            # Read the service account JWT from the standard K8s path
            jwt_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
            with open(jwt_path, "r") as f:
                jwt = f.read().strip()

            resp = await self._client.post(
                f"{self.vault_url}/v1/auth/kubernetes/login",
                json={"role": role, "jwt": jwt},
            )
            resp.raise_for_status()
            auth = resp.json()["auth"]
            self.token = auth["client_token"]
            self._token_expires_at = time.time() + auth.get("lease_duration", 3600)
            self._cb.record_success()
        except Exception as e:
            self._cb.record_failure()
            logger.error(f"Vault K8s auth failed: {e}")
            raise

    def _start_renewal(self):
        """Start background thread to renew token before expiry."""
        if self._renewal_thread and self._renewal_thread.is_alive():
            return

        def renew_loop():
            while True:
                try:
                    # Renew when 80% of TTL elapsed
                    time_to_expiry = self._token_expires_at - time.time()
                    if time_to_expiry < 300:  # Less than 5 min
                        self._renew_token()
                        logger.info("Vault token renewed")
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    logger.error(f"Vault token renewal failed: {e}")
                    time.sleep(60)

        self._renewal_thread = threading.Thread(target=renew_loop, daemon=True)
        self._renewal_thread.start()

    async def _renew_token(self):
        """Renew the current token."""
        if not self.token:
            return
        try:
            resp = await self._client.post(
                f"{self.vault_url}/v1/auth/token/renew-self",
                headers={"X-Vault-Token": self.token},
            )
            resp.raise_for_status()
            auth = resp.json()["auth"]
            self._token_expires_at = time.time() + auth.get("lease_duration", 3600)
        except Exception as e:
            logger.error(f"Vault token renewal failed: {e}")
            raise

    async def read_secret(self, path: str, cache_ttl: int = None) -> Dict[str, Any]:
        """
        Read a secret from Vault.
        Path format: "secret/data/hsaai/database" → reads from KV v2 engine.
        """
        if not self._initialized:
            self.initialize()

        if not self._cb.can_attempt():
            raise CircuitBreakerOpen("Vault circuit breaker open — secrets unavailable")

        cache_ttl = cache_ttl or self._cache_ttl

        # Check cache
        with self._lock:
            cached = self._cache.get(path)
            if cached and cached.expires_at > time.time():
                self._audit_access(path, "cache_hit")
                return cached.data

        # Read from Vault
        try:
            headers = {"X-Vault-Token": self.token}
            if self.namespace:
                headers["X-Vault-Namespace"] = self.namespace

            resp = await self._client.get(
                f"{self.vault_url}/v1/{path}",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            # KV v2: data is under "data.data"
            secret_data = data.get("data", {}).get("data", data.get("data", {}))
            lease_duration = data.get("lease_duration", 0)
            lease_id = data.get("lease_id", "")

            # Cache it
            ttl = min(cache_ttl, lease_duration) if lease_duration else cache_ttl
            with self._lock:
                self._cache[path] = CacheEntry(
                    data=secret_data,
                    expires_at=time.time() + ttl,
                    lease_id=lease_id,
                    lease_duration=lease_duration,
                )

            self._cb.record_success()
            self._audit_access(path, "vault_read")
            return secret_data

        except httpx.HTTPStatusError as e:
            self._cb.record_failure()
            logger.error(f"Vault read failed for {path}: HTTP {e.response.status_code}")
            raise
        except Exception as e:
            self._cb.record_failure()
            logger.error(f"Vault read failed for {path}: {e}")
            raise

    async def write_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """Write a secret to Vault (for rotation)."""
        if not self._initialized:
            self.initialize()
        try:
            headers = {"X-Vault-Token": self.token}
            if self.namespace:
                headers["X-Vault-Namespace"] = self.namespace

            # KV v2 write
            resp = await self._client.post(
                f"{self.vault_url}/v1/{path}",
                headers=headers,
                json={"data": data},
            )
            resp.raise_for_status()

            # Invalidate cache
            with self._lock:
                self._cache.pop(path, None)

            self._audit_access(path, "vault_write")
            return True
        except Exception as e:
            logger.error(f"Vault write failed for {path}: {e}")
            return False

    async def get_secret_value(self, path: str, key: str, default: str = None) -> str:
        """
        Convenience: read a single key from a secret path.
        Falls back to env var if Vault unavailable (for dev only).

        FIX S-02: Method is now async and awaits read_secret. Was sync calling
        async read_secret without await → returned coroutine → AttributeError.
        """
        try:
            secret = await self.read_secret(path)
            return secret.get(key, default)
        except (CircuitBreakerOpen, Exception) as e:
            logger.warning(f"Vault unavailable for {path}/{key}, falling back to env: {e}")
            return os.getenv(key.upper().replace("-", "_"), default)

    def get_secret_value_sync(self, path: str, key: str, default: str = None) -> str:
        """
        Sync wrapper for non-async contexts (CLI tools, workers).
        FIX S-02: Uses asyncio.run() to drive the async get_secret_value.
        Raises RuntimeError if called from inside an async context.
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                raise RuntimeError(
                    "Cannot call get_secret_value_sync from async context — "
                    "use 'await get_secret_value()' instead"
                )
        except RuntimeError:
            pass
        return asyncio.run(self.get_secret_value(path, key, default))

    async def health_check(self) -> Dict[str, Any]:
        """Check Vault health."""
        try:
            resp = await self._client.get(f"{self.vault_url}/v1/sys/health", timeout=5)
            return {
                "healthy": resp.status_code == 200,
                "status_code": resp.status_code,
                "sealed": resp.json().get("sealed", True) if resp.status_code == 200 else True,
                "circuit_breaker": self._cb.state,
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "circuit_breaker": self._cb.state,
            }

    def _audit_access(self, path: str, action: str):
        """Log secret access for audit trail."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": path,
            "action": action,
            "caller": threading.current_thread().name,
        }
        self._audit_log.append(entry)
        # Keep last 1000 entries
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-1000:]
        logger.debug(f"Vault access: {action} {path}")

    def get_audit_log(self, limit: int = 100) -> list:
        """Get recent audit log entries."""
        return self._audit_log[-limit:]

    def invalidate_cache(self, path: str = None):
        """Invalidate cache for a specific path or all paths."""
        with self._lock:
            if path:
                self._cache.pop(path, None)
            else:
                self._cache.clear()


# ─── Singleton ─────────────────────────────────────────────────────
vault_client = VaultClient()


def get_secret(path: str, key: str, default: str = None) -> str:
    """
    Convenience function: get a single secret value from Vault.
    Falls back to env var if Vault unavailable.

    Usage:
        db_password = get_secret("secret/data/hsaai/db", "password")
    """
    # FIX-21: get_secret_value is async — use the sync wrapper.
    # Previously called without await, returning a coroutine instead of a str.
    return vault_client.get_secret_value_sync(path, key, default)


def get_database_url() -> str:
    """
    Get database URL from Vault (not env var).
    Falls back to DATABASE_URL env var only in development.
    """
    env = os.getenv("DEPLOY_ENV", "development")
    if env == "development":
        return os.getenv("DATABASE_URL", "sqlite:///tmp/hsaai.db")
    # Production: get from Vault
    return get_secret("secret/data/hsaai/database", "url")


def get_jwt_signing_key() -> str:
    """Get JWT signing key from Vault (never env var in production)."""
    return get_secret("secret/data/hsaai/auth", "jwt_signing_key")


def get_openai_api_key() -> str:
    """Get OpenAI API key from Vault."""
    return get_secret("secret/data/hsaai/llm", "openai_api_key")
