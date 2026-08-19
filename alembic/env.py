"""Alembic environment configuration for HSAAI Enterprise.

Imports all model bases and configures migration with proper
metadata collection from all service modules.
"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services"))

config = context.config

# Override sqlalchemy.url from environment if available
db_url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models to register them with their respective Base.metadata
# Each module defines its own Base; we collect all metadata objects
_all_metadata = []

def _import_models():
    """Import all model modules to register their tables with SQLAlchemy metadata.

    FIX D-03: Added model_training.db.models — was missing, so its 8 tables
    were never included in autogenerate or migration target_metadata.
    """
    model_modules = [
        "backend_core.db.models",
        "backend_core.knowledge_graph.graph_models",
        "backend_core.smart_responses.models",
        "backend_core.maturity_upgrade.models",
        "backend_core.enterprise_os.models",
        "backend_core.enterprise_integrations.models",
        "backend_core.enterprise_upgrade.domain",
        # FIX D-03: model_training tables were never migrated
        "model_training.db.models",
    ]
    for module_name in model_modules:
        try:
            mod = __import__(module_name, fromlist=["Base"])
            if hasattr(mod, "Base") and hasattr(mod.Base, "metadata"):
                _all_metadata.append(mod.Base.metadata)
                print(f"  Registered metadata from {module_name}")
        except ImportError as e:
            print(f"  WARNING: Could not import {module_name}: {e}")
        except Exception as e:
            print(f"  WARNING: Error loading {module_name}: {e}")

_import_models()

target_metadata = _all_metadata if _all_metadata else None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL generation without DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connected to the database)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
