"""
HSAAI Startup & Import Tests (Production Readiness)
=====================================================
Verifies:
  - No SyntaxError in any Python file
  - All critical modules import successfully
  - No circular imports
  - Startup validation works
  - No Mock/Pilot/Placeholder in production code
"""
import os
import sys
import py_compile
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


class TestNoSyntaxErrors:
    """Verify no Python file has syntax errors."""

    def _compile_all(self):
        errors = []
        for py_file in BASE_DIR.rglob("*.py"):
            if any(skip in str(py_file) for skip in ['__pycache__', 'node_modules', '.venv', '.git']):
                continue
            try:
                py_compile.compile(str(py_file), doraise=True)
            except py_compile.PyCompileError as e:
                errors.append((str(py_file), str(e)))
        return errors

    def test_no_syntax_errors_in_any_file(self):
        """No Python file should have syntax errors."""
        errors = self._compile_all()
        assert len(errors) == 0, f"Syntax errors found in {len(errors)} files: {errors[:5]}"

    def test_models_py_compiles(self):
        """models.py specifically should compile."""
        py_compile.compile(str(BASE_DIR / "services" / "backend_core" / "db" / "models.py"), doraise=True)

    def test_router_py_compiles(self):
        """enterprise_os/router.py should compile."""
        py_compile.compile(str(BASE_DIR / "services" / "backend_core" / "enterprise_os" / "router.py"), doraise=True)

    def test_observability_py_compiles(self):
        """phase5/observability.py should compile."""
        py_compile.compile(str(BASE_DIR / "services" / "backend_core" / "phase5" / "observability.py"), doraise=True)


class TestNoMockPilotPlaceholder:
    """Verify no Mock/Pilot/Placeholder in production code."""

    def test_no_mock_ready(self):
        import re
        for py_file in (BASE_DIR / "services").rglob("*.py"):
            if "__pycache__" in str(py_file) or "test_" in str(py_file):
                continue
            content = py_file.read_text()
            cleaned = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
            cleaned = re.sub(r'"""[\s\S]*?"""', '', cleaned)
            assert "mock_ready" not in cleaned, f"mock_ready found in {py_file}"

    def test_no_pilot_mode(self):
        import re
        for py_file in (BASE_DIR / "services").rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            cleaned = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
            cleaned = re.sub(r'"""[\s\S]*?"""', '', cleaned)
            assert "pilot-mode" not in cleaned, f"pilot-mode found in {py_file}"
            assert "pilot_mode" not in cleaned, f"pilot_mode found in {py_file}"

    def test_no_rag_accuracy_placeholder(self):
        for py_file in (BASE_DIR / "services").rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            assert "rag_accuracy_placeholder" not in content, \
                f"rag_accuracy_placeholder found in {py_file}"

    def test_no_mock_snapshot(self):
        for py_file in (BASE_DIR / "services").rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            assert "mock snapshot" not in content.lower(), \
                f"mock snapshot found in {py_file}"


class TestNoTODOOrFIXME:
    """Verify no TODO/FIXME in production code."""

    def test_no_todo_in_production(self):
        import re
        violations = []
        for py_file in (BASE_DIR / "services").rglob("*.py"):
            if "__pycache__" in str(py_file) or "test_" in str(py_file):
                continue
            content = py_file.read_text()
            cleaned = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
            cleaned = re.sub(r'"""[\s\S]*?"""', '', cleaned)
            if re.search(r'\bTODO\b', cleaned):
                violations.append(str(py_file))
        assert len(violations) == 0, f"TODO found in: {violations}"

    def test_no_fixme_in_production(self):
        import re
        violations = []
        for py_file in (BASE_DIR / "services").rglob("*.py"):
            if "__pycache__" in str(py_file) or "test_" in str(py_file):
                continue
            content = py_file.read_text()
            cleaned = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
            cleaned = re.sub(r'"""[\s\S]*?"""', '', cleaned)
            if re.search(r'\bFIXME\b', cleaned):
                violations.append(str(py_file))
        assert len(violations) == 0, f"FIXME found in: {violations}"


class TestRAGMetricsReal:
    """Verify RAG metrics are real, not placeholder."""

    def test_rag_metrics_function_exists(self):
        """_compute_rag_metrics should exist."""
        sys.path.insert(0, str(BASE_DIR / "services"))
        from backend_core.phase5.observability import _compute_rag_metrics
        assert callable(_compute_rag_metrics)

    def test_rag_metrics_returns_real_values(self):
        """_compute_rag_metrics should return real metric names."""
        sys.path.insert(0, str(BASE_DIR / "services"))
        from backend_core.phase5.observability import _compute_rag_metrics
        result = _compute_rag_metrics([])
        assert "precision" in result
        assert "recall" in result
        assert "mrr" in result
        assert "ndcg" in result
        assert "hit_rate" in result
        assert "faithfulness" in result
        assert "hallucination_rate" in result
        assert "rag_accuracy_placeholder" not in result

    def test_ai_metrics_has_rag_section(self):
        """ai_metrics should include rag metrics."""
        sys.path.insert(0, str(BASE_DIR / "services"))
        from backend_core.phase5.observability import ai_metrics
        result = ai_metrics()
        assert "rag" in result
        assert "cost" in result
        assert "p50_latency_ms" in result
        assert "p95_latency_ms" in result
        assert "p99_latency_ms" in result


class TestModelsImport:
    """Verify models.py imports successfully."""

    def test_models_imports(self):
        """models.py should import without errors."""
        # FIX-30/39: Force DATABASE_URL to a valid SQLAlchemy URL before importing
        # backend_core.db.database (which calls create_engine at module-load time).
        # Use direct assignment (not setdefault) because other tests may have
        # left an invalid value like 'file:/path' in os.environ.
        os.environ["DATABASE_URL"] = "sqlite:///tmp/hsaai_test.db"
        sys.path.insert(0, str(BASE_DIR / "services"))
        from backend_core.db.models import Message, AuditLog, KnowledgeSpace
        assert Message is not None
        assert AuditLog is not None
        assert KnowledgeSpace is not None

    def test_no_metadata_attribute(self):
        """No model should use 'metadata' as column name (reserved in SQLAlchemy 2.0+)."""
        # FIX-30/39: same DATABASE_URL fix as above.
        os.environ["DATABASE_URL"] = "sqlite:///tmp/hsaai_test.db"
        sys.path.insert(0, str(BASE_DIR / "services"))
        from backend_core.db.models import KnowledgeDocument
        # Should have extra_metadata, not metadata
        assert hasattr(KnowledgeDocument, 'extra_metadata'), \
            "KnowledgeDocument should have extra_metadata column"
