from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import MetaData, engine_from_config, pool


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

SERVICES_ROOT = os.path.join(PROJECT_ROOT, "services")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if SERVICES_ROOT not in sys.path:
    sys.path.insert(0, SERVICES_ROOT)


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


db_url = (
    os.getenv("DATABASE_URL")
    or os.getenv("SQLALCHEMY_DATABASE_URL")
)

if db_url:
    config.set_main_option("sqlalchemy.url", db_url)


MODEL_MODULES = [
    "backend_core.db.models",
    "backend_core.knowledge_graph.graph_models",
    "backend_core.smart_responses.models",
    "backend_core.maturity_upgrade.models",
    "backend_core.enterprise_os.models",
    "backend_core.enterprise_integrations.models",
    "backend_core.enterprise_upgrade.domain",
    "model_training.db.models",
]


def import_model_modules() -> None:
    for module_name in MODEL_MODULES:
        try:
            __import__(module_name, fromlist=["*"])
            print(f"Registered model module: {module_name}")
        except Exception as exc:
            raise RuntimeError(
                f"Unable to import model module "
                f"{module_name}: {exc}"
            ) from exc


def collect_metadata_objects() -> list[MetaData]:
    metadata_objects: list[MetaData] = []
    seen_ids: set[int] = set()

    for module_name in MODEL_MODULES:
        module = sys.modules.get(module_name)

        if module is None:
            continue

        candidates = []

        base = getattr(module, "Base", None)

        if base is not None:
            metadata = getattr(base, "metadata", None)

            if isinstance(metadata, MetaData):
                candidates.append(metadata)

        metadata = getattr(module, "metadata", None)

        if isinstance(metadata, MetaData):
            candidates.append(metadata)

        metadata = getattr(
            module,
            "MODEL_METADATA",
            None,
        )

        if isinstance(metadata, MetaData):
            candidates.append(metadata)

        for metadata in candidates:
            metadata_id = id(metadata)

            if metadata_id in seen_ids:
                continue

            seen_ids.add(metadata_id)
            metadata_objects.append(metadata)

    return metadata_objects


def build_target_metadata() -> MetaData:
    target_metadata = MetaData()
    seen_table_keys: set[str] = set()

    metadata_objects = collect_metadata_objects()

    print(
        f"Collected {len(metadata_objects)} unique "
        f"SQLAlchemy MetaData objects"
    )

    for metadata in metadata_objects:
        for table_key, table in metadata.tables.items():

            if table_key in seen_table_keys:
                continue

            table.to_metadata(target_metadata)
            seen_table_keys.add(table_key)

    print(
        f"Alembic target metadata contains "
        f"{len(target_metadata.tables)} unique tables"
    )

    return target_metadata


import_model_modules()

target_metadata = build_target_metadata()


def include_object(
    object,
    name,
    type_,
    reflected,
    compare_to,
):
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(
        config.config_ini_section
    )

    if section is None:
        section = {}

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
