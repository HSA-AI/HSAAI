"""
HSAAI Database Engine + Migrations (v4.0)

FIX D-06: USE_ALEMBIC now defaults to 'true'. Was 'false' → production used
create_all() which skipped RLS, indexes, and constraints from migrations.

FIX D-08: Connection pool configured explicitly. Was using SQLAlchemy defaults
(pool_size=5, max_overflow=10) → 12 services × 4 workers × 15 conns = 720
which exceeded Postgres max_connections=200.
"""
import os
import logging
import subprocess
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from backend_core.config import settings

logger = logging.getLogger("hsaai.database")

database_url = settings.effective_database_url
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}

# FIX D-08: Explicit connection pool configuration.
# pool_size + max_overflow per worker × 4 workers × 12 services ≈ 240
# Route through PgBouncer in production to stay under Postgres max_connections.
pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "5"))
pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "1800"))

if database_url.startswith("sqlite"):
    engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True, future=True)
else:
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def import_all_models() -> None:
    """Import all SQLAlchemy models so they register with Base.metadata."""
    from backend_core.db import models  # noqa: F401
    from backend_core.smart_responses import models as smart_response_models  # noqa: F401
    from backend_core.enterprise_integrations import models as enterprise_integration_models  # noqa: F401
    from backend_core.enterprise_upgrade import domain as enterprise_upgrade_models  # noqa: F401
    from backend_core.maturity_upgrade import models as maturity_upgrade_models  # noqa: F401
    from backend_core.enterprise_os import models as enterprise_os_models  # noqa: F401
    from backend_core.knowledge_graph import graph_models as knowledge_graph_models  # noqa: F401


def init_db() -> None:
    """Create all tables via SQLAlchemy metadata (development only)."""
    import_all_models()
    Base.metadata.create_all(bind=engine)


def run_migrations() -> None:
    """Run database migrations.

    FIX D-06: USE_ALEMBIC defaults to 'true' now. Production/staging refuse
    to run with USE_ALEMBIC=false (RLS, indexes, constraints would be missing).
    """
    # FIX D-06: default to 'true' (was 'false')
    use_alembic = os.getenv("USE_ALEMBIC", "true").lower() == "true"
    app_env = os.getenv("APP_ENV", "development").lower()

    if not use_alembic and app_env in {"production", "prod", "staging"}:
        # Refuse to run without alembic in production
        raise RuntimeError(
            "USE_ALEMBIC=false is forbidden in production/staging. "
            "Set USE_ALEMBIC=true and ensure migrations are tested."
        )

    if use_alembic:
        logger.info("USE_ALEMBIC=true — running `alembic upgrade head`")
        candidates = [
            Path.cwd() / "alembic.ini",
            Path(__file__).resolve().parent.parent.parent.parent / "alembic.ini",
            Path(__file__).resolve().parent.parent.parent / "alembic.ini",
        ]
        alembic_ini = next((p for p in candidates if p.exists()), None)
        if alembic_ini is None:
            logger.error("USE_ALEMBIC=true but alembic.ini not found. Falling back to create_all.")
            init_db()
            return
        try:
            result = subprocess.run(
                ["alembic", "-c", str(alembic_ini), "upgrade", "head"],
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
            logger.info("Alembic migration completed:\n%s", result.stdout[-2000:])
            if result.stderr:
                logger.warning("Alembic stderr:\n%s", result.stderr[-1000:])
        except subprocess.CalledProcessError as exc:
            logger.error("Alembic migration FAILED (exit %d):\n%s\n%s",
                         exc.returncode, exc.stdout[-1000:], exc.stderr[-1000:])
            raise
        except FileNotFoundError:
            logger.error("`alembic` command not found. Install with: pip install alembic")
            raise
    else:
        logger.warning(
            "run_migrations() is using Base.metadata.create_all() — dev only. "
            "For production, set USE_ALEMBIC=true and run `alembic upgrade head`."
        )
        init_db()


def check_db() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "type": "postgresql" if "postgresql" in database_url else "sqlite",
            "migrations_mode": "alembic" if os.getenv("USE_ALEMBIC", "true").lower() == "true" else "create_all_dev_only",
            "pool_size": pool_size,
            "max_overflow": max_overflow,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:300]}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
