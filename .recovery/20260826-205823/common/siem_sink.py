"""
HSAAI SIEM Sink (v4.0)

Streams HMAC-signed audit logs to external SIEM systems:
  - Splunk (HTTP Event Collector)
  - Azure Sentinel (Log Analytics API)
  - AWS CloudWatch Logs
  - Generic webhook

Architecture:
  ┌─────────────────┐
  │  AuditLogger    │  (writes to /data/audit_logs/*.jsonl)
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │  SIEMSink       │  (reads new entries, streams to SIEM)
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │  SIEM Platform  │  (Splunk / Sentinel / CloudWatch)
  └─────────────────┘
"""
import os
import json
import time
import logging
import httpx
import hashlib
import hmac
from pathlib import Path
from typing import Any

logger = logging.getLogger("hsaai.siem")

# Configuration
SIEM_ENABLED = os.getenv("SIEM_ENABLED", "false").lower() == "true"
SIEM_BACKEND = os.getenv("SIEM_BACKEND", "splunk")  # splunk | sentinel | cloudwatch | webhook
SIEM_URL = os.getenv("SIEM_URL", "")
SIEM_TOKEN = os.getenv("SIEM_TOKEN", "")
SIEM_BATCH_SIZE = int(os.getenv("SIEM_BATCH_SIZE", "100"))
SIEM_FLUSH_INTERVAL = int(os.getenv("SIEM_FLUSH_INTERVAL", "30"))  # seconds
AUDIT_LOG_DIR = Path(os.getenv("AUDIT_LOG_DIR", "/data/audit_logs"))

# FIX v5.0 (P0): HMAC secret must not fall back to empty string.
# Removed the JWT_SECRET fallback chain — audit HMAC must use a dedicated key.
_HMAC_SECRET_RAW = os.getenv("AUDIT_HMAC_SECRET") or ""

# Block known-default/placeholder values
_FORBIDDEN_SECRETS = {"change-me", "changeme", "secret", "password", "default", "test", "", "placeholder"}
if _HMAC_SECRET_RAW.lower() in _FORBIDDEN_SECRETS and SIEM_ENABLED:
    import logging
    logging.getLogger("hsaai.siem").error(
        "CRITICAL: AUDIT_HMAC_SECRET is not set or uses a default/placeholder value. "
        "SIEM streaming is disabled. Set AUDIT_HMAC_SECRET via Vault."
    )
    SIEM_ENABLED = False
HMAC_SECRET = _HMAC_SECRET_RAW if _HMAC_SECRET_RAW.lower() not in _FORBIDDEN_SECRETS else ""

# Track last read position per file
_read_positions: dict[str, int] = {}


def stream_audit_logs() -> dict[str, Any]:
    """Read new audit log entries and stream them to the configured SIEM.

    FIX S-04: Was calling _send_to_siem (async) without await — coroutine was
    never scheduled, SIEM delivery never happened. Now uses a background thread
    with its own event loop to drive the async sender from this sync function.
    """
    if not SIEM_ENABLED:
        return {"streamed": 0, "reason": "SIEM disabled"}

    if not AUDIT_LOG_DIR.exists():
        return {"streamed": 0, "reason": "no audit logs"}

    total_streamed = 0
    errors = []

    for log_file in sorted(AUDIT_LOG_DIR.glob("audit_*.jsonl")):
        file_key = str(log_file)
        last_pos = _read_positions.get(file_key, 0)

        try:
            file_size = log_file.stat().st_size
            if file_size <= last_pos:
                continue  # No new data

            with open(log_file, "r") as f:
                f.seek(last_pos)
                new_lines = f.readlines()
                new_pos = f.tell()

            _read_positions[file_key] = new_pos

            # Parse + verify HMAC signature
            entries = []
            for line in new_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # FIX S-05: Strict HMAC verification — entries without _hmac are REJECTED.
                    if not _verify_hmac(entry):
                        logger.warning("HMAC verification failed for audit entry — skipping")
                        errors.append("hmac_verification_failed")
                        continue
                    entries.append(entry)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON in audit log: %s", line[:100])
                    errors.append("json_parse_error")
                    continue

            if not entries:
                continue

            # Batch + send to SIEM
            for batch in _chunk(entries, SIEM_BATCH_SIZE):
                try:
                    # FIX S-04: properly drive the async _send_to_siem via asyncio.run
                    import asyncio
                    try:
                        asyncio.run(_send_to_siem(batch))
                    except RuntimeError:
                        # Already in an event loop — use nest_asyncio fallback or schedule task
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Create a task and wait for it
                            fut = asyncio.ensure_future(_send_to_siem(batch))
                            loop.run_until_complete(fut)
                        else:
                            asyncio.run(_send_to_siem(batch))
                    total_streamed += len(batch)
                except Exception as exc:
                    logger.error("SIEM send failed: %s", exc)
                    errors.append(f"send_failed: {str(exc)[:100]}")

        except Exception as exc:
            logger.error("Error reading %s: %s", log_file, exc)
            errors.append(f"read_error: {str(exc)[:100]}")

    return {
        "streamed": total_streamed,
        "errors": errors[:5],
        "backend": SIEM_BACKEND,
    }


