"""Gateway policy/HTTP contracts. MockTransport is not a running LLM model."""
import importlib
import json
from pathlib import Path
from unittest.mock import Mock
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

@pytest.fixture
def gateway(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]/'services/llm_gateway'))
    m=importlib.import_module('services.llm_gateway.main')
    for key in m.BLOCKED_EXTERNAL_SECRET_KEYS:monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(m,'LOCAL_ONLY',True);monkeypatch.setattr(m,'ALLOW_EXTERNAL_AI',False)
    monkeypatch.setattr(m,'OLLAMA_BASE_URL','http://127.0.0.1:11434')
    monkeypatch.setattr(m,'ENABLE_SEMANTIC_CACHE',False);monkeypatch.setattr(m,'ENABLE_TOKEN_BUDGET',False)
    monkeypatch.setattr(m,'route_model',lambda *a:{'model':'unit-model','model_key':'unit','provider':'ollama','reason':'unit route','local_only':True})
    yield m
    m.app.dependency_overrides.clear()


def who(**kw):return {'sub':'user','tenant_id':'t','workspace_id':'w'}|kw

def transport(monkeypatch,m,peer):
    real=httpx.AsyncClient;monkeypatch.setattr(m.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(peer),**kw))

@pytest.mark.asyncio
async def test_chat_messages_scope_and_response(gateway,monkeypatch):
    m=gateway;seen=[]
    def peer(req):seen.append(req);return httpx.Response(200,json={'message':{'content':'Answer'}})
    transport(monkeypatch,m,peer)
    req=m.GenerateRequest(prompt='Question',system='Policy',tenant_id='forged',workspace_id='forged')
    result=await m.generate(req,who())
    assert result.text=='Answer' and req.tenant_id=='t' and req.workspace_id=='w'
    assert json.loads(seen[0].content)['messages']==[{'role':'system','content':'Policy'},{'role':'user','content':'Question'}]

@pytest.mark.parametrize('status',[400,401,429,500,503])
@pytest.mark.asyncio
async def test_provider_errors_are_sanitized(gateway,monkeypatch,status):
    transport(monkeypatch,gateway,lambda req:httpx.Response(status,text='credential=private'))
    with pytest.raises(HTTPException) as error:await gateway.ollama_generate(gateway.GenerateRequest(prompt='question'))
    assert error.value.status_code==status and 'private' not in error.value.detail

@pytest.mark.parametrize('claims',[{},who(tenant_id=''),who(workspace_id=None)])
@pytest.mark.asyncio
async def test_generate_and_stream_require_verified_scope(gateway,claims):
    for endpoint in [gateway.generate,gateway.stream]:
        with pytest.raises(HTTPException) as error:await endpoint(gateway.GenerateRequest(prompt='x'),claims)
        assert error.value.status_code==403

@pytest.mark.asyncio
async def test_budget_rejection_does_not_contact_model(gateway,monkeypatch):
    monkeypatch.setattr(gateway,'_check_token_budget',lambda *a:(False,100,100))
    model=Mock(side_effect=AssertionError('must not call'));monkeypatch.setattr(gateway,'ollama_generate',model)
    for endpoint in [gateway.generate,gateway.stream]:
        with pytest.raises(HTTPException) as e:await endpoint(gateway.GenerateRequest(prompt='x'),who())
        assert e.value.status_code==429
    model.assert_not_called()

@pytest.mark.parametrize('changed',[{'tenant_id':'other'},{'workspace_id':'other'},{'sub':'other'},{}])
@pytest.mark.asyncio
async def test_cache_identity_is_user_workspace_tenant(gateway,monkeypatch,changed):
    scopes=[]
    def cache(*args):scopes.append(args[4]);return {'text':'cached','provider':'ollama'}
    monkeypatch.setattr(gateway,'_check_semantic_cache',cache)
    for claims in [who(),who(**changed)]:
        result=await gateway.generate(gateway.GenerateRequest(prompt='x'),claims)
        assert result.text=='cached' and 'cache_hit' in result.route_reason
    assert (scopes[0]!=scopes[1])==bool(changed)

@pytest.mark.asyncio
async def test_stream_tokens_done_and_metrics(gateway,monkeypatch):
    content='\n'.join([json.dumps({'message':{'content':text},'done':False}) for text in ['مرحبا',' بك']]+[json.dumps({'done':True})])
    transport(monkeypatch,gateway,lambda r:httpx.Response(200,text=content))
    chunks=b''.join([c async for c in gateway.ollama_stream(gateway.GenerateRequest(prompt='x'))]).decode()
    assert 'مرحبا' in chunks and ' بك' in chunks and 'event: metrics' in chunks and '[DONE]' in chunks
    assert '"total_tokens": 2' in chunks

@pytest.mark.parametrize('failure',['http','timeout'])
@pytest.mark.asyncio
async def test_stream_failure_is_explicit_and_sanitized(gateway,monkeypatch,failure):
    def peer(r):
        if failure=='timeout':raise httpx.ReadTimeout('credential=private',request=r)
        return httpx.Response(503,text='credential=private')
    transport(monkeypatch,gateway,peer)
    body=b''.join([c async for c in gateway.ollama_stream(gateway.GenerateRequest(prompt='x'))]).decode()
    assert 'error' in body and '[DONE]' in body and 'private' not in body

@pytest.mark.parametrize('state',['ready','missing','http_error','invalid_json'])
@pytest.mark.asyncio
async def test_readiness_requires_installed_model(gateway,monkeypatch,state):
    def peer(req):
        if state=='http_error':return httpx.Response(503)
        if state=='invalid_json':return httpx.Response(200,text='bad')
        return httpx.Response(200,json={'models':[{'name':gateway.DEFAULT_MODEL}] if state=='ready' else []})
    transport(monkeypatch,gateway,peer)
    result=await gateway.readiness()
    assert result=={'status':'ready'} if state=='ready' else result.status_code==503

@pytest.mark.parametrize('secret',['OPENAI_API_KEY','ANTHROPIC_API_KEY','GOOGLE_API_KEY','MISTRAL_API_KEY','COHERE_API_KEY'])
def test_internal_mode_rejects_external_credentials(gateway,monkeypatch,secret):
    monkeypatch.setenv(secret,'unit-only')
    with pytest.raises(HTTPException) as e:gateway.assert_no_external_ai()
    assert e.value.status_code==500


def test_http_validation_and_missing_auth(gateway):
    client=TestClient(gateway.app)
    assert client.post('/v1/generate',json={'prompt':'x'}).status_code==401
    gateway.app.dependency_overrides[gateway._auth_dep]=lambda:who()
    for payload in [{'prompt':''},{'prompt':'x','temperature':5},{'prompt':'x','max_tokens':0}]:
        assert client.post('/v1/generate',json=payload).status_code==422


def test_production_budget_storage_outage_fails_closed(gateway,monkeypatch):
    monkeypatch.setenv('APP_ENV','production');monkeypatch.setattr(gateway,'ENABLE_TOKEN_BUDGET',True)
    monkeypatch.setattr(gateway,'_get_redis_client',lambda *a:None)
    with pytest.raises(HTTPException) as e:gateway._check_token_budget('t',5)
    assert e.value.status_code==503
