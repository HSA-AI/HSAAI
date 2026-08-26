from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.model_training.config import settings
from services.model_training.db.models import (
    Dataset,
    TrainingJob,
    TrainingLog,
)
from services.model_training.schemas import (
    JobStatus,
    TrainingJobCreate,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrainingService:
    """
    Tenant-aware service for model-training jobs.
    """

    def __init__(
        self,
        db: Session,
        tenant_id: str = "default",
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id or "default"

    def _require_job(
        self,
        job_id: int,
    ) -> TrainingJob:
        stmt = select(TrainingJob).where(
            TrainingJob.id == job_id,
            TrainingJob.tenant_id == self.tenant_id,
        )

        job = self.db.scalar(stmt)

        if not job:
            raise ValueError("Training job not found")

        return job

    def _validate_dataset(
        self,
        dataset_id: int | None,
    ) -> Dataset | None:
        if dataset_id is None:
            return None

        stmt = select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.tenant_id == self.tenant_id,
        )

        dataset = self.db.scalar(stmt)

        if not dataset:
            raise ValueError(
                "Dataset not found or does not belong to this tenant"
            )

        return dataset

    def create_job(
        self,
        payload: TrainingJobCreate,
        created_by: str = "system",
    ) -> TrainingJob:
        self._validate_dataset(payload.dataset_id)

        config = payload.model_dump(mode="json")

        # Never trust a tenant_id supplied by the request body.
        config["tenant_id"] = self.tenant_id

        job = TrainingJob(
            tenant_id=self.tenant_id,
            training_name=payload.training_name,
            description=payload.description,
            base_model=payload.base_model,
            dataset_id=payload.dataset_id,
            dataset_path=payload.dataset_path,
            method=payload.method.value,
            status=JobStatus.pending.value,
            gpu_device=payload.compute.gpu_device,
            cpu_limit=payload.compute.cpu_limit,
            ram_limit=payload.compute.ram_limit,
            vram_limit=payload.compute.vram_limit,
            created_by=created_by,
            config=config,
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        self.db.add(
            TrainingLog(
                tenant_id=self.tenant_id,
                job_id=job.id,
                level="INFO",
                message="Training job created",
                payload={
                    "training_name": job.training_name,
                    "method": job.method,
                },
            )
        )

        self.db.commit()

        return job

    def list_jobs(self) -> list[TrainingJob]:
        stmt = (
            select(TrainingJob)
            .where(
                TrainingJob.tenant_id == self.tenant_id,
            )
            .order_by(
                TrainingJob.created_at.desc(),
            )
        )

        return list(self.db.scalars(stmt).all())

    def get_job(
        self,
        job_id: int,
    ) -> TrainingJob | None:
        stmt = select(TrainingJob).where(
            TrainingJob.id == job_id,
            TrainingJob.tenant_id == self.tenant_id,
        )

        return self.db.scalar(stmt)

    def enqueue(
        self,
        job_id: int,
    ) -> str:
        job = self._require_job(job_id)

        if job.status in {
            JobStatus.completed.value,
            JobStatus.cancelled.value,
        }:
            raise ValueError(
                f"Cannot enqueue job in status: {job.status}"
            )

        if job.status == JobStatus.training.value:
            raise ValueError(
                "Training job is already running"
            )

        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=False,
        )

        queue = Queue(
            settings.default_queue,
            connection=redis,
        )

        rq_job = queue.enqueue(
            "services.model_training.workers.training_worker.run_training_job",
            job.id,
            job_timeout=settings.job_timeout,
        )

        job.status = JobStatus.preparing.value

        job.started_at = utcnow()

        job.config = {
            **(job.config or {}),
            "tenant_id": self.tenant_id,
            "rq_job_id": rq_job.id,
        }

        self.db.add(
            TrainingLog(
                tenant_id=self.tenant_id,
                job_id=job.id,
                level="INFO",
                message=f"Queued training job {rq_job.id}",
                payload={
                    "rq_job_id": rq_job.id,
                },
            )
        )

        self.db.commit()

        return rq_job.id

    def cancel(
        self,
        job_id: int,
    ) -> TrainingJob:
        job = self._require_job(job_id)

        if job.output_dir:
            output_dir = Path(job.output_dir)
            output_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            (
                output_dir / ".cancel"
            ).write_text(
                "cancelled",
                encoding="utf-8",
            )

        job.status = JobStatus.cancelled.value
        job.finished_at = utcnow()

        self.db.add(
            TrainingLog(
                tenant_id=self.tenant_id,
                job_id=job.id,
                level="WARN",
                message="Cancel requested",
                payload={},
            )
        )

        self.db.commit()

        return job

    def pause(
        self,
        job_id: int,
    ) -> TrainingJob:
        job = self._require_job(job_id)

        if job.status not in {
            JobStatus.preparing.value,
            JobStatus.training.value,
        }:
            raise ValueError(
                f"Cannot pause job in status: {job.status}"
            )

        job.status = JobStatus.paused.value

        self.db.add(
            TrainingLog(
                tenant_id=self.tenant_id,
                job_id=job.id,
                level="WARN",
                message="Pause requested",
                payload={},
            )
        )

        self.db.commit()

        return job

    def resume(
        self,
        job_id: int,
    ) -> str:
        job = self._require_job(job_id)

        if job.status != JobStatus.paused.value:
            raise ValueError(
                "Only paused jobs can be resumed"
            )

        job.status = JobStatus.pending.value
        self.db.commit()

        return self.enqueue(job_id)

    def retry(
        self,
        job_id: int,
    ) -> str:
        job = self._require_job(job_id)

        if job.status not in {
            JobStatus.failed.value,
            JobStatus.cancelled.value,
        }:
            raise ValueError(
                f"Only failed or cancelled jobs can be retried; "
                f"current status: {job.status}"
            )

        if job.output_dir:
            cancel_file = Path(job.output_dir) / ".cancel"

            if cancel_file.exists():
                cancel_file.unlink()

        job.status = JobStatus.pending.value
        job.finished_at = None

        self.db.commit()

        return self.enqueue(job_id)
