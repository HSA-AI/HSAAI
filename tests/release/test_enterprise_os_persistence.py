"""Exercise actual Enterprise OS persistence and review boundaries in SQLite."""
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend_core.enterprise_os import router as mod
from backend_core.db.database import Base

@pytest.fixture
def db(tmp_path):
    mod._models();engine=sa.create_engine(f'sqlite:///{tmp_path}/enterprise.db');Base.metadata.create_all(engine)
    with Session(engine) as session:yield session
    engine.dispose()

def claims(sub='requester',tenant='t',workspace='w',roles=None):
    return {'sub':sub,'tenant_id':tenant,'workspace_id':workspace,'roles':roles or ['hsaai_admin']}

def approval(db,**kwargs):
    data={'title':'Approve payment','action_type':'financial_action','risk_level':'critical','required_roles':['department_manager']};data.update(kwargs)
    return mod.create_approval(mod.ApprovalCreate(**data),claims(),db)['approval_id']

def test_agent_json_fields_survive_create_update_and_audit(db):
    data=mod.AgentUpsert(agent_key='finance-custom',name='Finance custom',tools=['ledger'],knowledge_sources=['policy'],permissions=['agents:execute'])
    row=mod.create_agent(data,claims(),db)
    assert row['tools']==['ledger'] and row['knowledge_sources']==['policy']
    assert mod.get_agent('finance-custom',db,claims())['permissions']==['agents:execute']
    updated=mod.update_agent('finance-custom',data.model_copy(update={'tools':['report']}),claims(),db)
    assert updated['tools']==['report'] and updated['version']==2
    audit=db.query(mod._models()['AuditLog']).all()
    assert len(audit)==2 and all(a.tenant_id=='t' and a.workspace_id=='w' for a in audit)

@pytest.mark.parametrize('other',[claims(tenant='elsewhere'),claims(workspace='elsewhere')])
def test_agent_scope_prevents_cross_scope_read_and_update(db,other):
    data=mod.AgentUpsert(agent_key='private-agent',name='Private');mod.create_agent(data,claims(),db)
    with pytest.raises(HTTPException) as e:mod.get_agent('private-agent',db,other)
    assert e.value.status_code==404
    with pytest.raises(HTTPException) as e:mod.update_agent('private-agent',data,other,db)
    assert e.value.status_code==404
    assert 'private-agent' not in [x['agent_key'] for x in mod.list_agents(db,other)['items']]

def test_default_agents_are_scoped_and_not_falsely_healthy(db):
    first=mod.list_agents(db,claims())['items'];second=mod.list_agents(db,claims(tenant='other'))['items']
    assert len(first)==len(second)==12
    assert not {a['agent_key'] for a in first}&{a['agent_key'] for a in second}
    assert all(a['health_status']=='not_tested' for a in first+second)
    assert len(mod.list_agents(db,claims())['items'])==12

def test_routing_does_not_claim_model_execution(db):
    result=mod.run_agent({'message':'finance quarterly report'},claims(),db)
    assert result['status']=='routed' and result['answer']=='' and result['executed'] is False
    assert db.query(mod._models()['AgentLog']).one().success is False

def test_sensitive_routing_creates_persisted_review_chain(db):
    result=mod.run_agent({'message':'payment','action_type':'financial_action'},claims(),db)
    assert result['status']=='awaiting_approval' and result['requires_approval']
    row=db.query(mod._models()['ApprovalRequest']).one()
    assert row.risk_level=='critical' and 'executive' in row.required_roles and row.status=='pending'

def test_critical_approval_requires_two_distinct_people_and_never_claims_execution(db):
    key=approval(db)
    first=mod.approve(key,mod.DecisionPayload(comment='reviewed'),claims(sub='r1',roles=['department_manager']),db)
    assert first['status']=='pending' and first['execution']=='pending_executor'
    with pytest.raises(HTTPException) as e:mod.approve(key,mod.DecisionPayload(),claims(sub='r1'),db)
    assert e.value.status_code==403
    second=mod.approve(key,mod.DecisionPayload(),claims(sub='r2'),db)
    assert second['status']=='approved' and second['executed'] is False
    assert db.query(mod._models()['ApprovalHistory']).count()==2
    with pytest.raises(HTTPException) as e:mod.approve(key,mod.DecisionPayload(),claims(sub='r3'),db)
    assert e.value.status_code==409

@pytest.mark.parametrize('reviewer,code',[('self',403),('wrong_role',403),('other_tenant',404),('other_workspace',404)])
def test_approval_rejects_requester_wrong_role_and_other_scope(db,reviewer,code):
    key=approval(db)
    who={'self':claims(),'wrong_role':claims(sub='viewer',roles=['ai_user']),'other_tenant':claims(sub='r',tenant='other'),'other_workspace':claims(sub='r',workspace='other')}[reviewer]
    for method in (mod.approve,mod.reject):
        with pytest.raises(HTTPException) as e:method(key,mod.DecisionPayload(),who,db)
        assert e.value.status_code==code
    assert db.query(mod._models()['ApprovalRequest']).one().status=='pending'

def test_rejection_is_terminal_and_lists_are_scoped(db):
    key=approval(db)
    assert mod.reject(key,mod.DecisionPayload(comment='unsafe'),claims(sub='reviewer'),db)['status']=='rejected'
    assert mod.list_approvals('rejected',db,claims())['items'][0]['required_roles']==['department_manager']
    assert mod.list_approvals(None,db,claims(tenant='other'))['items']==[]
    with pytest.raises(HTTPException) as e:mod.reject(key,mod.DecisionPayload(),claims(sub='another'),db)
    assert e.value.status_code==409

def test_graph_json_and_search_are_scoped(db):
    a=mod.create_entity(mod.EntityCreate(name='Policy',entity_type='Document',metadata={'revision':2}),claims(),db)
    b=mod.create_entity(mod.EntityCreate(name='Owner',entity_type='Employee'),claims(),db)
    row=db.query(mod._models()['KnowledgeEntity']).filter_by(entity_key=a['entity_key']).one();assert row.extra_metadata=={'revision':2}
    relation=mod.RelationshipCreate(source_key=a['entity_key'],target_key=b['entity_key'],relationship_type='owns')
    mod.create_relationship(relation,claims(),db)
    assert len(mod.graph(db,claims())['relationships'])==1
    assert mod.graph(db,claims(tenant='other'))=={'entities':[],'relationships':[]}
    assert mod.enterprise_search(mod.SearchRequest(query='Policy'),claims(),db)['result_count']==1
    assert mod.enterprise_search(mod.SearchRequest(query='Policy'),claims(tenant='other'),db)['result_count']==0
    with pytest.raises(HTTPException) as e:mod.create_relationship(relation,claims(tenant='other'),db)
    assert e.value.status_code==404

def test_client_cannot_downgrade_financial_action_risk(db):
    key=approval(db,risk_level='low')
    row=db.query(mod._models()['ApprovalRequest']).filter_by(approval_id=key).one()
    assert row.risk_level=='critical'
