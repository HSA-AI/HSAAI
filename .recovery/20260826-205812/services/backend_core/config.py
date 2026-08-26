from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", ".env.production"), extra="ignore")

    app_name: str = "HSAAI Core Backend"
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")

    # Database: production must use PostgreSQL. DATABASE_URL is the source of truth.
    database_url: str = Field(default="sqlite:///./hsaai.db", validation_alias="DATABASE_URL")
    direct_url: str | None = Field(default=None, validation_alias="DIRECT_URL")
    postgres_dsn: str | None = None  # backward compatibility only
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    # Keycloak / OIDC
    keycloak_url: str = Field(default="http://keycloak:8080", validation_alias="KEYCLOAK_URL")
    keycloak_realm: str = Field(default="hsaai", validation_alias="KEYCLOAK_REALM")
    keycloak_client_id: str = Field(default="hsaai-web", validation_alias="KEYCLOAK_CLIENT_ID")
    keycloak_client_secret: str | None = Field(default=None, validation_alias="KEYCLOAK_CLIENT_SECRET")
    keycloak_issuer: str | None = Field(default=None, validation_alias="KEYCLOAK_ISSUER")
    keycloak_audience: str = Field(default="hsaai-api", validation_alias="KEYCLOAK_AUDIENCE")
    verify_keycloak_audience: bool = Field(default=True, validation_alias="VERIFY_KEYCLOAK_AUDIENCE")
    auth_required: bool = Field(default=True, validation_alias="AUTH_REQUIRED")
    # FIX: ALLOW_DEV_RBAC has been permanently disabled. This was a critical
    # security flaw that allowed unauthenticated admin access. The field is
    # kept for backward compatibility with .env files but is always False.
    allow_dev_rbac: bool = Field(default=False, validation_alias="ALLOW_DEV_RBAC")

    # Vector database
    qdrant_url: str = Field(default="http://qdrant:6333", validation_alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="hsaai_knowledge", validation_alias="QDRANT_COLLECTION")
    qdrant_vector_size: int = Field(default=384, validation_alias="QDRANT_VECTOR_SIZE")
    require_qdrant: bool = Field(default=True, validation_alias="REQUIRE_QDRANT")

    # Production security
    cors_allow_origins: str = Field(default="http://localhost:3000", validation_alias="CORS_ALLOW_ORIGINS")
    rate_limit_per_minute: int = Field(default=120, validation_alias="RATE_LIMIT_PER_MINUTE")
    max_upload_bytes: int = Field(default=26214400, validation_alias="RAG_MAX_UPLOAD_BYTES")
    allowed_upload_mime_types: str = Field(default="application/pdf,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", validation_alias="ALLOWED_UPLOAD_MIME_TYPES")


    # Knowledge Graph
    knowledge_graph_enabled: bool = Field(default=True, validation_alias="KNOWLEDGE_GRAPH_ENABLED")
    graph_ingestion_enabled: bool = Field(default=True, validation_alias="GRAPH_INGESTION_ENABLED")
    graph_rag_bridge_enabled: bool = Field(default=True, validation_alias="GRAPH_RAG_BRIDGE_ENABLED")
    neo4j_uri: str | None = Field(default=None, validation_alias="NEO4J_URI")
    neo4j_username: str | None = Field(default=None, validation_alias="NEO4J_USERNAME")
    neo4j_password: str | None = Field(default=None, validation_alias="NEO4J_PASSWORD")

    # Human approval notifications
    approval_email_from: str | None = Field(default=None, validation_alias="APPROVAL_EMAIL_FROM")
    smtp_host: str | None = Field(default=None, validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, validation_alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    teams_webhook_url: str | None = Field(default=None, validation_alias="TEAMS_WEBHOOK_URL")
    slack_webhook_url: str | None = Field(default=None, validation_alias="SLACK_WEBHOOK_URL")
    approval_webhook_url: str | None = Field(default=None, validation_alias="APPROVAL_WEBHOOK_URL")

    # FinOps
    llm_provider: str = Field(default="ollama", validation_alias="LLM_PROVIDER")
    llm_model: str = Field(default="qwen2.5:7b-instruct", validation_alias="LLM_MODEL")
    llm_input_cost_per_1k: float = Field(default=0.0, validation_alias="LLM_INPUT_COST_PER_1K")
    llm_output_cost_per_1k: float = Field(default=0.0, validation_alias="LLM_OUTPUT_COST_PER_1K")
    monthly_ai_budget: float = Field(default=0.0, validation_alias="MONTHLY_AI_BUDGET")
    cost_alert_threshold: float = Field(default=0.8, validation_alias="COST_ALERT_THRESHOLD")

    @property
    def is_production(self) -> bool:
        return (self.app_env or self.environment).lower() in {"production", "prod"}

    @property
    def effective_database_url(self) -> str:
        return self.database_url or self.postgres_dsn or "sqlite:///./hsaai.db"

    @property
    def effective_keycloak_issuer(self) -> str:
        return self.keycloak_issuer or f"{self.keycloak_url.rstrip('/')}/realms/{self.keycloak_realm}"

    @field_validator("keycloak_client_secret", "smtp_password")
    @classmethod
    def reject_placeholder_secret(cls, value: str | None):
        if value and value.lower() in {"change-me", "change-me-in-production", "secret", "password"}:
            raise ValueError("Production secrets must not use placeholder values")
        return value

    @model_validator(mode="after")
    def validate_production(self):
        if self.is_production:
            if self.effective_database_url.startswith("sqlite"):
                raise ValueError("SQLite is forbidden in production. Set DATABASE_URL to PostgreSQL.")
            if "postgresql" not in self.effective_database_url:
                raise ValueError("Production DATABASE_URL must be PostgreSQL.")
            required = {
                "KEYCLOAK_URL": self.keycloak_url,
                "KEYCLOAK_REALM": self.keycloak_realm,
                "KEYCLOAK_CLIENT_ID": self.keycloak_client_id,
                "KEYCLOAK_CLIENT_SECRET": self.keycloak_client_secret,
                "QDRANT_URL": self.qdrant_url,
                "QDRANT_COLLECTION": self.qdrant_collection,
            }
            missing = [k for k, v in required.items() if not v]
            if missing:
                raise ValueError(f"Missing required production environment variables: {', '.join(missing)}")
            if self.allow_dev_rbac:
                raise ValueError("ALLOW_DEV_RBAC must be false in production")
        return self

settings = Settings()
