"""HSAAI Consciousness Stream Service — v0.2.0
The 'eyes' of the cognitive organism. Ingests enterprise events in real-time."""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from common.consciousness import consciousness_stream, EnterpriseEvent
from common.constitution import constitution
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")

logger = logging.getLogger("consciousness_stream")
app = FastAPI(title="HSAAI Consciousness Stream", version="0.2.0")

class EventIngest(BaseModel):
    event_type: str
    source: str
    entities: list[dict] = []
    payload: dict = {}
    severity: str = "info"
    tenant_id: str = "default"

@app.get("/health")
def health(): return {"status": "ok", "service": "consciousness_stream", **consciousness_stream.stats()}

@app.post("/v1/event/ingest")
async def ingest_event(evt: EventIngest, claims: dict = Depends(_auth_dep)):
    event = EnterpriseEvent(
        event_type=evt.event_type, source=evt.source, entities=evt.entities,
        payload=evt.payload, severity=evt.severity, tenant_id=evt.tenant_id,
    )
    # Constitutional check
    verdict = await constitution.check(
        action={"type": "event_ingest", "sensitivity": evt.payload.get("sensitivity", "internal")},
        actor=claims,
    )
    if not verdict.compliant:
        return {"error": "Constitutional violation", "details": verdict.to_dict()}, 403
    result = await consciousness_stream.ingest(event)
    return result

@app.get("/v1/stats")
def stats(claims: dict = Depends(_auth_dep)):
    return consciousness_stream.stats()
