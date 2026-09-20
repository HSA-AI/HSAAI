"""HSAAI AI Quality API Endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/v1/ai-quality", tags=["AI Quality"])


class EvalRequest(BaseModel):
    prompt: str
    response: str
    context_documents: list[str] = []
    model: str = "unknown"
    tenant_id: str = "default"
    policy_rules: list[str] = []


class ABOutcomeRequest(BaseModel):
    experiment_id: str
    variant: str
    score: float
    latency_ms: int = 0


@router.post("/evaluate")
async def evaluate(req: EvalRequest):
    """Evaluate an LLM response quality."""
    from backend_core.ai_quality.eval_pipeline import evaluate_response
    result = await evaluate_response(
        prompt=req.prompt,
        response=req.response,
        context_documents=req.context_documents,
        model=req.model,
        tenant_id=req.tenant_id,
        policy_rules=req.policy_rules,
    )
    return {
        "overall_score": result.overall_score,
        "groundedness": result.groundedness,
        "hallucination_risk": result.hallucination_risk,
        "arabic_quality": result.arabic_quality,
        "policy_compliance": result.policy_compliance,
        "accuracy": result.accuracy,
        "issues": result.issues,
        "passed": result.passed,
        "latency_ms": result.latency_ms,
    }


@router.get("/experiments")
async def list_experiments():
    """List active A/B testing experiments."""
    from backend_core.ai_quality.ab_testing import ABTestingService
    ab = ABTestingService()
    experiments = []
    for exp_id, exp in ab._experiments.items():
        results = ab.get_results(exp_id)
        experiments.append({
            "id": exp_id,
            "name": exp.name,
            "description": exp.description,
            "is_active": exp.is_active,
            "variants": [{"name": v.name, "weight": v.weight, "config": v.config} for v in exp.variants],
            "results": results,
        })
    return {"experiments": experiments}


@router.post("/experiments/{experiment_id}/outcome")
async def record_outcome(experiment_id: str, req: ABOutcomeRequest):
    """Record an A/B test outcome."""
    from backend_core.ai_quality.ab_testing import ABTestingService
    ab = ABTestingService()
    ab.record_outcome(
        experiment_id=experiment_id,
        variant=req.variant,
        score=req.score,
        latency_ms=req.latency_ms,
    )
    return {"status": "recorded"}


@router.get("/hallucination/check")
async def check_hallucination(response: str, context: str = ""):
    """Quick hallucination check on a response."""
    from backend_core.ai_quality.eval_pipeline import HallucinationDetector
    detector = HallucinationDetector()
    context_docs = [context] if context else []
    result = await detector.detect(response, context_docs)
    return result
