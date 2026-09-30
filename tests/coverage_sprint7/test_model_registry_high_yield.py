import importlib
from types import SimpleNamespace

import pytest


def _module():
    return importlib.import_module(
        "services.model_training.model_registry"
    )


def _registry(m):
    registry = object.__new__(m.ModelRegistry)
    registry._mlflow = None
    registry._use_mlflow = True
    registry._models = {"models": []}
    registry._save = lambda: None
    return registry


def _model(m, *, status=None):
    if status is None:
        status = m.ModelStatus.PRODUCTION

    return SimpleNamespace(
        model_id="enterprise-model",
        version="1.2.3",
        model_path="/models/enterprise-model.bin",
        base_model="base-model",
        lora_r=16,
        lora_alpha=32,
        train_examples=1000,
        model_hash="sha256-test",
        accuracy=0.91,
        perplexity=2.4,
        eval_loss=0.15,
        training_hours=4.5,
        created_by="qa-user",
        status=status,
    )


class FakeRun:
    def __init__(self, run_id="run-123"):
        self.info = SimpleNamespace(
            run_id=run_id
        )


class FakeRunContext:
    def __init__(self, run_id="run-123"):
        self.run = FakeRun(run_id)

    def __enter__(self):
        return self.run

    def __exit__(self, exc_type, exc, tb):
        return False


def test_register_mlflow_success_and_stage_transition(monkeypatch):
    m = _module()

    registry = _registry(m)
    model = _model(m)

    captured = {
        "params": None,
        "metrics": None,
        "transition": None,
        "created_version": None,
        "saved": False,
    }

    class Client:
        def create_registered_model(self, name):
            captured["registered_model"] = name

        def create_model_version(
            self,
            name,
            source,
            run_id,
            tags,
        ):
            captured["created_version"] = {
                "name": name,
                "source": source,
                "run_id": run_id,
                "tags": tags,
            }

            return SimpleNamespace(
                version=7
            )

        def transition_model_version_stage(
            self,
            **kwargs,
        ):
            captured["transition"] = kwargs

    client = Client()

    mlflow = SimpleNamespace(
        tracking=SimpleNamespace(
            MlflowClient=lambda: client
        ),
        start_run=lambda **kwargs: FakeRunContext(
            "run-123"
        ),
        log_params=lambda values: captured.__setitem__(
            "params",
            values,
        ),
        log_metrics=lambda values: captured.__setitem__(
            "metrics",
            values,
        ),
    )

    registry._mlflow = mlflow

    monkeypatch.setattr(
        m,
        "asdict",
        lambda obj: dict(vars(obj)),
    )

    def save():
        captured["saved"] = True

    registry._save = save

    result = registry._register_mlflow(model)

    assert result is True

    assert (
        captured["registered_model"]
        == "enterprise-model"
    )

    created = captured["created_version"]

    assert created["name"] == "enterprise-model"
    assert created["run_id"] == "run-123"
    assert created["source"] == "runs:/run-123/model"

    assert (
        created["tags"]["hsaai_version"]
        == "1.2.3"
    )
    assert (
        created["tags"]["model_hash"]
        == "sha256-test"
    )

    assert captured["params"]["lora_r"] == 16
    assert captured["metrics"]["accuracy"] == 0.91

    transition = captured["transition"]

    assert transition is not None
    assert transition["name"] == "enterprise-model"
    assert transition["version"] == 7
    assert transition[
        "archive_existing_versions"
    ] is True

    assert len(registry._models["models"]) == 1
    assert captured["saved"] is True


def test_register_mlflow_existing_registered_model_is_allowed(
    monkeypatch,
):
    m = _module()

    registry = _registry(m)
    model = _model(m)

    captured = {
        "version_created": False,
    }

    class Client:
        def create_registered_model(self, name):
            raise RuntimeError(
                "already exists"
            )

        def create_model_version(
            self,
            **kwargs,
        ):
            captured["version_created"] = True

            return SimpleNamespace(
                version=3
            )

        def transition_model_version_stage(
            self,
            **kwargs,
        ):
            pass

    registry._mlflow = SimpleNamespace(
        tracking=SimpleNamespace(
            MlflowClient=lambda: Client()
        ),
        start_run=lambda **kwargs: FakeRunContext(
            "run-existing"
        ),
        log_params=lambda values: None,
        log_metrics=lambda values: None,
    )

    monkeypatch.setattr(
        m,
        "asdict",
        lambda obj: dict(vars(obj)),
    )

    assert registry._register_mlflow(model) is True
    assert captured["version_created"] is True


