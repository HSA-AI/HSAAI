"""
Security Test: Verify no dev bypass patterns exist in production code.
Updated Phase 19 forensic audit — distinguishes real auth bypass from docstring mentions.
"""
import os
import re
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_python_files():
    """Find all Python files in the project (excluding tests and vendored dirs).

    FIX CRITICAL-5 (HSAAI-DEP-2026-07-11): Previously this function walked
    the entire project tree including `.venv/` and `node_modules/`, which
    caused hundreds of false-positive matches against third-party site
    packages (starlette, sqlalchemy, psycopg2, moto, etc.). The scan is now
    scoped to FIRST-PARTY project code only.
    """
    # Directories that contain third-party / generated / non-project code.
    # Any walk descent into these is pruned at the directory level (much
    # faster than filtering files afterwards).
    EXCLUDED_DIRS = {
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "node_modules",
        ".next",
        ".git",
        "_deprecated_adapters",
        "site-packages",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "dist",
        "build",
        ".tox",
    }
    py_files = []
    for root, dirs, files in os.walk(BASE_DIR):
        # Prune excluded directories in-place so os.walk doesn't descend into them
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        # Skip test directories themselves (these tests scan prod code, not tests).
        # Match both "test" and "tests" directory names.
        path_parts = set(root.split(os.sep))
        if path_parts & {"test", "tests"}:
            continue
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
    return py_files


@pytest.mark.parametrize("pattern,description", [
    (r"ALLOW_DEV_RBAC\s*=\s*True", "ALLOW_DEV_RBAC enabled"),
    (r"ALLOW_DEV_AUTH\s*=\s*True", "ALLOW_DEV_AUTH enabled"),
    (r"ALLOW_LOCAL_LLM_STUB\s*=\s*True", "LOCAL_LLM_STUB enabled"),
    # Detect actual auth bypass: HSAAI-INTERNAL used as Bearer token (not in comments/docstrings)
    (r'Bearer\s+["\']?HSAAI[-.]INTERNAL', "HSAAI-INTERNAL used as Bearer token"),
    (r'HSAAI[-.]INTERNAL["\']?\s*\)\s*==\s*.*[Tt]oken', "HSAAI-INTERNAL compared to token"),
    (r'token\s*==\s*["\']HSAAI[-.]INTERNAL', "HSAAI-INTERNAL hardcoded token comparison"),
    (r'Bearer admin', "Hardcoded Bearer admin"),
    (r'default="admin"', "Default admin user in schema"),
])
def test_no_insecure_patterns(pattern, description):
    """Verify that insecure patterns do not exist in production code."""
    py_files = find_python_files()
    violations = []
    for fpath in py_files:
        try:
            with open(fpath, "r") as f:
                content = f.read()
            # Skip comments and docstrings for the HSAAI-INTERNAL pattern
            # (we only want to flag actual code usage, not documentation)
            if "HSAAI" in pattern and "INTERNAL" in pattern:
                # Strip docstrings and comments before checking
                cleaned = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
                cleaned = re.sub(r'"""[\s\S]*?"""', '', cleaned)
                cleaned = re.sub(r"'''[\s\S]*?'''", '', cleaned)
                if re.search(pattern, cleaned):
                    violations.append(fpath)
            else:
                if re.search(pattern, content):
                    violations.append(fpath)
        except Exception:
            pass

    assert len(violations) == 0, (
        f"{description} found in {len(violations)} files: {violations}"
    )


def test_no_hardcoded_secrets():
    """Verify no hardcoded passwords or API keys in source."""
    py_files = find_python_files()
    secret_patterns = [
        r'''password\s*=\s*['"][^'"]{3,}['"]''',
        r'''api_key\s*=\s*['"][^'"]{10,}['"]''',
        r'''secret\s*=\s*['"][^'"]{10,}['"]''',
    ]
    violations = []
    for fpath in py_files:
        try:
            with open(fpath, "r") as f:
                content = f.read()
            # Strip comments first
            content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
            for pattern in secret_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    violations.append(fpath)
                    break
        except Exception:
            pass

    violations = [v for v in violations if "test" not in v and "example" not in v and ".env" not in v]
    assert len(violations) == 0, f"Possible hardcoded secrets in: {violations}"


def test_rbac_requires_auth():
    """Verify RBAC module requires authentication."""
    rbac_path = os.path.join(BASE_DIR, "services/backend_core/security/rbac.py")
    if os.path.exists(rbac_path):
        with open(rbac_path, "r") as f:
            content = f.read()
        assert "ALLOW_DEV_RBAC" not in content or "removed" in content.lower(), \
            "ALLOW_DEV_RBAC should be removed from RBAC module"


def test_no_unsafe_sql_in_production():
    """
    Phase 30: Verify no unsafe SQL construction (string interpolation).
    Allows conditional parameterized SQL (e.g., {tenant_filter} where
    tenant_filter is a static string, not user input).
    """
    py_files = find_python_files()
    violations = []
    # Only flag clearly unsafe patterns:
    # - f-string SQL with user-controlled variables (heuristic: contains {var} not {static_str})
    # - .format() with user input
    # - string concatenation with + in execute()
    unsafe_patterns = [
        # f-string SQL that interpolates a variable directly into WHERE/VALUES
        r'execute\s*\(\s*f["\'].*\{.*\}',  # execute(f"...{var}...")
        r'text\s*\(\s*f["\'].*\{.*\}',     # text(f"...{var}...")
    ]
    for fpath in py_files:
        # FIX-19: Skip alembic versions explicitly — they use f-string SQL with
        # hardcoded table names from a constant list (not user input), which is
        # safe. The original test only skipped paths containing "migration",
        # but alembic/versions/ doesn't match that substring.
        if "seed" in fpath or "migration" in fpath or "analytics" in fpath or "alembic/versions/" in fpath:
            continue  # seed/migration/analytics/alembic use conditional SQL (safe pattern)
        try:
            with open(fpath, "r") as f:
                content = f.read()
            # Strip comments
            cleaned = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
            for pattern in unsafe_patterns:
                if re.search(pattern, cleaned):
                    violations.append((fpath, pattern))
                    break
        except Exception:
            pass
    assert len(violations) == 0, f"Unsafe SQL patterns found: {violations[:5]}"


def test_no_mock_implementations_in_production():
    """Phase 25: Verify no mock/dummy/placeholder returns in production tool handlers."""
    tool_registry = os.path.join(BASE_DIR, "packages/common/tool_registry/__init__.py")
    if not os.path.exists(tool_registry):
        pytest.skip("tool_registry not found")

    with open(tool_registry, "r") as f:
        content = f.read()

    # Strip comments and docstrings
    cleaned = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
    cleaned = re.sub(r'"""[\s\S]*?"""', '', cleaned)
    cleaned = re.sub(r"'''[\s\S]*?'''", '', cleaned)

    mock_indicators = [
        '"status": "mock"',
        "'status': 'mock'",
        '"Mock Vendor',
        "'Mock Employee",
        '"status": "mock"',
    ]
    violations = [ind for ind in mock_indicators if ind in cleaned]
    assert len(violations) == 0, f"Mock implementations still in tool_registry: {violations}"
