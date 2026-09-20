"""Actual SQLite persistence and HTTP denial. PostgreSQL RLS needs its own host."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session
from backend_core.enterprise_os import router as api
from backend_core.db.database import Base, set_transaction_tenant
from backend_core.db.models import AICostRecord, AuditLog, ExecutiveMetric, LLMUsageLog
from backend_core.security import rbac
from common.security.request_policy import tenant_context, workspace_context, authorization_context

def claims(tenant="company-a", workspace="finance", sub="owner"):
    return {"tenant_id": tenant, "workspace_id": workspace, "sub": sub, "roles": ["hsaai_admin"]}

@pytest.fixture
def db(tmp_path):
    api._models(); engine = sa.create_engine(f"sqlite:///{tmp_path}/enterprise.db"); Base.metadata.create_all(engine)
    with Session(engine) as session: yield session
    engine.dispose()

@pytest.mark.parametrize("model_name,route,key,required", [
    ("AICoEProject",api.coe_projects,"project_key",{"name":"Payroll"}),
    ("AIPolicy",api.coe_policies,"policy_key",{"title":"Hiring"}),
    ("AIRisk",api.coe_risks,"risk_key",{"title":"Data exposure"}),
    ("AITraining",api.coe_training,"course_key",{"title":"AI onboarding"}),
])
def test_coe_queries_are_isolated_even_for_admin(db,model_name,route,key,required):
    model=api._models()[model_name]; scopes=(claims(),claims(tenant="company-b"),claims(workspace="hr"))
    for i,who in enumerate(scopes): db.add(model(**required,**{key:str(i)},tenant_id=who["tenant_id"],workspace_id=who["workspace_id"]))
    db.commit()
    for i,who in enumerate(scopes): assert [row[key] for row in route(db,who)["items"]]==[str(i)]

def test_project_ownership_audit_and_duplicate_rollback(db):
    payload=api.ProjectCreate(project_key="strategy",name="Strategy",tenant_id="forged",workspace_id="forged")
    api.create_project(payload,db,claims()); row=db.query(api._models()["AICoEProject"]).one()
    assert (row.tenant_id,row.workspace_id)==("company-a","finance")
    audit=db.query(AuditLog).one(); assert (audit.actor,audit.tenant_id,audit.workspace_id)==("owner","company-a","finance")
    with pytest.raises(HTTPException) as error: api.create_project(payload,db,claims(tenant="company-b"))
    assert error.value.status_code==409 and db.query(AuditLog).count()==1
    assert api.coe_projects(db,claims(tenant="company-b"))["items"]==[]

@pytest.mark.parametrize("field,value",[("tenant_id",None),("tenant_id",""),("workspace_id"," "),("tenant_id","x"*129),("sub",None)])
def test_missing_or_invalid_scope_never_inherits_legacy_default(db,field,value):
    with pytest.raises(HTTPException) as error: api.coe_projects(db,claims()|{field:value})
    assert error.value.status_code==403

def test_finops_aggregates_only_own_scope_and_limits_returned_rows(db):
    model=api._models()["CostRecord"]
    db.add_all([model(record_key=f"a-{i}",tokens=2,total_cost=0.5,tenant_id="company-a",workspace_id="finance") for i in range(105)])
    db.add_all([model(record_key="b",tokens=99999,total_cost=8888,tenant_id="company-b",workspace_id="finance"),model(record_key="hr",tokens=777,total_cost=777,tenant_id="company-a",workspace_id="hr")]);db.commit()
    result=api.finops_usage(db,claims());assert (result["total_tokens"],result["total_cost"])==(210,52.5)
    assert len(result["records"])==100 and result["records"][0]["record_key"]=="a-104" and result["records"][-1]["record_key"]=="a-5"
    assert api.finops_usage(db,claims(tenant="empty"))=={"total_tokens":0,"total_cost":0.0,"records":[]}

def test_recorded_cost_persists_scope_actor_components_and_audit(db):
    result=api.record_cost(api.CostCreate(tokens=123,api_calls=2,embedding_cost=0.2,vector_storage_cost=0.3,compute_cost=1.5),claims(),db)
    row=db.query(api._models()["CostRecord"]).one();assert row.record_key==result["record_key"] and row.total_cost==2.0
    assert (row.tenant_id,row.workspace_id,row.user_id)==("company-a","finance","owner") and row.tokens==123 and row.api_calls==2
    assert api.audit_logs(db=db,claims=claims())["items"][0]["resource"]==result["record_key"]
    assert api.audit_logs(db=db,claims=claims(tenant="company-b"))["items"]==[]

@pytest.mark.parametrize("payload",[{"tokens":-1},{"api_calls":-1},{"latency_ms":-1},{"compute_cost":-0.1},{"embedding_cost":float("nan")},{"vector_storage_cost":float("inf")}])
def test_invalid_accounting_values_are_rejected(payload):
    with pytest.raises(ValidationError): api.CostCreate(**payload)

def test_integration_json_scope_and_honest_configuration_probe(db):
    payload=api.IntegrationCreate(connector_key="erp-a",name="ERP A",system_type="SAP",enabled=True,base_url="https://sap.example.test",permissions_mapping={"accountant":"read"},data_mapping={"cost":"amount"})
    api.create_integration(payload,claims(),db);row=db.query(api._models()["Integration"]).one()
    assert row.permissions_mapping=={"accountant":"read"} and row.data_mapping=={"cost":"amount"} and row.retry_policy["max_retries"]==3
    assert api.list_integrations(db,claims())["items"][0]["connector_key"]=="erp-a"
    for who in (claims(tenant="company-b"),claims(workspace="hr")):
        assert api.list_integrations(db,who)["items"]==[] and api.integrations_catalog(db,who)["connectors"]==[]
        with pytest.raises(HTTPException) as error: api.test_integration("erp-a",db,who)
        assert error.value.status_code==404
    result=api.test_integration("erp-a",db,claims());assert result["health_status"]=="not_tested" and not result["connected"] and result["validation"]=="configuration_only"
    log=db.query(api._models()["ConnectorLog"]).one();assert not log.success and (log.tenant_id,log.workspace_id)==("company-a","finance")
    assert not api.integrations_catalog(db,claims())["connectors"][0]["connected"]
    row.enabled=False;db.commit();assert api.test_integration("erp-a",db,claims())["health_status"]=="not_configured"

@pytest.mark.parametrize("who",[claims(),claims(tenant="company-b")])
def test_duplicate_connector_does_not_leave_partial_audit_or_poison_session(db,who):
    payload=api.IntegrationCreate(connector_key="erp",name="ERP",system_type="SAP");api.create_integration(payload,claims(),db)
    with pytest.raises(HTTPException) as error: api.create_integration(payload,who,db)
    assert error.value.status_code==409 and db.query(api._models()["Integration"]).count()==db.query(AuditLog).count()==1

def test_executive_database_metrics_use_correct_column_and_verified_scope(db):
    for who,count,cost,agents in [(claims(),2,12.5,3),(claims(tenant="company-b"),3,90,7),(claims(workspace="hr"),1,88,9)]:
        scope={key:who[key] for key in ("tenant_id","workspace_id")}
        db.add_all([LLMUsageLog(user_id="u",department="d",**scope) for _ in range(count)])
        db.add(AICostRecord(user_id="u",department="d",total_cost=cost,**scope));db.add(ExecutiveMetric(metric_key="active_agents",metric_value=agents,**scope))
    db.commit();result=api.executive_command_center(db,claims())["snapshot"]
    assert (result["total_queries"],result["total_cost"],result["active_agents"])==(2,12.5,3)

def test_executive_database_outage_is_not_reported_as_zero_usage(db):
    LLMUsageLog.__table__.drop(db.get_bind())
    with pytest.raises(HTTPException) as error: api.executive_command_center(db,claims())
    assert error.value.status_code==503 and "SELECT" not in error.value.detail and "sqlite" not in error.value.detail

@pytest.mark.parametrize("path",["coe/projects","coe/policies","coe/risks","coe/training","finops/usage","integrations","integrations/catalog","executive/command-center","audit-logs"])
@pytest.mark.asyncio
async def test_sensitive_http_routes_reject_missing_auth_before_database_access(path):
    app=FastAPI();app.include_router(api.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client: response=await client.get(f"/api/{path}")
    assert response.status_code==401

def test_additive_migration_preserves_legacy_data_and_is_repeatable(tmp_path):
    spec=importlib.util.spec_from_file_location("enterprise_scope_migration",Path(__file__).parents[2]/"alembic/versions/0009_enterprise_scope.py")
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=sa.create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with engine.begin() as conn:
        for table in migration.TABLES:
            conn.execute(sa.text(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY,payload TEXT NOT NULL)'))
            conn.execute(sa.text(f'INSERT INTO "{table}" VALUES (1,:payload)'),{"payload":"preserve original data"})
        with Operations.context(MigrationContext.configure(conn)): migration.upgrade();migration.upgrade()
        for table in migration.TABLES:
            assert conn.execute(sa.text(f'SELECT id,payload,tenant_id,workspace_id FROM "{table}"')).one()==(1,"preserve original data","default","default")
            assert {f"ix_{table}_tenant_id",f"ix_{table}_workspace_id"}<={i["name"] for i in sa.inspect(conn).get_indexes(table)}
        with pytest.raises(RuntimeError,match="discard enterprise ownership"):migration.downgrade()
    engine.dispose()

@pytest.mark.asyncio
async def test_verified_workspace_propagates_to_transaction_context(monkeypatch):
    monkeypatch.setattr(rbac,"_verify_with_keycloak_jwks_async",AsyncMock(return_value=claims()))
    contexts=(tenant_context,workspace_context,authorization_context);tokens=[context.set(None) for context in contexts]
    try:
        await rbac.verify_authorization("Bearer synthetic-unit-token")
        assert tenant_context.get()=="company-a" and workspace_context.get()=="finance"
        calls=[];connection=SimpleNamespace(dialect=SimpleNamespace(name="postgresql"),execute=lambda sql,params:calls.append((str(sql),params)))
        set_transaction_tenant(None,None,connection)
        assert calls==[("SELECT set_config('app.tenant_id', :tenant, true)",{"tenant":"company-a"}),("SELECT set_config('app.workspace_id', :workspace, true)",{"workspace":"finance"})]
    finally:
        for context,token in zip(contexts,tokens):context.reset(token)
