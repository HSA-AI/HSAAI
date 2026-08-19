"""
HSAAI 10/10 Capability Tests
==============================
Verifies all new advanced AI capabilities.
"""
import os, sys, pytest, asyncio
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR / "packages" / "common"))


class TestModelConfig:
    """Test the production model chain configuration."""

    def test_model_chain_exists(self):
        from security.model_config import get_model_chain
        chain = get_model_chain()
        assert len(chain) >= 1

    def test_primary_model_is_qwen(self):
        from security.model_config import get_model_chain, ModelTier
        chain = get_model_chain()
        primary = [m for m in chain if m.tier == ModelTier.PRIMARY]
        assert len(primary) == 1
        assert "Qwen" in primary[0].model_id or "qwen" in primary[0].model_id.lower()

    def test_no_dev_only_token(self):
        """The model config should NOT use dev-only-token."""
        from security.model_config import get_model_chain
        chain = get_model_chain()
        for model in chain:
            assert model.model_id != "dev-only-token"

    def test_cost_estimation(self):
        from security.model_config import get_model_chain, estimate_cost
        chain = get_model_chain()
        if chain:
            cost = estimate_cost(chain[0], 1000, 500)
            assert cost >= 0.0  # Local models have 0 cost

    def test_finetuning_config(self):
        from security.model_config import get_finetuning_config
        config = get_finetuning_config()
        assert config.base_model == "Qwen/Qwen2.5-7B-Instruct"
        assert config.lora_r > 0
        assert config.num_epochs > 0


class TestReasoningEngine:
    """Test the multi-strategy reasoning engine."""

    def test_reasoning_engine_imports(self):
        from ai.reasoning_engine import ReasoningEngine, ReasoningStrategy
        assert ReasoningEngine is not None
        assert ReasoningStrategy.COT == "chain_of_thought"

    def test_strategy_selection(self):
        from ai.reasoning_engine import ReasoningEngine, ReasoningStrategy
        engine = ReasoningEngine(llm_gateway_url="http://localhost:1")
        # Search query → ReAct
        assert engine._select_strategy("search for contracts", "") == ReasoningStrategy.REACT
        # Analysis query → ToT
        assert engine._select_strategy("analyze this contract", "") == ReasoningStrategy.TOT
        # Writing query → Reflexion
        assert engine._select_strategy("write a summary", "") == ReasoningStrategy.REFLEXION
        # Default → CoT (or Self-Consistency for factual)
        result = engine._select_strategy("explain the architecture", "")
        assert result in (ReasoningStrategy.COT, ReasoningStrategy.SELF_CONSISTENCY)

    def test_all_strategies_defined(self):
        from ai.reasoning_engine import ReasoningStrategy
        assert ReasoningStrategy.COT
        assert ReasoningStrategy.SELF_CONSISTENCY
        assert ReasoningStrategy.TOT
        assert ReasoningStrategy.REACT
        assert ReasoningStrategy.REFLEXION


class TestAdvancedRAG:
    """Test GraphRAG + Corrective RAG + Self-RAG."""

    def test_advanced_rag_imports(self):
        from ai.advanced_rag import AdvancedRAGEngine, RetrievalMode
        assert AdvancedRAGEngine is not None

    def test_mode_selection(self):
        from ai.advanced_rag import AdvancedRAGEngine, RetrievalMode
        engine = AdvancedRAGEngine()
        # Relationship query → Graph
        assert engine._select_mode("what is the relationship between") == RetrievalMode.GRAPH
        # Latest/current → Corrective
        assert engine._select_mode("what is the latest news") == RetrievalMode.CORRECTIVE
        # Image query → Multimodal
        assert engine._select_mode("show me the chart") == RetrievalMode.MULTIMODAL
        # Default → Hybrid
        assert engine._select_mode("what is the policy") == RetrievalMode.HYBRID

    def test_all_modes_defined(self):
        from ai.advanced_rag import RetrievalMode
        assert RetrievalMode.HYBRID
        assert RetrievalMode.GRAPH
        assert RetrievalMode.CORRECTIVE
        assert RetrievalMode.SELF_RAG
        assert RetrievalMode.MULTIMODAL


class TestMultiRegion:
    """Test multi-region configuration."""

    def test_multi_region_imports(self):
        from infrastructure.multi_region import MultiRegionConfig, Region
        assert MultiRegionConfig is not None

    def test_gcc_user_routed_to_me_south_1(self):
        from infrastructure.multi_region import MultiRegionConfig, Region
        config = MultiRegionConfig()
        assert config.get_region_for_user(user_country="SA") == Region.ME_SOUTH_1
        assert config.get_region_for_user(user_country="AE") == Region.ME_SOUTH_1

    def test_eu_user_routed_to_eu_central_1(self):
        from infrastructure.multi_region import MultiRegionConfig, Region
        config = MultiRegionConfig()
        assert config.get_region_for_user(user_country="DE") == Region.EU_CENTRAL_1

    def test_data_residency_enforced(self):
        from infrastructure.multi_region import MultiRegionConfig, Region
        config = MultiRegionConfig()
        # GCC tenant data must NOT go to EU
        assert config.check_data_residency("hsa-foods", Region.EU_CENTRAL_1) is False
        # GCC tenant data CAN stay in GCC
        assert config.check_data_residency("hsa-foods", Region.ME_SOUTH_1) is True

    def test_failover_region_exists(self):
        from infrastructure.multi_region import MultiRegionConfig, Region
        config = MultiRegionConfig()
        failover = config.get_failover_region()
        assert failover is not None

    def test_health_check_all_regions(self):
        from infrastructure.multi_region import MultiRegionConfig
        config = MultiRegionConfig()
        health = config.health_check_all()
        assert "me-south-1" in health
        assert "eu-central-1" in health
        assert "us-east-1" in health
