"""HSAAI APP-ANALYTICS — Enterprise AI Analytics Center Tests"""
from __future__ import annotations
import asyncio, sys
from pathlib import Path
from typing import Any
import pytest

_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.ai_operations.analytics_center import (  # noqa: E402
    AnalyticsMetric, AnalyticsSecurity, AnalyticsAssistant,
    EnterpriseAnalyticsEngine, PowerBIIntegration,
    get_analytics_engine, get_analytics_assistant, get_analytics_security, get_powerbi,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.ai_operations.analytics_center as mod
    mod._analytics_engine = None
    mod._powerbi = None
    mod._assistant = None
    mod._security = None
    yield


# ═══ EnterpriseAnalyticsEngine ═══
class TestAnalyticsEngine:
    def test_record_metric(self):
        engine = EnterpriseAnalyticsEngine()
        metric = AnalyticsMetric(metric_key="sales", metric_value=1500, category="finance", department_id="finance")
        result = engine.record_metric(metric)
        assert result["recorded"] is True

    def test_generate_insight(self):
        engine = EnterpriseAnalyticsEngine()
        result = engine.generate_insight(
            "Sales Decline", "Sales decreased 15% due to supply chain delays",
            category="finance", severity="warning", confidence=0.92,
        )
        assert result["title"] == "Sales Decline"
        assert result["severity"] == "warning"
        assert result["confidence_score"] == 0.92

    def test_detect_trend_growth(self):
        engine = EnterpriseAnalyticsEngine()
        for v in [100, 110, 120, 130, 140]:
            engine.record_metric(AnalyticsMetric(metric_key="revenue", metric_value=v, category="finance"))
        result = engine.detect_trend("revenue", category="finance")
        assert result["trend"] == "growth"

    def test_detect_trend_decline(self):
        engine = EnterpriseAnalyticsEngine()
        for v in [200, 180, 160, 140, 120]:
            engine.record_metric(AnalyticsMetric(metric_key="orders", metric_value=v, category="sales"))
        result = engine.detect_trend("orders", category="sales")
        assert result["trend"] == "decline"

    def test_detect_trend_stable(self):
        engine = EnterpriseAnalyticsEngine()
        for v in [100, 101, 100, 101, 100]:
            engine.record_metric(AnalyticsMetric(metric_key="visitors", metric_value=v, category="web"))
        result = engine.detect_trend("visitors", category="web")
        assert result["trend"] == "stable"

    def test_detect_trend_insufficient_data(self):
        engine = EnterpriseAnalyticsEngine()
        engine.record_metric(AnalyticsMetric(metric_key="test", metric_value=100))
        result = engine.detect_trend("test")
        assert result["trend"] == "insufficient_data"

    def test_detect_anomaly_critical(self):
        engine = EnterpriseAnalyticsEngine()
        result = engine.detect_anomaly("cost", actual_value=200, expected_value=100)
        assert result["severity"] == "critical"
        assert result["deviation_score"] == 1.0

    def test_detect_anomaly_low(self):
        engine = EnterpriseAnalyticsEngine()
        result = engine.detect_anomaly("latency", actual_value=105, expected_value=100)
        assert result["severity"] == "low"

    def test_predict_forecast(self):
        engine = EnterpriseAnalyticsEngine()
        for v in [100, 105, 110, 115, 120]:
            engine.record_metric(AnalyticsMetric(metric_key="users", metric_value=v, category="platform"))
        result = engine.predict_forecast("users", horizon_hours=24, category="platform")
        assert result["forecasted_value"] > 120
        assert result["trend"] == "increasing"

    def test_predict_forecast_insufficient_data(self):
        engine = EnterpriseAnalyticsEngine()
        result = engine.predict_forecast("unknown")
        assert result["status"] == "insufficient_data"

    def test_get_insights_filtered(self):
        engine = EnterpriseAnalyticsEngine()
        engine.generate_insight("Test1", "desc1", severity="warning")
        engine.generate_insight("Test2", "desc2", severity="critical")
        warnings = engine.get_insights(severity="warning")
        assert len(warnings) == 1

    def test_get_anomalies_filtered(self):
        engine = EnterpriseAnalyticsEngine()
        engine.detect_anomaly("m1", actual_value=200, expected_value=100)
        engine.detect_anomaly("m2", actual_value=101, expected_value=100)
        critical = engine.get_anomalies(severity="critical")
        assert len(critical) == 1

    def test_get_stats(self):
        engine = EnterpriseAnalyticsEngine()
        engine.generate_insight("Test", "desc")
        engine.detect_anomaly("m", actual_value=200, expected_value=100)
        stats = engine.get_stats()
        assert stats["total_insights"] == 1
        assert stats["total_anomalies"] == 1

    def test_singleton(self):
        assert get_analytics_engine() is get_analytics_engine()


# ═══ PowerBIIntegration ═══
class TestPowerBIIntegration:
    def test_register_report(self):
        pbi = PowerBIIntegration()
        result = pbi.register_report("rpt-1", title="Sales Report", powerbi_report_id="pb-123")
        assert result["report_id"] == "rpt-1"

    def test_generate_embed_token_authorized(self):
        pbi = PowerBIIntegration()
        pbi.register_report("rpt-1", title="Sales", powerbi_report_id="pb-123",
                             permissions={"roles": ["EXECUTIVE", "ANALYTICS_ADMIN"]})
        result = pbi.generate_embed_token("rpt-1", user_id="user-1", user_role="EXECUTIVE")
        assert result["token"] is not None
        assert result["powerbi_report_id"] == "pb-123"

    def test_generate_embed_token_unauthorized(self):
        pbi = PowerBIIntegration()
        pbi.register_report("rpt-1", title="Sales", powerbi_report_id="pb-123",
                             permissions={"roles": ["EXECUTIVE"]})
        result = pbi.generate_embed_token("rpt-1", user_id="user-1", user_role="VIEWER")
        assert result["token"] is None
        assert "Insufficient" in result["error"]

    def test_generate_embed_token_unknown_report(self):
        pbi = PowerBIIntegration()
        result = pbi.generate_embed_token("unknown", user_id="u", user_role="EXECUTIVE")
        assert result["token"] is None

    def test_validate_token(self):
        pbi = PowerBIIntegration()
        pbi.register_report("rpt-1", title="Test", powerbi_report_id="pb-1",
                             permissions={"roles": ["EXECUTIVE"]})
        token_info = pbi.generate_embed_token("rpt-1", user_id="u", user_role="EXECUTIVE")
        validated = pbi.validate_token(token_info["token"])
        assert validated is not None
        assert validated["user_id"] == "u"

    def test_validate_token_invalid(self):
        pbi = PowerBIIntegration()
        assert pbi.validate_token("invalid") is None

    def test_revoke_token(self):
        pbi = PowerBIIntegration()
        pbi.register_report("rpt-1", title="Test", powerbi_report_id="pb-1",
                             permissions={"roles": ["EXECUTIVE"]})
        token_info = pbi.generate_embed_token("rpt-1", user_id="u", user_role="EXECUTIVE")
        assert pbi.revoke_token(token_info["token"]) is True
        assert pbi.validate_token(token_info["token"]) is None

    def test_access_log(self):
        pbi = PowerBIIntegration()
        pbi.register_report("rpt-1", title="Test", powerbi_report_id="pb-1",
                             permissions={"roles": ["EXECUTIVE"]})
        pbi.generate_embed_token("rpt-1", user_id="u", user_role="EXECUTIVE")
        log = pbi.get_access_log()
        assert len(log) == 1

    def test_singleton(self):
        assert get_powerbi() is get_powerbi()


# ═══ AnalyticsAssistant ═══
class TestAnalyticsAssistant:
    @pytest.mark.asyncio
    async def test_ask_performance_query(self):
        engine = EnterpriseAnalyticsEngine()
        assistant = AnalyticsAssistant(engine)
        result = await assistant.ask("ما حالة الأداء؟", user_id="u1", user_role="EXECUTIVE")
        assert result["intent"] == "performance_query"
        assert "answer" in result

    @pytest.mark.asyncio
    async def test_ask_risk_query(self):
        engine = EnterpriseAnalyticsEngine()
        engine.detect_anomaly("cost", actual_value=200, expected_value=100)
        assistant = AnalyticsAssistant(engine)
        result = await assistant.ask("ما أهم المخاطر؟", user_id="u1", user_role="EXECUTIVE")
        assert result["intent"] == "risk_query"

    @pytest.mark.asyncio
    async def test_ask_trend_query(self):
        engine = EnterpriseAnalyticsEngine()
        for v in [100, 110, 120]:
            engine.record_metric(AnalyticsMetric(metric_key="revenue", metric_value=v, category="finance"))
        engine.detect_trend("revenue", category="finance")
        assistant = AnalyticsAssistant(engine)
        result = await assistant.ask("ما الاتجاهات؟", user_id="u1", user_role="ANALYST")
        assert result["intent"] == "trend_query"

    @pytest.mark.asyncio
    async def test_ask_insight_query(self):
        engine = EnterpriseAnalyticsEngine()
        engine.generate_insight("Test", "description")
        assistant = AnalyticsAssistant(engine)
        result = await assistant.ask("اعرض الرؤى", user_id="u1", user_role="ANALYST")
        assert result["intent"] in ("insight_query", "unknown")

    @pytest.mark.asyncio
    async def test_ask_unknown_query(self):
        engine = EnterpriseAnalyticsEngine()
        assistant = AnalyticsAssistant(engine)
        result = await assistant.ask("كم سعر المنزل؟", user_id="u1", user_role="VIEWER")
        assert result["intent"] == "unknown"

    @pytest.mark.asyncio
    async def test_conversations_recorded(self):
        engine = EnterpriseAnalyticsEngine()
        assistant = AnalyticsAssistant(engine)
        await assistant.ask("الأداء", user_id="u1", user_role="EXECUTIVE")
        await assistant.ask("المخاطر", user_id="u1", user_role="EXECUTIVE")
        assert len(assistant.get_conversations()) == 2

    def test_singleton(self):
        assert get_analytics_assistant() is get_analytics_assistant()


# ═══ AnalyticsSecurity ═══
class TestAnalyticsSecurity:
    def test_check_permission_executive(self):
        sec = AnalyticsSecurity()
        assert sec.check_permission("EXECUTIVE", "analytics:view") is True
        assert sec.check_permission("EXECUTIVE", "analytics:admin") is True

    def test_check_permission_viewer(self):
        sec = AnalyticsSecurity()
        assert sec.check_permission("VIEWER", "analytics:view") is True
        assert sec.check_permission("VIEWER", "analytics:query") is False

    def test_check_permission_unknown_role(self):
        sec = AnalyticsSecurity()
        assert sec.check_permission("UNKNOWN", "analytics:view") is False

    def test_check_department_access_executive(self):
        sec = AnalyticsSecurity()
        assert sec.check_department_access("EXECUTIVE", "finance", "hr") is True

    def test_check_department_access_manager(self):
        sec = AnalyticsSecurity()
        assert sec.check_department_access("DEPARTMENT_MANAGER", "finance", "finance") is True
        assert sec.check_department_access("DEPARTMENT_MANAGER", "finance", "hr") is False

    def test_get_rls_policy(self):
        sec = AnalyticsSecurity()
        policy = sec.get_rls_policy("analytics_metrics")
        assert "ROW LEVEL SECURITY" in policy
        assert "tenant_id" in policy
        assert "department_id" in policy

    def test_get_roles(self):
        sec = AnalyticsSecurity()
        roles = sec.get_roles()
        assert "EXECUTIVE" in roles
        assert "VIEWER" in roles
        assert len(roles) == 5

    def test_log_access(self):
        sec = AnalyticsSecurity()
        sec.log_access(user_id="u1", action="view", resource="dashboard", success=True)
        log = sec.get_access_log()
        assert len(log) == 1

    def test_singleton(self):
        assert get_analytics_security() is get_analytics_security()
