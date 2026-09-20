"""HSAAI Proactive Intelligence Service — v0.2.0
Doesn't wait for questions — discovers anomalies, opportunities, and risks."""
import os, sys, logging, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends, BackgroundTasks
from pydantic import BaseModel
from common.proactive import proactive_engine
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")

logger = logging.getLogger("proactive_intelligence")
app = FastAPI(title="HSAAI Proactive Intelligence", version="0.2.0")

class MetricsInput(BaseModel):
    metrics: dict
class IndicatorsInput(BaseModel):
    indicators: dict
class OpportunityInput(BaseModel):
    data: dict

@app.get("/health")
def health(): return {"status": "ok", "service": "proactive_intelligence",
                      "total_alerts": len(proactive_engine._alerts)}

@app.post("/v1/detect/anomalies")
async def detect_anomalies(inp: MetricsInput, claims: dict = Depends(_auth_dep)):
    alerts = await proactive_engine.detect_anomalies(inp.metrics)
    return {"alerts": [a.__dict__ for a in alerts], "count": len(alerts)}

@app.post("/v1/discover/opportunities")
async def discover_opportunities(inp: OpportunityInput, claims: dict = Depends(_auth_dep)):
    opportunities = await proactive_engine.discover_opportunities(inp.data)
    return {"opportunities": [o.__dict__ for o in opportunities], "count": len(opportunities)}

@app.post("/v1/predict/risks")
async def predict_risks(inp: IndicatorsInput, claims: dict = Depends(_auth_dep)):
    risks = await proactive_engine.predict_risks(inp.indicators)
    return {"risks": [r.__dict__ for r in risks], "count": len(risks)}

@app.get("/v1/alerts")
def list_alerts(alert_type: str = None, limit: int = 50, claims: dict = Depends(_auth_dep)):
    alerts = proactive_engine.list_alerts(alert_type, limit)
    return {"alerts": [a.__dict__ for a in alerts]}
