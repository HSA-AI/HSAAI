"""
HSAAI Fine-Tuning Production Tests
"""
import os, sys, json, pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


class TestFinetunePipelineV2:
    """Test the production fine-tuning pipeline."""

    def test_pipeline_compiles(self):
        import py_compile
        py_compile.compile(str(BASE_DIR / "services" / "model_training" / "finetune_pipeline_v2.py"), doraise=True)

    def test_pii_redaction(self):
        sys.path.insert(0, str(BASE_DIR / "services" / "model_training"))
        from finetune_pipeline_v2 import redact_pii
        # National ID
        assert "[REDACTED" in redact_pii("ID: 1234567890")
        # Email
        assert "[REDACTED" in redact_pii("Email: test@hsagroup.com")
        # IBAN
        assert "[REDACTED" in redact_pii("IBAN: SA0380000000608010167519")

    def test_clean_text(self):
        sys.path.insert(0, str(BASE_DIR / "services" / "model_training"))
        from finetune_pipeline_v2 import clean_text
        assert clean_text("hello\x00world") == "helloworld"
        assert clean_text("  multiple   spaces  ") == "multiple spaces"

    def test_detect_language(self):
        sys.path.insert(0, str(BASE_DIR / "services" / "model_training"))
        from finetune_pipeline_v2 import detect_language
        assert detect_language("مرحبا بكم في المنصة") == "ar"
        assert detect_language("Welcome to the platform") == "en"

    def test_quality_check(self):
        sys.path.insert(0, str(BASE_DIR / "services" / "model_training"))
        from finetune_pipeline_v2 import quality_check
        ok, _ = quality_check({"instruction": "What is the policy?", "response": "The policy states..."})
        assert ok is True
        ok, reason = quality_check({"instruction": "Hi", "response": "Hello"})
        assert ok is False
        assert "short" in reason


class TestModelRegistry:
    """Test the model registry."""

    def test_registry_compiles(self):
        import py_compile
        py_compile.compile(str(BASE_DIR / "services" / "model_training" / "model_registry.py"), doraise=True)

    def test_register_and_retrieve(self, tmp_path):
        sys.path.insert(0, str(BASE_DIR / "services" / "model_training"))
        from model_registry import ModelRegistry, ModelVersion, ModelStatus
        reg = ModelRegistry(registry_dir=str(tmp_path))
        model = ModelVersion(
            model_id="hsaai-r1", version="1.0.0",
            base_model="Qwen/Qwen2.5-7B-Instruct",
            accuracy=0.85, lora_r=64,
        )
        reg.register(model)
        latest = reg.get_latest("hsaai-r1")
        assert latest is not None
        assert latest["version"] == "1.0.0"

    def test_promote_to_production(self, tmp_path):
        sys.path.insert(0, str(BASE_DIR / "services" / "model_training"))
        from model_registry import ModelRegistry, ModelVersion, ModelStatus
        reg = ModelRegistry(registry_dir=str(tmp_path))
        # Register and promote v1 to production first
        reg.register(ModelVersion(model_id="hsaai-r1", version="1.0", base_model="Qwen"))
        reg.promote("hsaai-r1", "1.0", ModelStatus.PRODUCTION, "admin")
        # Register v2 and promote to production (v1 gets archived)
        reg.register(ModelVersion(model_id="hsaai-r1", version="2.0", base_model="Qwen"))
        reg.promote("hsaai-r1", "2.0", ModelStatus.PRODUCTION, "admin")
        prod = reg.get_production("hsaai-r1")
        assert prod["version"] == "2.0"
        # v1 should be archived
        v1 = [m for m in reg.list_all() if m["version"] == "1.0"][0]
        assert v1["status"] == "archived"

    def test_rollback(self, tmp_path):
        sys.path.insert(0, str(BASE_DIR / "services" / "model_training"))
        from model_registry import ModelRegistry, ModelVersion, ModelStatus
        reg = ModelRegistry(registry_dir=str(tmp_path))
        reg.register(ModelVersion(model_id="hsaai-r1", version="1.0", base_model="Qwen"))
        reg.promote("hsaai-r1", "1.0", ModelStatus.PRODUCTION, "admin")
        reg.register(ModelVersion(model_id="hsaai-r1", version="2.0", base_model="Qwen"))
        reg.promote("hsaai-r1", "2.0", ModelStatus.PRODUCTION, "admin")
        # Rollback
        prev = reg.rollback("hsaai-r1")
        assert prev["version"] == "1.0"
