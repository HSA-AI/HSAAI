
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

# Unit HTTP peers; production acceptance requires separately running services.
import httpx
import pytest
from backend_core.phase5 import observability

@pytest.fixture(autouse=True)
def isolated_unit_peers(monkeypatch, tmp_path):
    real_client = httpx.AsyncClient
    def peer(request):
        assert request.method == 'POST'
        if request.url.path == '/v1/generate':
            return httpx.Response(200, json={'text': 'Unit transport inference result'})
        assert request.url.path == '/v1/search'
        return httpx.Response(200, json={'results': [{'title':'Leave policy','text':'Approved leave policy','score':0.9}]})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(peer), **kw))
    monkeypatch.setattr(observability, 'STORE', tmp_path/'events.jsonl')
