from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "HSAAI Model Training Service"

    environment: str = Field(
        default="production",
        alias="ENVIRONMENT",
    )

    database_url: str = Field(
        default="postgresql+psycopg://hsaai:hsaai@postgres:5432/hsaai_training",
        alias="DATABASE_URL",
    )

    redis_url: str = Field(
        default="redis://redis:6379/0",
        alias="REDIS_URL",
    )

    artifacts_root: str = Field(
        default="/app/artifacts",
        alias="ARTIFACTS_ROOT",
    )

    hf_home: str = Field(
        default="/app/.cache/huggingface",
        alias="HF_HOME",
    )

    allowed_roles: str = Field(
        default="Super Admin,AI Admin,ML Engineer,Data Scientist,Viewer"
    )

    default_queue: str = Field(
        default="training",
        alias="TRAINING_QUEUE",
    )

    max_upload_mb: int = Field(
        default=5120,
        alias="MAX_UPLOAD_MB",
    )

    job_timeout: str = Field(
        default="7d",
        alias="TRAINING_JOB_TIMEOUT",
    )

    @property
    def allowed_roles_list(self) -> list[str]:
        return [
            role.strip()
            for role in self.allowed_roles.split(",")
            if role.strip()
        ]


settings = Settings()
