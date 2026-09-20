"""Behavioral regressions for verified RAG scope and generation cache keys."""
import importlib
from pathlib import Path
import pytest

@pytest.mark.asyncio
async def test_stream_uses_verified_scope_and_offloads_sync_search(monkeypatch):
    from rag_engine import main
    seen={}
    def search(req,claims):
        seen.update(tenant=req.tenant_id,workspace=req.workspace_id)
        return {'results':[],'features':[]}
    monkeypatch.setattr(main,'search',search)
    response=await main.answer_stream(main.AnswerRequest(query='سياسة الشركة',tenant_id='forged',workspace_id='forged'),{'sub':'user','tenant_id':'actual','workspace_id':'actual-w'})
    assert seen=={'tenant':'actual','workspace':'actual-w'}
    assert response.media_type=='text/event-stream'
    await response.body_iterator.aclose()

def test_highlight_does_not_accept_body_tenant(monkeypatch):
    from rag_engine import main
    seen={}
    def search(req,claims):
        seen['tenant']=req.tenant_id
        return {'results':[]}
    monkeypatch.setattr(main,'search',search)
    assert main.highlight(main.HighlightRequest(query='test',tenant_id='forged'),{'tenant_id':'actual','workspace_id':'w'})['count']==0
    assert seen['tenant']=='actual'

def test_cache_distinguishes_case_and_output_limit(monkeypatch):
    root=Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root/'services/llm_gateway'))
    mod=importlib.import_module('llm_gateway.main')
    assert mod._cache_key('A','','local',.1,32)!=mod._cache_key('a','','local',.1,32)
    assert mod._cache_key('A','','local',.1,32)!=mod._cache_key('A','','local',.1,900)
