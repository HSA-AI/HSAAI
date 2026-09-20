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
import tempfile
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("hsaai.encryption")

_ENABLE = os.getenv("FIELD_ENCRYPTION_ENABLED", "true").lower() == "true"
_RAW_KEY = os.getenv("DATA_ENCRYPTION_KEY", "")
_SALT_PATH = os.getenv("ENCRYPTION_SALT_PATH", "/data/encryption.salt")
if not os.access(os.path.dirname(_SALT_PATH) or ".", os.W_OK):
    # PORTABILITY FIX: /data exists only inside the Docker deployment.
    # Keep the salt in a writable persistent location; path stays overridable
    # via ENCRYPTION_SALT_PATH for volume-mounted production setups.
    _salt_dir = Path(os.getenv("HSAAI_HOME", Path.cwd())) / "data"
    _SALT_PATH = str(_salt_dir / "encryption.salt")
    os.makedirs(_salt_dir, exist_ok=True)

# OWASP 2023 recommendation for PBKDF2-HMAC-SHA256
_PBKDF2_ITERATIONS = 600_000


def _load_or_create_salt() -> bytes:
    """Load the salt from disk, or create it on first run.

    The salt MUST persist across restarts — without it, all encrypted data
    becomes undecryptable. We store it with 0600 permissions.
    """
    path = Path(_SALT_PATH)
    def read_valid_salt() -> bytes:
        salt = path.read_bytes()
        if len(salt) != 16:
            raise RuntimeError("Invalid encryption salt; restore the original persistent salt")
        return salt

    if path.exists():
        return read_valid_salt()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Publish only a complete private salt; concurrent processes share a winner.
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".salt-", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(os.urandom(16))
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            os.link(temporary_path, path)
            logger.info("Created persistent encryption salt")
        except FileExistsError:
            pass  # Another process published the complete persistent salt.
        return read_valid_salt()
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


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
            encoded = raw.encode("ascii")
            Fernet(encoded)
            return encoded
        except (ValueError, UnicodeError):
            pass  # Not an encoded Fernet key; use passphrase derivation.

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