def test_register_mlflow_draft_skips_stage_transition(
    monkeypatch,
):
    m = _module()

    registry = _registry(m)

    model = _model(
        m,
        status=m.ModelStatus.DRAFT,
    )

    captured = {
        "transitioned": False,
    }

    class Client:
        def create_registered_model(self, name):
            pass

        def create_model_version(
            self,
            **kwargs,
        ):
            return SimpleNamespace(
                version=9
            )

        def transition_model_version_stage(
            self,
            **kwargs,
        ):
            captured["transitioned"] = True

    registry._mlflow = SimpleNamespace(
        tracking=SimpleNamespace(
            MlflowClient=lambda: Client()
        ),
        start_run=lambda **kwargs: FakeRunContext(
            "run-draft"
        ),
        log_params=lambda values: None,
        log_metrics=lambda values: None,
    )

    monkeypatch.setattr(
        m,
        "asdict",
        lambda obj: dict(vars(obj)),
    )

    result = registry._register_mlflow(model)

    assert result is True

    # DRAFT maps to the MLflow "None" stage and therefore
    # must not call transition_model_version_stage.
    assert captured["transitioned"] is False


def test_register_mlflow_failure_is_propagated(monkeypatch):
    m = _module()

    registry = _registry(m)
    model = _model(m)

    class Client:
        def create_registered_model(self, name):
            pass

        def create_model_version(
            self,
            **kwargs,
        ):
            raise RuntimeError(
                "MLflow version creation failed"
            )

    registry._mlflow = SimpleNamespace(
        tracking=SimpleNamespace(
            MlflowClient=lambda: Client()
        ),
        start_run=lambda **kwargs: FakeRunContext(
            "run-fail"
        ),
        log_params=lambda values: None,
        log_metrics=lambda values: None,
    )

    with pytest.raises(
        RuntimeError,
        match="version creation failed",
    ):
        registry._register_mlflow(model)


def test_promote_mlflow_production_success_and_mirror(
    monkeypatch,
):
    m = _module()

    registry = _registry(m)

    registry._models = {
        "models": [
            {
                "model_id": "enterprise-model",
                "version": "1.2.3",
                "status": m.ModelStatus.STAGING.value,
            }
        ]
    }

    captured = {
        "transition": None,
        "tags": [],
        "saved": False,
    }

    target = SimpleNamespace(
        version=11,
        tags={
            "hsaai_version": "1.2.3",
        },
    )

    other = SimpleNamespace(
        version=10,
        tags={
            "hsaai_version": "1.1.0",
        },
    )

    class Client:
        def search_model_versions(self, query):
            captured["query"] = query
            return [
                other,
                target,
            ]

        def transition_model_version_stage(
            self,
            **kwargs,
        ):
            captured["transition"] = kwargs

        def set_model_version_tag(
            self,
            **kwargs,
        ):
            captured["tags"].append(kwargs)

    registry._mlflow = SimpleNamespace(
        tracking=SimpleNamespace(
            MlflowClient=lambda: Client()
        )
    )

    def save():
        captured["saved"] = True

    registry._save = save

    result = registry._promote_mlflow(
        "enterprise-model",
        "1.2.3",
        m.ModelStatus.PRODUCTION,
        "security-admin",
    )

    assert result is True

    assert (
        captured["query"]
        == "name='enterprise-model'"
    )

    transition = captured["transition"]

    assert transition["name"] == "enterprise-model"
    assert transition["version"] == 11
    assert transition[
        "archive_existing_versions"
    ] is True

    tag_map = {
        item["key"]: item["value"]
        for item in captured["tags"]
    }

    assert tag_map["approved_by"] == "security-admin"
    assert "approved_at" in tag_map

    mirrored = registry._models["models"][0]

    assert (
        mirrored["status"]
        == m.ModelStatus.PRODUCTION.value
    )
    assert (
        mirrored["approved_by"]
        == "security-admin"
    )
    assert "approved_at" in mirrored

    assert captured["saved"] is True


