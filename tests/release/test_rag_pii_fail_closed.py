"""RAG upload security regressions: PII decisions must fail closed."""

import io
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException, UploadFile


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario,expected_status",
    [
        ("blocked", 422),
        ("detector_503", 503),
        ("network_failure", 503),
        ("invalid_decision", 503),
        ("missing_redaction", 503),
    ],
)
async def test_pii_rejection_never_persists_document(
    monkeypatch, tmp_path, scenario, expected_status
):
    from rag_engine import main as rag

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Storage, embedding, or indexing reached after PII failure"
        )

    monkeypatch.setenv("USE_OBJECT_STORAGE", "false")
    monkeypatch.setattr(rag, "STORAGE", tmp_path)
    monkeypatch.setattr(rag, "_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(rag, "get_qdrant", forbidden)
    monkeypatch.setattr(rag, "chunk_text_advanced", forbidden)

    monkeypatch.setattr(
        rag,
        "extract_text_with_metadata",
        lambda *args, **kwargs: {
            "text": "Security regression fixture",
            "page_map": [],
        },
    )

    url = "http://pii_detector:8092/v1/pii/check-document"
    request = httpx.Request("POST", url)

    responses = {
        "blocked": httpx.Response(
            200,
            request=request,
            json={
                "decision": "block",
                "risk_level": "critical",
                "pii_types": ["CREDIT_CARD"],
            },
        ),
        "detector_503": httpx.Response(
            503,
            request=request,
            json={"detail": "Unavailable"},
        ),
        "invalid_decision": httpx.Response(
            200,
            request=request,
            json={
                "decision": "unknown",
                "risk_level": "none",
            },
        ),
        "missing_redaction": httpx.Response(
            200,
            request=request,
            json={
                "decision": "warn",
                "risk_level": "high",
                "redacted_text": None,
            },
        ),
    }

    calls = []

    class FakePIIClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, target, **kwargs):
            calls.append((target, kwargs))

            if scenario == "network_failure":
                raise httpx.ConnectError(
                    "Simulated detector outage",
                    request=request,
                )

            return responses[scenario]

    monkeypatch.setattr(
        rag.httpx,
        "AsyncClient",
        FakePIIClient,
    )

    claims = {
        "sub": "ci-test-user",
        "tenant_id": "verified-tenant",
        "workspace_id": "verified-workspace",
    }

    fake_request = SimpleNamespace(
        state=SimpleNamespace(claims=claims)
    )

    # Test-only context sentinel, not a real Keycloak credential.
    context = rag.authorization_context.set(
        "Bearer CI_TEST_ONLY_SENTINEL"
    )

    try:
        with pytest.raises(HTTPException) as error:
            await rag.upload_document(
                request=fake_request,
                file=UploadFile(
                    file=io.BytesIO(
                        b"Security regression fixture"
                    ),
                    filename="security-fixture.txt",
                ),
                tenant_id="forged-tenant",
                workspace_id="forged-workspace",
            )
    finally:
        rag.authorization_context.reset(context)

    assert error.value.status_code == expected_status
    assert len(calls) == 1

    target, kwargs = calls[0]

    assert target == url
    assert kwargs["headers"]["Authorization"] == (
        "Bearer CI_TEST_ONLY_SENTINEL"
    )

    assert kwargs["json"]["tenant_id"] == "verified-tenant"
    assert kwargs["json"]["workspace_id"] == "verified-workspace"

    # No local document should remain after rejection.
    assert not any(tmp_path.rglob("*"))
