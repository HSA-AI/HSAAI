"""HSAAI Digital Twin Service — v0.2.0
Simulates the enterprise. Answers 'What happens if?' before execution."""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from common.twin import digital_twin
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")

logger = logging.getLogger("digital_twin")
app = FastAPI(title="HSAAI Digital Twin", version="0.2.0")

class SimulationRequest(BaseModel):
    scenario: str
    variables: dict = {}
    horizon_months: int = 12
    iterations: int = 1000

@app.get("/health")
def health(): return {"status": "ok", "service": "digital_twin",
                      "simulations_run": digital_twin._simulation_count,
                      "snapshots": digital_twin.list_snapshots()}

@app.post("/v1/simulate")
async def simulate(req: SimulationRequest, claims: dict = Depends(_auth_dep)):
    result = await digital_twin.simulate(req.scenario, req.variables, req.horizon_months, req.iterations)
    return result.__dict__

@app.post("/v1/snapshot")
async def take_snapshot(label: str = "current", claims: dict = Depends(_auth_dep)):
    snap = await digital_twin.snapshot(label)
    return snap
