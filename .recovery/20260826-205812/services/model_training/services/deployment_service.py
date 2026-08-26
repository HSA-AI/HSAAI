from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.model_training.db.models import (
    Deployment,
    TrainedModel,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeploymentService:
    """
    Tenant-aware model deployment registry.

    This service records a deployment request.
    Actual Ollama/vLLM deployment must be implemented separately.
    """

    def __init__(
        self,
        db: Session,
        tenant_id: str = "default",
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id or "default"

    def _get_model(
        self,
        model_id: int,
    ) -> TrainedModel:
        stmt = select(TrainedModel).where(
            TrainedModel.id == model_id,
            TrainedModel.tenant_id == self.tenant_id,
        )

        model = self.db.scalar(stmt)

        if not model:
            raise ValueError(
                "Model not found or does not belong to this tenant"
            )

        return model

    def deploy(
        self,
        model_id: int,
        target: str,
        endpoint_url: str | None = None,
        config: dict | None = None,
    ) -> Deployment:
        model = self._get_model(model_id)

        target = (target or "").strip()

        if not target:
            raise ValueError(
                "Deployment target is required"
            )

        deployment_config = dict(config or {})

        deployment_config["tenant_id"] = self.tenant_id
        deployment_config["model_id"] = model.id

        deployment = Deployment(
            tenant_id=self.tenant_id,
            model_id=model.id,
            target=target,
            endpoint_url=endpoint_url,
            config=deployment_config,
            status="Pending",
            created_at=utcnow(),
        )

        self.db.add(deployment)
        self.db.commit()
        self.db.refresh(deployment)

        return deploymentt

    def get(
        self,
        deployment_id: int,
    ) -> Deployment | None:
        stmt = select(Deployment).where(
            Deployment.id == deployment_id,
            Deployment.tenant_id == self.tenant_id,
        )

        return self.db.scalar(stmt)

    def list(
        self,
    ) -> list[Deployment]:
        stmt = (
            select(Deployment)
            .where(
                Deployment.tenant_id == self.tenant_id,
            )
            .order_by(
                Deployment.created_at.desc(),
            )
        )

        return list(self.db.scalars(stmt).all())
