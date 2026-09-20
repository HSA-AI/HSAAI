"""HSAAI Empathy Engine Service — v0.4.0
Senses the emotional state of the organization."""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from common.empathy import empathy_engine
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")

logger = logging.getLogger("empathy_service")
app = FastAPI(title="HSAAI Empathy Engine", version="0.4.0")

class EntityAssessment(BaseModel):
    entity_id: str
    entity_type: str = "person"
    signals: dict = {}

@app.get("/health")
def health(): return {"status": "ok", "service": "empathy_engine", **empathy_engine.stats()}

@app.post("/v1/assess")
async def assess_entity(req: EntityAssessment, claims: dict = Depends(_auth_dep)):
    state = await empathy_engine.assess_entity(req.entity_id, req.entity_type, req.signals)
    return state.__dict__

@app.get("/v1/climate")
async def get_climate(claims: dict = Depends(_auth_dep)):
    climate = await empathy_engine.assess_organizational_climate()
    return climate.__dict__

@app.get("/v1/entity/{entity_id}")
def get_entity(entity_id: str, claims: dict = Depends(_auth_dep)):
    return empathy_engine.get_entity_state(entity_id) or {"error": "not found"}

@app.get("/v1/trend")
def climate_trend(days: int = 30, claims: dict = Depends(_auth_dep)):
    return empathy_engine.climate_trend(days)
