"""
HSAAI Database Evolution Audit (Phase 13)
==========================================
Audits models vs Alembic migrations vs actual schema.
Detects: missing migrations, orphan tables, schema drift, unsafe changes.
"""
import os
import re
import json
from pathlib import Path
from collections import defaultdict


def audit_models(models_dir: str) -> dict:
    """Audit SQLAlchemy models for table definitions."""
    tables = {}
    for py_file in Path(models_dir).rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        # Find __tablename__ definitions
        matches = re.findall(r'__tablename__\s*=\s*["\']([^"\']+)["\']', content)
        for table in matches:
            tables[table] = {
                "file": str(py_file),
                "columns": _extract_columns(content),
            }
    return tables


def _extract_columns(content: str) -> list:
    """Extract column names from a SQLAlchemy model."""
    columns = []
    # Match Column("name", ...) or name = Column(...)
    matches = re.findall(r'(?:Column\(["\'](\w+)["\']|(\w+)\s*=\s*Column)', content)
    for m in matches:
        col = m[0] or m[1]
        if col and col not in {"id", "created_at", "updated_at"}:  # common ones
            columns.append(col)
    return list(set(columns))


def audit_migrations(alembic_dir: str) -> dict:
    """Audit Alembic migrations for upgrade/downgrade functions."""
    migrations = []
    versions_dir = Path(alembic_dir) / "versions"
    if not versions_dir.exists():
        return {"migrations": [], "missing_versions_dir": True}
    for py_file in versions_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        revision = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", content)
        down_revision = re.search(r"down_revision\s*=\s*['\"]?([^'\"]*)['\"]?", content)
        creates = re.findall(r"create_table\(['\"](\w+)['\"]", content)
        drops = re.findall(r"drop_table\(['\"](\w+)['\"]", content)
        migrations.append({
            "file": py_file.name,
            "revision": revision.group(1) if revision else None,
            "down_revision": down_revision.group(1) if down_revision else None,
            "creates_tables": creates,
            "drops_tables": drops,
        })
    return {"migrations": migrations, "missing_versions_dir": False}


def audit_schema_sql(init_sql: str) -> dict:
    """Audit PostgreSQL init.sql for table definitions."""
    if not Path(init_sql).exists():
        return {"tables": [], "missing": True}
    content = Path(init_sql).read_text()
    tables = re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", content, re.IGNORECASE)
    return {"tables": tables, "missing": False}


def detect_drift(models: dict, migrations: dict, schema: dict) -> list:
    """Detect drift between models, migrations, and schema."""
    issues = []
    model_tables = set(models.keys())
    migration_tables = set()
    for m in migrations.get("migrations", []):
        migration_tables.update(m["creates_tables"])
    schema_tables = set(schema.get("tables", []))

    # Tables in models but not in migrations
    for t in model_tables - migration_tables:
        issues.append({
            "type": "MISSING_MIGRATION",
            "table": t,
            "severity": "HIGH",
            "description": f"Table '{t}' defined in model but no migration creates it",
        })

    # Tables in migrations but not in models
    for t in migration_tables - model_tables:
        issues.append({
            "type": "ORPHAN_MIGRATION",
            "table": t,
            "severity": "MEDIUM",
            "description": f"Table '{t}' has migration but no model",
        })

    # Tables in schema but not in models
    for t in schema_tables - model_tables:
        issues.append({
            "type": "SCHEMA_ONLY",
            "table": t,
            "severity": "LOW",
            "description": f"Table '{t}' in schema but no model (may be reference data)",
        })

    return issues


def generate_missing_migrations(issues: list) -> list:
    """Generate Alembic migration stubs for missing tables."""
    migrations = []
    for issue in issues:
        if issue["type"] == "MISSING_MIGRATION":
            stub = f'''# Auto-generated migration for table: {issue["table"]}
from alembic import op
import sqlalchemy as sa

revision = 'auto_{issue["table"]}'
down_revision = None

def upgrade():
    op.create_table('{issue["table"]}',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_{issue["table"]}_tenant', '{issue["table"]}', ['tenant_id'])

def downgrade():
    op.drop_table('{issue["table"]}')
'''
            migrations.append(stub)
    return migrations


if __name__ == "__main__":
    print("=" * 60)
    print("HSAAI Database Evolution Audit (Phase 13)")
    print("=" * 60)

    models = audit_models("services/backend_core/db/models")
    migrations = audit_migrations("alembic")
    schema = audit_schema_sql("infrastructure/postgres/init.sql")

    print(f"\nModels: {len(models)} tables defined")
    print(f"Migrations: {len(migrations.get('migrations', []))} files")
    print(f"Schema (init.sql): {len(schema.get('tables', []))} tables")

    print("\n--- Model Tables ---")
    for t, info in sorted(models.items()):
        print(f"  {t}: {len(info['columns'])} columns ({info['file']})")

    print("\n--- Migration Files ---")
    for m in migrations.get("migrations", []):
        print(f"  {m['file']}: creates={m['creates_tables']}, drops={m['drops_tables']}")

    print("\n--- Schema Tables (init.sql) ---")
    for t in schema.get("tables", []):
        print(f"  {t}")

    drift = detect_drift(models, migrations, schema)
    print(f"\n--- Drift Detection: {len(drift)} issues ---")
    for issue in drift:
        print(f"  [{issue['severity']}] {issue['type']}: {issue['description']}")

    print("\n--- Audit Complete ---")
