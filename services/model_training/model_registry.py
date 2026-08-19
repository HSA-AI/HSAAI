"""
HSAAI Model Registry with MLflow Integration (Phase 2 — Modernize)
===================================================================

FIX v2.2 (Phase 2): Previously a file-based JSON registry (self-admitted
"production: use MLflow" in the docstring). Now integrates with MLflow
as the primary registry backend, with the file-based registry as a
fallback for dev environments where MLflow is not deployed.

MLflow provides:
  - Experiment tracking (parameters, metrics, artifacts)
  - Model versioning with stage transitions (None → Staging → Production → Archived)
  - Model artifacts stored in MinIO (S3-compatible)
  - Audit trail of all model transitions
  - REST API + UI for browsing models
  - Concurrency control (no race conditions on simultaneous promotions)

Environment variables:
  MLFLOW_TRACKING_URI  — http://mlflow:5000 (default)
  MLFLOW_S3_ENDPOINT   — http://minio:9000 (for artifact storage)
  AWS_ACCESS_KEY_ID    — MinIO access key
  AWS_SECRET_ACCESS_KEY — MinIO secret key

Usage:
    from services.model_training.model_registry import ModelRegistry, ModelVersion, ModelStatus

    registry = ModelRegistry()  # auto-detects MLflow or falls back to file

    # Register a trained model
    registry.register(model_version)

    # Promote to production
    registry.promote("qwen3-hr-finetuned", "v1", ModelStatus.PRODUCTION, approved_by="data-scientist@hsa.com")

    # Get current production model
    prod = registry.get_production("qwen3-hr-finetuned")
"""
import os, json, time, logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import hashlib

logger = logging.getLogger("hsaai.model_registry")


class ModelStatus(str, Enum):
    DRAFT = "draft"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"
    REJECTED = "rejected"


@dataclass
class ModelVersion:
    model_id: str
    version: str
    base_model: str
    status: ModelStatus = ModelStatus.DRAFT
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = ""
    # Metrics
    accuracy: float = 0.0
    perplexity: float = 0.0
    eval_loss: float = 0.0
    # Training metadata
    lora_r: int = 0
    lora_alpha: int = 0
    train_examples: int = 0
    eval_examples: int = 0
    training_hours: float = 0.0
    # Files
    model_path: str = ""
    gguf_path: str = ""
    # Hash (for integrity)
    model_hash: str = ""
    # Approval
    approved_by: str = ""
    approved_at: str = ""


# Map HSAAI ModelStatus to MLflow model stage names.
_MLFLOW_STAGE_MAP = {
    ModelStatus.DRAFT: "None",
    ModelStatus.STAGING: "Staging",
    ModelStatus.PRODUCTION: "Production",
    ModelStatus.ARCHIVED: "Archived",
    ModelStatus.REJECTED: "Archived",  # MLflow has no "Rejected" — use Archived
}

# Reverse map: MLflow stage → HSAAI ModelStatus.
_MLFLOW_STAGE_REVERSE = {
    "None": ModelStatus.DRAFT,
    "Staging": ModelStatus.STAGING,
    "Production": ModelStatus.PRODUCTION,
    "Archived": ModelStatus.ARCHIVED,
}


def _is_mlflow_available() -> bool:
    """Check if MLflow is configured and reachable."""
    uri = os.getenv("MLFLOW_TRACKING_URI", "")
    if not uri:
        return False
    try:
        import mlflow
        mlflow.set_tracking_uri(uri)
        # Quick connectivity check — try to list experiments.
        try:
            mlflow.search_experiments(max_results=1)
            return True
        except Exception:
            return False
    except ImportError:
        return False


