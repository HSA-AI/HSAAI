"""HSAAI Multi Agents Runtime — v0.3.0

Upgraded to Agent Civilization with:
  - 12 enterprise agents with identity, purpose, skills, authority
  - Chief Intelligence Supervisor for task decomposition + conflict resolution
  - A2A Protocol for agent-to-agent communication
  - Wisdom + Failure Memory integration
  - Constitutional enforcement on every agent action
"""
from fastapi import FastAPI, Depends, HTTPException, Request
import sys as _sys, os as _os, logging, asyncio, time, uuid
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..', 'packages'))
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
    _AUTH_AVAILABLE = True
except ImportError as _e:
    _AUTH_AVAILABLE = False
    _AUTH_LOAD_ERROR = str(_e)
    async def _auth_dep():  # type: ignore
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Authentication module unavailable.")

from pydantic import BaseModel
from multi_agents.agents import SupervisorAgent, AGENTS, MEMORY
from multi_agents.agent_civilization import (
    AGENT_REGISTRY, ChiefIntelligenceSupervisor, AGENT_REGISTRY as CIV_REGISTRY
)
from common.a2a_protocol import a2a_protocol, A2AMessage
from common.wisdom import wisdom_engine, failure_memory
from common.constitution import constitution

logger = logging.getLogger("multi_agents")
app = FastAPI(title="HSAAI Multi Agents — Agent Civilization", version="0.3.0")

# Initialize supervisors
legacy_supervisor = SupervisorAgent()
civilization_supervisor = ChiefIntelligenceSupervisor()


class RunRequest(BaseModel):
    message: str
    context: str = ""
    tenant_id: str = "default"
    workspace_id: str = "default"
    preferred_agent: str | None = None
    use_civilization: bool = True  # v0.3: use Agent Civilization by default


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "multi_agents",
        "version": "0.3.0",
        "agents": list(AGENTS.keys()),
        "civilization_agents": list(CIV_REGISTRY.keys()),
        "a2a_stats": a2a_protocol.stats(),
        "wisdom_count": len(wisdom_engine.list_wisdom()),
        "failure_count": len(failure_memory.list_failures(limit=1000)),
    }


from common.security.request_policy import verified_scope, authorization_context
from common.auth.service_auth import require_permission

@app.post("/v1/run")
async def run(req: RunRequest, request: Request, claims: dict = Depends(require_permission("agents:execute"))):
    try:
        req.tenant_id, req.workspace_id = verified_scope(claims)
    except ValueError as exc:
        raise HTTPException(403, str(exc)) from exc
    token = authorization_context.set(request.headers.get("authorization"))
    try:
        return await _run_scoped(req, claims)
    finally:
        authorization_context.reset(token)

