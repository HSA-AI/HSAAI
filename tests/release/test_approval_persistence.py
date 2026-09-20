"""Real SQLite persistence; PostgreSQL locking/RLS still require external validation."""
import importlib.util
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import AsyncMock
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend_core.approvals import service as svc
from backend_core.approvals import router as api
from backend_core.db.models import HumanApprovalRequest,AuditLog

@pytest.fixture
def database(tmp_path,monkeypatch):
    engine=sa.create_engine(f'sqlite:///{tmp_path}/approvals.db')
    HumanApprovalRequest.__table__.create(engine);AuditLog.__table__.create(engine)
    monkeypatch.setattr(svc,'notify_approval',AsyncMock())
    with Session(engine,expire_on_commit=False) as db: yield db,engine
    engine.dispose()


def claims(user='owner',tenant='t',workspace='w'):
    return {'sub':user,'tenant_id':tenant,'workspace_id':workspace,'roles':['department_manager']}

async def create(db,**kw):
    args=dict(action_type='data_export',resource_type='document',resource_id='d',requester='owner',payload={'purpose':'audit'},tenant_id='t',workspace_id='w')
    return await svc.create_approval(db,**(args|kw))

@pytest.mark.asyncio
async def test_critical_controls_survive_reopen(database):
    db,engine=database;row=await create(db,risk_level='critical',requires_two_person=False,sla_hours=48)
    request_id=row.request_id
    assert svc.notify_approval.await_count==1
    db.close()
    with Session(engine) as reopened:
        row=reopened.query(HumanApprovalRequest).filter_by(request_id=request_id).one()
        assert row.requires_two_person and row.risk_level=='critical' and row.sla_hours==48
        assert row.sla_deadline and row.status=='pending_first_approval'
        assert reopened.query(AuditLog).count()==1

@pytest.mark.asyncio
async def test_distinct_two_reviewers_and_audit(database):
    db,_=database;row=await create(db,risk_level='critical');rid=row.request_id
    with pytest.raises(ValueError):svc.decide_approval(db,request_id=rid,approver='owner',approved=True)
    first=svc.decide_approval(db,request_id=rid,approver='first',approved=True)
    assert first.status=='pending_second_approval'
    for user in ['first','owner']:
        with pytest.raises(ValueError):svc.decide_approval(db,request_id=rid,approver=user,approved=True)
    second=svc.decide_approval(db,request_id=rid,approver='second',approved=True)
    assert second.status=='approved' and second.second_approver=='second' and second.decided_at
    assert [a.action for a in db.query(AuditLog).order_by(AuditLog.id)]==['approval.create','approval.first_approve','approval.second_approve']
    with pytest.raises(ValueError):svc.decide_approval(db,request_id=rid,approver='third',approved=True)

@pytest.mark.parametrize('critical,approved,status',[(False,True,'approved'),(False,False,'rejected'),(True,False,'rejected')])
@pytest.mark.asyncio
async def test_single_decision_paths(database,critical,approved,status):
    db,_=database;row=await create(db,risk_level='critical' if critical else 'low')
    result=svc.decide_approval(db,request_id=row.request_id,approver='reviewer',approved=approved,reason='checked')
    assert result.status==status and result.decision_reason=='checked' and result.decided_at

@pytest.mark.asyncio
async def test_cancel_permission_and_terminal_state(database):
    db,_=database;row=await create(db)
    with pytest.raises(ValueError):svc.cancel_approval(db,request_id=row.request_id,actor='stranger')
    assert svc.cancel_approval(db,request_id=row.request_id,actor='owner').status=='cancelled'
    with pytest.raises(ValueError):svc.cancel_approval(db,request_id=row.request_id,actor='owner')
    other=await create(db)
    assert svc.cancel_approval(db,request_id=other.request_id,actor='admin',allow_admin=True).status=='cancelled'

