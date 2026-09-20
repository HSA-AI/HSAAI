"""HSAAI Intelligence Economy Service — v0.2.0
Measures intelligence as a financial asset."""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from common.intelligence_economy import intelligence_economy
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")

logger = logging.getLogger("intelligence_economy")
app = FastAPI(title="HSAAI Intelligence Economy", version="0.2.0")

class DecisionRecord(BaseModel):
    outcome_value: float = 0.0
class AutomationRecord(BaseModel):
    hours_saved: int
    hourly_rate: float = 50.0
class LossAvoidedRecord(BaseModel):
    amount: float

@app.get("/health")
def health(): return {"status": "ok", "service": "intelligence_economy"}

@app.post("/v1/record/decision")
def record_decision(rec: DecisionRecord, claims: dict = Depends(_auth_dep)):
    intelligence_economy.record_decision(rec.outcome_value)
    return {"recorded": True}

@app.post("/v1/record/automation")
def record_automation(rec: AutomationRecord, claims: dict = Depends(_auth_dep)):
    intelligence_economy.record_automation(rec.hours_saved, rec.hourly_rate)
    return {"recorded": True}

@app.post("/v1/record/loss-avoided")
def record_loss_avoided(rec: LossAvoidedRecord, claims: dict = Depends(_auth_dep)):
    intelligence_economy.record_loss_avoided(rec.amount)
    return {"recorded": True}

@app.get("/v1/balance-sheet")
def balance_sheet(period: str = "monthly", costs: float = 195000.0, claims: dict = Depends(_auth_dep)):
    bs = intelligence_economy.generate_balance_sheet(period, costs)
    return bs.__dict__
