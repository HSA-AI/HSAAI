import importlib

import pytest


def _m():
    return importlib.import_module(
        "backend_core.intent_detection.service"
    )


class Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _install_client(
    monkeypatch,
    m,
    *,
    status=200,
    payload=None,
    exc=None,
):
    calls = []

    class Client:
        def __init__(self, *args, **kwargs):
            calls.append(("init", args, kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, **kwargs):
            calls.append(("post", url, kwargs))
            if exc:
                raise exc
            return Response(status, payload)

    monkeypatch.setattr(
        m.httpx,
        "Client",
        Client,
    )

    return calls


def test_keyword_score_unknown_exact_and_fuzzy():
    m = _m()

    assert m._keyword_score(
        "anything",
        "__missing__",
    ) == 0.0

    exact = m._keyword_score(
        "employee salary information",
        "hr_query",
    )

    fuzzy = m._keyword_score(
        "salry",
        "hr_query",
    )

    assert exact > 0
    assert fuzzy > 0
    assert exact <= 1.0
    assert fuzzy <= 1.0


def test_detect_intent_prefers_high_confidence_llm(
    monkeypatch,
):
    m = _m()

    expected = {
        "intent": "finance_query",
        "confidence": 0.95,
        "department": "finance",
        "method": "llm_classification",
    }

    monkeypatch.setattr(
        m,
        "_llm_classify",
        lambda query: expected,
    )

    assert m.detect_intent("anything") is expected


def test_detect_intent_keyword_and_default(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "_llm_classify",
        lambda query: None,
    )

    result = m.detect_intent(
        "employee salary leave benefits"
    )

    assert result["intent"] == "hr_query"
    assert result["method"] == "keyword_hybrid"
    assert result["department"] == "hr"
    assert result["confidence"] > 0

    monkeypatch.setattr(
        m,
        "_keyword_score",
        lambda query, key: 0.0,
    )

    result = m.detect_intent("unclassifiable")

    assert result["intent"] == "general_query"
    assert result["confidence"] == 0.3
    assert result["method"] == "default"


def test_intent_to_agent_all_paths(monkeypatch):
    m = _m()

    assert m.intent_to_agent("") == "general"
    assert m.intent_to_agent("hr_query") == "hr"

    custom = dict(m.INTENT_KEYWORDS)
    custom["custom_intent"] = {
        "department": "legal",
        "keywords": ["contract"],
    }

    monkeypatch.setattr(
        m,
        "INTENT_KEYWORDS",
        custom,
    )

    assert (
        m.intent_to_agent("custom_intent")
        == "legal"
    )
    assert (
        m.intent_to_agent("unknown_intent")
        == "general"
    )


def test_llm_classify_success_caps_confidence(
    monkeypatch,
):
    m = _m()

    calls = _install_client(
        monkeypatch,
        m,
        payload={
            "text": (
                'result {"intent":"finance_query",'
                '"confidence":1.7}'
            )
        },
    )

    result = m._llm_classify("invoice")

    assert result["intent"] == "finance_query"
    assert result["confidence"] == 1.0
    assert result["department"] == "finance"
    assert result["method"] == "llm_classification"

    post = [
        call
        for call in calls
        if call[0] == "post"
    ][0]

    assert post[2]["json"]["temperature"] == 0.0


@pytest.mark.parametrize(
    "status,payload",
    [
        (500, {"text": "ignored"}),
        (200, {"text": "no json response"}),
    ],
)
def test_llm_classify_nonusable_responses(
    monkeypatch,
    status,
    payload,
):
    m = _m()

    _install_client(
        monkeypatch,
        m,
        status=status,
        payload=payload,
    )

    assert m._llm_classify("query") is None


def test_llm_classify_exception_and_bad_json(
    monkeypatch,
):
    m = _m()

    _install_client(
        monkeypatch,
        m,
        exc=RuntimeError("gateway offline"),
    )

    assert m._llm_classify("query") is None

    _install_client(
        monkeypatch,
        m,
        payload={
            "text": '{"intent": bad-json}'
        },
    )

    assert m._llm_classify("query") is None
