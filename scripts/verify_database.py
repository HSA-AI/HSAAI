#!/usr/bin/env python3
"""Run with the restricted runtime role on a dedicated acceptance PostgreSQL DB.
All probe rows are rolled back. Existing data is not modified.
"""
import json,uuid
from sqlalchemy import inspect,text
from sqlalchemy.exc import DBAPIError
from backend_core.db.database import engine,Base,import_all_models,run_migrations
from model_training.db.models import Base as TrainingBase

def main():
    if engine.dialect.name!='postgresql':raise RuntimeError('PostgreSQL required')
    run_migrations();import_all_models();tables={**Base.metadata.tables,**TrainingBase.metadata.tables};inspector=inspect(engine)
    for name,table in tables.items():
        assert name in inspector.get_table_names(),'Missing table: '+name
        assert set(table.columns.keys())<={c['name'] for c in inspector.get_columns(name)},'Missing columns: '+name
    tenant_a,tenant_b='acceptance-'+uuid.uuid4().hex,'acceptance-'+uuid.uuid4().hex
    with engine.connect() as conn:
        tx=conn.begin()
        try:
            assert not any(conn.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()),'Unsafe runtime role'
            protected=dict(conn.execute(text("SELECT relname,relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace")).all())
            for name,table in tables.items():
                if 'tenant_id' in table.columns:assert protected.get(name),'Missing RLS: '+name
            conn.execute(text("SELECT set_config('app.tenant_id',:tenant,true)"),{'tenant':tenant_a})
            sql=text('INSERT INTO messages (tenant_id,workspace_id,"user",role,message) VALUES (:tenant,\'release-test\',\'acceptance\',\'user\',\'Temporary RLS test\')')
            conn.execute(sql,{'tenant':tenant_a})
            conn.execute(text("SELECT set_config('app.tenant_id',:tenant,true)"),{'tenant':tenant_b})
            assert conn.execute(text('SELECT count(*) FROM messages WHERE tenant_id=:tenant'),{'tenant':tenant_a}).scalar()==0
            sp=conn.begin_nested()
            try:conn.execute(sql,{'tenant':tenant_a})
            except DBAPIError:sp.rollback()
            else:sp.rollback();raise AssertionError('Cross-tenant insert allowed')
            conn.execute(text("SELECT set_config('app.tenant_id','',true)"))
            assert conn.execute(text('SELECT count(*) FROM messages WHERE tenant_id=:tenant'),{'tenant':tenant_a}).scalar()==0
        finally:tx.rollback()
    print(json.dumps({'schema_tables':len(tables),'runtime_role':'restricted','cross_tenant_read':'denied','cross_tenant_write':'denied','missing_tenant':'denied','test_rows':'rolled back'}))
if __name__=='__main__':main()
