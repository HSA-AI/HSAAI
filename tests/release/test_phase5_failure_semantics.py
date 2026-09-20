"""Unavailable dependencies cannot report success. HTTP boundary is isolated."""
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend_core.phase5 import agent_runtime as agents, enterprise_search as search, workflow_engine as workflows, observability as obs, router
from backend_core.phase5.schemas import AgentRunRequest,WorkflowRunRequest,EnterpriseSearchRequest,WorkflowStep,ObservabilityEvent
from common.security.request_policy import authorization_context

@pytest.fixture
def peer(monkeypatch,tmp_path):
    mode={'error':None,'requests':[]};real=httpx.AsyncClient
    def handle(req):
        mode['requests'].append(req)
        if mode['error']=='timeout':raise httpx.ReadTimeout('secret-provider-body',request=req)
        if mode['error']=='http':return httpx.Response(503,text='secret-provider-body')
        if mode['error']=='empty':return httpx.Response(200,json={'text':''})
        if req.url.path=='/v1/generate':return httpx.Response(200,json={'text':'Actual peer response'})
        return httpx.Response(200,json={'results':[{'text':'Evidence','title':'Policy','score':0.8}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handle),**kw))
    monkeypatch.setattr(obs,'STORE',tmp_path/'events.jsonl')
    return mode

@pytest.mark.parametrize('failure',['timeout','http','empty'])
def test_model_failure_is_failed_without_fabricated_answer(peer,failure):
    peer['error']=failure;result=agents.run_agent(AgentRunRequest(task='question'))
    assert result['status']=='failed' and result['answer']=='' and result['llm_error']
    assert 'secret-provider-body' not in str(result)
    assert obs.read_events()[-1]['success'] is False

@pytest.mark.parametrize('failure',['timeout','http'])
def test_rag_outage_is_not_a_successful_search(peer,failure):
    peer['error']=failure;result=search.unified_search(EnterpriseSearchRequest(query='question',sources=['rag']))
    assert result['status']=='failed' and not result['real_search_performed'] and result['results']==[]
    assert obs.read_events()[-1]['success'] is False


def test_workflow_stops_at_approval_without_executing_next_step(peer):
    steps=[WorkflowStep(id='approval',type='approval',name='Review'),WorkflowStep(id='ai',type='agent',name='Process')]
    result=workflows.run_workflow(WorkflowRunRequest(goal='question',steps=steps))
    assert result['status']=='waiting_approval' and len(result['trace'])==1 and peer['requests']==[]


def test_workflow_fails_if_agent_fails(peer):
    peer['error']='http';result=workflows.run_workflow(WorkflowRunRequest(goal='question',steps=[WorkflowStep(id='ai',type='agent',name='Process')]))
    assert result['status']=='failed' and result['trace'][0]['status']=='failed'

@pytest.mark.asyncio
async def test_async_caller_keeps_auth_context_in_worker_thread(peer):
    token=authorization_context.set('Bearer verified-request')
    try:result=agents.run_agent(AgentRunRequest(task='question'))
    finally:authorization_context.reset(token)
    assert result['status']=='completed' and peer['requests'][0].headers['authorization']=='Bearer verified-request'


def test_observability_scope_filter_does_not_leak_other_tenants(peer):
    for tenant,workspace in [('t','w'),('t','other'),('other','w')]:
        obs.record_event(ObservabilityEvent(event_type='request',component='backend',tenant_id=tenant,workspace_id=workspace))
    rows=obs.read_events(100,tenant_id='t',workspace_id='w')
    assert len(rows)==1 and rows[0]['tenant_id']=='t' and rows[0]['workspace_id']=='w'
    assert obs.ai_metrics(tenant_id='t',workspace_id='w')['events']==1


def test_http_router_uses_verified_scope_and_role(peer,monkeypatch):
    from backend_core.security import rbac
    from unittest.mock import AsyncMock
    app=FastAPI();app.include_router(router.router);client=TestClient(app)
    assert client.post('/v1/ops/agents/run',json={'task':'x'}).status_code==401
    claims={'sub':'u','tenant_id':'t','workspace_id':'w','roles':['department_manager']}
    monkeypatch.setattr(rbac,'_verify_with_keycloak_jwks_async',AsyncMock(side_effect=lambda token:claims))
    client.headers['Authorization']='Bearer unit-verified-by-crypto-boundary'
    response=client.post('/v1/ops/agents/run',json={'task':'x','context':{'tenant_id':'forged','workspace_id':'forged'}})
    assert response.status_code==200 and obs.read_events()[-1]['tenant_id']=='t'
    claims['roles']=['auditor'];assert client.post('/v1/ops/agents/run',json={'task':'x'}).status_code==403
