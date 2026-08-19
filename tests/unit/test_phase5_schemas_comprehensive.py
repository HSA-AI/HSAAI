"""
HSAAI Enterprise AI Platform — Phase 5 Schemas Test Suite (v7.0)
=================================================================
Comprehensive Pytest suite for `services/backend_core/phase5/schemas.py`.

Coverage targets:
  - RuntimeContext (4 fields with defaults)
  - AgentRunRequest (with Field defaults + default_factory)
  - WorkflowStep (Literal type field)
  - WorkflowRunRequest (nested model + default_factory)
  - ModelRouteRequest (Literal sensitivity, Optional max_latency_ms)
  - EnterpriseSearchRequest (lambda default_factory for sources)
  - ObservabilityEvent (Optional fields, defaults, metadata dict)

Test categories per requirements:
  - Positive tests (valid inputs)
  - Negative tests (invalid inputs → ValidationError)
  - Boundary tests (empty strings, single-element lists, large inputs)
  - Validation tests (Literal enforcement, required fields)
  - Serialization tests (model_dump round-trip)
  - Default values tests (every default is verified)
  - Edge cases (None where allowed, unicode/Arabic, nested context)

Rules followed:
  - No Mocks (pure model tests)
  - Independent (no shared state, no execution order dependency)
  - Pydantic v2 best practices
  - 100% compatible with existing code (no field/behavior assumptions)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# ─── Path setup (mirrors tests/conftest.py) ────────────────────────────
_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.phase5.schemas import (  # noqa: E402
    AgentRunRequest,
    EnterpriseSearchRequest,
    ModelRouteRequest,
    ObservabilityEvent,
    RuntimeContext,
    WorkflowRunRequest,
    WorkflowStep,
)


# ═══════════════════════════════════════════════════════════════════════
# RuntimeContext
# ═══════════════════════════════════════════════════════════════════════
class TestRuntimeContext:
    """Tests for the RuntimeContext model — 4 string fields with defaults."""

    def test_default_values_all_strings(self):
        """Verify every field has its documented default."""
        ctx = RuntimeContext()
        assert ctx.tenant_id == "default"
        assert ctx.workspace_id == "default"
        assert ctx.user_id == "system"
        assert ctx.department == "general"

    def test_positive_explicit_values(self):
        """All four fields accept arbitrary non-empty strings."""
        ctx = RuntimeContext(
            tenant_id="hsa-ye",
            workspace_id="finance-bu",
            user_id="user-123",
            department="finance",
        )
        assert ctx.tenant_id == "hsa-ye"
        assert ctx.workspace_id == "finance-bu"
        assert ctx.user_id == "user-123"
        assert ctx.department == "finance"

    def test_positive_arabic_values(self):
        """Arabic strings are first-class (no normalization in the model)."""
        ctx = RuntimeContext(
            tenant_id="مجموعة-هائل",
            workspace_id="المالية",
            user_id="مستخدم-1",
            department="إدارة المالية",
        )
        assert ctx.department == "إدارة المالية"

    def test_boundary_empty_strings_allowed(self):
        """Pydantic v2 `str` accepts empty strings — verify behavior."""
        ctx = RuntimeContext(tenant_id="", workspace_id="", user_id="", department="")
        assert ctx.tenant_id == ""
        assert ctx.workspace_id == ""

    def test_serialization_roundtrip(self):
        """model_dump → RuntimeContext(**dump) must reproduce identical object."""
        original = RuntimeContext(tenant_id="t1", department="d1")
        dumped = original.model_dump()
        assert dumped == {
            "tenant_id": "t1",
            "workspace_id": "default",
            "user_id": "system",
            "department": "d1",
        }
        rebuilt = RuntimeContext(**dumped)
        assert rebuilt == original

    def test_extra_fields_ignored_by_default(self):
        """Pydantic v2 default `extra='ignore'` — extra fields are silently dropped.

        Conflict note: This contradicts the strict-validation expectation, but matches
        the actual schema (no `model_config = ConfigDict(extra='forbid')` is set).
        We test the real behavior, not an aspirational one.
        """
        ctx = RuntimeContext(unknown_field="value")  # type: ignore[call-arg]
        assert not hasattr(ctx, "unknown_field"), "Pydantic v2 default ignores extra fields"

    def test_wrong_type_rejected(self):
        """Dict tenant_id (non-coercible) must raise ValidationError.

        Note: int is coercible to str in Pydantic v2 lax mode, so we use a dict
        which is truly non-coercible.
        """
        with pytest.raises(ValidationError):
            RuntimeContext(tenant_id={"nested": "dict"})  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════
# AgentRunRequest
# ═══════════════════════════════════════════════════════════════════════
class TestAgentRunRequest:
    """Tests for AgentRunRequest — task is required, others have defaults."""

    def test_default_values(self):
        """Verify Field defaults: agent_id='supervisor', require_sources=True."""
        req = AgentRunRequest(task="test task")
        assert req.agent_id == "supervisor"
        assert req.task == "test task"
        assert req.tools == []
        assert req.require_sources is True
        # Nested RuntimeContext default
        assert isinstance(req.context, RuntimeContext)
        assert req.context.tenant_id == "default"

    def test_positive_full_payload(self):
        """Full explicit payload round-trips correctly."""
        ctx = RuntimeContext(tenant_id="t1", department="hr")
        req = AgentRunRequest(
            agent_id="finance",
            task="تحليل التكاليف",
            context=ctx,
            tools=["rag", "sap"],
            require_sources=False,
        )
        assert req.agent_id == "finance"
        assert req.tools == ["rag", "sap"]
        assert req.require_sources is False
        assert req.context.tenant_id == "t1"

    def test_negative_missing_task_raises(self):
        """`task` is required — ValidationError when missing."""
        with pytest.raises(ValidationError) as exc_info:
            AgentRunRequest()
        assert "task" in str(exc_info.value)

    def test_default_factory_tools_independent_per_instance(self):
        """default_factory=list must create a new list per instance (no shared state)."""
        a = AgentRunRequest(task="a")
        b = AgentRunRequest(task="b")
        a.tools.append("shared_tool")
        assert b.tools == [], "default_factory must isolate per-instance state"

    def test_default_factory_context_independent_per_instance(self):
        """default_factory=RuntimeContext must isolate nested context per instance."""
        a = AgentRunRequest(task="a")
        b = AgentRunRequest(task="b")
        a.context.tenant_id = "modified"
        assert b.context.tenant_id == "default", "context must not be shared"

    def test_boundary_empty_task_string(self):
        """Empty task string is accepted by Pydantic str type."""
        req = AgentRunRequest(task="")
        assert req.task == ""

    def test_boundary_unicode_task(self):
        """Mixed Arabic/English/symbols task preserved verbatim."""
        task = "حلل Q1 2026 📊 report — see SAP /ref #123"
        req = AgentRunRequest(task=task)
        assert req.task == task

    def test_serialization_includes_nested_context(self):
        """model_dump must recursively serialize nested RuntimeContext."""
        req = AgentRunRequest(task="x", context=RuntimeContext(tenant_id="t9"))
        dumped = req.model_dump()
        assert dumped["context"]["tenant_id"] == "t9"
        # Round-trip
        assert AgentRunRequest(**dumped) == req

    def test_validation_tools_must_be_list_of_strings(self):
        """List of non-strings must raise."""
        with pytest.raises(ValidationError):
            AgentRunRequest(task="x", tools=[1, 2, 3])  # type: ignore[list-item]

    def test_validation_require_sources_string_coerced(self):
        """Pydantic v2 lax mode coerces strings to bool.

        Conflict note: Pydantic v2 coerces "yes"/"true"/"1" to True and "no"/"false"/"0"
        to False in lax mode. We document this real behavior rather than expecting strict
        rejection. Truly non-coercible values (e.g., a list) do raise.
        """
        # Coercible strings are accepted
        req_true = AgentRunRequest(task="x", require_sources="yes")  # type: ignore[arg-type]
        assert req_true.require_sources is True
        req_false = AgentRunRequest(task="x", require_sources="false")  # type: ignore[arg-type]
        assert req_false.require_sources is False
        # Non-coercible value raises
        with pytest.raises(ValidationError):
            AgentRunRequest(task="x", require_sources=["not", "a", "bool"])  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════
# WorkflowStep
# ═══════════════════════════════════════════════════════════════════════
class TestWorkflowStep:
    """Tests for WorkflowStep — Literal type field enforces 6 allowed values."""

    @pytest.mark.parametrize(
        "step_type",
        ["agent", "rag", "llm", "approval", "integration", "policy_check"],
    )
    def test_positive_all_literal_values_accepted(self, step_type: str):
        """All 6 documented Literal values must be accepted."""
        step = WorkflowStep(id="s1", type=step_type, name="Step")
        assert step.type == step_type

    def test_default_type_is_agent(self):
        """Default `type` is 'agent' per schema definition."""
        step = WorkflowStep(id="s1", name="Step")
        assert step.type == "agent"

    def test_default_input_empty_dict(self):
        """Default `input` is an empty dict."""
        step = WorkflowStep(id="s1", name="Step")
        assert step.input == {}

    def test_negative_invalid_type_rejected(self):
        """Literal enforcement: invalid type must raise ValidationError."""
        with pytest.raises(ValidationError):
            WorkflowStep(id="s1", type="invalid_type", name="Step")

    def test_negative_missing_id_raises(self):
        """`id` is required."""
        with pytest.raises(ValidationError):
            WorkflowStep(name="Step")  # type: ignore[call-arg]

    def test_negative_missing_name_raises(self):
        """`name` is required."""
        with pytest.raises(ValidationError):
            WorkflowStep(id="s1")  # type: ignore[call-arg]

    def test_default_factory_input_independent(self):
        """default_factory=dict isolates per-instance state."""
        a = WorkflowStep(id="a", name="A")
        b = WorkflowStep(id="b", name="B")
        a.input["k"] = "v"
        assert b.input == {}

    def test_serialization_roundtrip(self):
        """Full model_dump round-trip reproduces step."""
        step = WorkflowStep(id="s1", type="approval", name="Approve", input={"role": "manager"})
        dumped = step.model_dump()
        assert dumped == {"id": "s1", "type": "approval", "name": "Approve", "input": {"role": "manager"}}
        assert WorkflowStep(**dumped) == step

    def test_boundary_empty_string_id(self):
        """Empty string id is accepted by str type (validation only on type)."""
        step = WorkflowStep(id="", name="Step")
        assert step.id == ""

    def test_input_accepts_arbitrary_nested_dict(self):
        """`input` is dict[str, Any] — nested structures allowed."""
        step = WorkflowStep(
            id="s1",
            name="Step",
            input={"nested": {"deep": [1, 2, {"k": "v"}]}, "bool": True, "null": None},
        )
        assert step.input["nested"]["deep"][2]["k"] == "v"
        assert step.input["null"] is None


# ═══════════════════════════════════════════════════════════════════════
# WorkflowRunRequest
# ═══════════════════════════════════════════════════════════════════════
class TestWorkflowRunRequest:
    """Tests for WorkflowRunRequest — goal required, steps default to []."""

    def test_default_values(self):
        """workflow_id defaults to 'ad-hoc', steps to empty list."""
        req = WorkflowRunRequest(goal="achieve objective")
        assert req.workflow_id == "ad-hoc"
        assert req.goal == "achieve objective"
        assert req.steps == []
        assert isinstance(req.context, RuntimeContext)

    def test_positive_with_explicit_steps(self):
        """Steps list of WorkflowStep objects accepted."""
        req = WorkflowRunRequest(
            goal="g",
            steps=[
                WorkflowStep(id="s1", name="A"),
                WorkflowStep(id="s2", type="approval", name="B"),
            ],
        )
        assert len(req.steps) == 2
        assert req.steps[1].type == "approval"

    def test_positive_steps_via_dict_coercion(self):
        """Pydantic v2 coerces list of dicts into WorkflowStep instances."""
        req = WorkflowRunRequest(
            goal="g",
            steps=[{"id": "s1", "name": "A"}, {"id": "s2", "type": "rag", "name": "B"}],
        )
        assert all(isinstance(s, WorkflowStep) for s in req.steps)
        assert req.steps[1].type == "rag"

    def test_negative_missing_goal_raises(self):
        """`goal` is required."""
        with pytest.raises(ValidationError):
            WorkflowRunRequest()  # type: ignore[call-arg]

    def test_default_factory_steps_independent(self):
        """steps default list must be isolated per instance."""
        a = WorkflowRunRequest(goal="a")
        b = WorkflowRunRequest(goal="b")
        a.steps.append(WorkflowStep(id="x", name="X"))
        assert b.steps == []

    def test_serialization_nested_steps_roundtrip(self):
        """Nested list of WorkflowStep round-trips via model_dump."""
        req = WorkflowRunRequest(
            goal="g",
            workflow_id="wf-1",
            steps=[WorkflowStep(id="s1", name="A")],
        )
        dumped = req.model_dump()
        assert dumped["steps"][0]["id"] == "s1"
        assert WorkflowRunRequest(**dumped) == req

    def test_boundary_empty_goal(self):
        """Empty goal string is accepted."""
        req = WorkflowRunRequest(goal="")
        assert req.goal == ""


# ═══════════════════════════════════════════════════════════════════════
# ModelRouteRequest
# ═══════════════════════════════════════════════════════════════════════
class TestModelRouteRequest:
    """Tests for ModelRouteRequest — Literal sensitivity + Optional max_latency_ms."""

    @pytest.mark.parametrize("sensitivity", ["low", "medium", "high", "restricted"])
    def test_positive_all_sensitivity_values(self, sensitivity: str):
        """All 4 documented Literal sensitivity values accepted."""
        req = ModelRouteRequest(task="t", sensitivity=sensitivity)
        assert req.sensitivity == sensitivity

    def test_default_values(self):
        """sensitivity='medium', language='ar', max_latency_ms=None, require_local_only=True."""
        req = ModelRouteRequest(task="t")
        assert req.sensitivity == "medium"
        assert req.language == "ar"
        assert req.max_latency_ms is None
        assert req.require_local_only is True

    def test_negative_invalid_sensitivity_rejected(self):
        """Literal enforcement: invalid sensitivity must raise."""
        with pytest.raises(ValidationError):
            ModelRouteRequest(task="t", sensitivity="critical")  # type: ignore[arg-type]

    def test_negative_missing_task_raises(self):
        """`task` is required."""
        with pytest.raises(ValidationError):
            ModelRouteRequest()  # type: ignore[call-arg]

    def test_optional_max_latency_ms_accepts_none(self):
        """max_latency_ms is Optional — None is valid."""
        req = ModelRouteRequest(task="t", max_latency_ms=None)
        assert req.max_latency_ms is None

    def test_optional_max_latency_ms_accepts_int(self):
        """max_latency_ms accepts a positive integer."""
        req = ModelRouteRequest(task="t", max_latency_ms=500)
        assert req.max_latency_ms == 500

    def test_boundary_max_latency_ms_zero(self):
        """Zero is a valid integer for max_latency_ms."""
        req = ModelRouteRequest(task="t", max_latency_ms=0)
        assert req.max_latency_ms == 0

    def test_boundary_max_latency_ms_negative(self):
        """Negative integer is accepted by Pydantic (no gt/ge constraint in schema)."""
        req = ModelRouteRequest(task="t", max_latency_ms=-1)
        assert req.max_latency_ms == -1

    def test_negative_max_latency_ms_string_coerced(self):
        """Pydantic v2 lax mode coerces numeric strings to int.

        Conflict note: "500" is coerced to int 500 by Pydantic v2 lax mode.
        We test the real behavior (coercion) and verify truly non-coercible
        values (like a list) raise.
        """
        # Numeric string is coerced
        req = ModelRouteRequest(task="t", max_latency_ms="500")  # type: ignore[arg-type]
        assert req.max_latency_ms == 500
        # Non-coercible value raises
        with pytest.raises(ValidationError):
            ModelRouteRequest(task="t", max_latency_ms=["500"])  # type: ignore[arg-type]

    def test_require_local_only_can_be_disabled(self):
        """require_local_only can be set to False (used by router fallback logic)."""
        req = ModelRouteRequest(task="t", require_local_only=False)
        assert req.require_local_only is False

    def test_serialization_roundtrip(self):
        """Full round-trip including Optional field."""
        req = ModelRouteRequest(task="t", sensitivity="high", max_latency_ms=200)
        dumped = req.model_dump()
        assert dumped["max_latency_ms"] == 200
        assert ModelRouteRequest(**dumped) == req


# ═══════════════════════════════════════════════════════════════════════
# EnterpriseSearchRequest
# ═══════════════════════════════════════════════════════════════════════
class TestEnterpriseSearchRequest:
    """Tests for EnterpriseSearchRequest — lambda default_factory for sources."""

    def test_default_values(self):
        """Defaults: sources=['rag','agents','integrations','audit'], top_k=8, answer=True."""
        req = EnterpriseSearchRequest(query="q")
        assert req.sources == ["rag", "agents", "integrations", "audit"]
        assert req.top_k == 8
        assert req.answer is True
        assert isinstance(req.context, RuntimeContext)

    def test_positive_explicit_sources(self):
        """Custom sources list overrides default."""
        req = EnterpriseSearchRequest(query="q", sources=["rag"])
        assert req.sources == ["rag"]

    def test_default_factory_sources_independent(self):
        """Lambda default_factory must isolate per-instance (no shared list)."""
        a = EnterpriseSearchRequest(query="a")
        b = EnterpriseSearchRequest(query="b")
        a.sources.append("extra")
        assert b.sources == ["rag", "agents", "integrations", "audit"]

    def test_negative_missing_query_raises(self):
        """`query` is required."""
        with pytest.raises(ValidationError):
            EnterpriseSearchRequest()  # type: ignore[call-arg]

    def test_boundary_top_k_zero(self):
        """top_k=0 is accepted by Pydantic int (no ge constraint in schema)."""
        req = EnterpriseSearchRequest(query="q", top_k=0)
        assert req.top_k == 0

    def test_boundary_top_k_large(self):
        """Large top_k accepted."""
        req = EnterpriseSearchRequest(query="q", top_k=10_000)
        assert req.top_k == 10_000

    def test_negative_top_k_string_coerced(self):
        """Pydantic v2 lax mode coerces numeric strings to int.

        Conflict note: "10" is coerced to int 10. Non-coercible values raise.
        """
        req = EnterpriseSearchRequest(query="q", top_k="10")  # type: ignore[arg-type]
        assert req.top_k == 10
        with pytest.raises(ValidationError):
            EnterpriseSearchRequest(query="q", top_k={"a": 1})  # type: ignore[arg-type]

    def test_answer_can_be_disabled(self):
        """answer=False suppresses answer generation (per docstring)."""
        req = EnterpriseSearchRequest(query="q", answer=False)
        assert req.answer is False

    def test_serialization_roundtrip(self):
        """Full round-trip preserves sources list and nested context."""
        req = EnterpriseSearchRequest(query="q", sources=["rag", "audit"], top_k=5)
        dumped = req.model_dump()
        assert dumped["sources"] == ["rag", "audit"]
        assert EnterpriseSearchRequest(**dumped) == req

    def test_arabic_query_preserved(self):
        """Arabic query string preserved verbatim."""
        req = EnterpriseSearchRequest(query="ما هي سياسة الإجازات السنوية؟")
        assert req.query == "ما هي سياسة الإجازات السنوية؟"


# ═══════════════════════════════════════════════════════════════════════
# ObservabilityEvent
# ═══════════════════════════════════════════════════════════════════════
class TestObservabilityEvent:
    """Tests for ObservabilityEvent — many Optional fields + defaults."""

    def test_minimal_required_fields(self):
        """Only event_type and component are required."""
        ev = ObservabilityEvent(event_type="agent_run", component="agent_runtime")
        assert ev.event_type == "agent_run"
        assert ev.component == "agent_runtime"
        # Defaults
        assert ev.tenant_id == "default"
        assert ev.workspace_id == "default"
        assert ev.latency_ms is None
        assert ev.tokens_in == 0
        assert ev.tokens_out == 0
        assert ev.model is None
        assert ev.success is True
        assert ev.risk_level == "low"
        assert ev.metadata == {}

    def test_negative_missing_event_type_raises(self):
        with pytest.raises(ValidationError):
            ObservabilityEvent(component="c")  # type: ignore[call-arg]

    def test_negative_missing_component_raises(self):
        with pytest.raises(ValidationError):
            ObservabilityEvent(event_type="e")  # type: ignore[call-arg]

    def test_positive_full_payload(self):
        """All fields populated explicitly."""
        ev = ObservabilityEvent(
            event_type="llm_call",
            component="llm_gateway",
            tenant_id="t1",
            workspace_id="w1",
            latency_ms=234,
            tokens_in=150,
            tokens_out=80,
            model="qwen2.5:7b-instruct",
            success=True,
            risk_level="high",
            metadata={"run_id": "r1", "user": "u1"},
        )
        assert ev.latency_ms == 234
        assert ev.tokens_in == 150
        assert ev.model == "qwen2.5:7b-instruct"
        assert ev.metadata["run_id"] == "r1"

    def test_optional_latency_ms_none_default(self):
        """latency_ms defaults to None (Optional)."""
        ev = ObservabilityEvent(event_type="e", component="c")
        assert ev.latency_ms is None

    def test_optional_model_none_default(self):
        """model defaults to None (Optional)."""
        ev = ObservabilityEvent(event_type="e", component="c")
        assert ev.model is None

    def test_default_factory_metadata_independent(self):
        """metadata default_factory=dict isolates per-instance."""
        a = ObservabilityEvent(event_type="a", component="c")
        b = ObservabilityEvent(event_type="b", component="c")
        a.metadata["k"] = "v"
        assert b.metadata == {}

    def test_boundary_zero_tokens(self):
        """tokens_in=0 and tokens_out=0 are valid (cost computation uses these)."""
        ev = ObservabilityEvent(event_type="e", component="c", tokens_in=0, tokens_out=0)
        assert ev.tokens_in == 0
        assert ev.tokens_out == 0

    def test_boundary_negative_latency_accepted(self):
        """Pydantic int has no ge constraint — negative latency accepted (mathematically odd but valid)."""
        ev = ObservabilityEvent(event_type="e", component="c", latency_ms=-5)
        assert ev.latency_ms == -5

    def test_success_false_indicates_failure(self):
        """success=False is the canonical failure marker (used by ai_metrics)."""
        ev = ObservabilityEvent(event_type="e", component="c", success=False)
        assert ev.success is False

    def test_serialization_roundtrip(self):
        """Full round-trip including None Optionals and metadata dict."""
        ev = ObservabilityEvent(
            event_type="e",
            component="c",
            metadata={"key": "value", "nested": {"n": 1}},
        )
        dumped = ev.model_dump()
        assert dumped["latency_ms"] is None
        assert dumped["model"] is None
        assert dumped["metadata"]["nested"]["n"] == 1
        assert ObservabilityEvent(**dumped) == ev

    def test_metadata_accepts_arbitrary_json_serializable_values(self):
        """metadata is dict[str, Any] — lists, nested dicts, bools, None all allowed."""
        ev = ObservabilityEvent(
            event_type="e",
            component="c",
            metadata={
                "list": [1, 2, 3],
                "nested": {"deep": {"value": True}},
                "null": None,
                "float": 3.14,
            },
        )
        assert ev.metadata["list"] == [1, 2, 3]
        assert ev.metadata["nested"]["deep"]["value"] is True
        assert ev.metadata["null"] is None
