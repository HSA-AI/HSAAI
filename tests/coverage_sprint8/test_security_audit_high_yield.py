import importlib
import json


def _m():
    return importlib.import_module(
        "backend_core.security.audit"
    )


def test_compute_hmac_disabled_and_enabled(monkeypatch):
    m = _m()

    monkeypatch.setattr(m, "_AUDIT_HMAC_KEY", b"")
    assert m._compute_hmac("payload") == ""

    monkeypatch.setattr(
        m,
        "_AUDIT_HMAC_KEY",
        b"unit-test-secret",
    )

    sig = m._compute_hmac("payload")

    assert sig
    assert len(sig) == 64
    assert sig == m._compute_hmac("payload")
    assert sig != m._compute_hmac("different")


def test_get_audit_file(monkeypatch, tmp_path):
    m = _m()
    monkeypatch.setattr(m, "AUDIT_DIR", tmp_path)

    path = m._get_audit_file()

    assert path.parent == tmp_path
    assert path.name.startswith("audit_")
    assert path.suffix == ".jsonl"


def test_rotate_if_needed(monkeypatch, tmp_path):
    m = _m()

    path = tmp_path / "audit_test.jsonl"
    path.write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        m,
        "MAX_AUDIT_FILE_SIZE_MB",
        0,
    )

    m._rotate_if_needed(path)

    assert not path.exists()

    rotated = list(
        tmp_path.glob("audit_test_*.jsonl")
    )
    assert len(rotated) == 1


def test_write_audit_and_alias(monkeypatch, tmp_path):
    m = _m()

    monkeypatch.setattr(
        m,
        "_AUDIT_HMAC_KEY",
        b"unit-secret",
    )
    monkeypatch.setattr(m, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(
        m,
        "MAX_AUDIT_FILE_SIZE_MB",
        100,
    )

    m.write_audit(
        actor="user-1",
        action="read",
        resource="document-1",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        success=True,
        detail="unit",
        ip="127.0.0.1",
    )

    path = m._get_audit_file()
    row = json.loads(
        path.read_text(encoding="utf-8").strip()
    )

    assert row["actor"] == "user-1"
    assert row["action"] == "read"
    assert row["extra"]["ip"] == "127.0.0.1"
    assert row["hmac"]

    captured = {}

    def fake_write(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(m, "write_audit", fake_write)

    m.audit(
        "actor-x",
        "update",
        "resource-x",
        "workspace-x",
        tenant_id="tenant-x",
    )

    assert captured["actor"] == "actor-x"
    assert captured["action"] == "update"
    assert captured["workspace_id"] == "workspace-x"
    assert captured["tenant_id"] == "tenant-x"


def test_verify_missing_key_and_missing_file(
    monkeypatch,
    tmp_path,
):
    m = _m()

    monkeypatch.setattr(m, "_AUDIT_HMAC_KEY", b"")

    result = m.verify_audit_integrity(
        tmp_path / "missing.jsonl"
    )

    assert result["missing_key"] is True

    monkeypatch.setattr(
        m,
        "_AUDIT_HMAC_KEY",
        b"secret",
    )

    result = m.verify_audit_integrity(
        tmp_path / "missing.jsonl"
    )

    assert result == {
        "total": 0,
        "valid": 0,
        "invalid": [],
        "missing_key": False,
    }


def test_verify_valid_invalid_missing_hmac_and_bad_json(
    monkeypatch,
    tmp_path,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "_AUDIT_HMAC_KEY",
        b"verify-secret",
    )

    valid_entry = {
        "actor": "u",
        "action": "read",
    }

    canonical = json.dumps(
        valid_entry,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    valid = {
        **valid_entry,
        "hmac": m._compute_hmac(canonical),
    }

    bad_sig = {
        **valid_entry,
        "hmac": "bad-signature",
    }

    missing_sig = {
        **valid_entry,
    }

    path = tmp_path / "audit.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(valid),
                json.dumps(bad_sig),
                json.dumps(missing_sig),
                "{bad-json",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = m.verify_audit_integrity(path)

    assert result["total"] == 4
    assert result["valid"] == 1
    assert result["invalid"] == [2, 3, 4]
    assert result["missing_key"] is False
