"""
إعدادات pytest لحزمة اختبارات الموصلات
=======================================
تضمن أن packages/ على sys.path ليعمل `from packages.common.connectors import ...`.
"""
import sys
from pathlib import Path

# إضافة جذر المشروع و packages/ إلى sys.path
_project_root = Path(__file__).resolve().parents[4]  # hsaai_extract/
_packages_dir = str(_project_root / "packages")
if _packages_dir not in sys.path:
    sys.path.insert(0, _packages_dir)

_project_root_str = str(_project_root)
if _project_root_str not in sys.path:
    sys.path.insert(0, _project_root_str)
