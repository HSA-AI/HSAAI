"""Real SQLite schema/write/read tests; Qdrant is an explicit transport boundary."""
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend_core.db import models
from backend_core.knowledge import service as mod
from backend_core.knowledge.schemas import KnowledgeDocumentRegister,KnowledgeSearchRequest,KnowledgePermissionGrant

@pytest.fixture
def service(tmp_path,monkeypatch):
    engine=sa.create_engine(f'sqlite:///{tmp_path}/knowledge.db')
    @sa.event.listens_for(engine,'connect')
    def foreign_keys(connection,record):connection.execute('PRAGMA foreign_keys=ON')
    tables=[getattr(models,name).__table__ for name in ['KnowledgeSpace','KnowledgeCollection','KnowledgeDocument','KnowledgeVersion','KnowledgePermission','KnowledgeAnalyticsEvent','DocumentApprovalEvent']]
    models.Base.metadata.create_all(engine,tables=tables)
    monkeypatch.setattr(mod,'delete_document_vectors',lambda doc:{'status':'ok'})
    with Session(engine) as db:
        claims={'tenant_id':'t','workspace_id':'w','sub':'owner','roles':['knowledge_admin']}
        svc=mod.KnowledgeHubService(db,claims);svc.ensure_defaults()
        yield svc
    engine.dispose()


def register(svc,**kw):
    collection=svc.list_collections()[0]
    payload=KnowledgeDocumentRegister(filename='policy.txt',title='Leave policy',space_key=collection.space_key,collection_key=collection.key,metadata={'year':2026},tags=['policy'],uploaded_by='forged',tenant_id='forged',workspace_id='forged',**kw)
    return svc.register_document(payload)


def test_register_preserves_json_version_audit_and_verified_scope(service):
    row=register(service)
    assert row.extra_metadata=={'year':2026} and row.tags==['policy']
    assert (row.tenant_id,row.workspace_id,row.uploaded_by)==('t','w','owner')
    assert not row.qdrant_indexed
    assert service.db.query(models.KnowledgeVersion).filter_by(document_id=row.document_id).count()==1
    assert service.audit_trail(row.document_id)[0].action=='register'
    assert service.analytics()['documents']==1


def test_review_does_not_claim_vector_ingestion(service):
    row=register(service,status='draft')
    assert service.submit_for_review(row.document_id,'owner').status=='pending_review'
    result=service.approve_document(row.document_id,'reviewer','checked')
    assert result.status=='approved' and not result.qdrant_indexed
    with pytest.raises(HTTPException) as e:service.approve_document(row.document_id,'reviewer')
    assert e.value.status_code==409

@pytest.mark.parametrize('operation',['archive_document','delete_document'])
def test_vector_outage_preserves_document_for_retry(service,monkeypatch,operation):
    row=register(service);row.qdrant_indexed=True;service.db.commit();before=row.status
    def fail(doc):raise mod.QdrantDeleteError('unit outage')
    monkeypatch.setattr(mod,'delete_document_vectors',fail)
    with pytest.raises(HTTPException) as e:getattr(service,operation)(row.document_id,'reviewer')
    assert e.value.status_code==503
    service.db.refresh(row);assert row.status==before and row.qdrant_indexed
    assert service.db.query(models.KnowledgeDocument).count()==1

@pytest.mark.parametrize('operation,status',[('archive_document','archived'),('delete_document','deleted')])
def test_vector_cleanup_then_retention_preserves_audit_fk(service,operation,status):
    row=register(service);getattr(service,operation)(row.document_id,'reviewer')
    service.db.refresh(row);assert row.status==status and not row.qdrant_indexed
    assert service.db.query(models.DocumentApprovalEvent).filter_by(document_id=row.document_id).count()==2
    assert service.list_documents(claims=service.claims)==[]

@pytest.mark.parametrize('tenant,workspace',[('other','w'),('t','other')])
def test_scope_covers_get_review_delete_lists_and_analytics(service,tenant,workspace):
    row=register(service,status='draft')
    other=mod.KnowledgeHubService(service.db,{'tenant_id':tenant,'workspace_id':workspace,'sub':'admin','roles':['hsaai_admin']})
    assert other.list_documents(claims=other.claims)==[] and other.list_pending_documents()==[]
    assert other.analytics()['documents']==0 and other.audit_trail(row.document_id)==[]
    for method,args in [('get_document',[]),('approve_document',['reviewer']),('archive_document',['reviewer']),('delete_document',['reviewer'])]:
        with pytest.raises(HTTPException) as e:getattr(other,method)(row.document_id,*args)
        assert e.value.status_code==404
    assert row.status=='draft'
    # Default spaces for a second scope must not collide with the first scope.
    assert len(other.list_spaces())==3


def test_metadata_search_and_injection_are_scoped(service):
    row=register(service)
    assert service.search_metadata(KnowledgeSearchRequest(query='2026'),service.claims)['results'][0].document_id==row.document_id
    assert service.search_metadata(KnowledgeSearchRequest(query="' OR 1=1 --"),service.claims)['results']==[]


def test_permission_grants_are_scoped(service):
    payload=KnowledgePermissionGrant(resource_type='document',resource_key='policy',principal='ai_user',permission='read')
    row=service.grant_permission(payload)
    assert row.tenant_id=='t' and row.workspace_id=='w' and len(service.permissions())==1
    other=mod.KnowledgeHubService(service.db,{'tenant_id':'other','workspace_id':'w','sub':'admin','roles':['hsaai_admin']})
    assert other.permissions()==[]


def test_uploader_cannot_explicitly_self_approve(service):
    service.claims['roles']=['document_uploader']
    with pytest.raises(HTTPException) as e:register(service,status='approved')
    assert e.value.status_code==403 and service.db.query(models.KnowledgeDocument).count()==0


def test_registration_cannot_reference_another_scope_collection(service):
    from backend_core.knowledge.schemas import KnowledgeCollectionCreate
    collection=service.list_collections()[0]
    other=mod.KnowledgeHubService(service.db,{'tenant_id':'other','workspace_id':'w','sub':'u','roles':[]})
    with pytest.raises(HTTPException) as e:
        other.create_collection(KnowledgeCollectionCreate(space_key=collection.space_key,key='forged',name='forged'))
    assert e.value.status_code==404
    with pytest.raises(HTTPException) as e:
        other.register_document(KnowledgeDocumentRegister(filename='attack.txt',space_key=collection.space_key,collection_key=collection.key))
    assert e.value.status_code==404
