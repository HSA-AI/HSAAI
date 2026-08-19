"""
HSAAI v12 — AI Evaluation & Bias Detection Test Suite
======================================================
Tests for:
  1. BiasDetectionEngine (dataset, output, performance disparity)
  2. FairnessMetrics (demographic parity, equal opportunity, equalized odds, disparate impact)
  3. NISTAIRMFAlignment (GOVERN/MAP/MEASURE/MANAGE)
  4. ResponsibleAIControls
  5. AIEvaluationServiceV12

Coverage target: >95%
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.ai_operations.ai_evaluation_v12 import (  # noqa: E402
    AIEvaluationServiceV12,
    BiasDetectionEngine,
    BiasDetectionError,
    FairnessMetrics,
    NISTAIRMFAlignment,
    ResponsibleAIControls,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════
@pytest.fixture
def balanced_dataset():
    """Dataset with balanced gender representation."""
    return [
        {"gender": "male", "prediction": True, "actual": True, "confidence": 0.9},
        {"gender": "male", "prediction": False, "actual": False, "confidence": 0.8},
        {"gender": "female", "prediction": True, "actual": True, "confidence": 0.9},
        {"gender": "female", "prediction": False, "actual": False, "confidence": 0.85},
    ] * 25  # 100 records, 50/50 split


@pytest.fixture
def biased_dataset():
    """Dataset with gender bias (95% male, 5% female)."""
    data = [{"gender": "male", "prediction": True, "actual": True}] * 95
    data += [{"gender": "female", "prediction": False, "actual": True}] * 5
    return data


@pytest.fixture
def fair_predictions():
    """Predictions with fair outcomes across groups."""
    return [
        {"gender": "male", "prediction": True, "actual": True, "confidence": 0.9},
        {"gender": "male", "prediction": False, "actual": False, "confidence": 0.85},
        {"gender": "female", "prediction": True, "actual": True, "confidence": 0.9},
        {"gender": "female", "prediction": False, "actual": False, "confidence": 0.85},
    ] * 25


@pytest.fixture
def biased_predictions():
    """Predictions with bias (males get approved more)."""
    return [
        {"gender": "male", "prediction": "approved", "actual": True, "confidence": 0.9},
        {"gender": "male", "prediction": "approved", "actual": True, "confidence": 0.85},
        {"gender": "female", "prediction": "rejected", "actual": True, "confidence": 0.7},
        {"gender": "female", "prediction": "rejected", "actual": True, "confidence": 0.65},
    ] * 25


# ═══════════════════════════════════════════════════════════════════════
# 1. BiasDetectionEngine Tests
# ═══════════════════════════════════════════════════════════════════════
class TestBiasDetectionDataset:
    """Tests for dataset bias analysis."""

    def test_balanced_dataset_passes(self, balanced_dataset):
        engine = BiasDetectionEngine()
        result = engine.analyze_dataset_bias(balanced_dataset, "gender")
        assert result["status"] == "pass"
        assert result["severity"] == "low"
        assert len(result["underrepresented_groups"]) == 0

    def test_biased_dataset_fails(self, biased_dataset):
        engine = BiasDetectionEngine()
        result = engine.analyze_dataset_bias(biased_dataset, "gender")
        assert result["status"] == "fail"
        assert "female" in result["underrepresented_groups"]
        assert result["severity"] in ("high", "critical")

    def test_unknown_attribute_raises(self, balanced_dataset):
        engine = BiasDetectionEngine()
        with pytest.raises(BiasDetectionError, match="Unknown protected attribute"):
            engine.analyze_dataset_bias(balanced_dataset, "unknown_attr")

    def test_empty_dataset_raises(self):
        engine = BiasDetectionEngine()
        with pytest.raises(BiasDetectionError, match="empty"):
            engine.analyze_dataset_bias([], "gender")

    def test_custom_min_representation(self, balanced_dataset):
        engine = BiasDetectionEngine()
        # Set very high threshold — even balanced data fails
        result = engine.analyze_dataset_bias(
            balanced_dataset, "gender", min_representation=0.6
        )
        assert result["status"] == "fail"

    def test_severity_critical_for_very_low_representation(self):
        engine = BiasDetectionEngine()
        data = [{"gender": "male"}] * 95 + [{"gender": "female"}] * 5
        result = engine.analyze_dataset_bias(data, "gender")
        assert result["severity"] == "critical"


class TestBiasDetectionOutput:
    """Tests for output bias analysis."""

    def test_fair_output_passes(self, balanced_dataset):
        engine = BiasDetectionEngine()
        result = engine.analyze_output_bias(balanced_dataset, "gender")
        assert result["status"] == "pass"

    def test_biased_output_fails(self, biased_predictions):
        engine = BiasDetectionEngine()
        result = engine.analyze_output_bias(
            biased_predictions, "gender", outcome_field="prediction"
        )
        assert result["status"] == "fail"
        assert result["actual_disparity"] > 0.1

    def test_empty_predictions_raises(self):
        engine = BiasDetectionEngine()
        with pytest.raises(BiasDetectionError):
            engine.analyze_output_bias([], "gender")

    def test_severity_increases_with_disparity(self, biased_predictions):
        engine = BiasDetectionEngine()
        result = engine.analyze_output_bias(biased_predictions, "gender")
        assert result["severity"] in ("high", "critical")


class TestBiasDetectionPerformance:
    """Tests for performance disparity analysis."""

    def test_consistent_performance_passes(self, fair_predictions):
        engine = BiasDetectionEngine()
        result = engine.analyze_performance_disparity(fair_predictions, "gender")
        assert result["status"] == "pass"
        assert result["actual_accuracy_gap"] < 0.05

    def test_disparate_performance_fails(self):
        engine = BiasDetectionEngine()
        # Males: 100% accuracy, Females: 50% accuracy
        data = [
            {"gender": "male", "prediction": True, "actual": True},
            {"gender": "male", "prediction": False, "actual": False},
            {"gender": "female", "prediction": True, "actual": False},  # Wrong
            {"gender": "female", "prediction": False, "actual": True},  # Wrong
        ] * 25
        result = engine.analyze_performance_disparity(data, "gender")
        assert result["status"] == "fail"
        assert result["actual_accuracy_gap"] > 0.05


class TestBiasDetectionSummary:
    """Tests for summary and results retrieval."""

    def test_get_all_results(self, balanced_dataset):
        engine = BiasDetectionEngine()
        engine.analyze_dataset_bias(balanced_dataset, "gender")
        engine.analyze_output_bias(balanced_dataset, "gender")
        results = engine.get_all_results()
        assert len(results) == 2

    def test_get_summary(self, balanced_dataset, biased_dataset):
        engine = BiasDetectionEngine()
        engine.analyze_dataset_bias(balanced_dataset, "gender")  # pass
        engine.analyze_dataset_bias(biased_dataset, "gender")  # fail
        summary = engine.get_summary()
        assert summary["total_analyses"] == 2
        assert summary["by_status"]["pass"] == 1
        assert summary["by_status"]["fail"] == 1
        assert summary["overall_status"] == "fail"


# ═══════════════════════════════════════════════════════════════════════
# 2. FairnessMetrics Tests
# ═══════════════════════════════════════════════════════════════════════
class TestDemographicParity:
    """Tests for demographic parity metric."""

    def test_fair_predictions_pass(self, fair_predictions):
        result = FairnessMetrics.demographic_parity(fair_predictions, "gender")
        assert result["is_fair"] is True
        assert result["status"] == "pass"

    def test_biased_predictions_fail(self, biased_predictions):
        result = FairnessMetrics.demographic_parity(
            biased_predictions, "gender", outcome_field="prediction"
        )
        assert result["status"] == "fail"

    def test_parity_difference_calculated(self, fair_predictions):
        result = FairnessMetrics.demographic_parity(fair_predictions, "gender")
        assert "parity_difference" in result
        assert "parity_ratio" in result
        assert 0 <= result["parity_difference"] <= 1


class TestEqualOpportunity:
    """Tests for equal opportunity metric."""

    def test_equal_tpr_passes(self, fair_predictions):
        result = FairnessMetrics.equal_opportunity(fair_predictions, "gender")
        assert result["is_fair"] is True

    def test_unequal_tpr_fails(self):
        # Males: high TPR (all true positives predicted positive)
        # Females: low TPR (true positives predicted negative)
        data = []
        # 25 males: all TP (actual=True, prediction=True)
        for _ in range(25):
            data.append({"gender": "male", "prediction": True, "actual": True})
        # 25 females: all FN (actual=True, prediction=False)
        for _ in range(25):
            data.append({"gender": "female", "prediction": False, "actual": True})
        result = FairnessMetrics.equal_opportunity(data, "gender")
        assert result["status"] == "fail"
        assert result["tpr_gap"] > 0.1

    def test_tpr_gap_calculated(self, fair_predictions):
        result = FairnessMetrics.equal_opportunity(fair_predictions, "gender")
        assert "tpr_gap" in result
        assert "group_tpr" in result


class TestEqualizedOdds:
    """Tests for equalized odds metric."""

    def test_equal_odds_passes(self, fair_predictions):
        result = FairnessMetrics.equalized_odds(fair_predictions, "gender")
        assert result["is_fair"] is True

    def test_unequal_odds_fails(self):
        # Create data with very different FPR
        data = []
        # Males: high FPR
        for _ in range(20):
            data.append({"gender": "male", "prediction": True, "actual": False})  # FP
        for _ in range(20):
            data.append({"gender": "male", "prediction": True, "actual": True})  # TP
        # Females: low FPR
        for _ in range(20):
            data.append({"gender": "female", "prediction": False, "actual": False})  # TN
        for _ in range(20):
            data.append({"gender": "female", "prediction": True, "actual": True})  # TP
        result = FairnessMetrics.equalized_odds(data, "gender")
        assert result["fpr_gap"] > 0.1
        assert result["status"] == "fail"

    def test_tpr_and_fpr_both_calculated(self, fair_predictions):
        result = FairnessMetrics.equalized_odds(fair_predictions, "gender")
        assert "tpr_gap" in result
        assert "fpr_gap" in result
        assert "group_stats" in result


class TestDisparateImpact:
    """Tests for disparate impact metric."""

    def test_fair_predictions_pass(self, fair_predictions):
        result = FairnessMetrics.disparate_impact(fair_predictions, "gender")
        assert result["is_fair"] is True
        assert result["disparate_impact_ratio"] >= 0.8

    def test_biased_predictions_fail(self, biased_predictions):
        result = FairnessMetrics.disparate_impact(
            biased_predictions, "gender", outcome_field="prediction"
        )
        assert result["is_fair"] is False
        assert result["disparate_impact_ratio"] < 0.8

    def test_favored_and_disadvantaged_groups_identified(self, biased_predictions):
        result = FairnessMetrics.disparate_impact(
            biased_predictions, "gender", outcome_field="prediction"
        )
        assert result["favored_group"] == "male"
        assert result["disadvantaged_group"] == "female"


class TestPerformanceDistribution:
    """Tests for performance distribution metric."""

    def test_performance_calculated_per_group(self, fair_predictions):
        result = FairnessMetrics.performance_distribution(fair_predictions, "gender")
        assert "group_performance" in result
        assert "male" in result["group_performance"]
        assert "female" in result["group_performance"]
        assert "accuracy" in result["group_performance"]["male"]
        assert "error_rate" in result["group_performance"]["male"]

    def test_confidence_calculated_when_present(self):
        data = [
            {"gender": "male", "prediction": True, "actual": True, "confidence": 0.9},
            {"gender": "female", "prediction": True, "actual": True, "confidence": 0.8},
        ]
        result = FairnessMetrics.performance_distribution(data, "gender")
        assert result["group_performance"]["male"]["avg_confidence"] == 0.9
        assert result["group_performance"]["female"]["avg_confidence"] == 0.8

    def test_confidence_none_when_absent(self):
        data = [
            {"gender": "male", "prediction": True, "actual": True},
            {"gender": "female", "prediction": True, "actual": True},
        ]
        result = FairnessMetrics.performance_distribution(data, "gender")
        assert result["group_performance"]["male"]["avg_confidence"] is None


class TestFairnessCalculateAll:
    """Tests for calculate_all method."""

    def test_calculate_all_returns_all_metrics(self, fair_predictions):
        result = FairnessMetrics.calculate_all(fair_predictions, "gender")
        assert "demographic_parity" in result
        assert "equal_opportunity" in result
        assert "equalized_odds" in result
        assert "disparate_impact" in result
        assert "performance_distribution" in result
        assert "timestamp" in result


# ═══════════════════════════════════════════════════════════════════════
# 3. NIST AI RMF Alignment Tests
# ═══════════════════════════════════════════════════════════════════════
class TestNISTAIRMFAlignment:
    """Tests for NIST AI RMF alignment."""

    def test_alignment_report_has_all_functions(self):
        report = NISTAIRMFAlignment.get_alignment_report()
        assert "GOVERN" in report["functions"]
        assert "MAP" in report["functions"]
        assert "MEASURE" in report["functions"]
        assert "MANAGE" in report["functions"]

    def test_alignment_report_has_controls(self):
        report = NISTAIRMFAlignment.get_alignment_report()
        assert report["total_controls"] > 0
        assert report["implemented_controls"] > 0

    def test_alignment_percentage(self):
        report = NISTAIRMFAlignment.get_alignment_report()
        assert report["alignment_percentage"] > 0
        assert report["alignment_percentage"] <= 100

    def test_all_controls_implemented(self):
        report = NISTAIRMFAlignment.get_alignment_report()
        assert report["implemented_controls"] == report["total_controls"]
        assert report["overall_status"] == "aligned"

    def test_get_function_controls(self):
        govern_controls = NISTAIRMFAlignment.get_function_controls("GOVERN")
        assert len(govern_controls) > 0
        assert all(c["control_id"].startswith("GOVERN") for c in govern_controls)

    def test_unknown_function_raises(self):
        with pytest.raises(ValueError, match="Unknown function"):
            NISTAIRMFAlignment.get_function_controls("UNKNOWN")

    def test_each_function_has_description(self):
        report = NISTAIRMFAlignment.get_alignment_report()
        for func_name, func_data in report["functions"].items():
            assert "description" in func_data
            assert "controls" in func_data
            assert len(func_data["controls"]) > 0


# ═══════════════════════════════════════════════════════════════════════
# 4. ResponsibleAIControls Tests
# ═══════════════════════════════════════════════════════════════════════
class TestResponsibleAIControls:
    """Tests for Responsible AI controls."""

    def test_get_all_controls(self):
        controls = ResponsibleAIControls.get_all_controls()
        assert "explainability" in controls
        assert "transparency" in controls
        assert "fairness_monitoring" in controls
        assert "safety_controls" in controls
        assert "privacy_protection" in controls
        assert "human_oversight" in controls

    def test_each_control_has_required_fields(self):
        controls = ResponsibleAIControls.get_all_controls()
        for name, control in controls.items():
            assert "description" in control
            assert "methods" in control
            assert "status" in control
            assert "implementation" in control

    def test_all_controls_implemented(self):
        controls = ResponsibleAIControls.get_all_controls()
        for name, control in controls.items():
            assert control["status"] == "implemented", f"Control '{name}' not implemented"

    def test_get_specific_control(self):
        control = ResponsibleAIControls.get_control("explainability")
        assert control["description"]
        assert "SHAP" in control["methods"]

    def test_unknown_control_raises(self):
        with pytest.raises(ValueError, match="Unknown control"):
            ResponsibleAIControls.get_control("nonexistent")


# ═══════════════════════════════════════════════════════════════════════
# 5. AIEvaluationServiceV12 Tests
# ═══════════════════════════════════════════════════════════════════════
class TestAIEvaluationServiceV12:
    """Tests for the v12 AI Evaluation Service."""

    def test_evaluate_quality(self):
        service = AIEvaluationServiceV12()
        eval_dataset = [
            {"prediction": True, "actual": True, "success": True},
            {"prediction": False, "actual": False, "success": True},
            {"prediction": True, "actual": False, "success": False, "hallucination": True},
        ]
        result = service.evaluate_quality("test-model", eval_dataset)
        assert result["target"] == "test-model"
        assert result["eval_type"] == "quality"
        assert "accuracy" in result["metrics"]
        assert result["metrics"]["accuracy"] > 0

    def test_evaluate_bias(self, balanced_dataset):
        service = AIEvaluationServiceV12()
        result = service.evaluate_bias("test-model", balanced_dataset, "gender")
        assert result["eval_type"] == "bias"
        assert "dataset_bias" in result
        assert "output_bias" in result
        assert "performance_disparity" in result

    def test_evaluate_fairness(self, fair_predictions):
        service = AIEvaluationServiceV12()
        result = service.evaluate_fairness("test-model", fair_predictions, "gender")
        assert result["eval_type"] == "fairness"
        assert "demographic_parity" in result
        assert "equal_opportunity" in result
        assert "overall_status" in result

    def test_get_responsible_ai_report(self):
        service = AIEvaluationServiceV12()
        report = service.get_responsible_ai_report()
        assert "controls" in report
        assert "nist_ai_rmf" in report
        assert report["nist_ai_rmf"]["framework"] == "NIST AI RMF 1.0"

    def test_get_all_evaluations(self, balanced_dataset):
        service = AIEvaluationServiceV12()
        service.evaluate_quality("model-1", balanced_dataset)
        service.evaluate_bias("model-1", balanced_dataset, "gender")
        evals = service.get_all_evaluations()
        assert len(evals) == 2

    def test_quality_evaluation_with_custom_metrics(self):
        service = AIEvaluationServiceV12()
        eval_dataset = [
            {"prediction": True, "actual": True, "success": True},
            {"prediction": False, "actual": True, "success": False, "hallucination": True},
        ]
        result = service.evaluate_quality(
            "test-model", eval_dataset, metrics=["accuracy", "hallucination_rate"]
        )
        assert "accuracy" in result["metrics"]
        assert "hallucination_rate" in result["metrics"]
        assert "task_success_rate" not in result["metrics"]

    def test_fairness_overall_status_pass(self, fair_predictions):
        service = AIEvaluationServiceV12()
        result = service.evaluate_fairness("test-model", fair_predictions, "gender")
        assert result["overall_status"] == "pass"

    def test_fairness_overall_status_fail(self, biased_predictions):
        service = AIEvaluationServiceV12()
        result = service.evaluate_fairness("test-model", biased_predictions, "gender")
        assert result["overall_status"] == "fail"
