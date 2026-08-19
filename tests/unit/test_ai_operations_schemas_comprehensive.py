"""
HSAAI Enterprise AI Platform — AI Operations Schemas Test Suite (v7.0)
========================================================================
Comprehensive tests for `services/backend_core/ai_operations/schemas.py`.

Coverage targets:
  - RuntimeProvider (Literal type, status default, active_models default)
  - ModelDeployment (Literal status, no defaults — all required)
  - GpuNode (5 required float fields)

Test categories: positive, negative, boundary, validation, serialization, defaults, edge cases.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

_BASE = Path(__file__).resolve().parents[2]
for _p in [str(_BASE / "services"), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.ai_operations.schemas import (  # noqa: E402
    GpuNode,
    ModelDeployment,
    RuntimeProvider,
)


# ═══════════════════════════════════════════════════════════════════════
# RuntimeProvider
# ═══════════════════════════════════════════════════════════════════════
class TestRuntimeProvider:
    """Tests for RuntimeProvider — provider with status and active_models defaults."""

    @pytest.mark.parametrize("provider_type", ["ollama", "vllm", "gpu_server", "local"])
    def test_positive_all_type_values_accepted(self, provider_type: str):
        """All 4 documented Literal type values accepted."""
        p = RuntimeProvider(id="p1", name="P", type=provider_type, endpoint="http://e")
        assert p.type == provider_type

    def test_default_values(self):
        """status defaults to 'healthy', active_models defaults to 0."""
        p = RuntimeProvider(id="p1", name="P", type="ollama", endpoint="http://e")
        assert p.status == "healthy"
        assert p.active_models == 0

    @pytest.mark.parametrize("status", ["healthy", "degraded", "offline"])
    def test_positive_all_status_values(self, status: str):
        p = RuntimeProvider(id="p1", name="P", type="ollama", endpoint="http://e", status=status)
        assert p.status == status

    def test_negative_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            RuntimeProvider(id="p", name="P", type="invalid", endpoint="http://e")  # type: ignore[arg-type]

    def test_negative_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            RuntimeProvider(id="p", name="P", type="ollama", endpoint="http://e", status="unknown")  # type: ignore[arg-type]

    @pytest.mark.parametrize("missing_field", ["id", "name", "type", "endpoint"])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {"id": "p", "name": "P", "type": "ollama", "endpoint": "http://e"}
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            RuntimeProvider(**kwargs)  # type: ignore[arg-type]

    def test_default_active_models_zero(self):
        p = RuntimeProvider(id="p", name="P", type="ollama", endpoint="http://e")
        assert p.active_models == 0

    def test_active_models_accepts_positive_int(self):
        p = RuntimeProvider(id="p", name="P", type="vllm", endpoint="http://e", active_models=5)
        assert p.active_models == 5

    def test_boundary_active_models_zero(self):
        p = RuntimeProvider(id="p", name="P", type="ollama", endpoint="http://e", active_models=0)
        assert p.active_models == 0

    def test_serialization_roundtrip(self):
        p = RuntimeProvider(id="p1", name="Ollama", type="ollama", endpoint="http://ollama:11434",
                            status="degraded", active_models=3)
        dumped = p.model_dump()
        assert dumped["type"] == "ollama"
        assert dumped["active_models"] == 3
        assert RuntimeProvider(**dumped) == p

    def test_boundary_empty_endpoint(self):
        """Empty endpoint string is accepted by str type."""
        p = RuntimeProvider(id="p", name="P", type="local", endpoint="")
        assert p.endpoint == ""


# ═══════════════════════════════════════════════════════════════════════
# ModelDeployment
# ═══════════════════════════════════════════════════════════════════════
class TestModelDeployment:
    """Tests for ModelDeployment — all fields required, Literal status."""

    @pytest.mark.parametrize("status", ["running", "deploying", "failed", "stopped"])
    def test_positive_all_status_values(self, status: str):
        d = ModelDeployment(id="d1", model_name="qwen", version="1.0", provider="ollama",
                            status=status, latency_ms=100, requests_per_minute=10)
        assert d.status == status

    def test_negative_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            ModelDeployment(id="d", model_name="m", version="v", provider="p",
                            status="unknown", latency_ms=100, requests_per_minute=10)  # type: ignore[arg-type]

    @pytest.mark.parametrize("missing_field", ["id", "model_name", "version", "provider",
                                                 "status", "latency_ms", "requests_per_minute"])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {"id": "d", "model_name": "m", "version": "v", "provider": "p",
                  "status": "running", "latency_ms": 100, "requests_per_minute": 10}
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            ModelDeployment(**kwargs)  # type: ignore[arg-type]

    def test_positive_full_payload(self):
        d = ModelDeployment(id="d1", model_name="qwen2.5", version="1.0.0", provider="vllm",
                            status="running", latency_ms=234, requests_per_minute=120)
        assert d.model_name == "qwen2.5"
        assert d.latency_ms == 234
        assert d.requests_per_minute == 120

    def test_boundary_latency_zero(self):
        d = ModelDeployment(id="d", model_name="m", version="v", provider="p",
                            status="running", latency_ms=0, requests_per_minute=10)
        assert d.latency_ms == 0

    def test_boundary_rpm_zero(self):
        d = ModelDeployment(id="d", model_name="m", version="v", provider="p",
                            status="stopped", latency_ms=0, requests_per_minute=0)
        assert d.requests_per_minute == 0

    def test_serialization_roundtrip(self):
        d = ModelDeployment(id="d1", model_name="m", version="v", provider="p",
                            status="deploying", latency_ms=500, requests_per_minute=0)
        dumped = d.model_dump()
        assert ModelDeployment(**dumped) == d


# ═══════════════════════════════════════════════════════════════════════
# GpuNode
# ═══════════════════════════════════════════════════════════════════════
class TestGpuNode:
    """Tests for GpuNode — 5 required float fields."""

    def test_positive_full_payload(self):
        n = GpuNode(id="gpu1", name="A100", usage_percent=75.5, vram_percent=60.0,
                    temperature_c=70.5, power_watts=350.2)
        assert n.usage_percent == 75.5
        assert n.temperature_c == 70.5
        assert n.power_watts == 350.2

    @pytest.mark.parametrize("missing_field", ["id", "name", "usage_percent",
                                                 "vram_percent", "temperature_c", "power_watts"])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {"id": "g", "name": "G", "usage_percent": 50.0, "vram_percent": 50.0,
                  "temperature_c": 50.0, "power_watts": 200.0}
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            GpuNode(**kwargs)  # type: ignore[arg-type]

    def test_boundary_zero_values(self):
        """All float fields accept 0.0."""
        n = GpuNode(id="g", name="G", usage_percent=0.0, vram_percent=0.0,
                    temperature_c=0.0, power_watts=0.0)
        assert n.usage_percent == 0.0

    def test_boundary_max_values(self):
        """High values accepted (no upper bound constraint in schema)."""
        n = GpuNode(id="g", name="G", usage_percent=100.0, vram_percent=100.0,
                    temperature_c=100.0, power_watts=500.0)
        assert n.usage_percent == 100.0

    def test_int_coerced_to_float(self):
        """Pydantic v2 coerces int to float for float fields."""
        n = GpuNode(id="g", name="G", usage_percent=50, vram_percent=40,
                    temperature_c=60, power_watts=200)  # type: ignore[arg-type]
        assert n.usage_percent == 50.0
        assert isinstance(n.usage_percent, float)

    def test_negative_string_rejected(self):
        """Non-numeric string for float field raises (non-coercible)."""
        with pytest.raises(ValidationError):
            GpuNode(id="g", name="G", usage_percent="not_a_number",  # type: ignore[arg-type]
                    vram_percent=50.0, temperature_c=50.0, power_watts=200.0)

    def test_serialization_roundtrip(self):
        n = GpuNode(id="g1", name="A100", usage_percent=80.5, vram_percent=65.0,
                    temperature_c=72.0, power_watts=340.5)
        dumped = n.model_dump()
        assert GpuNode(**dumped) == n
