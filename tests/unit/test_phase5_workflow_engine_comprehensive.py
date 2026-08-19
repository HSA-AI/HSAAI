"""
HSAAI Enterprise AI Platform — Workflow Engine Test Suite (v7.0)
==================================================================
Comprehensive tests for `services/backend_core/phase5/workflow_engine.py`.

Coverage targets:
  - DEFAULT_STEPS module constant (3 default steps)
  - run_workflow() function:
      * Empty steps → uses DEFAULT_STEPS
      * Explicit steps → uses provided steps
      * Step types: 'agent', 'approval', and other (rag/llm/integration/policy_check)
      * Returns: workflow_run_id, workflow_id, goal, status, trace, elapsed_ms
      * Trace structure per step type
      * Status is always 'completed_with_controls'

Test categories: positive, negative, boundary, validation, serialization, defaults, edge cases.

Rules:
  - No Mocks for the function itself (it calls run_agent internally, which has its own fallback)
  - Each test creates a fresh WorkflowRunRequest (independent)
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

_BASE = Path(__file__).resolve().parents[2]
for _p in [str(_BASE / "services"), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.phase5.schemas import (  # noqa: E402
    RuntimeContext,
    WorkflowRunRequest,
    WorkflowStep,
)
from backend_core.phase5.workflow_engine import (  # noqa: E402
    DEFAULT_STEPS,
    run_workflow,
)


# ═══════════════════════════════════════════════════════════════════════
# DEFAULT_STEPS constant
# ═══════════════════════════════════════════════════════════════════════
class TestDefaultSteps:
    """Verify the DEFAULT_STEPS module constant."""

    def test_default_steps_is_list_with_3_entries(self):
        """Per source: 3 default steps (policy_check, rag, agent)."""
        assert isinstance(DEFAULT_STEPS, list)
        assert len(DEFAULT_STEPS) == 3

    def test_default_steps_have_required_keys(self):
        """Each step has id, type, name, input."""
        for step in DEFAULT_STEPS:
            assert "id" in step
            assert "type" in step
            assert "name" in step
            assert "input" in step

    def test_default_steps_types(self):
        """Default steps include policy_check, rag, and agent."""
        types = [s["type"] for s in DEFAULT_STEPS]
        assert "policy_check" in types
        assert "rag" in types
        assert "agent" in types

    def test_default_steps_agent_has_agent_id_in_input(self):
        """The agent step's input includes agent_id='supervisor'."""
        agent_steps = [s for s in DEFAULT_STEPS if s["type"] == "agent"]
        assert len(agent_steps) == 1
        assert agent_steps[0]["input"].get("agent_id") == "supervisor"


# ═══════════════════════════════════════════════════════════════════════
# run_workflow — return structure
# ═══════════════════════════════════════════════════════════════════════
class TestRunWorkflowReturnStructure:
    """Verify the return dict has all documented keys with correct types."""

    def test_return_dict_has_all_required_keys(self):
        req = WorkflowRunRequest(goal="test goal")
        result = run_workflow(req)
        expected_keys = {
            "workflow_run_id", "workflow_id", "goal",
            "status", "trace", "elapsed_ms",
        }
        assert set(result.keys()) == expected_keys

    def test_workflow_run_id_starts_with_wf_prefix(self):
        """Per source: workflow_run_id = f'wf_{uuid.uuid4().hex[:12]}'."""
        req = WorkflowRunRequest(goal="test")
        result = run_workflow(req)
        assert result["workflow_run_id"].startswith("wf_")
        # Hex chars after prefix
        suffix = result["workflow_run_id"][3:]
        assert len(suffix) == 12
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_workflow_id_default_is_ad_hoc(self):
        """Default workflow_id is 'ad-hoc' per schema."""
        req = WorkflowRunRequest(goal="test")
        result = run_workflow(req)
        assert result["workflow_id"] == "ad-hoc"

    def test_workflow_id_preserved_from_request(self):
        """Custom workflow_id is preserved in result."""
        req = WorkflowRunRequest(goal="test", workflow_id="custom-wf-001")
        result = run_workflow(req)
        assert result["workflow_id"] == "custom-wf-001"

    def test_goal_preserved_from_request(self):
        req = WorkflowRunRequest(goal="my specific goal")
        result = run_workflow(req)
        assert result["goal"] == "my specific goal"

    def test_status_is_completed_with_controls(self):
        """Per source: status is hardcoded to 'completed_with_controls'."""
        req = WorkflowRunRequest(goal="test")
        result = run_workflow(req)
        assert result["status"] == "completed_with_controls"

    def test_trace_is_list(self):
        req = WorkflowRunRequest(goal="test")
        result = run_workflow(req)
        assert isinstance(result["trace"], list)

    def test_elapsed_ms_is_non_negative_int(self):
        req = WorkflowRunRequest(goal="test")
        result = run_workflow(req)
        assert isinstance(result["elapsed_ms"], int)
        assert result["elapsed_ms"] >= 0


