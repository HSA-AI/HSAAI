import importlib.util
import json
import logging
import sys
import types
from pathlib import Path


_MODULE_NAME = "_hsaai_test_observability_logging"


def _m():
    """
    Load logging.py directly for isolated unit testing.

    Termux does not have the full OpenTelemetry dependency stack installed.
    Importing common.observability.logging normally executes the package
    common.observability.__init__ first, which requires OpenTelemetry.

    Loading this production source file directly avoids changing production
    code or weakening dependencies while still executing the real logging.py.
    Coverage is attributed to the source file path.
    """
    existing = sys.modules.get(_MODULE_NAME)
    if existing is not None:
        return existing

    repo_root = Path(__file__).resolve().parents[2]
    source = (
        repo_root
        / "packages"
        / "common"
        / "observability"
        / "logging.py"
    )

    spec = importlib.util.spec_from_file_location(
        _MODULE_NAME,
        source,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Unable to load observability logging module: {source}"
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)

    return module


def _install_otel(monkeypatch, recording=True):
    class Ctx:
        trace_id = 0x123456789ABCDEF
        span_id = 0x1234
        trace_flags = 1

    class Span:
        def is_recording(self):
            return recording

        def get_span_context(self):
            return Ctx()

    trace_mod = types.ModuleType("opentelemetry.trace")
    trace_mod.get_current_span = lambda: Span()

    otel_mod = types.ModuleType("opentelemetry")
    otel_mod.trace = trace_mod

    monkeypatch.setitem(sys.modules, "opentelemetry", otel_mod)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", trace_mod)


def _record(level=logging.INFO, msg="hello"):
    return logging.LogRecord(
        "unit.logger",
        level,
        __file__,
        10,
        msg,
        (),
        None,
    )


def test_json_formatter_context_trace_extra_and_exception(monkeypatch):
    m = _m()
    m.clear_request_context()
    m.set_request_context(
        request_id="request-123456",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        correlation_id="corr-a",
    )
    _install_otel(monkeypatch)

    record = _record(logging.ERROR, "failure")
    record.hsaai_extra = {"custom": "value"}

    try:
        raise ValueError("broken")
    except ValueError:
        record.exc_info = sys.exc_info()

    data = json.loads(m.HSAAIJsonFormatter().format(record))

    assert data["message"] == "failure"
    assert data["request_id"] == "request-123456"
    assert data["tenant_id"] == "tenant-a"
    assert data["workspace_id"] == "workspace-a"
    assert data["correlation_id"] == "corr-a"
    assert data["trace_id"]
    assert data["span_id"]
    assert data["trace_flags"] == "01"
    assert data["custom"] == "value"
    assert data["exception"]["type"] == "ValueError"
    assert data["exception"]["message"] == "broken"

    m.clear_request_context()


def test_json_formatter_without_optional_context(monkeypatch):
    m = _m()
    m.clear_request_context()
    _install_otel(monkeypatch, recording=False)

    data = json.loads(
        m.HSAAIJsonFormatter().format(
            _record(msg="plain")
        )
    )

    assert data["message"] == "plain"
    assert "request_id" not in data
    assert "trace_id" not in data


def test_text_formatter_request_trace_and_exception(monkeypatch):
    m = _m()
    m.clear_request_context()
    m.set_request_context(request_id="abcdefgh-123")
    _install_otel(monkeypatch)

    record = _record(logging.ERROR, "text failure")

    try:
        raise RuntimeError("boom")
    except RuntimeError:
        record.exc_info = sys.exc_info()

    text = m.HSAAITextFormatter().format(record)

    assert "[req=abcdefgh]" in text
    assert "[trace=" in text
    assert "text failure" in text
    assert "RuntimeError: boom" in text

    m.clear_request_context()


def test_setup_logging_json_and_text(monkeypatch):
    m = _m()
    root = logging.getLogger()

    old_handlers = root.handlers[:]
    old_level = root.level

    noisy_names = (
        "uvicorn.access",
        "httpx",
        "httpcore",
        "sqlalchemy.engine",
    )
    old_noisy = {
        name: logging.getLogger(name).level
        for name in noisy_names
    }
    old_hsaai = logging.getLogger("hsaai").level

    try:
        monkeypatch.setattr(m, "LOG_LEVEL", "DEBUG")
        monkeypatch.setattr(m, "LOG_FORMAT", "json")

        m.setup_logging("unit-service")

        assert len(root.handlers) == 1
        assert isinstance(
            root.handlers[0].formatter,
            m.HSAAIJsonFormatter,
        )
        assert root.level == logging.DEBUG

        for name in noisy_names:
            assert logging.getLogger(name).level == logging.WARNING

        monkeypatch.setattr(m, "LOG_FORMAT", "text")
        m.setup_logging()

        assert len(root.handlers) == 1
        assert isinstance(
            root.handlers[0].formatter,
            m.HSAAITextFormatter,
        )

    finally:
        root.handlers[:] = old_handlers
        root.setLevel(old_level)
        for name, level in old_noisy.items():
            logging.getLogger(name).setLevel(level)
        logging.getLogger("hsaai").setLevel(old_hsaai)


def test_request_context_helpers():
    m = _m()
    m.clear_request_context()

    rid = m.new_request_id()

    assert rid
    assert m.request_id_var.get() == rid

    m.set_request_context(
        tenant_id="t1",
        workspace_id="w1",
        correlation_id="c1",
    )

    assert m.tenant_id_var.get() == "t1"
    assert m.workspace_id_var.get() == "w1"
    assert m.correlation_id_var.get() == "c1"

    m.clear_request_context()

    assert m.request_id_var.get() == ""
    assert m.tenant_id_var.get() == ""
    assert m.workspace_id_var.get() == ""
    assert m.correlation_id_var.get() == ""
