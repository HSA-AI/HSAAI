
from backend_core.phase5.model_router import route_model
from backend_core.phase5.schemas import ModelRouteRequest, AgentRunRequest, WorkflowRunRequest, EnterpriseSearchRequest
from backend_core.phase5.agent_runtime import run_agent
from backend_core.phase5.workflow_engine import run_workflow
from backend_core.phase5.enterprise_search import unified_search


def test_model_router_local_only():
    res = route_model(ModelRouteRequest(task="تحليل ملف Excel مالي", sensitivity="high"))
    assert res["local_only"] is True
    assert res["provider"] == "ollama"


def test_agent_runtime_executes():
    res = run_agent(AgentRunRequest(agent_id="finance", task="حلل تقرير المبيعات"))
    assert res["status"] == "completed"
    assert "execution_trace" in res


def test_workflow_engine_executes():
    res = run_workflow(WorkflowRunRequest(goal="لخص سياسة الموارد البشرية"))
    assert res["status"] == "completed_with_controls"


def test_enterprise_search_returns_sources():
    res = unified_search(EnterpriseSearchRequest(query="سياسة الإجازات"))
    assert res["count"] > 0