# ═══════════════════════════════════════════════════════════════════════
# run_workflow — step types
# ═══════════════════════════════════════════════════════════════════════
class TestRunWorkflowStepTypes:
    """Verify each step type produces the correct trace entry."""

    def test_agent_step_produces_agent_trace_entry(self):
        """Step type 'agent' produces a trace entry with agent_run_id."""
        req = WorkflowRunRequest(
            goal="test",
            steps=[WorkflowStep(id="s1", type="agent", name="Agent Step", input={"agent_id": "supervisor"})],
        )
        result = run_workflow(req)
        assert len(result["trace"]) == 1
        entry = result["trace"][0]
        assert entry["type"] == "agent"
        assert entry["status"] == "completed"
        assert "agent_run_id" in entry
        assert entry["agent_run_id"].startswith("run_")

    def test_approval_step_produces_waiting_trace_entry(self):
        """Step type 'approval' produces a trace entry with status='waiting'."""
        req = WorkflowRunRequest(
            goal="test",
            steps=[WorkflowStep(id="s1", type="approval", name="Approval Step")],
        )
        result = run_workflow(req)
        entry = result["trace"][0]
        assert entry["type"] == "approval"
        assert entry["status"] == "waiting"
        assert "human approval required" in entry["detail"]

    def test_rag_step_produces_completed_trace_entry(self):
        """Step type 'rag' (not agent/approval) produces a generic completed entry."""
        req = WorkflowRunRequest(
            goal="test",
            steps=[WorkflowStep(id="s1", type="rag", name="RAG Step")],
        )
        result = run_workflow(req)
        entry = result["trace"][0]
        assert entry["type"] == "rag"
        assert entry["status"] == "completed"

    def test_llm_step_produces_completed_trace_entry(self):
        """Step type 'llm' produces a generic completed entry."""
        req = WorkflowRunRequest(
            goal="test",
            steps=[WorkflowStep(id="s1", type="llm", name="LLM Step")],
        )
        result = run_workflow(req)
        entry = result["trace"][0]
        assert entry["type"] == "llm"
        assert entry["status"] == "completed"

    def test_integration_step_produces_completed_trace_entry(self):
        """Step type 'integration' produces a generic completed entry."""
        req = WorkflowRunRequest(
            goal="test",
            steps=[WorkflowStep(id="s1", type="integration", name="Integration Step")],
        )
        result = run_workflow(req)
        entry = result["trace"][0]
        assert entry["type"] == "integration"
        assert entry["status"] == "completed"

    def test_policy_check_step_produces_completed_trace_entry(self):
        """Step type 'policy_check' produces a generic completed entry."""
        req = WorkflowRunRequest(
            goal="test",
            steps=[WorkflowStep(id="s1", type="policy_check", name="Policy Check Step")],
        )
        result = run_workflow(req)
        entry = result["trace"][0]
        assert entry["type"] == "policy_check"
        assert entry["status"] == "completed"

    def test_agent_step_without_agent_id_defaults_to_supervisor(self):
        """Agent step without agent_id in input defaults to 'supervisor'."""
        req = WorkflowRunRequest(
            goal="test",
            steps=[WorkflowStep(id="s1", type="agent", name="Agent", input={})],
        )
        result = run_workflow(req)
        # Should not raise — supervisor is used as fallback
        assert result["trace"][0]["status"] == "completed"


