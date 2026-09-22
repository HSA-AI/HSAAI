
"""Security regressions for scoped RAG document deletion."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from rag_engine import main


def claims(**changes):
    value = {
        "sub": "authorized-user",
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "permissions": ["knowledge:delete"],
        "roles": [],
    }
    value.update(changes)
    return value


def metadata(acl=None, deleted=False):
    return {
        "doc_id": "doc-test",
        "filename": "test.txt",
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "deleted": deleted,
        "acl": acl or {
            "visibility": "workspace",
            "allowed_users": [],
            "allowed_roles": [],
        },
    }


class FakeQdrant:
    def __init__(
        self,
        payload=None,
        fail_scroll=False,
        fail_update=False,
        missing=False,
    ):
        self.payload = payload or metadata()
        self.fail_scroll = fail_scroll
        self.fail_update = fail_update
        self.missing = missing
        self.updated = []
        self.filters = []
        self.update_calls = 0

    def scroll(
        self,
        collection_name,
        scroll_filter=None,
        limit=None,
        offset=None,
        with_payload=False,
    ):
        if self.fail_scroll:
            raise RuntimeError("Synthetic Qdrant failure")

        conditions = {
            condition.key: condition.match.value
            for condition in scroll_filter.must
        }

        self.filters.append(conditions)

        if conditions.get("point_type") == "document_metadata":
            if self.missing:
                return [], None

            return [
                SimpleNamespace(
                    id="metadata-point",
                    payload=self.payload,
                )
            ], None

        if offset is None:
            return [
                SimpleNamespace(id="metadata-point"),
                SimpleNamespace(id="chunk-1"),
            ], 2

        if offset == 2:
            return [
                SimpleNamespace(id="chunk-2")
            ], None

        raise AssertionError("Unexpected scroll cursor")

    def set_payload(
        self,
        collection_name,
        payload,
        points,
        wait=False,
    ):
        self.update_calls += 1

        if self.fail_update:
            raise RuntimeError("Synthetic update failure")

        assert payload == {"deleted": True}
        assert wait is True

        self.updated.extend(points)


@pytest.fixture
def setup_delete(monkeypatch):
    client = FakeQdrant()
    events = []

    monkeypatch.setattr(
        main,
        "get_qdrant",
        lambda: client,
    )

    monkeypatch.setattr(
        main,
        "_event",
        lambda *args, **kwargs: events.append((args, kwargs)),
    )

    return client, events


def test_authorized_delete_scopes_and_paginates(setup_delete):
    client, events = setup_delete

    result = main.delete_document(
        "doc-test",
        claims(),
    )

    assert result == {
        "status": "deleted",
        "doc_id": "doc-test",
    }

    assert client.updated == [
        "metadata-point",
        "chunk-1",
        "chunk-2",
    ]

    assert client.update_calls == 1

    assert all(
        item["tenant_id"] == "tenant-a"
        and item["workspace_id"] == "workspace-a"
        and item["doc_id"] == "doc-test"
        for item in client.filters
    )

    assert len(events) == 1


@pytest.mark.parametrize(
    "permission_claims",
    [
        {"permissions": []},
        {"permissions": ["knowledge:read"]},
        {"permissions": [], "scope": "knowledge:read"},
    ],
)
def test_delete_requires_permission(
    setup_delete,
    permission_claims,
):
    client, events = setup_delete

    with pytest.raises(HTTPException) as exc:
        main.delete_document(
            "doc-test",
            claims(**permission_claims),
        )

    assert exc.value.status_code == 403
    assert not client.updated
    assert not events


def test_delete_accepts_verified_scope_permission(setup_delete):
    client, events = setup_delete

    result = main.delete_document(
        "doc-test",
        claims(
            permissions=[],
            scope="knowledge:delete",
        ),
    )

    assert result["status"] == "deleted"
    assert client.updated
    assert len(events) == 1


def test_restricted_document_denies_other_user(
    monkeypatch,
    setup_delete,
):
    client, events = setup_delete

    client.payload = metadata({
        "visibility": "restricted",
        "allowed_users": ["different-user"],
        "allowed_roles": [],
    })

    with pytest.raises(HTTPException) as exc:
        main.delete_document(
            "doc-test",
            claims(),
        )

    assert exc.value.status_code == 404
    assert not client.updated
    assert not events


def test_other_workspace_cannot_delete(
    setup_delete,
):
    client, events = setup_delete

    client.missing = True

    with pytest.raises(HTTPException) as exc:
        main.delete_document(
            "doc-test",
            claims(workspace_id="workspace-b"),
        )

    assert exc.value.status_code == 404

    assert client.filters[0]["workspace_id"] == "workspace-b"
    assert not client.updated
    assert not events


def test_other_tenant_cannot_delete(
    setup_delete,
):
    client, events = setup_delete
    client.missing = True

    with pytest.raises(HTTPException) as exc:
        main.delete_document(
            "doc-test",
            claims(tenant_id="tenant-b"),
        )

    assert exc.value.status_code == 404
    assert client.filters[0]["tenant_id"] == "tenant-b"
    assert not events


def test_deleted_document_cannot_be_deleted_again(
    setup_delete,
):
    client, events = setup_delete
    client.payload = metadata(deleted=True)

    with pytest.raises(HTTPException) as exc:
        main.delete_document(
            "doc-test",
            claims(),
        )

    assert exc.value.status_code == 404
    assert not client.updated
    assert not events


@pytest.mark.parametrize(
    "failure",
    ["fail_scroll", "fail_update"],
)
def test_qdrant_failure_never_reports_success(
    setup_delete,
    failure,
):
    client, events = setup_delete

    setattr(client, failure, True)

    with pytest.raises(HTTPException) as exc:
        main.delete_document(
            "doc-test",
            claims(),
        )

    assert exc.value.status_code == 503
    assert not events


def test_missing_qdrant_returns_503(
    monkeypatch,
    setup_delete,
):
    _, events = setup_delete

    monkeypatch.setattr(
        main,
        "get_qdrant",
        lambda: None,
    )

    with pytest.raises(HTTPException) as exc:
        main.delete_document(
            "doc-test",
            claims(),
        )

    assert exc.value.status_code == 503
    assert not events
