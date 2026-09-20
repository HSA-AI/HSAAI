"""
HSAAI Default Secrets Detector (Fix #3)
=========================================
Scans all environment variables at startup to detect default/placeholder secrets.
If any forbidden value is found, the service refuses to start (Fail Closed).

Usage (add to any service's startup):
    from packages.common.security.secret_validator import validate_no_default_secrets
    validate_no_default_secrets()
"""
import os
import re
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger("hsaai.secret_validator")

# Known default/placeholder/weak secret values
FORBIDDEN_VALUES = {
    "change-me", "changeme", "secret", "password", "default", "test",
    "placeholder", "example", "todo", "fixme", "your-secret-here",
    "your-key-here", "replace-me", "xxx", "123456", "admin", "root",
}

# Secret-related env var names to check
SECRET_ENV_VARS = [
    "JWT_SECRET", "JWT_SIGNING_KEY", "AUDIT_HMAC_SECRET",
    "DATABASE_PASSWORD", "REDIS_PASSWORD", "POSTGRES_PASSWORD",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "KEYCLOAK_PASSWORD", "VAULT_TOKEN", "VAULT_APPROLE_SECRET_ID",
    "SHAREPOINT_CLIENT_SECRET", "SAP_CLIENT_SECRET",
    "SUCCESSFACTORS_CLIENT_SECRET", "SLACK_BOT_TOKEN",
    "AD_PASSWORD", "NEO4J_PASSWORD", "QDRANT_API_KEY",
]

# Patterns that indicate a weak secret
WEAK_PATTERNS = [
    re.compile(r"^(test|demo|sample|example)", re.IGNORECASE),
    re.compile(r"^(password|secret|key)\d*$", re.IGNORECASE),
    re.compile(r"^changeme", re.IGNORECASE),
    re.compile(r"^(xxx+|yyy+|zzz+)$", re.IGNORECASE),
    re.compile(r"^<.*>$"),  # <your-secret>
    re.compile(r"^\$\{.*\}$"),  # ${placeholder}
]


def is_secret_weak(value: str) -> bool:
    """Check if a secret value is weak/default/placeholder."""
    if not value or len(value) < 8:
        return True
    lower = value.lower()
    if lower in FORBIDDEN_VALUES:
        return True
    for pattern in WEAK_PATTERNS:
        if pattern.match(value):
            return True
    return False


def scan_env_for_default_secrets() -> List[Tuple[str, str]]:
    """
    Scan environment variables for default/weak secrets.
    Returns list of (env_var_name, reason) tuples for violations.
    """
    violations = []
    for var_name in SECRET_ENV_VARS:
        value = os.getenv(var_name, "")
        if not value:
            continue  # Not set — skip (Vault will provide)
        if is_secret_weak(value):
            violations.append((var_name, f"weak/default value: '{value[:3]}...'"))
    return violations


def validate_no_default_secrets(fail_closed: bool = True) -> bool:
    """
    Validate that no default/weak secrets are in use.
    Call at service startup.

    Args:
        fail_closed: If True, raise SystemExit on violation.
                     If False, log warning and return False.

    Returns:
        True if all secrets are valid, False if violations found.
    """
    # Skip in test environment
    if os.getenv("DEPLOY_ENV") == "test" or os.getenv("ALLOW_WEAK_SECRETS") == "true":
        return True

    violations = scan_env_for_default_secrets()

    if violations:
        logger.error("=" * 60)
        logger.error("CRITICAL: Default/weak secrets detected!")
        for var_name, reason in violations:
            logger.error(f"  {var_name}: {reason}")
        logger.error("All secrets must come from Vault with strong values.")
        logger.error("=" * 60)

        if fail_closed:
            raise SystemExit(1)
        return False

    logger.info("✓ Secret validation passed — no default/weak secrets detected")
    return True
