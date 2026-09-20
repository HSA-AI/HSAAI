
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    app_name: str = "HSAAI Model Training Service"
    environment: str = Field(default="production", alias="ENVIRONMENT")
    database_url: str = Field(default="postgresql+psycopg://hsaai:hsaai@postgres:5432/hsaai_training", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    artifacts_root: str = Field(default="/app/artifacts", alias="ARTIFACTS_ROOT")
    hf_home: str = Field(default="/app/.cache/huggingface", alias="HF_HOME")
    allowed_roles: str = "Super Admin,AI Admin,ML Engineer,Data Scientist,Viewer"
    default_queue: str = "training"
    max_upload_mb: int = 5120

settings = Settings()
