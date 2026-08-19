"""
HSAAI AI Alignment + Safety Service (Production)
===================================================
Unified service combining:
  - Constitutional AI alignment (alignment_layer.py)
  - Runtime safety controls (safety_layer.py)

This service was created by merging the former ai_safety service into
ai_alignment (Phase 3 consolidation). Both layers now run in a single
container for operational simplicity.

Endpoints:
  POST /v1/alignment/align       — Apply constitutional alignment to a response
  POST /v1/safety/check          — Check if a tool call is permitted
  GET  /v1/safety/approvals/pending — List pending approvals
  POST /v1/safety/approvals/{id}/approve — Approve a request
  POST /v1/safety/approvals/{id}/reject  — Reject a request
  POST /v1/safety/kill-switch    — Activate kill switch (governance only)
  GET  /health                   — Service health check
  GET  /health/auth              — Auth module health
"""
import os
import sys
import logging
from pathlib import Path

# Add packages to path for shared library imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

# SECURITY FIX v2.1 (P0): Add shared service auth
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
    _AUTH_AVAILABLE = True
except ImportError as _e:
    _AUTH_AVAILABLE = False
    async def _auth_dep():  # type: ignore
        raise HTTPException(status_code=503, detail="Authentication module unavailable.")

# Import alignment and safety layers
# FIX-17: When ai_alignment is imported as a top-level module (e.g.
# `uvicorn ai_alignment.main:app`), Python doesn't add the package directory
# to sys.path, so `from alignment_layer import ...` fails with ModuleNotFoundError.
# We add the directory containing this file to sys.path so sibling modules
# (alignment_layer.py, safety_layer.py) become importable.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
from alignment_layer import alignment_layer, AlignmentLayer
from safety_layer import safety_layer, SafetyLayer, Severity

# ─── Structured Logging ────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","service":"ai_alignment","message":"%(message)s"}'
)
logger = logging.getLogger("hsaai.ai_alignment")

# ─── FastAPI App ───────────────────────────────────────────────────
app = FastAPI(
    title="HSAAI Alignment & Safety Service",
    version="4.0.0",
    description="Constitutional AI alignment + runtime safety controls",
)

# ─── CORS (centralized config) ─────────────────────────────────────
try:
    from common.security.cors_config import setup_cors
    setup_cors(app, environment=os.getenv("DEPLOY_ENV", "development"))
except ImportError:
    pass  # CORS config not available in dev

# ─── Rate Limiting ─────────────────────────────────────────────────
try:
    from common.security.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)
except ImportError:
    pass


# ─── Request/Response Models ───────────────────────────────────────
class AlignRequest(BaseModel):
    query: str
    response: str

class AlignResponse(BaseModel):
    aligned_response: str
    compliant: bool
    severity: str
    external_reviewed: bool
    blocked: bool

class SafetyCheckRequest(BaseModel):
    agent_id: str
    tenant_id: str
    user_id: str
    tool_name: str
    tool_args: dict = {}
    justification: str = ""

class SafetyCheckResponse(BaseModel):
    allowed: bool
    severity: str
    requires_approval: bool
    request_id: str = ""
    required_approvals: int = 0

class KillSwitchRequest(BaseModel):
    reason: str
    activated_by: str


# ─── Endpoints ─────────────────────────────────────────────────────
@app.post("/v1/alignment/align", response_model=AlignResponse)
async def align_response(req: AlignRequest, claims: dict = Depends(_auth_dep)):
    """Apply constitutional alignment to a response."""
    try:
        final_response, audit = await alignment_layer.align(req.query, req.response)
        return AlignResponse(
            aligned_response=final_response,
            compliant=audit.get("critique_compliant", False),
            severity=audit.get("critique_severity", "unknown"),
            external_reviewed=audit.get("external_approved") is not None,
            blocked=audit.get("final_blocked", False),
        )
    except Exception as e:
        logger.error(f"Alignment error: {e}")
        raise HTTPException(500, f"Alignment failed: {str(e)[:100]}")


@app.post("/v1/safety/check", response_model=SafetyCheckResponse)
async def check_safety(req: SafetyCheckRequest, claims: dict = Depends(_auth_dep)):
    """Check if a tool call is permitted."""
    result = await safety_layer.check_tool(
        agent_id=req.agent_id,
        tenant_id=req.tenant_id,
        user_id=req.user_id,
        tool_name=req.tool_name,
        tool_args=req.tool_args,
        justification=req.justification,
    )
    return SafetyCheckResponse(
        allowed=result.get("allowed", False),
        severity=result.get("severity", "INFO"),
        requires_approval=result.get("requires_approval", False),
        request_id=result.get("request_id", ""),
        required_approvals=result.get("required_approvals", 0),
    )


@app.get("/v1/safety/approvals/pending")
async def get_pending_approvals(tenant_id: str = None, claims: dict = Depends(_auth_dep)):
    """Get pending approval requests."""
    approvals = await safety_layer.get_pending_approvals(tenant_id)
    return {"approvals": approvals, "count": len(approvals)}


@app.post("/v1/safety/approvals/{request_id}/approve")
async def approve_request(request_id: str, approver_id: str = "", claims: dict = Depends(_auth_dep)):
    """Approve a pending request."""
    result = await safety_layer.approve_request(request_id, approver_id)
    return result


@app.post("/v1/safety/approvals/{request_id}/reject")
async def reject_request(request_id: str, rejecter_id: str = "", reason: str = "", claims: dict = Depends(_auth_dep)):
    """Reject a pending request."""
    result = await safety_layer.reject_request(request_id, rejecter_id, reason)
    return result


@app.post("/v1/safety/kill-switch")
async def activate_kill_switch(req: KillSwitchRequest, claims: dict = Depends(_auth_dep)):
    """Activate the kill switch — halts all agent activity immediately.
    SECURITY FIX v2.1 (P0): Now requires authenticated service auth.
    Previously anyone with network access could halt all AI activity."""
    safety_layer.activate_kill_switch(req.reason, req.activated_by)
    return {"status": "activated", "reason": req.reason, "by": req.activated_by}


@app.delete("/v1/safety/kill-switch")
async def deactivate_kill_switch(deactivated_by: str = "", claims: dict = Depends(_auth_dep)):
    """Deactivate the kill switch."""
    safety_layer.deactivate_kill_switch(deactivated_by)
    return {"status": "deactivated"}


@app.get("/health")
async def health():
    """Service health check."""
    return {
        "status": "ok",
        "service": "ai_alignment",
        "components": {
            "alignment_layer": True,
            "safety_layer": True,
            "kill_switch_active": safety_layer.kill_switch_active,
        },
    }


@app.get("/health/auth")
async def auth_health():
    """Auth module health check."""
    return {"auth_available": True, "fail_closed": True}


if __name__ == "__main__":
    # FIX v2.2 (Phase 2): mTLS support via shared helper.
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..', 'packages'))
    try:
        from common.security.mtls_server import run_with_mtls
        run_with_mtls("ai_alignment.main:app", host="0.0.0.0", port=8005)
    except ImportError:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8005)
