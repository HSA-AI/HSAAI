import importlib.util
import json
import logging
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_NAME = "_hsaai_observability_init_test"


class FakeInstrument:
    def __init__(self):
        self.calls = []

    def add(self, *args, **kwargs):
        self.calls.append(("add", args, kwargs))

    def record(self, *args, **kwargs):
        self.calls.append(("record", args, kwargs))


class FakeMeter:
    def __init__(self):
        self.created = []

    def create_counter(self, name, *args, **kwargs):
        obj = FakeInstrument()
        obj.name = name
        self.created.append(obj)
        return obj

    def create_histogram(self, name, *args, **kwargs):
        obj = FakeInstrument()
        obj.name = name
        self.created.append(obj)
        return obj


class FakeTraceAPI:
    def __init__(self):
        self.current_span = None
        self.provider = None
        self.tracer_names = []

    def get_current_span(self):
        return self.current_span

    def set_tracer_provider(self, provider):
        self.provider = provider

    def get_tracer(self, name):
        self.tracer_names.append(name)
        return f"tracer:{name}"


class FakeMetricsAPI:
    def __init__(self):
        self.provider = None
        self.meters = []

    def get_meter(self, name):
        meter = FakeMeter()
        meter.name = name
        self.meters.append(meter)
        return meter

    def set_meter_provider(self, provider):
        self.provider = provider


class Resource:
    @classmethod
    def create(cls, attrs):
        return dict(attrs)


class TracerProvider:
    def __init__(self, resource=None):
        self.resource = resource
        self.processors = []

    def add_span_processor(self, processor):
        self.processors.append(processor)


class BatchSpanProcessor:
    def __init__(self, exporter):
        self.exporter = exporter


class MeterProvider:
    def __init__(self, resource=None, metric_readers=None):
        self.resource = resource
        self.metric_readers = list(metric_readers or [])


class PeriodicExportingMetricReader:
    def __init__(self, exporter, export_interval_millis=None):
        self.exporter = exporter
        self.export_interval_millis = export_interval_millis


class OTLPSpanExporter:
    def __init__(self, endpoint=None):
        self.endpoint = endpoint


class OTLPMetricExporter:
    def __init__(self, endpoint=None):
        self.endpoint = endpoint


class Instrumentor:
    calls = []

    def instrument(self, **kwargs):
        type(self).calls.append(kwargs)


