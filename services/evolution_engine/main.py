"""HSAAI Evolution Engine — v0.3.0
Autonomous self-improvement. Monitor → Detect → Hypothesize → Test → Deploy."""
import os, sys, logging, time, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends, BackgroundTasks
from pydantic import BaseModel
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")

logger = logging.getLogger("evolution_engine")
app = FastAPI(title="HSAAI Evolution Engine", version="0.3.0")

class EvolutionCycle(BaseModel):
    domain: str = "general"
    metrics: dict = {}
    target_improvement: str = ""
    experiment_duration_hours: int = 24

class ImprovementProposal(BaseModel):
    proposal_id: str = ""
    hypothesis: str = ""
    expected_improvement: float = 0.0
    test_plan: str = ""
    risk_level: str = "low"
    status: str = "proposed"

_proposals: list[dict] = []
_experiments: list[dict] = []
_cycle_count = 0

@app.get("/health")
def health(): return {"status": "ok", "service": "evolution_engine",
                      "cycles": _cycle_count, "proposals": len(_proposals),
                      "experiments": len(_experiments)}

@app.post("/v1/evolve")
async def evolve(cycle: EvolutionCycle, bg: BackgroundTasks, claims: dict = Depends(_auth_dep)):
    global _cycle_count
    _cycle_count += 1
    # 1. Detect: check for degradation
    degradations = []
    for metric, values in cycle.metrics.items():
        if len(values) >= 5:
            recent = sum(values[-3:]) / 3
            baseline = sum(values[:-3]) / max(len(values) - 3, 1)
            if baseline > 0 and recent < baseline * 0.9:
                degradations.append({"metric": metric, "drop": (1 - recent/baseline) * 100})
    # 2. Hypothesize
    proposals = []
    for deg in degradations:
        prop = {
            "proposal_id": f"prop-{_cycle_count:04d}-{deg['metric']}",
            "hypothesis": f"Restoring {deg['metric']} by adjusting related parameters. "
                         f"Detected {deg['drop']:.1f}% degradation.",
            "expected_improvement": deg["drop"] / 2,
            "test_plan": f"Shadow mode for {cycle.experiment_duration_hours}h, "
                        f"then canary 10% for 4h, then full deploy if improved.",
            "risk_level": "low",
            "status": "proposed",
            "domain": cycle.domain,
        }
        proposals.append(prop)
        _proposals.append(prop)
    return {"cycle": _cycle_count, "degradations_found": len(degradations),
            "proposals": proposals, "status": "analyzed"}

@app.post("/v1/experiment/{proposal_id}")
async def start_experiment(proposal_id: str, claims: dict = Depends(_auth_dep)):
    prop = next((p for p in _proposals if p["proposal_id"] == proposal_id), None)
    if not prop: return {"error": "Proposal not found"}
    prop["status"] = "experimenting"
    exp = {"experiment_id": f"exp-{proposal_id}", "proposal": prop,
           "started_at": time.time(), "status": "running"}
    _experiments.append(exp)
    logger.info("Experiment started: %s", proposal_id)
    return {"experiment": exp, "status": "started"}

@app.get("/v1/proposals")
def list_proposals(status: str = None, claims: dict = Depends(_auth_dep)):
    props = _proposals
    if status: props = [p for p in props if p.get("status") == status]
    return {"proposals": props, "total": len(props)}

@app.get("/v1/experiments")
def list_experiments(claims: dict = Depends(_auth_dep)):
    return {"experiments": _experiments, "total": len(_experiments)}
