
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from services.model_training.db.database import Base

# FIX D-04: Every model below now carries a `tenant_id` column (indexed, NOT
# NULL with a "default" server-side default for backward compatibility with
# pre-existing rows). Previously these tables had NO tenant_id, so any
# tenant's datasets / training jobs / trained models / deployments were
# visible to every other tenant — a cross-tenant data leak. The companion
# alembic migration `0004_model_training_tenant_isolation.py` adds the
# column to the existing tables and creates a tenant_isolation RLS policy
# on each. Application code must always filter by tenant_id when querying
# these tables.

_TENANT_ID_LENGTH = 64


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(primary_key=True)
    # FIX D-04: tenant isolation column
    tenant_id: Mapped[str] = mapped_column(String(_TENANT_ID_LENGTH), index=True, nullable=False, default="default")
    name: Mapped[str] = mapped_column(String(255), index=True)
    version: Mapped[str] = mapped_column(String(64), default="v1")
    format: Mapped[str] = mapped_column(String(32))
    path: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    records_count: Mapped[int] = mapped_column(Integer, default=0)
    tokens_count: Mapped[int] = mapped_column(Integer, default=0)
    validation_status: Mapped[str] = mapped_column(String(32), default="pending")
    statistics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(255), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class TrainingJob(Base):
    __tablename__ = "training_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    # FIX D-04: tenant isolation column
    tenant_id: Mapped[str] = mapped_column(String(_TENANT_ID_LENGTH), index=True, nullable=False, default="default")
    training_name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_model: Mapped[str] = mapped_column(String(255), index=True)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    dataset_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="Pending", index=True)
    gpu_device: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cpu_limit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ram_limit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vram_limit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    output_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset = relationship("Dataset")

class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(primary_key=True)
    # FIX D-04: tenant isolation column
    tenant_id: Mapped[str] = mapped_column(String(_TENANT_ID_LENGTH), index=True, nullable=False, default="default")
    job_id: Mapped[int] = mapped_column(ForeignKey("training_jobs.id"), index=True)
    hyperparameters: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    runtime_seconds: Mapped[float] = mapped_column(Float, default=0)
    gpu_usage: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Checkpoint(Base):
    __tablename__ = "checkpoints"
    id: Mapped[int] = mapped_column(primary_key=True)
    # FIX D-04: tenant isolation column
    tenant_id: Mapped[str] = mapped_column(String(_TENANT_ID_LENGTH), index=True, nullable=False, default="default")
    job_id: Mapped[int] = mapped_column(ForeignKey("training_jobs.id"), index=True)
    path: Mapped[str] = mapped_column(Text)
    step: Mapped[int] = mapped_column(Integer, default=0)
    epoch: Mapped[float] = mapped_column(Float, default=0)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class TrainedModel(Base):
    __tablename__ = "trained_models"
    id: Mapped[int] = mapped_column(primary_key=True)
    # FIX D-04: tenant isolation column
    tenant_id: Mapped[str] = mapped_column(String(_TENANT_ID_LENGTH), index=True, nullable=False, default="default")
    model_name: Mapped[str] = mapped_column(String(255), index=True)
    version: Mapped[str] = mapped_column(String(64))
    base_model: Mapped[str] = mapped_column(String(255))
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    method: Mapped[str] = mapped_column(String(32))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    owner: Mapped[str] = mapped_column(String(255), default="system")
    artifact_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

class Deployment(Base):
    __tablename__ = "deployments"
    id: Mapped[int] = mapped_column(primary_key=True)
    # FIX D-04: tenant isolation column
    tenant_id: Mapped[str] = mapped_column(String(_TENANT_ID_LENGTH), index=True, nullable=False, default="default")
    model_id: Mapped[int] = mapped_column(ForeignKey("trained_models.id"), index=True)
    target: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="Pending")
    endpoint_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class TrainingLog(Base):
    __tablename__ = "training_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    # FIX D-04: tenant isolation column
    tenant_id: Mapped[str] = mapped_column(String(_TENANT_ID_LENGTH), index=True, nullable=False, default="default")
    job_id: Mapped[int] = mapped_column(ForeignKey("training_jobs.id"), index=True)
    level: Mapped[str] = mapped_column(String(20), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class GPUMetric(Base):
    __tablename__ = "gpu_metrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    # FIX D-04: tenant isolation column (GPU metrics can leak which tenants are training what)
    tenant_id: Mapped[str] = mapped_column(String(_TENANT_ID_LENGTH), index=True, nullable=False, default="default")
    job_id: Mapped[int | None] = mapped_column(ForeignKey("training_jobs.id"), nullable=True, index=True)
    gpu_index: Mapped[int] = mapped_column(Integer, default=0)
    gpu_name: Mapped[str] = mapped_column(String(255), default="unknown")
    gpu_usage: Mapped[float] = mapped_column(Float, default=0)
    vram_usage: Mapped[float] = mapped_column(Float, default=0)
    vram_total: Mapped[float] = mapped_column(Float, default=0)
    temperature: Mapped[float] = mapped_column(Float, default=0)
    power_usage: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
