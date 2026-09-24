import importlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


def _agents():
    return importlib.import_module("multi_agents.agents")


def _main():
    return importlib.import_module("multi_agents.main")


def test_supervisor_routing_planning_and_reflection():
    m = _agents()
    s = m.SupervisorAgent(confidence_threshold=0.7, reflection_quality_threshold=0.6)

    empty = s.route_with_confidence("")
    assert empty.agent == "general"
    assert empty.needs_clarification is True
    assert empty.confidence == 0.0

    general = s.route_with_confidence("hello how are you")
    assert general.agent == "general"
    assert general.needs_clarification is True

    finance = s.route_with_confidence("compare finance budget and HR payroll")
    assert finance.agent in {"finance", "hr"}
    assert finance.secondary_agent is not None
    assert finance.plan
    assert any("Compare" in step for step in finance.plan)

    weak = s.reflect("q", "", "context")
    assert weak["regenerate"] is True
    assert weak["reason"] == "empty_response"

    good = s.reflect(
        "leave",
        "The internal leave policy confirms annual leave entitlement [1].",
        "The internal leave policy confirms annual leave entitlement.",
    )
    assert good["grounded"] is True
    assert good["complete"] is True


@pytest.mark.asyncio
async def test_self_correction_regenerates_then_accepts(monkeypatch):
    m = _agents()
    s = m.SupervisorAgent(max_regenerations=1, reflection_quality_threshold=0.6)

    class Agent:
        name = "mock"
        calls = []
        async def run(self, message, **kwargs):
            self.calls.append(message)
            if len(self.calls) == 1:
                return {"answer": "too short"}
            return {"answer": "Internal context confirms the policy clearly and completely [1]."}

    reflections = iter([
        {"quality": 0.1, "grounded": False, "relevant": False, "complete": False, "regenerate": True},
        {"quality": 0.9, "grounded": True, "relevant": True, "complete": True, "regenerate": False},
    ])
    monkeypatch.setattr(s, "reflect", lambda *args, **kwargs: next(reflections))

    agent = Agent()
    result = await s.run_with_self_correction(agent, "policy", context="internal context")
    assert result["attempt"] == 1
    assert len(agent.calls) == 2
    assert "Self-correction hint" in agent.calls[1]


@pytest.mark.asyncio
async def test_base_agent_rag_fallback_without_real_http(monkeypatch):
    m = _agents()
    agent = m.BaseAgent()

    async def rag(query, tenant_id, workspace_id):
        return "[1] enterprise policy", 1

    async def no_llm(prompt):
        return ""

    monkeypatch.setattr(agent, "_get_rag_context", rag)
    monkeypatch.setattr(agent, "_call_llm", no_llm)

    # BaseAgent imports dispatch_tool dynamically; replace it so unit tests never
    # reach RAG/HTTP/tool services.
    import common.tool_registry as tool_registry
    async def fake_dispatch(tool_name, args, context):
        return {"success": False, "tool": tool_name}
    monkeypatch.setattr(tool_registry, "dispatch_tool", fake_dispatch)

    result = await agent.run("policy", memory=[{"x": 1}], tenant_id="t", workspace_id="w")
    assert result["context_used"] is True
    assert result["rag_results_count"] == 1
    assert "available internal sources" in result["answer"]
    assert result["memory_turns_used"] == 1


@pytest.mark.asyncio
async def test_run_scoped_constitutional_fail_closed(monkeypatch):
    m = _main()
    req = m.RunRequest(message="delete confidential data", use_civilization=False)

    class Constitution:
        async def check(self, *args, **kwargs):
            return SimpleNamespace(compliant=False, violations=["policy"], to_dict=lambda: {"compliant": False})

    monkeypatch.setattr(m, "constitution", Constitution())
    with pytest.raises(HTTPException) as exc:
        await m._run_scoped(req, {"tenant_id": "t1"})
    assert exc.value.status_code == 403
    assert "Constitutional" in exc.value.detail


@pytest.mark.asyncio
async def test_run_scoped_legacy_happy_path_with_wisdom_and_failure(monkeypatch):
    m = _main()
    req = m.RunRequest(
        message="finance budget",
        context="ctx",
        tenant_id="t1",
        workspace_id="w1",
        preferred_agent="finance",
        use_civilization=False,
    )

    class Verdict:
        compliant = True
        violations = []
        def to_dict(self):
            return {"compliant": True}

    class Constitution:
        async def check(self, *args, **kwargs):
            return Verdict()

    failure = SimpleNamespace(lesson_learned="validate inputs", avoidance_strategy="use checks")
    wisdom = SimpleNamespace(statement="Prefer audited data", wisdom_id="wis-1")
    monkeypatch.setattr(m, "constitution", Constitution())
    monkeypatch.setattr(
        m, "failure_memory",
        SimpleNamespace(find_similar_failures=lambda *a, **k: [failure]),
    )
    monkeypatch.setattr(
        m, "wisdom_engine",
        SimpleNamespace(
            find_applicable_wisdom=lambda *a, **k: [wisdom],
            record_application=lambda *a, **k: None,
        ),
    )

    decision = SimpleNamespace(
        agent="finance", reason="test", confidence=1.0,
        needs_clarification=False, clarification_question="",
        secondary_agent=None, plan=[],
    )
    monkeypatch.setattr(m.legacy_supervisor, "route", lambda message: decision)

    async def run_with_self_correction(**kwargs):
        return {"agent": "Finance Agent", "answer": "ok"}
    monkeypatch.setattr(m.legacy_supervisor, "run_with_self_correction", run_with_self_correction)

    remembered = []
    monkeypatch.setattr(m.MEMORY, "recent", lambda *a, **k: [])
    monkeypatch.setattr(m.MEMORY, "remember", lambda *a, **k: remembered.append(a))

    result = await m._run_scoped(req, {"tenant_id": "t1"})
    assert result["mode"] == "legacy"
    assert result["wisdom_applied"] == ["Prefer audited data"]
    assert result["failure_warning"]["lessons"] == ["validate inputs"]
    assert result["result"]["reflection_activated"] is True
    assert remembered
