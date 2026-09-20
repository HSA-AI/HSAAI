import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services'))
os.environ.setdefault('POSTGRES_DSN', 'sqlite:///./test_maturity.db')
os.environ.setdefault('ALLOW_DEV_RBAC', 'true')

from backend_core.maturity_upgrade.agent_orchestration import agent_orchestrator
from backend_core.maturity_upgrade.workflow_runtime import workflow_engine, WORKFLOW_TEMPLATES
from backend_core.maturity_upgrade.connectors_runtime import ADVANCED_CONNECTOR_CAPABILITIES
from backend_core.maturity_upgrade.observability import observability_service
from backend_core.maturity_upgrade.schemas import AgentRouteRequest, WorkflowStartRequest, ObservabilityEventIn
from backend_core.db.database import Base, engine, SessionLocal


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_supervisor_routes_finance_request():
    db = SessionLocal()
    try:
        result = agent_orchestrator.route(db, AgentRouteRequest(message='أريد تحليل المشتريات والمخزون لهذا الشهر', roles=['department_manager']))
        assert result['selected_agent'] == 'finance'
        assert 'sap_s4hana' in result['required_connectors']
    finally:
        db.close()


def test_workflow_templates_include_required_business_flows():
    assert {'purchase_request', 'document_review', 'leave_request', 'support_ticket'}.issubset(set(WORKFLOW_TEMPLATES.keys()))


def test_start_purchase_workflow():
    db = SessionLocal()
    try:
        result = workflow_engine.start(db, WorkflowStartRequest(template_key='purchase_request', title='طلب شراء تجريبي', requested_by='tester'))
        assert result['status'] == 'running'
        assert 'sap_check' in result['steps']
    finally:
        db.close()


def test_connector_runtime_capabilities_are_advanced():
    assert 'circuit_breaker' in ADVANCED_CONNECTOR_CAPABILITIES['runtime']
    assert 'incremental' in ADVANCED_CONNECTOR_CAPABILITIES['sync_modes']


def test_observability_records_model_usage():
    db = SessionLocal()
    try:
        observability_service.record(db, ObservabilityEventIn(event_type='model', component='llm_gateway', model='qwen3', tokens=120, latency_ms=80))
        dashboard = observability_service.dashboard(db, 'default', 'default')
        assert dashboard['executive_summary']['tokens'] >= 120
    finally:
        db.close()