class ModelRegistry:
    """Hybrid model registry: MLflow primary, file-based fallback.

    FIX v2.2 (Phase 2): Now uses MLflow as the primary backend when
    MLFLOW_TRACKING_URI is set and MLflow is reachable. Falls back to
    file-based JSON registry for dev environments.

    Benefits of MLflow backend:
      - Concurrency-safe version transitions (no race conditions)
      - Audit trail of all transitions (who/when/from/to)
      - Artifact storage in MinIO (S3-compatible, scalable)
      - REST API + UI for browsing models
      - Integration with experiment tracking (metrics, params)
    """

    def __init__(self, registry_dir: str = "./models/registry"):
        self.registry_dir = os.getenv("MODEL_REGISTRY_DIR", registry_dir)
        os.makedirs(self.registry_dir, exist_ok=True)
        self.registry_file = os.path.join(self.registry_dir, "registry.json")
        self._models: Dict = {"models": []}
        self._load()

        # FIX v2.2 (Phase 2): Detect MLflow availability.
        self._use_mlflow = _is_mlflow_available()
        if self._use_mlflow:
            try:
                import mlflow
                self._mlflow = mlflow
                logger.info("ModelRegistry: using MLflow backend (uri=%s)", os.getenv("MLFLOW_TRACKING_URI"))
            except ImportError:
                self._use_mlflow = False
                logger.warning("ModelRegistry: MLflow not installed — falling back to file registry")
        else:
            self._mlflow = None
            logger.info("ModelRegistry: MLflow not available — using file-based registry")

    def _load(self):
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r") as f:
                    self._models = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._models = {"models": []}
        else:
            self._models = {"models": []}

    def _save(self):
        try:
            with open(self.registry_file, "w") as f:
                json.dump(self._models, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error("Failed to save registry file: %s", e)

    def register(self, model: ModelVersion) -> bool:
        """Register a new model version.

        With MLflow: creates a logged model + transitions to the initial stage.
        With file: appends to the JSON registry.
        """
        if self._use_mlflow:
            try:
                return self._register_mlflow(model)
            except Exception as e:
                logger.warning("MLflow register failed (%s) — falling back to file", e)

        # File-based fallback.
        self._models["models"].append(asdict(model))
        self._save()
        logger.info("Registered (file): %s v%s", model.model_id, model.version)
        return True

    def _register_mlflow(self, model: ModelVersion) -> bool:
        """Register a model version in MLflow."""
        mlflow = self._mlflow
        # Create or get the registered model (top-level container).
        try:
            client = mlflow.tracking.MlflowClient()
            try:
                client.create_registered_model(model.model_id)
            except Exception:
                pass  # already exists — that's fine

            # Create a source URI for the model artifact.
            # If model_path is a local path, log it as an artifact.
            source = model.model_path or f"minio://hsaai-models/{model.model_id}/{model.version}/model.bin"

            # Log metrics + params as a run, then create a model version.
            with mlflow.start_run(run_name=f"{model.model_id}-{model.version}") as run:
                mlflow.log_params({
                    "base_model": model.base_model,
                    "lora_r": model.lora_r,
                    "lora_alpha": model.lora_alpha,
                    "train_examples": model.train_examples,
                    "version": model.version,
                    "model_hash": model.model_hash,
                })
                mlflow.log_metrics({
                    "accuracy": model.accuracy,
                    "perplexity": model.perplexity,
                    "eval_loss": model.eval_loss,
                    "training_hours": model.training_hours,
                })
                run_id = run.info.run_id

            # Create the model version pointing to this run.
            mv = client.create_model_version(
                name=model.model_id,
                source=f"runs:/{run_id}/model",
                run_id=run_id,
                tags={
                    "base_model": model.base_model,
                    "version": model.version,
                    "created_by": model.created_by,
                    "model_hash": model.model_hash,
                    "hsaai_version": model.version,
                },
            )
            logger.info("Registered (MLflow): %s v%s (mv_version=%d)", model.model_id, model.version, mv.version)

            # Transition to the appropriate stage.
            stage = _MLFLOW_STAGE_MAP.get(model.status, "None")
            if stage != "None":
                client.transition_model_version_stage(
                    name=model.model_id,
                    version=mv.version,
                    stage=stage,
                    archive_existing_versions=(model.status == ModelStatus.PRODUCTION),
                )

            # Also save to file as a local cache/mirror.
            self._models["models"].append(asdict(model))
            self._save()
            return True
        except Exception as e:
            logger.error("MLflow registration failed: %s", e)
            raise

    def get_latest(self, model_id: str, status: ModelStatus = None) -> Optional[Dict]:
        """Get latest version of a model."""
        if self._use_mlflow:
            try:
                return self._get_latest_mlflow(model_id, status)
            except Exception as e:
                logger.warning("MLflow get_latest failed (%s) — falling back to file", e)

        versions = [m for m in self._models["models"] if m["model_id"] == model_id]
        if status:
            versions = [m for m in versions if m["status"] == status.value]
        if not versions:
            return None
        return sorted(versions, key=lambda m: m["created_at"])[-1]

    def _get_latest_mlflow(self, model_id: str, status: ModelStatus = None) -> Optional[Dict]:
        """Get latest model version from MLflow."""
        client = self._mlflow.tracking.MlflowClient()
        stage = _MLFLOW_STAGE_MAP.get(status, None) if status else None
        versions = client.get_latest_versions(model_id, stages=[stage] if stage else None)
        if not versions:
            return None
        mv = versions[0]  # latest
        return {
            "model_id": mv.name,
            "version": mv.tags.get("hsaai_version", str(mv.version)),
            "base_model": mv.tags.get("base_model", ""),
            "status": _MLFLOW_STAGE_REVERSE.get(mv.current_stage, ModelStatus.DRAFT).value,
            "created_at": datetime.fromtimestamp(mv.creation_timestamp / 1000, tz=timezone.utc).isoformat(),
            "created_by": mv.tags.get("created_by", ""),
            "model_hash": mv.tags.get("model_hash", ""),
            "model_path": mv.source,
            "mlflow_version": mv.version,
            "mlflow_run_id": mv.run_id,
        }

    def promote(self, model_id: str, version: str, to_status: ModelStatus,
                approved_by: str) -> bool:
        """Promote a model to a new status (e.g., staging → production).

        With MLflow: transitions the model version stage.
        With file: updates the JSON registry.

        Only one model can be in PRODUCTION at a time — promoting to PRODUCTION
        automatically archives the previous production model.
        """
        if self._use_mlflow:
            try:
                return self._promote_mlflow(model_id, version, to_status, approved_by)
            except Exception as e:
                logger.warning("MLflow promote failed (%s) — falling back to file", e)

        # File-based fallback.
        for m in self._models["models"]:
            if m["model_id"] == model_id and m["version"] == version:
                if to_status == ModelStatus.PRODUCTION:
                    for other in self._models["models"]:
                        if (other["model_id"] == model_id and
                            other["status"] == ModelStatus.PRODUCTION.value):
                            other["status"] = ModelStatus.ARCHIVED.value
                m["status"] = to_status.value
                m["approved_by"] = approved_by
                m["approved_at"] = datetime.now(timezone.utc).isoformat()
                self._save()
                logger.info("Promoted (file) %s v%s → %s", model_id, version, to_status.value)
                return True
        return False

    def _promote_mlflow(self, model_id: str, version: str, to_status: ModelStatus,
                        approved_by: str) -> bool:
        """Promote a model version in MLflow."""
        client = self._mlflow.tracking.MlflowClient()
        # Find the model version with the matching HSAAI version tag.
        all_versions = client.search_model_versions(f"name='{model_id}'")
        target_mv = None
        for mv in all_versions:
            if mv.tags.get("hsaai_version") == version:
                target_mv = mv
                break
        if target_mv is None:
            logger.error("Model version not found in MLflow: %s v%s", model_id, version)
            return False

        stage = _MLFLOW_STAGE_MAP[to_status]
        client.transition_model_version_stage(
            name=model_id,
            version=target_mv.version,
            stage=stage,
            archive_existing_versions=(to_status == ModelStatus.PRODUCTION),
        )
        # Add approval annotation as a tag.
        client.set_model_version_tag(
            name=model_id,
            version=target_mv.version,
            key="approved_by",
            value=approved_by,
        )
        client.set_model_version_tag(
            name=model_id,
            version=target_mv.version,
            key="approved_at",
            value=datetime.now(timezone.utc).isoformat(),
        )
        logger.info("Promoted (MLflow) %s v%s → %s by %s", model_id, version, stage, approved_by)

        # Mirror to file registry.
        for m in self._models["models"]:
            if m["model_id"] == model_id and m["version"] == version:
                m["status"] = to_status.value
                m["approved_by"] = approved_by
                m["approved_at"] = datetime.now(timezone.utc).isoformat()
                self._save()
                break
        return True

    def rollback(self, model_id: str) -> Optional[Dict]:
        """Rollback to the previous production model."""
        if self._use_mlflow:
            try:
                return self._rollback_mlflow(model_id)
            except Exception as e:
                logger.warning("MLflow rollback failed (%s) — falling back to file", e)

        prod_models = [m for m in self._models["models"]
                       if m["model_id"] == model_id and
                       m["status"] == ModelStatus.ARCHIVED.value]
        if not prod_models:
            return None
        prev = sorted(prod_models, key=lambda m: m["approved_at"])[-1]
        self.promote(model_id, prev["version"], ModelStatus.PRODUCTION, "rollback")
        return prev

    def _rollback_mlflow(self, model_id: str) -> Optional[Dict]:
        """Rollback in MLflow by finding the most recently archived version."""
        client = self._mlflow.tracking.MlflowClient()
        archived = client.search_model_versions(f"name='{model_id}'")
        archived_versions = [mv for mv in archived if mv.current_stage == "Archived"]
        if not archived_versions:
            return None
        # Sort by approved_at tag (fallback to creation timestamp).
        def _sort_key(mv):
            approved = mv.tags.get("approved_at", "")
            if approved:
                return approved
            return str(mv.creation_timestamp)
        prev = sorted(archived_versions, key=_sort_key)[-1]
        version_tag = prev.tags.get("hsaai_version", str(prev.version))
        self._promote_mlflow(model_id, version_tag, ModelStatus.PRODUCTION, "rollback")
        return {
            "model_id": model_id,
            "version": version_tag,
            "status": ModelStatus.PRODUCTION.value,
            "approved_by": "rollback",
        }

    def list_all(self) -> List[Dict]:
        """List all model versions."""
        if self._use_mlflow:
            try:
                return self._list_all_mlflow()
            except Exception as e:
                logger.warning("MLflow list_all failed (%s) — falling back to file", e)
        return self._models["models"]

    def _list_all_mlflow(self) -> List[Dict]:
        """List all model versions from MLflow."""
        client = self._mlflow.tracking.MlflowClient()
        registered = client.search_registered_models()
        result = []
        for rm in registered:
            for mv in client.search_model_versions(f"name='{rm.name}'"):
                result.append({
                    "model_id": rm.name,
                    "version": mv.tags.get("hsaai_version", str(mv.version)),
                    "base_model": mv.tags.get("base_model", ""),
                    "status": _MLFLOW_STAGE_REVERSE.get(mv.current_stage, ModelStatus.DRAFT).value,
                    "created_at": datetime.fromtimestamp(mv.creation_timestamp / 1000, tz=timezone.utc).isoformat(),
                    "created_by": mv.tags.get("created_by", ""),
                    "model_hash": mv.tags.get("model_hash", ""),
                    "approved_by": mv.tags.get("approved_by", ""),
                    "approved_at": mv.tags.get("approved_at", ""),
                    "mlflow_version": mv.version,
                    "mlflow_run_id": mv.run_id,
                })
        return result

    def get_production(self, model_id: str) -> Optional[Dict]:
        """Get the current production model."""
        return self.get_latest(model_id, ModelStatus.PRODUCTION)
