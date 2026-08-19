from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend_core.config import settings
from backend_core.db.models import LLMUsageLog, AICostRecord


def estimate_tokens(text: str) -> int:
    # deterministic fallback without provider tokenizer; enterprise deployments may replace this adapter.
    return max(1, int(len(text or "") / 4))


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return round((input_tokens / 1000.0 * settings.llm_input_cost_per_1k) + (output_tokens / 1000.0 * settings.llm_output_cost_per_1k), 8)


def log_llm_usage(db: Session, *, user_id: str, department: str, input_text: str, output_text: str, operation_type: str, agent: str, workspace_id: str, tenant_id: str, project: str = "default", request_id: str = "") -> LLMUsageLog:
    input_tokens = estimate_tokens(input_text)
    output_tokens = estimate_tokens(output_text)
    cost = estimate_cost(input_tokens, output_tokens)
    row = LLMUsageLog(user_id=user_id, department=department or "general", provider=settings.llm_provider, model=settings.llm_model, input_tokens=input_tokens, output_tokens=output_tokens, estimated_cost=cost, operation_type=operation_type, agent=agent, workspace_id=workspace_id, tenant_id=tenant_id, project=project, request_id=request_id)
    db.add(row)
    db.flush()
    period_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cost_record = AICostRecord(period="daily", period_key=period_key, user_id=user_id, department=department or "general", model=settings.llm_model, agent=agent, total_input_tokens=input_tokens, total_output_tokens=output_tokens, total_cost=cost, budget=settings.monthly_ai_budget, alert_triggered=(settings.monthly_ai_budget > 0 and cost >= settings.monthly_ai_budget * settings.cost_alert_threshold), tenant_id=tenant_id, workspace_id=workspace_id)
    db.add(cost_record)
    db.commit()
    return row


def summary(db: Session, tenant_id: str = "default", workspace_id: str | None = None) -> dict:
    q = db.query(LLMUsageLog).filter(LLMUsageLog.tenant_id == tenant_id)
    if workspace_id:
        q = q.filter(LLMUsageLog.workspace_id == workspace_id)
    total_cost = q.with_entities(func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0.0)).scalar() or 0.0
    total_requests = q.count()
    by_model = db.query(LLMUsageLog.model, func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0.0), func.count(LLMUsageLog.id)).filter(LLMUsageLog.tenant_id == tenant_id).group_by(LLMUsageLog.model).all()
    by_user = db.query(LLMUsageLog.user_id, func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0.0), func.count(LLMUsageLog.id)).filter(LLMUsageLog.tenant_id == tenant_id).group_by(LLMUsageLog.user_id).order_by(func.sum(LLMUsageLog.estimated_cost).desc()).limit(20).all()
    by_department = db.query(LLMUsageLog.department, func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0.0), func.count(LLMUsageLog.id)).filter(LLMUsageLog.tenant_id == tenant_id).group_by(LLMUsageLog.department).all()
    by_agent = db.query(LLMUsageLog.agent, func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0.0), func.count(LLMUsageLog.id)).filter(LLMUsageLog.tenant_id == tenant_id).group_by(LLMUsageLog.agent).order_by(func.sum(LLMUsageLog.estimated_cost).desc()).limit(20).all()
    return {
        "total_requests": total_requests,
        "total_cost": round(float(total_cost), 8),
        "monthly_budget": settings.monthly_ai_budget,
        "alert_threshold": settings.cost_alert_threshold,
        "budget_alert": bool(settings.monthly_ai_budget and total_cost >= settings.monthly_ai_budget * settings.cost_alert_threshold),
        "by_model": [{"model": m, "cost": float(c), "requests": n} for m, c, n in by_model],
        "by_user": [{"user": u, "cost": float(c), "requests": n} for u, c, n in by_user],
        "by_department": [{"department": d, "cost": float(c), "requests": n} for d, c, n in by_department],
        "top_agents": [{"agent": a, "cost": float(c), "requests": n} for a, c, n in by_agent],
    }