@pytest.mark.asyncio
async def test_sla_sweep_is_scoped_and_persistent(database):
    db,engine=database;a=await create(db);b=await create(db,tenant_id='other');fresh=await create(db)
    a.sla_deadline=b.sla_deadline=datetime.now(timezone.utc)-timedelta(hours=1);db.commit()
    assert svc.get_sla_status(db,a.request_id)['breached']
    for i in range(1,4):
        rows=svc.check_sla_breaches(db,tenant_id='t',workspace_id='w')
        assert [x.request_id for x in rows]==[a.request_id] and a.escalation_count==i
    assert a.status=='expired' and b.escalation_count==0 and fresh.status=='pending'
    assert not svc.get_sla_status(db,a.request_id)['breached']
    assert not svc.check_sla_breaches(db,tenant_id='t',workspace_id='w')

@pytest.mark.parametrize('tenant,workspace',[('other','w'),('t','other'),('other','other')])
@pytest.mark.asyncio
async def test_approval_api_denies_cross_scope(database,tenant,workspace):
    db,_=database;row=await create(db);who=claims(tenant=tenant,workspace=workspace)
    calls=[lambda:api.approval_detail(row.request_id,who,db),lambda:api.sla_status(row.request_id,who,db),lambda:api.decide(row.request_id,api.ApprovalDecisionIn(approved=True),who,db),lambda:api.cancel(row.request_id,api.ApprovalCancelIn(),who,db)]
    for call in calls:
        with pytest.raises(HTTPException) as e:call()
        assert e.value.status_code==404
    assert row.status=='pending'

@pytest.mark.asyncio
async def test_api_list_detail_create_cancel(database):
    db,_=database;row=await create(db);await create(db,workspace_id='other')
    result=api.approvals(None,200,claims(),db)
    assert [x['request_id'] for x in result['items']]==[row.request_id]
    assert api.approval_detail(row.request_id,claims(),db)["status"]=="pending"
    result=await api.request_approval(api.ApprovalCreateIn(action_type='delete',risk_level='critical'),claims(),db)
    assert result['requires_two_person'] and result['status']=='pending_first_approval'
    assert api.cancel(row.request_id,api.ApprovalCancelIn(reason='withdrawn'),claims(),db)['status']=='cancelled'

@pytest.mark.parametrize('kw',[{'risk_level':'invalid'},{'sla_hours':0},{'sla_hours':169}])
@pytest.mark.asyncio
async def test_invalid_risk_and_sla_no_rows(database,kw):
    db,_=database
    with pytest.raises(ValueError):await create(db,**kw)
    assert db.query(HumanApprovalRequest).count()==0

@pytest.mark.parametrize('operation',['decide','cancel','sla','get'])
def test_unknown_request(database,operation):
    db,_=database
    if operation=='get':assert svc.get_approval(db,'missing') is None;return
    with pytest.raises(ValueError):
        if operation=='decide':svc.decide_approval(db,request_id='missing',approver='a',approved=True)
        elif operation=='cancel':svc.cancel_approval(db,request_id='missing',actor='a')
        else:svc.get_sla_status(db,'missing')


def test_additive_migration_preserves_legacy_rows_and_reruns(tmp_path,monkeypatch):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path=Path(__file__).resolve().parents[2]/'alembic/versions/0007_approval_controls.py'
    spec=importlib.util.spec_from_file_location('approval_migration',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    engine=sa.create_engine(f'sqlite:///{tmp_path}/legacy.db')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE human_approval_requests (id INTEGER PRIMARY KEY, status VARCHAR(32), payload VARCHAR)')
        connection.exec_driver_sql("INSERT INTO human_approval_requests VALUES (1, 'pending_second_approval', 'preserved')")
        monkeypatch.setattr(mod,'op',Operations(MigrationContext.configure(connection)))
        mod.upgrade();mod.upgrade()
        row=connection.execute(sa.text('SELECT * FROM human_approval_requests')).mappings().one()
        assert row['payload']=='preserved' and row['requires_two_person']==1 and row['sla_hours']==24
    engine.dispose()
