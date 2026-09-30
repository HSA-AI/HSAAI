def _model(mr, version, created_at):
    return mr.ModelVersion(
        model_id="enterprise-model",
        version=version,
        base_model="base",
        created_at=created_at,
        accuracy=0.9,
        model_hash=f"hash-{version}",
    )


def test_file_registry_register_promote_rollback_and_reload(monkeypatch, tmp_path):
    import model_training.model_registry as mr

    monkeypatch.setattr(mr, "_is_mlflow_available", lambda: False)
    reg = mr.ModelRegistry(str(tmp_path))

    assert reg.list_all() == []
    assert reg.register(_model(mr, "v1", "2026-01-01T00:00:00+00:00")) is True
    assert reg.register(_model(mr, "v2", "2026-02-01T00:00:00+00:00")) is True

    assert reg.get_latest("enterprise-model")["version"] == "v2"
    assert reg.get_latest("missing") is None

    assert reg.promote("enterprise-model", "v1", mr.ModelStatus.PRODUCTION, "qa") is True
    assert reg.get_production("enterprise-model")["version"] == "v1"

    assert reg.promote("enterprise-model", "v2", mr.ModelStatus.PRODUCTION, "qa2") is True
    assert reg.get_production("enterprise-model")["version"] == "v2"

    v1 = next(x for x in reg.list_all() if x["version"] == "v1")
    assert v1["status"] == mr.ModelStatus.ARCHIVED.value
    assert reg.promote("enterprise-model", "missing", mr.ModelStatus.STAGING, "x") is False

    rolled = reg.rollback("enterprise-model")
    assert rolled["version"] == "v1"
    assert reg.get_production("enterprise-model")["version"] == "v1"

    reloaded = mr.ModelRegistry(str(tmp_path))
    assert len(reloaded.list_all()) == 2


def test_registry_corrupt_file_recovers(monkeypatch, tmp_path):
    import model_training.model_registry as mr

    monkeypatch.setattr(mr, "_is_mlflow_available", lambda: False)
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "registry.json").write_text("{broken", encoding="utf-8")

    reg = mr.ModelRegistry(str(tmp_path))
    assert reg.list_all() == []
    assert reg.rollback("nothing") is None
