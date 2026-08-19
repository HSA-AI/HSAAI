"""
HSAAI Phase 12 Tests — Observability Stack
============================================
Tests structured logging, metrics, SLO definitions, health checks.
"""
import pytest
import json
import logging
from packages.common.observability import (
    JSONFormatter, setup_logging, HSAAIMetrics, SLO_DEFINITIONS,
    health_check,
)


class TestJSONFormatter:
    def test_format_basic_record(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1,
            msg="Hello %s", args=("world",), exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "Hello world"
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert "timestamp" in data
        assert "service" in data

    def test_format_with_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test", level=logging.ERROR, pathname="test.py", lineno=1,
                msg="Failed", args=(), exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert "ValueError" in data["exception"]

    def test_format_includes_extra_fields(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1,
            msg="test", args=(), exc_info=None,
        )
        record.user_id = "u123"
        record.tenant_id = "t1"
        output = formatter.format(record)
        data = json.loads(output)
        assert data["user_id"] == "u123"
        assert data["tenant_id"] == "t1"


class TestSLODefinitions:
    def test_api_gateway_slo_defined(self):
        assert "api_gateway" in SLO_DEFINITIONS
        slo = SLO_DEFINITIONS["api_gateway"]
        assert slo["availability"]["target"] == 0.999
        assert slo["latency_p99"]["target_ms"] == 500

    def test_llm_gateway_slo_defined(self):
        slo = SLO_DEFINITIONS["llm_gateway"]
        assert slo["latency_p99"]["target_ms"] == 5000  # LLM is slower
        assert slo["cache_hit_rate"]["target"] == 0.30

    def test_all_services_have_availability_slo(self):
        for svc, slos in SLO_DEFINITIONS.items():
            assert "availability" in slos, f"{svc} missing availability SLO"
            assert slos["availability"]["target"] >= 0.99


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_no_deps(self):
        result = await health_check({})
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_check_with_bad_url(self):
        result = await health_check({"bad": "http://nonexistent:9999/health"})
        assert result["status"] == "degraded"
        assert "bad" in result["dependencies"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-cov"])
