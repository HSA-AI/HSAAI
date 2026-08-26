from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from services.model_training.config import settings


# ============================================================
# Database Engine
# ============================================================

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)


# ============================================================
# Session Factory
# ============================================================

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


# ============================================================
# SQLAlchemy Base
# ============================================================

class Base(DeclarativeBase):
    pass


# ============================================================
# Tenant / PostgreSQL RLS
# ============================================================

MAX_TENANT_ID_LENGTH = 64


def validate_tenant_id(tenant_id: str) -> str:
    """
    Validate and normalize tenant_id.

    IMPORTANT:
    tenant_id must come from authenticated JWT claims.
    Never trust a tenant ID supplied by a client header/body.
    """
    if tenant_id is None:
        raise ValueError("tenant_id is required")

    value = str(tenant_id).strip()

    if not value:
        raise ValueError("tenant_id cannot be empty")

    if len(value) > MAX_TENANT_ID_LENGTH:
        raise ValueError(
            "tenant_id exceeds maximum length"
        )

    return value


def set_tenant_id(db: Session, tenant_id: str) -> None:
    """
    Bind the current PostgreSQL transaction/session to a tenant.

    PostgreSQL RLS policies can read:

        current_setting('app.tenant_id', true)

    The value must originate from authenticated JWT claims.
    """
    tenant_id = validate_tenant_id(tenant_id)

    db.execute(
        text(
            "SELECT set_config("
            "'app.tenant_id', "
            ":tenant_id, "
            "true"
            ")"
        ),
        {
            "tenant_id": tenant_id,
        },
    )


def get_current_tenant_id(db: Session) -> str | None:
    """
    Return the tenant currently configured for this database session.
    """
    result = db.execute(
        text(
            "SELECT current_setting("
            "'app.tenant_id', "
            "true"
            ")"
        )
    )

    value = result.scalar()

    if value is None:
        return None

    value = str(value).strip()

    return value or None


def require_tenant_id(db: Session) -> str:
    """
    Require an active tenant context.

    Raises RuntimeError if the session has no tenant configured.
    """
    tenant_id = get_current_tenant_id(db)

    if not tenant_id:
        raise RuntimeError(
            "PostgreSQL RLS tenant context is not configured"
        )

    return validate_tenant_id(tenant_id)


# ============================================================
# Database Dependency
# ============================================================

def get_db() -> Generator[Session, None, None]:
    """
    Standard FastAPI database dependency.

    IMPORTANT:
    This function intentionally does NOT invent a tenant.

    Protected API dependencies must call set_tenant_id()
    using tenant_id extracted from authenticated JWT claims
    before executing tenant-scoped queries.
    """
    db = SessionLocal()

    try:
        yield db

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# Tenant-aware Database Dependency
# ============================================================

def get_tenant_db(
    tenant_id: str,
) -> Generator[Session, None, None]:
    """
    Create a tenant-bound SQLAlchemy session.

    Intended for internal/service/worker code where the tenant
    has already been obtained from a trusted authenticated context.
    """
    tenant_id = validate_tenant_id(tenant_id)

    db = SessionLocal()

    try:
        set_tenant_id(db, tenant_id)
        yield db

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# Health Check
# ============================================================

def check_database_connection() -> bool:
    """
    Verify that PostgreSQL is reachable.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return True

    except Exception:
        return False


def database_health() -> dict[str, object]:
    """
    Return database health information.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "postgresql",
        }

    except Exception as exc:
        return {
            "status": "unhealthy",
            "database": "postgresql",
            "error": str(exc),
        }
