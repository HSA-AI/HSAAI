
"""Regression tests for document metadata ACL enforcement."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from rag_engine import main


@pytest.mark.parametrize(
    "acl,subject,roles,expected",
    [
        (
            {
                "visibility": "restricted",
                "allowed_users": ["reader-a"],
                "allowed_roles": [],
            },
            "reader-a",
            [],
            True,
        ),
        (
            {
                "visibility": "restricted",
                "allowed_users": ["reader-a"],
                "allowed_roles": [],
            },
            "reader-b",
            [],
            False,
        ),
        (
            {
                "visibility": "restricted",
                "allowed_users": [],
                "allowed_roles": ["auditor"],
            },
            "reader-b",
            ["auditor"],
            True,
        ),
        (
            {
                "visibility": "restricted",
                "allowed_users": [],
                "allowed_roles": ["auditor"],
            },
            "reader-b",
            ["viewer"],
            False,
        ),
        (
            {
                "visibility": "restricted",
                "allowed_users": [],
                "allowed_roles": [],
            },
            "reader-a",
            [],
            False,
        ),
        (
            {
                "visibility": "workspace",
                "allowed_users": [],
                "allowed_roles": [],
            },
            "reader-b",
            [],
            True,
        ),
        (
            {
                "visibility": "public",
                "allowed_users": [],
                "allowed_roles": [],
            },
            "reader-b",
            [],
            True,
        ),
    ],
)
def test_get_document_enforces_acl(
    monkeypatch,
    acl,
    subject,
    roles,
    expected,
):
    payload = {
        "point_type": "document_metadata",
        "doc_id": "doc-acl-test",
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "filename": "test.txt",
        "deleted": False,
        "acl": acl,
    }

    class FakeQdrant:
        def scroll(
            self,
            collection_name,
            scroll_filter=None,
            limit=None,
            with_payload=False,
        ):
            conditions = {
                condition.key: condition.match.value
                for condition in scroll_filter.must
            }

            assert conditions == {
                "point_type": "document_metadata",
                "doc_id": "doc-acl-test",
                "tenant_id": "tenant-a",
                "workspace_id": "workspace-a",
            }

            return (
                [SimpleNamespace(payload=payload)],
                None,
            )

    monkeypatch.setattr(
        main,
        "get_qdrant",
        lambda: FakeQdrant(),
    )

    claims = {
        "sub": subject,
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "roles": roles,
    }

    if expected:
        result = main.get_document(
            "doc-acl-test",
            claims,
        )
        assert result["doc_id"] == "doc-acl-test"
    else:
        with pytest.raises(HTTPException) as exc:
            main.get_document(
                "doc-acl-test",
                claims,
            )

        assert exc.value.status_code == 404


def test_get_document_rejects_deleted_metadata(monkeypatch):
    class FakeQdrant:
        def scroll(self, *args, **kwargs):
            return (
                [
                    SimpleNamespace(
                        payload={
                            "deleted": True,
                            "acl": {
                                "visibility": "public"
                            },
                        }
                    )
                ],
                None,
            )

    monkeypatch.setattr(
        main,
        "get_qdrant",
        lambda: FakeQdrant(),
    )

    with pytest.raises(HTTPException) as exc:
        main.get_document(
            "deleted-doc",
            {
                "sub": "reader-a",
                "tenant_id": "tenant-a",
                "workspace_id": "workspace-a",
            },
        )

    assert exc.value.status_code == 404


def test_get_document_requires_tenant_claim():
    with pytest.raises(HTTPException) as exc:
        main.get_document(
            "any-doc",
            {
                "sub": "reader-a",
                "workspace_id": "workspace-a",
            },
        )

    assert exc.value.status_code == 403