def test_promote_mlflow_nonproduction_does_not_archive_existing(
    monkeypatch,
):
    m = _module()

    registry = _registry(m)
    registry._models = {
        "models": []
    }

    captured = {}

    target = SimpleNamespace(
        version=4,
        tags={
            "hsaai_version": "2.0.0",
        },
    )

    class Client:
        def search_model_versions(self, query):
            return [target]

        def transition_model_version_stage(
            self,
            **kwargs,
        ):
            captured.update(kwargs)

        def set_model_version_tag(
            self,
            **kwargs,
        ):
            pass

    registry._mlflow = SimpleNamespace(
        tracking=SimpleNamespace(
            MlflowClient=lambda: Client()
        )
    )

    result = registry._promote_mlflow(
        "enterprise-model",
        "2.0.0",
        m.ModelStatus.STAGING,
        "reviewer-a",
    )

    assert result is True
    assert (
        captured["archive_existing_versions"]
        is False
    )


def test_promote_mlflow_missing_version_returns_false():
    m = _module()

    registry = _registry(m)

    class Client:
        def search_model_versions(self, query):
            return [
                SimpleNamespace(
                    version=1,
                    tags={
                        "hsaai_version": "0.9.0"
                    },
                )
            ]

    registry._mlflow = SimpleNamespace(
        tracking=SimpleNamespace(
            MlflowClient=lambda: Client()
        )
    )

    result = registry._promote_mlflow(
        "enterprise-model",
        "9.9.9",
        m.ModelStatus.PRODUCTION,
        "admin",
    )

    assert result is False


def test_public_register_falls_back_to_file_on_mlflow_failure(
    monkeypatch,
):
    m = _module()

    registry = _registry(m)
    registry._use_mlflow = True

    model = _model(m)

    captured = {
        "saved": False,
    }

    monkeypatch.setattr(
        registry,
        "_register_mlflow",
        lambda model: (_ for _ in ()).throw(
            RuntimeError("mlflow offline")
        ),
    )

    monkeypatch.setattr(
        m,
        "asdict",
        lambda obj: dict(vars(obj)),
    )

    registry._save = lambda: captured.__setitem__(
        "saved",
        True,
    )

    result = registry.register(model)

    assert result is True
    assert len(registry._models["models"]) == 1
    assert captured["saved"] is True


def test_public_promote_falls_back_to_file(monkeypatch):
    m = _module()

    registry = _registry(m)
    registry._use_mlflow = True

    registry._models = {
        "models": [
            {
                "model_id": "enterprise-model",
                "version": "1.0.0",
                "status": m.ModelStatus.PRODUCTION.value,
            },
            {
                "model_id": "enterprise-model",
                "version": "2.0.0",
                "status": m.ModelStatus.STAGING.value,
            },
        ]
    }

    monkeypatch.setattr(
        registry,
        "_promote_mlflow",
        lambda *args, **kwargs: (
            _ for _ in ()
        ).throw(
            RuntimeError("mlflow unavailable")
        ),
    )

    saved = {
        "value": False,
    }

    registry._save = lambda: saved.__setitem__(
        "value",
        True,
    )

    result = registry.promote(
        "enterprise-model",
        "2.0.0",
        m.ModelStatus.PRODUCTION,
        "admin-a",
    )

    assert result is True

    old_model = registry._models["models"][0]
    new_model = registry._models["models"][1]

    assert (
        old_model["status"]
        == m.ModelStatus.ARCHIVED.value
    )
    assert (
        new_model["status"]
        == m.ModelStatus.PRODUCTION.value
    )
    assert new_model["approved_by"] == "admin-a"
    assert "approved_at" in new_model
    assert saved["value"] is True