def _module(name, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def _load():
    existing = sys.modules.get(MODULE_NAME)
    if existing is not None:
        return existing

    root = Path(__file__).resolve().parents[2]
    source = root / "packages/common/observability/__init__.py"

    fake_trace = FakeTraceAPI()
    fake_metrics = FakeMetricsAPI()

    modules = {
        "opentelemetry": _module(
            "opentelemetry",
            trace=fake_trace,
            metrics=fake_metrics,
        ),
        "opentelemetry.sdk": _module("opentelemetry.sdk"),
        "opentelemetry.sdk.trace": _module(
            "opentelemetry.sdk.trace",
            TracerProvider=TracerProvider,
        ),
        "opentelemetry.sdk.trace.export": _module(
            "opentelemetry.sdk.trace.export",
            BatchSpanProcessor=BatchSpanProcessor,
        ),
        "opentelemetry.sdk.resources": _module(
            "opentelemetry.sdk.resources",
            Resource=Resource,
        ),
        "opentelemetry.sdk.metrics": _module(
            "opentelemetry.sdk.metrics",
            MeterProvider=MeterProvider,
        ),
        "opentelemetry.sdk.metrics.export": _module(
            "opentelemetry.sdk.metrics.export",
            PeriodicExportingMetricReader=PeriodicExportingMetricReader,
        ),
        "opentelemetry.exporter": _module(
            "opentelemetry.exporter"
        ),
        "opentelemetry.exporter.otlp": _module(
            "opentelemetry.exporter.otlp"
        ),
        "opentelemetry.exporter.otlp.proto": _module(
            "opentelemetry.exporter.otlp.proto"
        ),
        "opentelemetry.exporter.otlp.proto.grpc": _module(
            "opentelemetry.exporter.otlp.proto.grpc"
        ),
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": _module(
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
            OTLPSpanExporter=OTLPSpanExporter,
        ),
        "opentelemetry.exporter.otlp.proto.grpc.metric_exporter": _module(
            "opentelemetry.exporter.otlp.proto.grpc.metric_exporter",
            OTLPMetricExporter=OTLPMetricExporter,
        ),
        "opentelemetry.instrumentation": _module(
            "opentelemetry.instrumentation"
        ),
        "opentelemetry.instrumentation.fastapi": _module(
            "opentelemetry.instrumentation.fastapi",
            FastAPIInstrumentor=Instrumentor,
        ),
        "opentelemetry.instrumentation.httpx": _module(
            "opentelemetry.instrumentation.httpx",
            HTTPXClientInstrumentor=Instrumentor,
        ),
        "opentelemetry.instrumentation.redis": _module(
            "opentelemetry.instrumentation.redis",
            RedisInstrumentor=Instrumentor,
        ),
        "opentelemetry.instrumentation.logging": _module(
            "opentelemetry.instrumentation.logging",
            LoggingInstrumentor=Instrumentor,
        ),
    }

    old = {
        name: sys.modules.get(name)
        for name in modules
    }

    sys.modules.update(modules)

    try:
        spec = importlib.util.spec_from_file_location(
            MODULE_NAME,
            source,
        )

        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load {source}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[MODULE_NAME] = module
        spec.loader.exec_module(module)

        module._fake_trace = fake_trace
        module._fake_metrics = fake_metrics

        return module

    finally:
        for name, previous in old.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def test_json_formatter_plain_extra_and_unserializable(monkeypatch):
    m = _load()

    monkeypatch.setenv("OTEL_SERVICE_NAME", "unit-service")
    monkeypatch.setenv("DEPLOY_ENV", "test")

    m._fake_trace.current_span = None

    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )

    record.custom = {"ok": True}
    record.unserializable = {1, 2}

    data = json.loads(
        m.JSONFormatter().format(record)
    )

    assert data["message"] == "hello world"
    assert data["service"] == "unit-service"
    assert data["environment"] == "test"
    assert data["trace_id"] == ""
    assert data["span_id"] == ""
    assert data["custom"] == {"ok": True}
    assert isinstance(data["unserializable"], str)


def test_json_formatter_trace_and_exception():
    m = _load()

    class Context:
        trace_id = 0x123
        span_id = 0x456

    class Span:
        def is_recording(self):
            return True

        def get_span_context(self):
            return Context()

    m._fake_trace.current_span = Span()

    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        "trace.logger",
        logging.ERROR,
        __file__,
        10,
        "failure",
        (),
        exc_info,
    )

    data = json.loads(
        m.JSONFormatter().format(record)
    )

    assert data["trace_id"].endswith("0123")
    assert data["span_id"].endswith("0456")
    assert "ValueError" in data["exception"]


def test_setup_logging(monkeypatch):
    m = _load()

    root = logging.getLogger()
    handler = logging.StreamHandler()

    old_handlers = list(root.handlers)
    root.handlers[:] = [handler]

    monkeypatch.setattr(
        logging,
        "basicConfig",
        lambda **kwargs: None,
    )

    try:
        m.setup_logging(
            "coverage-service",
            "DEBUG",
        )

        assert (
            sys.modules["os"].environ[
                "OTEL_SERVICE_NAME"
            ]
            == "coverage-service"
        )

        assert isinstance(
            handler.formatter,
            m.JSONFormatter,
        )
    finally:
        root.handlers[:] = old_handlers


def test_metrics_initialization_and_recording():
    m = _load()

    metrics = m.HSAAIMetrics("svc")

    metrics.record_request(
        "/health",
        0.25,
        200,
        "POST",
    )

    metrics.record_error(
        "ValueError",
        "/health",
    )

    metrics.record_llm_call(
        "model-a",
        42,
        1.5,
        cache_hit=True,
    )

    metrics.record_llm_call(
        "model-b",
        7,
        0.5,
        cache_hit=False,
    )

    metrics.record_agent_action(
        "agent-1",
        "search",
        True,
    )

    assert metrics.request_counter.calls
    assert metrics.request_duration.calls
    assert metrics.error_counter.calls
    assert metrics.llm_tokens_counter.calls
    assert metrics.llm_duration.calls
    assert metrics.cache_hits.calls
    assert metrics.cache_misses.calls
    assert metrics.agent_actions_counter.calls

    names = {
        item.name
        for item in metrics.meter.created
    }

    assert "hsaai_requests_total" in names
    assert "hsaai_db_query_seconds" in names


