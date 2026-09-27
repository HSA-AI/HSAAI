import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "packages", ROOT / "services"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEPLOY_ENV", "development")
os.environ.setdefault("JWT_SECRET", "unit-test-secret-" + "x" * 40)
os.environ.setdefault("USE_OBJECT_STORAGE", "false")
os.environ.setdefault("ALLOW_EXTERNAL_AI", "false")
os.environ.setdefault("ALLOW_EXTERNAL_APIS", "false")
os.environ.setdefault("INTERNAL_ONLY_MODE", "true")
os.environ.setdefault("STRICT_EGRESS_DENY", "true")
