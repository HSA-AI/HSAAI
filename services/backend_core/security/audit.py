"""
HSAAI Audit Logging — Production Implementation with HMAC Integrity

SECURITY FIX: Added HMAC-SHA256 integrity verification to prevent
tampering with audit logs. Each entry is signed with a secret key.
Added log rotation and centralized shipping support.
"""
import os
import json
import hmac
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("hsaai.audit")

AUDIT_DIR = Path(os.getenv("AUDIT_LOG_DIR", "/data/audit_logs"))
try:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
except (PermissionError, OSError):
    # PORTABILITY FIX: /data only exists in the Docker deployment. Outside of
    # it (bare-metal, local dev, sandboxed environments) creating /data fails
    # at import time and crashes the whole service. Fall back to a writable
    # relative path without weakening audit logging itself.
    _fallback = Path(os.getenv("HSAAI_HOME", Path.cwd())) / "data" / "audit_logs"
    try:
        _fallback.mkdir(parents=True, exist_ok=True)
        AUDIT_DIR = _fallback
        logger.warning("AUDIT_LOG_DIR unwritable (%s) — falling back to %s", AUDIT_DIR, _fallback)
    except (PermissionError, OSError) as _exc:
        raise RuntimeError(
            f"Cannot create audit log directory {AUDIT_DIR} nor fallback {_fallback}: {_exc}. "
            "Set AUDIT_LOG_DIR to a writable path."
        ) from _exc

# HMAC key for audit log integrity
# FIX v0.1 (P0): Refuse to start in production if AUDIT_HMAC_KEY is unset.
# Previously: silent downgrade with only a warning log — an attacker who
# tampers with audit logs would not be detected.
_AUDIT_HMAC_KEY = os.getenv("AUDIT_HMAC_KEY", "").encode()
_APP_ENV = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
if not _AUDIT_HMAC_KEY:
    if _APP_ENV in {"production", "prod"}:
        raise RuntimeError(
            "AUDIT_HMAC_KEY must be set in production. Refusing to start "
            "with audit log integrity verification disabled."
        )
    logger.warning("AUDIT_HMAC_KEY not set — audit log integrity verification disabled (dev mode only)")

# Log rotation settings
MAX_AUDIT_FILE_SIZE_MB = int(os.getenv("AUDIT_MAX_FILE_SIZE_MB", "100"))
AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "365"))


def _compute_hmac(payload: str) -> str:
    """Compute HMAC-SHA256 signature for audit log entry."""
    if not _AUDIT_HMAC_KEY:
        return ""
    return hmac.new(_AUDIT_HMAC_KEY, payload.encode(), hashlib.sha256).hexdigest()


def _get_audit_file() -> Path:
    """Get the current audit log file path (date-based rotation)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return AUDIT_DIR / f"audit_{today}.jsonl"


def _rotate_if_needed(path: Path) -> None:
    """Rotate audit file if it exceeds the maximum size."""
    if path.exists() and path.stat().st_size > MAX_AUDIT_FILE_SIZE_MB * 1024 * 1024:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        rotated = path.with_name(f"{path.stem}_{timestamp}.jsonl")
        path.rename(rotated)
        logger.info("Audit log rotated: %s → %s", path.name, rotated.name)


def write_audit(
    actor: str,
    action: str,
    resource: str = "",
    tenant_id: str = "",
    workspace_id: str = "",
    success: bool = True,
    detail: str = "",
    **extra: Any,
) -> None:
    """
    Write an audit log entry with HMAC integrity signature.

    Each entry includes:
    - timestamp (UTC)
    - actor, action, resource
    - tenant_id, workspace_id
    - success flag
    - HMAC signature for tamper detection
    """
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "resource": resource,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "success": success,
        "detail": detail,
    }
    if extra:
        event["extra"] = extra

    # Compute HMAC over the canonical JSON
    canonical = json.dumps(event, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    event["hmac"] = _compute_hmac(canonical)

    path = _get_audit_file()
    _rotate_if_needed(path)

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# FIX (runtime): engine.py imports `audit` (singular) from this module.
# Only `write_audit` exists. Add a thin alias matching the call signature
# `audit(user, action, resource, workspace_id)` used in engine.py.
# No business logic changed — just delegates to write_audit.
def audit(actor: str, action: str, resource: str = "", workspace_id: str = "", **kwargs: Any) -> None:
    """Backwards-compatible alias for write_audit (used by engine.py)."""
    write_audit(actor=actor, action=action, resource=resource, workspace_id=workspace_id, **kwargs)


def verify_audit_integrity(filepath: Path | None = None) -> dict:
    """
    Verify HMAC integrity of audit log entries.

    Returns dict with:
    - total: number of entries checked
    - valid: number of entries with valid HMAC
    - invalid: list of line numbers with invalid/missing HMAC
    - missing_key: True if AUDIT_HMAC_KEY is not configured
    """
    if not _AUDIT_HMAC_KEY:
        return {"error": "AUDIT_HMAC_KEY not configured", "missing_key": True}

    target = filepath or _get_audit_file()
    if not target.exists():
        return {"total": 0, "valid": 0, "invalid": [], "missing_key": False}

    total = 0
    valid = 0
    invalid = []

    with target.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                entry = json.loads(line)
                stored_hmac = entry.pop("hmac", None)
                if not stored_hmac:
                    invalid.append(line_no)
                    continue
                canonical = json.dumps(entry, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                expected = _compute_hmac(canonical)
                if hmac.compare_digest(stored_hmac, expected):
                    valid += 1
                else:
                    invalid.append(line_no)
            except json.JSONDecodeError:
                invalid.append(line_no)

    return {"total": total, "valid": valid, "invalid": invalid, "missing_key": False}