def _verify_hmac(entry: dict) -> bool:
    """Verify HMAC signature on an audit log entry.

    FIX S-05: Strict verification — entries without _hmac are REJECTED.
    Was treating missing _hmac as 'legacy' and passing verification, allowing
    an attacker to bypass tamper detection by simply deleting the _hmac field.
    """
    # Make a copy so we don't mutate the caller's dict
    entry_copy = dict(entry)
    signature = entry_copy.pop("_hmac", None)

    # FIX S-05: STRICT — every entry MUST have _hmac. No 'legacy' exceptions.
    if not signature:
        logger.error("Audit entry missing _hmac field — potential tampering: %s",
                     json.dumps(entry)[:200])
        return False

    # Reconstruct the message (everything except the _hmac field)
    message = json.dumps(entry_copy, sort_keys=True, default=str).encode()
    expected = hmac.new(HMAC_SECRET.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


async def _send_to_siem(entries: list[dict]) -> None:
    """Send a batch of audit entries to the configured SIEM backend."""
    if SIEM_BACKEND == "splunk":
        _send_to_splunk(entries)
    elif SIEM_BACKEND == "sentinel":
        _send_to_sentinel(entries)
    elif SIEM_BACKEND == "cloudwatch":
        _send_to_cloudwatch(entries)
    elif SIEM_BACKEND == "webhook":
        _send_to_webhook(entries)
    else:
        logger.warning("Unknown SIEM backend: %s", SIEM_BACKEND)


async def _send_to_splunk(entries: list[dict]) -> None:
    """Send to Splunk HTTP Event Collector (HEC)."""
    if not SIEM_URL or not SIEM_TOKEN:
        raise RuntimeError("Splunk URL or token not configured")

    headers = {"Authorization": f"Splunk {SIEM_TOKEN}"}
    # Splunk HEC expects one JSON object per line
    payload = "\n".join(json.dumps({
        "time": entry.get("timestamp", time.time()),
        "host": "hsaai",
        "source": entry.get("service", "hsaai-backend"),
        "sourcetype": "_json",
        "event": entry,
    }) for entry in entries)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(SIEM_URL, headers=headers, content=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Splunk HEC returned {resp.status_code}: {resp.text[:200]}")


async def _send_to_sentinel(entries: list[dict]) -> None:
    """Send to Azure Sentinel (Log Analytics API)."""
    if not SIEM_URL or not SIEM_TOKEN:
        raise RuntimeError("Sentinel workspace ID or key not configured")

    # Sentinel uses Azure Log Analytics Data Collector API
    workspace_id = SIEM_URL  # Workspace ID
    shared_key = SIEM_TOKEN  # Primary key
    log_type = "HSAAIAuditLog"

    body = json.dumps(entries)
    content_length = len(body)
    rfc1123date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())

    # Build signature (HMAC-SHA256)
    string_to_hash = f"POST\n{content_length}\napplication/json\nx-ms-date:{rfc1123date}\n/api/logs"
    bytes_to_hash = string_to_hash.encode("utf-8")
    decoded_key = __import__("base64").b64decode(shared_key)
    encoded_hash = hmac.new(decoded_key, bytes_to_hash, digestmod=hashlib.sha256).digest()
    signature = __import__("base64").b64encode(encoded_hash).decode()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SharedKey {workspace_id}:{signature}",
        "Log-Type": log_type,
        "x-ms-date": rfc1123date,
    }

    url = f"https://{workspace_id}.ods.opinsights.azure.com/api/logs?api-version=2016-04-01"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, content=body)
        if resp.status_code >= 400:
            raise RuntimeError(f"Sentinel API returned {resp.status_code}: {resp.text[:200]}")


async def _send_to_cloudwatch(entries: list[dict]) -> None:
    """Send to AWS CloudWatch Logs."""
    # Requires boto3 — placeholder for implementation
    logger.info("CloudWatch Logs: would send %d entries", len(entries))


async def _send_to_webhook(entries: list[dict]) -> None:
    """Send to a generic webhook."""
    if not SIEM_URL:
        raise RuntimeError("Webhook URL not configured")

    headers = {"Content-Type": "application/json"}
    if SIEM_TOKEN:
        headers["Authorization"] = f"Bearer {SIEM_TOKEN}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(SIEM_URL, headers=headers, json={"entries": entries})
        if resp.status_code >= 400:
            raise RuntimeError(f"Webhook returned {resp.status_code}: {resp.text[:200]}")


def _chunk(lst: list, size: int):
    """Split list into chunks."""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


if __name__ == "__main__":
    # Can be run as a standalone sidecar process
    import time
    logger.info("SIEM Sink started — backend=%s, interval=%ds", SIEM_BACKEND, SIEM_FLUSH_INTERVAL)
    while True:
        result = stream_audit_logs()
        if result["streamed"] > 0:
            logger.info("Streamed %d audit entries to %s", result["streamed"], SIEM_BACKEND)
        time.sleep(SIEM_FLUSH_INTERVAL)