def test_setup_tracing_full_and_initialized_branch(monkeypatch):
    m = _load()

    m._initialized = False
    Instrumentor.calls.clear()

    monkeypatch.setenv(
        "SERVICE_VERSION",
        "9.9.9",
    )
    monkeypatch.setenv(
        "DEPLOY_ENV",
        "testing",
    )

    m.setup_tracing(
        "trace-service",
        "http://collector:4317",
    )

    provider = m._fake_trace.provider

    assert provider is not None
    assert (
        provider.resource["service.name"]
        == "trace-service"
    )
    assert (
        provider.resource["service.version"]
        == "9.9.9"
    )

    assert len(provider.processors) == 1

    exporter = (
        provider.processors[0].exporter
    )

    assert (
        exporter.endpoint
        == "http://collector:4317"
    )

    previous = m._fake_trace.provider

    m.setup_tracing(
        "second-service",
        "http://ignored",
    )

    assert m._fake_trace.provider is previous


def test_setup_metrics_provider():
    m = _load()

    m.setup_metrics_provider(
        "metrics-service",
        "http://metrics:4317",
    )

    provider = m._fake_metrics.provider

    assert provider is not None
    assert (
        provider.resource["service.name"]
        == "metrics-service"
    )

    reader = provider.metric_readers[0]

    assert (
        reader.export_interval_millis
        == 15000
    )

    assert (
        reader.exporter.endpoint
        == "http://metrics:4317"
    )


def test_setup_observability_and_helpers(monkeypatch):
    m = _load()

    calls = []

    monkeypatch.setattr(
        m,
        "setup_logging",
        lambda name: calls.append(
            ("logging", name)
        ),
    )

    monkeypatch.setattr(
        m,
        "setup_tracing",
        lambda name: calls.append(
            ("tracing", name)
        ),
    )

    monkeypatch.setattr(
        m,
        "setup_metrics_provider",
        lambda name: calls.append(
            ("metrics", name)
        ),
    )

    m.setup_observability("all-service")

    assert calls == [
        ("logging", "all-service"),
        ("tracing", "all-service"),
        ("metrics", "all-service"),
    ]

    obj = m.get_metrics("helper-service")
    assert isinstance(obj, m.HSAAIMetrics)

    tracer = m.get_tracer("abc")
    assert tracer == "tracer:abc"


@pytest.mark.asyncio
async def test_health_check_all_dependency_paths(monkeypatch):
    m = _load()

    class Response:
        def __init__(self, code):
            self.status_code = code

    class AsyncClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

        async def get(self, url):
            if "degraded" in url:
                return Response(503)
            return Response(200)

    httpx = types.ModuleType("httpx")
    httpx.AsyncClient = AsyncClient

    class RedisConnection:
        def ping(self):
            return True

    redis = types.ModuleType("redis")

    def from_url(url):
        if "broken" in url:
            raise RuntimeError(
                "redis unavailable"
            )
        return RedisConnection()

    redis.from_url = from_url

    class Connection:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    psycopg2 = types.ModuleType("psycopg2")
    psycopg2.connect = (
        lambda url, connect_timeout=2:
        Connection()
    )

    monkeypatch.setitem(
        sys.modules,
        "httpx",
        httpx,
    )
    monkeypatch.setitem(
        sys.modules,
        "redis",
        redis,
    )
    monkeypatch.setitem(
        sys.modules,
        "psycopg2",
        psycopg2,
    )

    result = await m.health_check(
        {
            "api": "http://healthy",
            "downstream": (
                "http://degraded"
            ),
            "redis": (
                "redis://localhost"
            ),
            "broken_redis": (
                "redis://broken"
            ),
            "postgres": (
                "postgres://db"
            ),
        }
    )

    assert result["status"] == "degraded"

    deps = result["dependencies"]

    assert deps["api"] == "ok"
    assert deps["downstream"] == "degraded"
    assert deps["redis"] == "ok"
    assert deps["postgres"] == "ok"

    assert deps[
        "broken_redis"
    ].startswith("error:")

    assert result["timestamp"]
