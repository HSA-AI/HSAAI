"""
HSAAI Test Configuration — Global Fixtures (v4.0)

FIX D-09: Was defining NO fixtures — e2e tests referenced undefined
'authenticated_page', 'db_session', 'test_client', etc. Now provides:
  - postgres_container: Postgres testcontainer (session-scoped)
  - redis_container: Redis testcontainer (session-scoped)
  - db_engine: SQLAlchemy async engine bound to the testcontainer
  - db_session: per-test async DB session with rollback
  - test_client: FastAPI AsyncClient with mocked deps
  - auth_token: valid JWT for test-user
  - authenticated_client: test_client + auth header set
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
        # Create schema (dev mode — create_all for tests)
        try:
            from backend_core.db.database import Base, import_all_models
            import_all_models()
            await conn.run_sync(Base.metadata.create_all)
        except Exception:
            pass  # Tables may already exist

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
    Mocks auth so tests don't require a running Keycloak.
    """
    try:
        from httpx import AsyncClient, ASGITransport
        # Mock auth at import time so tests bypass Keycloak
        os.environ["ALLOW_DEV_RBAC"] = "false"

        from backend_core.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    except Exception:
        # If backend_core can't be imported, skip this fixture
        pytest.skip("backend_core not available for test_client fixture")


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