async def _run_scoped(req: RunRequest, claims: dict):
    """Run an agent with full civilization support.

    v0.3 upgrades:
      - Agent Civilization: 12 agents + Supervisor decomposition
      - A2A Protocol: agents can communicate during execution
      - Constitutional check: every action verified against AI Constitution
      - Wisdom lookup: check applicable wisdom before deciding
      - Failure Memory: check past failures before deciding
    """
    # 1. Constitutional pre-check
    action = {
        "type": "agent_run",
        "sensitivity": "internal",
        "decision_type": "operational",
        "requires_explanation": True,
        "reasoning_trace": req.message[:200],
    }
    verdict = await constitution.check(action, claims, {"tenant_id": req.tenant_id})
    if not verdict.compliant:
        raise HTTPException(403, f"Constitutional violation: {verdict.violations}")

    # 2. Check Failure Memory FIRST — "Have we failed at something similar?"
    past_failures = failure_memory.find_similar_failures(req.message, limit=3, tenant_id=req.tenant_id)
    failure_warning = None
    if past_failures:
        failure_warning = {
            "warning": f"Found {len(past_failures)} similar past failures",
            "lessons": [f.lesson_learned for f in past_failures if f.lesson_learned],
            "avoidance": [f.avoidance_strategy for f in past_failures if f.avoidance_strategy],
        }
        logger.info("Failure Memory: found %d similar past failures for: %s",
                    len(past_failures), req.message[:80])

    # 3. Check Wisdom Crystals — "What wisdom applies here?"
    applicable_wisdom = wisdom_engine.find_applicable_wisdom({
        "tenant_id": req.tenant_id,
        "message": req.message,
        "preferred_agent": req.preferred_agent,
    })
    wisdom_guidance = None
    if applicable_wisdom:
        wisdom_guidance = [w.statement for w in applicable_wisdom[:3]]
        logger.info("Wisdom: found %d applicable crystals", len(applicable_wisdom))

    # 4. Execute — use Civilization if requested
    if req.use_civilization and req.preferred_agent is None:
        # Agent Civilization mode: Supervisor decomposes + multi-agent fan-out
        subtasks = await civilization_supervisor.decompose(req.message)
        selected = await civilization_supervisor.select_agents(subtasks)

        # Execute subtasks in parallel
        results = []
        for item in selected:
            agent_id = item["agent"]
            subtask = item["subtask"]
            agent_identity = item["agent_identity"]

            # A2A: send task request to agent
            a2a_msg = A2AMessage(
                from_agent="supervisor",
                to_agent=agent_id,
                message_type="task_request",
                content={"task": subtask, "context": req.context,
                         "tenant_id": req.tenant_id, "wisdom": wisdom_guidance},
                priority="normal",
            )

            # Execute via legacy agent if available, else simulate
            if agent_id.replace("_agent", "") in AGENTS:
                agent = AGENTS[agent_id.replace("_agent", "")]
                try:
                    result = await agent.run(
                        subtask, req.context, memory=MEMORY.recent(req.tenant_id, req.workspace_id),
                        tenant_id=req.tenant_id, workspace_id=req.workspace_id,
                    )
                    result["agent"] = agent_id
                    results.append(result)
                except Exception as e:
                    logger.error("Agent %s failed: %s", agent_id, e)
                    results.append({"agent": agent_id, "error": str(e), "status": "failed"})
            else:
                results.append({
                    "agent": agent_id,
                    "purpose": agent_identity.purpose,
                    "subtask": subtask,
                    "status": "unavailable",
                    "note": f"Agent '{agent_id}' registered but not yet wired to legacy runtime",
                })

        # Resolve conflicts
        resolved = await civilization_supervisor.resolve_conflicts(results)

        # Synthesize
        synthesis = await civilization_supervisor.synthesize(resolved)

        # Record decision for wisdom crystallization
        for w in applicable_wisdom:
            wisdom_engine.record_application(w.wisdom_id)

        return {
            "mode": "agent_civilization",
            "route": {"decomposed": len(subtasks), "agents_selected": len(selected)},
            "result": synthesis,
            "wisdom_applied": wisdom_guidance,
            "failure_warning": failure_warning,
            "agents_executed": [r.get("agent") for r in results if r.get("status") not in {"failed", "unavailable"}],
            "requires_human_review": True,
            "tenant_id": req.tenant_id,
            "workspace_id": req.workspace_id,
            "constitutional_verdict": verdict.to_dict(),
        }

    else:
        # Legacy mode (single agent, v0.1 compatible)
        if req.preferred_agent and req.preferred_agent in AGENTS:
            agent_key = req.preferred_agent
            decision = legacy_supervisor.route(req.message)
            decision.agent = agent_key
        else:
            decision = legacy_supervisor.route(req.message)
            agent_key = decision.agent

        recent = MEMORY.recent(req.tenant_id, req.workspace_id)
        agent = AGENTS[agent_key]

        if hasattr(legacy_supervisor, "run_with_self_correction"):
            try:
                result = await legacy_supervisor.run_with_self_correction(
                    agent=agent, message=req.message, context=req.context,
                    memory=recent, tenant_id=req.tenant_id, workspace_id=req.workspace_id,
                )
                result["route"] = decision.__dict__
                result["reflection_activated"] = True
            except Exception as e:
                logger.error("Self-correction failed: %s", e)
                result = await agent.run(req.message, req.context, memory=recent,
                                         tenant_id=req.tenant_id, workspace_id=req.workspace_id)
                result["route"] = decision.__dict__
                result["reflection_activated"] = False
        else:
            result = await agent.run(req.message, req.context, memory=recent,
                                     tenant_id=req.tenant_id, workspace_id=req.workspace_id)
            result["route"] = decision.__dict__
            result["reflection_activated"] = False

        MEMORY.remember(req.tenant_id, req.workspace_id, result.get("agent", agent_key), req.message)

        return {
            "mode": "legacy",
            "route": decision.__dict__,
            "result": result,
            "wisdom_applied": wisdom_guidance,
            "failure_warning": failure_warning,
            "tenant_id": req.tenant_id,
            "workspace_id": req.workspace_id,
        }


@app.get("/v1/civilization/agents")
def list_civilization_agents(claims: dict = Depends(_auth_dep)):
    """List all agents in the Agent Civilization."""
    return {
        "agents": [asdict(a) if hasattr(a, '__dict__') else a.__dict__
                   for a in CIV_REGISTRY.values()],
        "total": len(CIV_REGISTRY),
        "a2a_stats": a2a_protocol.stats(),
    }


@app.get("/v1/a2a/messages")
def a2a_messages(agent_id: str = None, limit: int = 50, claims: dict = Depends(_auth_dep)):
    """Get A2A message log for debugging/audit."""
    return {"messages": [m for m in a2a_protocol.get_message_log(agent_id, limit) if m.get("content", {}).get("tenant_id") == claims.get("tenant_id")]}


@app.post("/v1/failure/record")
def record_failure(
    what_happened: str, what_was_expected: str, root_cause: str,
    cost_estimate: float = 0.0, lesson_learned: str = "",
    avoidance_strategy: str = "", domain: str = "general",
    claims: dict = Depends(_auth_dep),
):
    """Record a failure in Failure Memory (permanent, never deleted)."""
    record = failure_memory.record_failure(
        what_happened=what_happened, what_was_expected=what_was_expected,
        root_cause=root_cause, cost_estimate=cost_estimate,
        lesson_learned=lesson_learned, avoidance_strategy=avoidance_strategy,
        domain=domain, actor=claims.get("sub", "unknown"), tenant_id=claims.get("tenant_id", ""),
    )
    return {"failure_id": record.failure_id, "recorded": True}


@app.get("/v1/wisdom/list")
def list_wisdom(domain: str = None, claims: dict = Depends(_auth_dep)):
    """List all Wisdom Crystals."""
    crystals = [c for c in wisdom_engine.list_wisdom(domain) if c.tenant_id == claims.get("tenant_id")]
    return {"wisdom": [c.to_dict() for c in crystals], "total": len(crystals)}


from dataclasses import asdict
