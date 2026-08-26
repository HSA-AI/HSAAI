"""
HSAAI Field-level Encryption (v4.0)

FIX S-12: Two critical fixes:
  1. Replaced unsalted SHA-256 key derivation with PBKDF2-HMAC-SHA256
     (600,000 iterations per OWASP 2023). Was vulnerable to rainbow tables.
  2. decrypt_text now RAISES on InvalidToken instead of returning ciphertext.
     Was silently degrading security when keys rotated.
"""
import base64
import hashlib
import os
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("hsaai.encryption")

_ENABLE = os.getenv("FIELD_ENCRYPTION_ENABLED", "true").lower() == "true"
_RAW_KEY = os.getenv("DATA_ENCRYPTION_KEY", "")
_SALT_PATH = os.getenv("ENCRYPTION_SALT_PATH", "/data/encryption.salt")

# OWASP 2023 recommendation for PBKDF2-HMAC-SHA256
_PBKDF2_ITERATIONS = 600_000


def _load_or_create_salt() -> bytes:
    """Load the salt from disk, or create it on first run.

    The salt MUST persist across restarts — without it, all encrypted data
    becomes undecryptable. We store it with 0600 permissions.
    """
    if os.path.exists(_SALT_PATH):
        with open(_SALT_PATH, "rb") as f:
            return f.read()
    salt = os.urandom(16)
    os.makedirs(os.path.dirname(_SALT_PATH) or ".", exist_ok=True)
    with open(_SALT_PATH, "wb") as f:
        f.write(salt)
    try:
        os.chmod(_SALT_PATH, 0o600)
    except OSError:
        pass  # Windows / non-POSIX
    logger.info("Created new encryption salt at %s", _SALT_PATH)
    return salt


def _derive_key(raw: str) -> bytes:
    """Derive a Fernet key from a secret + salt using PBKDF2.

    FIX S-12: Was using unsalted SHA-256 (vulnerable to rainbow tables, no
    key stretching). Now uses PBKDF2-HMAC-SHA256 with 600k iterations.
    """
    if not raw:
        raise RuntimeError("DATA_ENCRYPTION_KEY is not set")
    if raw.startswith("replace-with") or raw.startswith("CHANGE_ME"):
        raise RuntimeError(
            "DATA_ENCRYPTION_KEY must be set to a real value before enabling field encryption. "
            "Default/placeholder values are refused."
        )
    # If the key is already a valid Fernet key (44-char base64), use it directly.
    # This supports key rotation scenarios where ops generates a Fernet key directly.
    if len(raw) == 44 and raw.startswith("gAAAA") is False:
        try:
            return base64.urlsafe_b64decode(raw.encode())
        except Exception:
            pass  # Fall through to PBKDF2

    salt = _load_or_create_salt()
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        raw.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
        dklen=32,
    )
    return base64.urlsafe_b64encode(derived)


def encrypt_text(value: str) -> str:
    """Encrypt a text value using Fernet with PBKDF2-derived key."""
    if not _ENABLE or not value:
        return value
    if not _RAW_KEY:
        raise RuntimeError("DATA_ENCRYPTION_KEY must be set before enabling field encryption")
    return Fernet(_derive_key(_RAW_KEY)).encrypt(value.encode()).decode()


def decrypt_text(value: str) -> str:
    """Decrypt a Fernet-encrypted value.

    FIX S-12: Now RAISES ValueError on InvalidToken. Previously returned the
    ciphertext silently — masking key rotation issues and leaking encrypted
    data to callers expecting plaintext.
    """
    if not _ENABLE or not value:
        return value
    try:
        return Fernet(_derive_key(_RAW_KEY)).decrypt(value.encode()).decode()
    except InvalidToken:
        # NEVER return ciphertext on failure — raise explicitly
        raise ValueError(
            "Decryption failed — possible key rotation mismatch, "
            "tampered ciphertext, or wrong DATA_ENCRYPTION_KEY. "
            "Refusing to return ciphertext to caller."
        )
