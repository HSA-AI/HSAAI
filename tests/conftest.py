"""
HSAAI Test Configuration — Global Fixtures (v4.0)

FIX D-09: Was defining NO fixtures — e2e tests referenced undefined
'authenticated_page', 'db_session', 'test_client', etc.

FIXED (audit): the module docstring previously advertised fixtures that do
not exist here (postgres_container, redis_container, authenticated_page).
Fixtures actually defined in this file:
  - configure_test_env (session-scoped, autouse): pins test env vars
  - test_settings: dict of test settings (DB URL, JWT secret, Keycloak)
  - db_session: per-test async SQLAlchemy session (SQLite/aiosqlite by
    default; override DATABASE_URL to point at a Postgres testcontainer)
  - test_client / auth_token / authenticated_client / admin_token:
    FastAPI test clients + JWT helpers (see below)

e2e tests use pytest-playwright's `page` fixture (tests/requirements.txt
installs pytest-playwright; browsers: `playwright install chromium`).
"""
import os
import sys
from pathlib import Path

# ─── CD-003 Fix: Add packages/ and services/ to sys.path ───────────
BASE_DIR = Path(__file__).parent.parent
PACKAGES_DIR = BASE_DIR / "packages"
SERVICES_DIR = BASE_DIR / "services"

for p in [str(PACKAGES_DIR), str(SERVICES_DIR), str(BASE_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

COMMON_DIR = PACKAGES_DIR / "common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

# ─── CD-005 Fix: Set DATABASE_URL for tests ────────────────────────
os.environ.setdefault("DATABASE_URL", f"sqlite:///{BASE_DIR}/tmp/hsaai_test.db")
os.environ.setdefault("LOCAL_FILE_STORAGE", f"{BASE_DIR}/tmp/local_uploads")
os.environ.setdefault("RAG_EVENT_DB", f"{BASE_DIR}/tmp/rag_events.db")
os.environ.setdefault("TESTING", "true")
# FIX D-09: required by auth_service/main.py
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-characters-long-for-testing-only")

tmp_dir = BASE_DIR / "tmp"
tmp_dir.mkdir(exist_ok=True)

# ─── pytest configuration ──────────────────────────────────────────
import pytest
import pytest_asyncio


@pytest.fixture(scope="session", autouse=True)
def configure_test_env():
    """Configure test environment once per session."""
    os.environ["TESTING"] = "true"
    os.environ["DEPLOY_ENV"] = "test"
    yield


# ─── FIX D-09: Real fixtures for tests ─────────────────────────────

@pytest.fixture
def test_settings():
    """Provide test settings."""
    return {
        "DATABASE_URL": os.environ["DATABASE_URL"],
        "TESTING": "true",
        "JWT_SECRET": "test-secret-at-least-32-characters-long-for-testing-only",
        "KEYCLOAK_ISSUER": "http://test-keycloak:8080/realms/hsaai",
        "KEYCLOAK_AUDIENCE": "hsaai-api",
    }


@pytest_asyncio.fixture
async def db_session():
    """Per-test async DB session with rollback isolation.

    Uses SQLite in-memory by default. For integration tests, override
    DATABASE_URL to point at a Postgres testcontainer.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    db_url = os.environ["DATABASE_URL"]
    # Convert sqlite:// to sqlite+aiosqlite:// for async
    if db_url.startswith("sqlite://") and "+aiosqlite" not in db_url:
        db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")

    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        from backend_core.db.database import Base, import_all_models
        import_all_models()
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()
    await engine.dispose()


@pytest_asyncio.fixture
async def test_client(db_session):
    """FastAPI test client with mocked dependencies.

    Provides a httpx.AsyncClient bound to the backend_core app.
    Authentication remains enforced; unsigned test tokens must be rejected.
    """
    from httpx import AsyncClient, ASGITransport
    os.environ["ALLOW_DEV_RBAC"] = "false"
    from backend_core.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_token():
    """A valid-looking JWT for testing (unsigned, test-only)."""
    import json
    import base64
    import time

    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload_data = {
        "sub": "test-user-001",
        "tenant_id": "test-tenant",
        "workspace_id": "test-workspace",
        "roles": ["ai_user"],
        "iss": "http://test-keycloak:8080/realms/hsaai",
        "aud": "hsaai-api",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    return f"{header}.{payload}."


@pytest_asyncio.fixture
async def authenticated_client(test_client, auth_token):
    """Test client with Authorization header preset."""
    test_client.headers["Authorization"] = f"Bearer {auth_token}"
    return test_client


@pytest.fixture
def admin_token():
    """JWT with admin role for testing admin endpoints."""
    import json
    import base64
    import time

    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload_data = {
        "sub": "test-admin-001",
        "tenant_id": "test-tenant",
        "workspace_id": "test-workspace",
        "roles": ["hsaai_admin"],
        "iss": "http://test-keycloak:8080/realms/hsaai",
        "aud": "hsaai-api",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    return f"{header}.{payload}."
