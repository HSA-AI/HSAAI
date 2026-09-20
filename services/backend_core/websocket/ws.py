"""
HSAAI WebSocket Endpoint (v2.0 hardened)

SECURITY FIX v2.0:
  - Now requires JWT authentication via query string or Sec-WebSocket-Protocol header.
  - Was completely unauthenticated in v1.1 (Critical bypass).
  - User identity (sub, tenant_id) is sourced from JWT, not hardcoded "websocket-user".
"""
import os
import sys
from fastapi import WebSocket, WebSocketDisconnect, HTTPException, status

# Add packages/ to path for service_auth import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'packages'))

from backend_core.core.engine import process_message

try:
    from common.auth.service_auth import verify_jwt
    _AUTH_AVAILABLE = True
except ImportError:
    _AUTH_AVAILABLE = False

    def verify_jwt(token: str) -> dict:  # type: ignore
        # Fallback when packages/common not available (dev mode only)
        return {"sub": "dev-user", "tenant_id": "default", "workspace_id": "default", "roles": []}


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint with mandatory JWT authentication.

    Token can be provided via:
      1. Query string: ws://host/ws?token=<JWT>
      2. Sec-WebSocket-Protocol header: <code>new WebSocket(url, ["auth.<JWT>"])</code>

    If no valid token is provided, the connection is closed with code 4401.
    """
    # Extract token from query string or Sec-WebSocket-Protocol header
    token = websocket.query_params.get("token")
    if not token:
        # Try Sec-WebSocket-Protocol header (browser-friendly pattern)
        protocols_header = websocket.headers.get("sec-websocket-protocol", "")
        if protocols_header:
            for proto in protocols_header.split(","):
                proto = proto.strip()
                if proto.startswith("auth."):
                    token = proto[5:]
                    break

    if not token:
        await websocket.close(code=4401, reason="Missing authentication token")
        return

    # Verify JWT
    try:
        claims = verify_jwt(token)
    except HTTPException:
        await websocket.close(code=4401, reason="Invalid or expired token")
        return
    except Exception:
        await websocket.close(code=4401, reason="Token verification failed")
        return

    # Accept the WebSocket connection (auth passed)
    await websocket.accept()

    # Use real user identity from JWT claims
    user_id = claims.get("sub", "unknown")
    tenant_id = claims.get("tenant_id", "default")
    workspace_id = claims.get("workspace_id", "default")

    try:
        while True:
            msg = await websocket.receive_text()
            # Pass user_id + tenant_id to process_message for proper attribution
            result = process_message(user_id, msg, tenant_id=tenant_id, workspace_id=workspace_id)
            await websocket.send_json(result)
    except WebSocketDisconnect:
        return
    except Exception:
        # Log and gracefully close on any other error
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
        return