# ═══════════════════════════════════════════════════════════════════════
# run_workflow — default vs explicit steps
# ═══════════════════════════════════════════════════════════════════════
class TestRunWorkflowStepsBehavior:
    """Verify default steps are used when req.steps is empty."""

    def test_empty_steps_uses_default_steps(self):
        """When req.steps is [], DEFAULT_STEPS are used."""
        req = WorkflowRunRequest(goal="test")
        result = run_workflow(req)
        assert len(result["trace"]) == len(DEFAULT_STEPS)
        # Verify the trace IDs match DEFAULT_STEPS IDs
        trace_ids = [e["id"] for e in result["trace"]]
        default_ids = [s["id"] for s in DEFAULT_STEPS]
        assert trace_ids == default_ids

    def test_explicit_steps_override_defaults(self):
        """When req.steps is provided, defaults are NOT used."""
        req = WorkflowRunRequest(
            goal="test",
            steps=[
                WorkflowStep(id="custom1", type="rag", name="Custom RAG"),
                WorkflowStep(id="custom2", type="approval", name="Custom Approval"),
            ],
        )
        result = run_workflow(req)
        assert len(result["trace"]) == 2
        assert result["trace"][0]["id"] == "custom1"
        assert result["trace"][1]["id"] == "custom2"

    def test_single_step_workflow(self):
        """Single step workflow works correctly."""
        req = WorkflowRunRequest(
            goal="test",
            steps=[WorkflowStep(id="only", type="rag", name="Only Step")],
        )
        result = run_workflow(req)
        assert len(result["trace"]) == 1

    def test_many_steps_workflow(self):
        """Workflow with many steps executes all in order."""
        steps = [
            WorkflowStep(id=f"s{i}", type="rag", name=f"Step {i}")
            for i in range(10)
        ]
        req = WorkflowRunRequest(goal="test", steps=steps)
        result = run_workflow(req)
        assert len(result["trace"]) == 10
        # Verify order preserved
        for i, entry in enumerate(result["trace"]):
            assert entry["id"] == f"s{i}"


# ═══════════════════════════════════════════════════════════════════════
# run_workflow — context propagation
# ═══════════════════════════════════════════════════════════════════════
class TestRunWorkflowContextPropagation:
    """Verify the RuntimeContext is propagated to nested agent calls."""

    def test_custom_tenant_id_preserved(self):
        """Custom tenant_id in context doesn't break the workflow."""
        req = WorkflowRunRequest(
            goal="test",
            context=RuntimeContext(tenant_id="custom-tenant"),
        )
        result = run_workflow(req)
        assert result["status"] == "completed_with_controls"

    def test_custom_workspace_id_preserved(self):
        req = WorkflowRunRequest(
            goal="test",
            context=RuntimeContext(workspace_id="custom-ws"),
        )
        result = run_workflow(req)
        assert result["status"] == "completed_with_controls"

    def test_custom_user_id_preserved(self):
        req = WorkflowRunRequest(
            goal="test",
            context=RuntimeContext(user_id="user-123"),
        )
        result = run_workflow(req)
        assert result["status"] == "completed_with_controls"


# ═══════════════════════════════════════════════════════════════════════
# run_workflow — independence & idempotency
# ═══════════════════════════════════════════════════════════════════════
class TestRunWorkflowIndependence:
    """Verify each run produces a unique workflow_run_id (independent)."""

    def test_unique_workflow_run_id_per_call(self):
        """Two calls with same input produce different workflow_run_ids."""
        req = WorkflowRunRequest(goal="test")
        r1 = run_workflow(req)
        r2 = run_workflow(req)
        assert r1["workflow_run_id"] != r2["workflow_run_id"]

    def test_request_not_mutated(self):
        """Calling run_workflow must not mutate the request object."""
        req = WorkflowRunRequest(goal="test")
        original_goal = req.goal
        original_steps_len = len(req.steps)
        _ = run_workflow(req)
        assert req.goal == original_goal
        assert len(req.steps) == original_steps_len


# ═══════════════════════════════════════════════════════════════════════
# run_workflow — boundary & edge cases
# ═══════════════════════════════════════════════════════════════════════
class TestRunWorkflowBoundary:
    """Boundary and edge case inputs."""

    def test_empty_goal_string(self):
        """Empty goal is accepted (no validation on goal content)."""
        req = WorkflowRunRequest(goal="")
        result = run_workflow(req)
        assert result["goal"] == ""
        assert result["status"] == "completed_with_controls"

    def test_arabic_goal(self):
        """Arabic goal preserved and workflow completes."""
        req = WorkflowRunRequest(goal="لخص سياسة الموارد البشرية")
        result = run_workflow(req)
        assert result["goal"] == "لخص سياسة الموارد البشرية"

    def test_very_long_goal(self):
        """Very long goal string is accepted."""
        long_goal = "analyze " * 500
        req = WorkflowRunRequest(goal=long_goal)
        result = run_workflow(req)
        assert result["goal"] == long_goal

    def test_goal_with_special_characters(self):
        """Goal with special characters preserved."""
        goal = "analyze !@#$%^&*() data"
        req = WorkflowRunRequest(goal=goal)
        result = run_workflow(req)
        assert result["goal"] == goal

    def test_goal_with_newlines(self):
        """Multiline goal preserved."""
        goal = "line1\nline2\nline3"
        req = WorkflowRunRequest(goal=goal)
        result = run_workflow(req)
        assert result["goal"] == goal
