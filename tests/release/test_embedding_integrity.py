"""Encoder-boundary contracts; does not assert real model quality or GPU execution."""
import importlib
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock
import pytest

@pytest.fixture
def emb(monkeypatch):
    m=importlib.import_module('services.rag_engine.embedding')
    monkeypatch.setattr(m,'_cache',m.EmbeddingCache(max_entries=10))
    monkeypatch.setattr(m,'_model',Mock())
    monkeypatch.setattr(m,'_current_model_name','model-a')
    monkeypatch.setattr(m,'_current_model_version','v1')
    monkeypatch.setattr(m,'_current_vector_size',3)
    monkeypatch.setattr(m,'VECTOR_SIZE',3)
    monkeypatch.setattr(m,'_model_load_error',None)
    return m


def test_default_model_reads_named_environment():
    env=dict(os.environ,EMBEDDING_MODEL='configured/model')
    code='from services.rag_engine.embedding import DEFAULT_EMBEDDING_MODEL;print(DEFAULT_EMBEDDING_MODEL)'
    result=subprocess.run([sys.executable,'-c',code],env=env,cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,check=True)
    assert result.stdout.strip()=='configured/model'


def test_batch_cache_order_and_defensive_copies(emb):
    emb._model.encode.return_value=[[1.,0.,0.],[0.,1.,0.]]
    assert emb.embed_texts(['a','b'])==[[1.,0.,0.],[0.,1.,0.]]
    first=emb.embed_text('a');first[0]=999
    assert emb.embed_texts(['b','a'])==[[0.,1.,0.],[1.,0.,0.]]
    assert emb._model.encode.call_count==1
    assert emb.get_cache_stats()['hits']==3

@pytest.mark.parametrize('vector',[[0,0,0],[1,0],[1,0,0,0],[float('nan'),0,0],[float('inf'),0,0]])
def test_bad_vectors_never_enter_cache(emb,vector):
    emb._model.encode.return_value=vector
    with pytest.raises(RuntimeError):emb.embed_text('bad')
    assert emb.get_cache_stats()['size']==0

@pytest.mark.parametrize('failure',['all_fail','short_batch'])
def test_failed_batch_has_no_pseudo_vectors(emb,failure):
    if failure=='all_fail':emb._model.encode.side_effect=RuntimeError('model down')
    else:emb._model.encode.return_value=[[1.,0.,0.]]
    with pytest.raises(RuntimeError):emb.embed_texts(['a','b'])
    assert emb.get_cache_stats()['size']==0


def test_per_text_retry_retains_real_results(emb):
    emb._model.encode.side_effect=[RuntimeError('batch OOM'),[1.,0.,0.],[0.,1.,0.]]
    assert emb.embed_texts(['a','b'])==[[1.,0.,0.],[0.,1.,0.]]
    assert emb._model.encode.call_count==3


def test_cache_identity_distinguishes_models_with_same_revision(emb,monkeypatch):
    emb._model.encode.return_value=[1.,0.,0.]
    assert emb.embed_text('shared')==[1.,0.,0.]
    monkeypatch.setattr(emb,'_current_model_name','model-b')
    emb._model.encode.return_value=[0.,1.,0.]
    assert emb.embed_text('shared')==[0.,1.,0.] and emb._model.encode.call_count==2


def test_lru_disabled_and_invalid_capacity(emb):
    cache=emb.EmbeddingCache(max_entries=2)
    cache.put('v','a',[1]);cache.put('v','b',[2]);assert cache.get('v','a')==[1]
    cache.put('v','c',[3]);assert cache.get('v','b') is None
    assert cache.invalidate_for_model('v')==2 and cache.stats()['size']==0
    cache.enabled=False;cache.put('v','d',[4]);assert cache.get('v','d') is None
    with pytest.raises(ValueError):emb.EmbeddingCache(max_entries=0)


def test_load_failure_health_and_explicit_reset(emb,monkeypatch):
    monkeypatch.setattr(emb,'_model',None);monkeypatch.setattr(emb,'_model_load_error',RuntimeError('model unavailable'))
    assert emb.embedding_status()['real_embedding_enabled'] is False
    with pytest.raises(RuntimeError):emb.embed_text('a')
    emb.reset_model_error();assert emb._model_load_error is None
    with pytest.raises(ValueError):emb.set_model('')
