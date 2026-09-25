import pytest

@pytest.mark.asyncio
async def test_reasoning_all_strategies_with_mocked_llm(monkeypatch):
    from common.ai.reasoning_engine import ReasoningEngine, ReasoningStrategy

    engine = ReasoningEngine("http://unit-llm")

    assert engine._select_strategy("search policy", "") == ReasoningStrategy.REACT
    assert engine._select_strategy("analyze this", "") == ReasoningStrategy.TOT
    assert engine._select_strategy("write report", "") == ReasoningStrategy.REFLEXION
    assert engine._select_strategy("what is this", "") == ReasoningStrategy.SELF_CONSISTENCY
    assert engine._select_strategy("hello", "") == ReasoningStrategy.COT

    calls = {"n": 0}
    async def fake_llm(prompt, tenant_id, max_tokens=512, temperature=0.7):
        calls["n"] += 1
        if "Generate 3 approaches" in prompt:
            return "Approach A\nApproach B\nApproach C", 3
        if "Rate each" in prompt:
            return "10\n8\n6", 2
        if "Final answer" in prompt or "provide a final answer" in prompt:
            return "Final answer", 2
        if "Critique:" in prompt:
            return "Needs stronger evidence", 2
        if "Revise:" in prompt:
            return "Revised answer", 2
        if "Think, then act" in prompt:
            return "Thought: enough\nAction: finish[Completed]", 2
        return "step one\nstep two", 2

    monkeypatch.setattr(engine, "_llm_call", fake_llm)

    cot = await engine.reason("hello", strategy=ReasoningStrategy.COT)
    assert cot.final_answer == "Final answer"
    assert len(cot.steps) == 2

    sc = await engine.reason("what is x", strategy=ReasoningStrategy.SELF_CONSISTENCY)
    assert sc.strategy == "self_consistency"
    assert len(sc.steps) == 5

    tot = await engine.reason("analyze", strategy=ReasoningStrategy.TOT, max_steps=2)
    assert tot.strategy == "tree_of_thoughts"
    assert len(tot.steps) == 2

    react = await engine.reason("search", strategy=ReasoningStrategy.REACT, max_steps=2)
    assert react.final_answer == "Completed"
    assert react.steps[-1].action == "finish"

    reflex = await engine.reason("write", strategy=ReasoningStrategy.REFLEXION)
    assert reflex.strategy == "reflexion"
    assert reflex.final_answer == "Revised answer"
    assert len(reflex.steps) == 3
    assert calls["n"] > 10

    await engine.close()


class _Resp:
    def __init__(self, data=None, status_code=200, exc=None):
        self._data = data or {}
        self.status_code = status_code
        self._exc = exc
    def raise_for_status(self):
        if self._exc:
            raise self._exc
    def json(self):
        return self._data


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.closed = False
    async def post(self, *args, **kwargs):
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_reasoning_llm_and_search_success_and_errors():
    from common.ai.reasoning_engine import ReasoningEngine

    engine = ReasoningEngine("http://unit-llm")
    engine.client = _Client([
        _Resp({"text": "ok", "tokens_used": 7}),
        RuntimeError("network down"),
        _Resp({"results": [{"content": "alpha"}, {"content": "beta"}]}, 200),
        RuntimeError("rag down"),
    ])

    text, tokens = await engine._llm_call("p", "t")
    assert (text, tokens) == ("ok", 7)

    text, tokens = await engine._llm_call("p", "t")
    assert text.startswith("[LLM Error:")
    assert tokens == 0

    found = await engine._execute_search("q", "t")
    assert "alpha" in found and "beta" in found

    missing = await engine._execute_search("q", "t")
    assert missing == "[No results]"

    await engine.close()
    assert engine.client.closed is True
