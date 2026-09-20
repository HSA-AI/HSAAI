"""Behavioral regressions for the v4 delivery; no external credentials required."""
import asyncio
import ast
import importlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from common.security.request_policy import SlidingWindowLimiter, verified_scope, origin_allowed, authorization_context, outgoing_headers

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('claims',[{}, {'tenant_id':'A'}, {'tenant_id':'A','workspace_id':''}, {'tenant_id':None,'workspace_id':'W'}])
def test_incomplete_scope_is_rejected(claims):
    with pytest.raises(ValueError): verified_scope(claims)

def test_verified_scope_is_exact():
    assert verified_scope({'tenant_id':'A','workspace_id':'W'}) == ('A','W')

@pytest.mark.parametrize('origin',['null',None,'https://portal.example.evil','https://portal.example@evil','https://portal.example/path'])
def test_origin_boundary(origin):
    assert not origin_allowed(origin,['https://portal.example'])

def test_allowed_origin():
    assert origin_allowed('https://portal.example',['https://portal.example'])

def test_limiter_capacity_and_expiry():
    now=[0]; limiter=SlidingWindowLimiter(2,window=60,max_clients=1,clock=lambda:now[0])
    assert limiter.allow('a') and limiter.allow('a')
    assert not limiter.allow('a') and not limiter.allow('b')
    now[0]=60
    assert limiter.allow('b') and not limiter.allow('a')

@pytest.mark.asyncio
async def test_tokens_do_not_cross_concurrent_requests():
    async def worker(token):
        context = authorization_context.set(token)
        try:
            await asyncio.sleep(0)
            return outgoing_headers()
        finally: authorization_context.reset(context)
    a,b=await asyncio.gather(worker('Bearer a'),worker('Bearer b'))
    assert a == {'Authorization':'Bearer a'} and b == {'Authorization':'Bearer b'}
    assert outgoing_headers() == {}

def test_migration_chain_has_single_head_and_no_missing_parent():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config=Config(str(ROOT/'alembic.ini')); config.set_main_option('script_location',str(ROOT/'alembic'))
    script=ScriptDirectory.from_config(config)
    assert len(script.get_heads()) == 1
    assert len(list(script.walk_revisions())) >= 5

@pytest.mark.parametrize('module',['precognition_engine','collective_intelligence_engine','immune_system','knowledge_genome_engine','singularity_engine'])
def test_advanced_services_deny_missing_auth(module):
    mod=importlib.import_module(f'services.{module}.main')
    route=next(r for r in mod.app.routes if getattr(r,'path','').startswith('/v1/') and 'POST' in getattr(r,'methods',set()))
    response=TestClient(mod.app).post(route.path,json={})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_failure_memory_is_tenant_scoped():
    from common.wisdom import FailureMemory
    memory=FailureMemory()
    memory.record_failure('budget failed','budget works','bad data',tenant_id='a')
    assert not memory.find_similar_failures('budget',tenant_id='b')
    assert len(memory.find_similar_failures('budget',tenant_id='a')) == 1

@pytest.mark.asyncio
async def test_wisdom_does_not_invent_percentage():
    from common.wisdom import WisdomCrystallizationEngine
    patterns=await WisdomCrystallizationEngine()._extract_patterns([{'outcome':'success'}]*25,'finance')
    assert not any('23%' in p['statement'] for p in patterns)

def test_gateway_csrf_cookie_request():
    from api_gateway.main import app
    client=TestClient(app)
    response=client.post('/v1/auth/logout',headers={'Origin':'https://evil.example','Cookie':'hsaai_access_token=example'})
    assert response.status_code == 403

def test_backend_llm_anonymous_is_rejected():
    from backend_core.main import app
    response=TestClient(app).post('/v1/llm/generate',json={'prompt':'hello'})
    assert response.status_code in (401,403)

@pytest.mark.asyncio
async def test_backend_unready_uses_503():
    from backend_core import main
    with patch.object(main,'check_db',return_value={'status':'error'}), patch.object(main,'qdrant_health',new=AsyncMock(return_value={'status':'ok'})):
        response=await main.ready()
    assert response.status_code == 503

def test_specialist_prompts_match_required_agents():
    prompts=json.loads((ROOT/'services/multi_agents/prompts.v1.json').read_text())
    assert {'business','legal','research','developer','security'} <= set(prompts['agents'])
    assert all(p['required_permission']=='agents:execute' for p in prompts['agents'].values())
