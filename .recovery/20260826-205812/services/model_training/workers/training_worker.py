from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from services.model_training.config import settings
from services.model_training.db.database import SessionLocal
from services.model_training.db.models import (
    GPUMetric,
    TrainingJob,
    TrainingLog,
)
from services.model_training.monitoring.gpu_monitor import (
    read_gpu_metrics,
)
from services.model_training.services.experiment_service import (
    ExperimentService,
)
from services.model_training.services.model_registry_service import (
    ModelRegistryService,
)
from services.model_training.trainers.base_trainer import (
    TrainingCancelled,
)
from services.model_training.trainers.lora_trainer import (
    LoraTrainer,
)
from services.model_training.trainers.qlora_trainer import (
    QLoraTrainer,
)
from services.model_training.trainers.sft_trainer import (
    SFTEnterpriseTrainer,
)


TRAINERS = {
    "LoRA": LoraTrainer,
    "QLoRA": QLoraTrainer,
    "SFT": SFTEnterpriseTrainer,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_training_job(
    job_id: int,
):
    """
    RQ worker entry point.

    IMPORTANT:
    The worker obtains the tenant exclusively from the persisted
    TrainingJob record. It does not accept tenant_id from RQ arguments.
    """

    db = SessionLocal()

    job: TrainingJob | None = None

    try:
        job = db.get(
            TrainingJob,
            job_id,
        )

        if not job:
            raise ValueError(
                f"Training job {job_id} not found"
            )

        tenant_id = job.tenant_id

        if not tenant_id:
            raise ValueError(
                f"Training job {job_id} has no tenant_id"
            )

        if job.status == "Completed":
            raise ValueError(
                f"Training job {job_id} is already completed"
            )

        if job.status == "Cancelled":
            raise TrainingCancelled(
                f"Training job {job_id} was cancelled"
            )

        job.status = "Training"

        out = (
            Path(settings.artifacts_root)
            / "trained_models"
            / f"tenant_{tenant_id}"
            / f"job_{job.id}"
        )

        out.mkdir(
            parents=True,
            exist_ok=True,
        )

        job.output_dir = str(out)

        db.add(
            TrainingLog(
                tenant_id=tenant_id,
                job_id=job.id,
                level="INFO",
                message="Starting real training",
                payload={
                    "method": job.method,
                    "tenant_id": tenant_id,
                    "job_id": job.id,
                },
            )
        )

        db.commit()

        exp = ExperimentService(db)

        def emit(
            payload: dict,
        ) -> None:
            """
            Persist training metrics with the same tenant as the job.
            """

            current_job = db.get(
                TrainingJob,
                job_id,
            )

            if not current_job:
                raise ValueError(
                    "Training job disappeared during execution"
                )

            if current_job.tenant_id != tenant_id:
                raise PermissionError(
                    "Training job tenant changed during execution"
                )

            for gpu in read_gpu_metrics():
                metric = dict(gpu)

                db.add(
                    GPUMetric(
                        tenant_id=tenant_id,
                        job_id=job.id,
                        **metric,
                    )
                )

                payload.setdefault(
                    "gpu",
                    [],
                ).append(metric)

            exp.log_metric(
                job.id,
                payload,
            )

            db.commit()

        trainer_cls = TRAINERS.get(
            job.method,
        )

        if not trainer_cls:
            raise ValueError(
                f"Unsupported training method: {job.method}"
            )

        config = dict(
            job.config or {}
        )

        config["tenant_id"] = tenant_id
        config["job_id"] = job.id

        dataset_path = (
            config.get("dataset_path")
            or job.dataset_path
        )

        if not dataset_path:
            raise ValueError(
                "dataset_path is required for real training"
            )

        config["dataset_path"] = dataset_path

        trainer = trainer_cls(
            job.id,
            config,
            str(out),
            emit,
        )

        result = trainer.run()

        if not isinstance(result, dict):
            raise ValueError(
                "Trainer returned an invalid result"
            )

        artifact_path = result.get(
            "artifact_path"
        )

        if not artifact_path:
            raise ValueError(
                "Trainer did not return artifact_path"
            )

        artifact = Path(
            artifact_path
        )

        if not artifact.exists():
            raise FileNotFoundError(
                f"Training artifact does not exist: {artifact_path}"
            )

        job.status = "Saving"

        db.commit()

        model = ModelRegistryService(
            db
        ).register_from_job(
            job,
            artifact_path,
            metrics=exp.metrics(job.id),
        )

        if model.tenant_id != tenant_id:
            raise PermissionError(
                "Registered model tenant mismatch"
            )

        job.status = "Completed"
        job.finished_at = utcnow()

        db.add(
            TrainingLog(
                tenant_id=tenant_id,
                job_id=job.id,
                level="INFO",
                message="Training completed",
                payload={
                    "model_id": model.id,
                    **result,
                },
            )
        )

        db.commit()

        return {
            "job_id": job.id,
            "model_id": model.id,
            **result,
        }

    except TrainingCancelled as exc:
        if job is None:
            job = db.get(
                TrainingJob,
                job_id,
            )

        if job:
            job.status = "Cancelled"
            job.finished_at = utcnow()

            db.add(
                TrainingLog(
                    tenant_id=job.tenant_id,
                    job_id=job.id,
                    level="WARN",
                    message=str(exc),
                    payload={
                        "type": "TrainingCancelled",
                    },
                )
            )

            db.commit()

        return {
            "job_id": job_id,
            "status": "Cancelled",
        }

    except Exception as exc:
        db.rollback()

        job = db.get(
            TrainingJob,
            job_id,
        )

        if job:
            job.status = "Failed"
            job.finished_at = utcnow()

            db.add(
                TrainingLog(
                    tenant_id=job.tenant_id,
                    job_id=job.id,
                    level="ERROR",
                    message=str(exc),
                    payload={
                        "type": type(exc).__name__,
                    },
                )
            )

            db.commit()

        raise

    finally:
        db.close()
