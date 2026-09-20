"""Workflow behavior at the service boundary. HTTP peers are explicit test doubles."""
import importlib
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from common.security.request_policy import authorization_context

@pytest.fixture
def wf(monkeypatch):
    m = importlib.import_module('services.workflow_engine.main')
    monkeypatch.setattr(m, 'RUNS', {})
    monkeypatch.setattr(m, 'EXECUTION_HISTORY', [])
    monkeypatch.setattr(m, 'STEP_EXECUTORS', dict(m.STEP_EXECUTORS))
    yield m
    m.app.dependency_overrides.clear()


def claims(user='requester', tenant='t', workspace='w', role='department_manager'):
    return dict(sub=user, tenant_id=tenant, workspace_id=workspace, roles=[role])


def request(m, types, **payload):
    return m.WorkflowRequest(name='invoice', tenant_id='forged', workspace_id='forged',
        structured_steps=[m.WorkflowStep(id=f's{i}', type=t) for i, t in enumerate(types)], payload=payload)

@pytest.mark.asyncio
async def test_approval_resumes_remaining_steps_once(wf):
    executor = AsyncMock(side_effect=lambda step, ctx: {'step_id':step.id,'status':'completed','answer':'done'})
    wf.STEP_EXECUTORS['llm'] = executor
    result = await wf.run(request(wf, ['llm','approval','llm'], token='untrusted'), claims())
    row = wf.RUNS[result['run_id']]
    assert result['status'] == 'waiting_approval' and executor.await_count == 1
    assert row['tenant_id'] == 't' and row['workspace_id'] == 'w'
    assert 'token' not in row['context'] and 'payload' not in row
    assert 'completed_at' not in row
    approved = await wf.approve_step(row['run_id'], 's1', claims('reviewer'))
    assert approved['status'] == 'completed' and approved['steps_completed'] == 3
    assert executor.await_count == 2 and row['completed_at']
    with pytest.raises(HTTPException) as error:
        await wf.approve_step(row['run_id'], 's1', claims('reviewer'))
    assert error.value.status_code == 409 and executor.await_count == 2
    assert len(wf.EXECUTION_HISTORY) == 1

@pytest.mark.parametrize('who,step,code', [
    (claims(),'s0',403), (claims('reviewer',tenant='other'),'s0',404),
    (claims('reviewer',workspace='other'),'s0',404),
    (claims('reviewer',role='ai_user'),'s0',403), (claims('reviewer'),'wrong',404),
])
@pytest.mark.asyncio
async def test_approval_scope_and_reviewer(wf, who, step, code):
    run = await wf.run(request(wf,['approval']), claims())
    with pytest.raises(HTTPException) as error:
        await wf.approve_step(run['run_id'], step, who)
    assert error.value.status_code == code
    assert wf.RUNS[run['run_id']]['status'] == 'waiting_approval'

@pytest.mark.parametrize('who', [{}, claims(role='ai_user'), claims(workspace='')])
@pytest.mark.asyncio
async def test_execute_requires_scope_and_permission(wf, who):
    with pytest.raises(HTTPException) as error:
        await wf.run(request(wf,['approval']),who)
    assert error.value.status_code == 403 and not wf.RUNS

@pytest.mark.parametrize('continue_after_error', [True,False])
@pytest.mark.asyncio
async def test_failure_never_reports_success(wf, continue_after_error):
    failing = AsyncMock(side_effect=RuntimeError('credential=secret'))
    wf.STEP_EXECUTORS['llm'] = failing
    req = request(wf,['llm','approval'])
    req.structured_steps[0].config['fail_workflow_on_error'] = not continue_after_error
    result = await wf.run(req, claims())
    assert result['steps_failed'] == 1
    assert 'secret' not in str(result)
    if continue_after_error:
        result = await wf.approve_step(result['run_id'],'s1',claims('reviewer'))
    assert result['status'] == 'failed'

@pytest.mark.asyncio
async def test_invalid_types_and_duplicate_ids(wf):
    result = await wf.run(request(wf,['unknown']),claims())
    assert result['status'] == 'failed'
    req=request(wf,['approval','approval']); req.structured_steps[1].id='s0'
    with pytest.raises(HTTPException) as error: await wf.run(req,claims())
    assert error.value.status_code == 422

@pytest.mark.asyncio
async def test_history_and_status_isolate_scope(wf):
    a = await wf.run(request(wf,['approval']),claims())
    await wf.run(request(wf,['approval']),claims(tenant='other'))
    assert [i['run_id'] for i in wf.history(50,claims())['items']] == [a['run_id']]
    assert 'context' not in wf.status(a['run_id'],claims())
    with pytest.raises(HTTPException) as e: wf.status(a['run_id'],claims(tenant='other',role='hsaai_admin'))
    assert e.value.status_code == 404

@pytest.mark.parametrize('kind', ['rag','llm','agent'])
@pytest.mark.parametrize('outcome', ['success','http_error','timeout','bad_json','empty'])
@pytest.mark.asyncio
async def test_http_executors_forward_verified_token(wf,monkeypatch,kind,outcome):
    captured=[]
    def peer(req):
        captured.append(req)
        if outcome=='timeout': raise httpx.ReadTimeout('secret',request=req)
        if outcome=='http_error': return httpx.Response(503,text='secret')
        if outcome=='bad_json': return httpx.Response(200,text='not json')
        return httpx.Response(200,json={} if outcome=='empty' else {'results':[{'id':'d'}], 'text':'answer','answer':'answer'})
    client_class=httpx.AsyncClient
    monkeypatch.setattr(wf.httpx,'AsyncClient',lambda **kw:client_class(transport=httpx.MockTransport(peer),**kw))
    token=authorization_context.set('Bearer verified')
    try:
        result=await wf.STEP_EXECUTORS[kind](wf.WorkflowStep(id='s',type=kind),{'query':'question','token':'forged','tenant_id':'t','workspace_id':'w'})
    finally: authorization_context.reset(token)
    assert captured[0].headers['Authorization']=='Bearer verified'
    assert result['status']==('completed' if outcome in {'success','empty'} else 'error')
    assert 'secret' not in str(result)

@pytest.mark.asyncio
async def test_tool_dispatch_receives_scope(wf,monkeypatch):
    import common.tool_registry as registry
    dispatch=AsyncMock(return_value={'amount':7});monkeypatch.setattr(registry,'dispatch_tool',dispatch)
    step=wf.WorkflowStep(id='t',type='tool',config={'tool':'ledger','parameters':{'account':'A'}})
    result=await wf._execute_tool_step(step,{'tenant_id':'t','workspace_id':'w','user_id':'u','token':'valid'})
    assert result['result']=={'amount':7}
    assert dispatch.await_args.args==('ledger',{'account':'A'},{'tenant_id':'t','workspace_id':'w','user_id':'u','token':'valid'})


def test_static_history_route_and_authentication(wf):
    client=TestClient(wf.app)
    assert client.get('/workflows/history').status_code==401
    wf.app.dependency_overrides[wf._auth_dep]=lambda:claims()
    response=client.get('/workflows/history',headers={'Authorization':'Bearer verified'})
    assert response.status_code==200 and response.json()=={'items':[]}
    assert client.get('/workflows/history?limit=0').status_code==422
