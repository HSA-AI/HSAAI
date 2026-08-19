"""
HSAAI v12 — AI Evaluation Service Expansion & Bias Detection Engine
====================================================================
Implements:
  1. BiasDetectionEngine — Dataset/output/representation/performance bias
  2. FairnessMetrics — Demographic parity, equal opportunity, equalized odds, disparate impact
  3. NISTAIRMFAlignment — GOVERN/MAP/MEASURE/MANAGE framework mapping
  4. ResponsibleAIControls — Explainability, transparency, safety

Aligned with NIST AI Risk Management Framework (AI RMF 1.0)
"""
from __future__ import annotations

import json
import logging
import math
import statistics
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("hsaai.ai_evaluation")
audit_logger = logging.getLogger("hsaai.audit.ai_evaluation")


# ═══════════════════════════════════════════════════════════════════════
# 1. BiasDetectionEngine
# ═══════════════════════════════════════════════════════════════════════
class BiasDetectionError(Exception):
    """Base exception for bias detection errors."""
    pass


class BiasDetectionEngine:
    """Enterprise AI Bias Detection Engine.

    Detects unfair or discriminatory AI model behavior across:
      1. Dataset bias — representation in training data
      2. Output bias — distribution of model predictions
      3. Representation bias — feature distribution across groups
      4. Performance disparity — accuracy/error differences across groups

    Supports protected attributes:
      - gender, age_group, ethnicity, religion, nationality, disability_status

    Each bias check produces:
      - metric_name, value, threshold, status (pass/warning/fail)
      - affected_group, severity, recommendation
    """

    # Protected attributes supported
    PROTECTED_ATTRIBUTES = [
        "gender", "age_group", "ethnicity", "religion",
        "nationality", "disability_status",
    ]

    # Severity levels
    SEVERITY_LOW = "low"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_HIGH = "high"
    SEVERITY_CRITICAL = "critical"

    def __init__(self):
        self._results: list[dict[str, Any]] = []

    def analyze_dataset_bias(
        self,
        dataset: list[dict[str, Any]],
        protected_attribute: str,
        *,
        min_representation: float = 0.1,
    ) -> dict[str, Any]:
        """Analyze representation bias in a dataset.

        Args:
            dataset: List of records (each a dict with protected_attribute key)
            protected_attribute: Which protected attribute to analyze
            min_representation: Minimum fraction each group should represent (default: 10%)

        Returns:
            Bias analysis result
        """
        if protected_attribute not in self.PROTECTED_ATTRIBUTES:
            raise BiasDetectionError(
                f"Unknown protected attribute '{protected_attribute}'. "
                f"Supported: {self.PROTECTED_ATTRIBUTES}"
            )
        if not dataset:
            raise BiasDetectionError("Dataset must not be empty")

        # Count records per group
        group_counts: dict[str, int] = defaultdict(int)
        for record in dataset:
            group = record.get(protected_attribute, "unknown")
            group_counts[str(group)] += 1

        total = len(dataset)
        groups = dict(group_counts)
        representation = {g: c / total for g, c in groups.items()}

        # Identify underrepresented groups
        underrepresented = [
            g for g, rep in representation.items() if rep < min_representation
        ]

        # Determine severity
        min_rep = min(representation.values()) if representation else 0
        if min_rep <= 0.05:
            severity = self.SEVERITY_CRITICAL
        elif min_rep < 0.1:
            severity = self.SEVERITY_HIGH
        elif min_rep < 0.15:
            severity = self.SEVERITY_MEDIUM
        else:
            severity = self.SEVERITY_LOW

        result = {
            "analysis_id": str(uuid.uuid4()),
            "analysis_type": "dataset_bias",
            "protected_attribute": protected_attribute,
            "total_records": total,
            "group_counts": groups,
            "group_representation": representation,
            "min_representation_threshold": min_representation,
            "underrepresented_groups": underrepresented,
            "severity": severity,
            "status": "fail" if underrepresented else "pass",
            "recommendation": (
                f"Collect more data for underrepresented groups: {underrepresented}"
                if underrepresented
                else "Dataset representation is balanced"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._results.append(result)
        return result

    def analyze_output_bias(
        self,
        predictions: list[dict[str, Any]],
        protected_attribute: str,
        outcome_field: str = "prediction",
        *,
        max_disparity: float = 0.1,
    ) -> dict[str, Any]:
        """Analyze bias in model output predictions.

        Args:
            predictions: List of {protected_attribute, outcome_field} dicts
            protected_attribute: Group attribute to analyze
            outcome_field: Field containing the prediction/outcome
            max_disparity: Maximum allowed difference in positive rate (default: 10%)

        Returns:
            Output bias analysis result
        """
        if protected_attribute not in self.PROTECTED_ATTRIBUTES:
            raise BiasDetectionError(
                f"Unknown protected attribute '{protected_attribute}'"
            )
        if not predictions:
            raise BiasDetectionError("Predictions must not be empty")

        # Group predictions by protected attribute
        grouped: dict[str, list[Any]] = defaultdict(list)
        for pred in predictions:
            group = str(pred.get(protected_attribute, "unknown"))
            outcome = pred.get(outcome_field)
            grouped[group].append(outcome)

        # Calculate positive outcome rate per group
        group_stats: dict[str, dict[str, float]] = {}
        for group, outcomes in grouped.items():
            total = len(outcomes)
            positive = sum(1 for o in outcomes if o in (True, 1, "yes", "positive", "approved"))
            group_stats[group] = {
                "total": total,
                "positive": positive,
                "positive_rate": positive / total if total else 0.0,
            }

        # Calculate disparity
        positive_rates = [s["positive_rate"] for s in group_stats.values()]
        if len(positive_rates) >= 2:
            max_rate = max(positive_rates)
            min_rate = min(positive_rates)
            disparity = max_rate - min_rate
        else:
            disparity = 0.0

        # Determine severity
        if disparity > 0.3:
            severity = self.SEVERITY_CRITICAL
        elif disparity > 0.2:
            severity = self.SEVERITY_HIGH
        elif disparity > max_disparity:
            severity = self.SEVERITY_MEDIUM
        else:
            severity = self.SEVERITY_LOW

        result = {
            "analysis_id": str(uuid.uuid4()),
            "analysis_type": "output_bias",
            "protected_attribute": protected_attribute,
            "outcome_field": outcome_field,
            "group_stats": group_stats,
            "max_disparity_threshold": max_disparity,
            "actual_disparity": round(disparity, 4),
            "severity": severity,
            "status": "fail" if disparity > max_disparity else "pass",
            "recommendation": (
                f"Output disparity {disparity:.2%} exceeds threshold {max_disparity:.2%}. "
                f"Review model for bias against underperforming groups."
                if disparity > max_disparity
                else "Output distribution is fair across groups"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._results.append(result)
        return result

    def analyze_performance_disparity(
        self,
        predictions: list[dict[str, Any]],
        protected_attribute: str,
        *,
        max_accuracy_gap: float = 0.05,
    ) -> dict[str, Any]:
        """Analyze performance disparity (accuracy gap) across groups.

        Args:
            predictions: List of {protected_attribute, prediction, actual} dicts
            protected_attribute: Group attribute
            max_accuracy_gap: Maximum allowed accuracy difference (default: 5%)

        Returns:
            Performance disparity analysis
        """
        if not predictions:
            raise BiasDetectionError("Predictions must not be empty")

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for pred in predictions:
            group = str(pred.get(protected_attribute, "unknown"))
            grouped[group].append(pred)

        group_accuracy: dict[str, dict[str, float]] = {}
        for group, preds in grouped.items():
            correct = sum(1 for p in preds if p.get("prediction") == p.get("actual"))
            total = len(preds)
            group_accuracy[group] = {
                "total": total,
                "correct": correct,
                "accuracy": correct / total if total else 0.0,
            }

        accuracies = [s["accuracy"] for s in group_accuracy.values()]
        if len(accuracies) >= 2:
            accuracy_gap = max(accuracies) - min(accuracies)
        else:
            accuracy_gap = 0.0

        if accuracy_gap > 0.15:
            severity = self.SEVERITY_CRITICAL
        elif accuracy_gap > 0.10:
            severity = self.SEVERITY_HIGH
        elif accuracy_gap > max_accuracy_gap:
            severity = self.SEVERITY_MEDIUM
        else:
            severity = self.SEVERITY_LOW

        result = {
            "analysis_id": str(uuid.uuid4()),
            "analysis_type": "performance_disparity",
            "protected_attribute": protected_attribute,
            "group_accuracy": group_accuracy,
            "max_accuracy_gap_threshold": max_accuracy_gap,
            "actual_accuracy_gap": round(accuracy_gap, 4),
            "severity": severity,
            "status": "fail" if accuracy_gap > max_accuracy_gap else "pass",
            "recommendation": (
                f"Accuracy gap {accuracy_gap:.2%} exceeds threshold {max_accuracy_gap:.2%}. "
                f"Model performs significantly differently across groups."
                if accuracy_gap > max_accuracy_gap
                else "Model performance is consistent across groups"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._results.append(result)
        return result

    def get_all_results(self) -> list[dict[str, Any]]:
        """Get all bias detection results."""
        return list(self._results)

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all bias analyses."""
        total = len(self._results)
        by_status = defaultdict(int)
        by_severity = defaultdict(int)
        for r in self._results:
            by_status[r["status"]] += 1
            by_severity[r["severity"]] += 1
        return {
            "total_analyses": total,
            "by_status": dict(by_status),
            "by_severity": dict(by_severity),
            "overall_status": "fail" if by_status.get("fail", 0) > 0 else "pass",
        }


# ═══════════════════════════════════════════════════════════════════════
# 2. FairnessMetrics
# ═══════════════════════════════════════════════════════════════════════
class FairnessMetrics:
    """Fairness metrics calculator aligned with NIST AI RMF.

    Metrics:
      1. Demographic Parity — equal outcome distribution
      2. Equal Opportunity — equal true positive rates
      3. Equalized Odds — equal TPR + FPR
      4. Disparate Impact — 80% rule (4/5ths rule)
      5. Performance Distribution — accuracy/error/confidence across groups
    """

    @staticmethod
    def demographic_parity(
        predictions: list[dict[str, Any]],
        protected_attribute: str,
        outcome_field: str = "prediction",
    ) -> dict[str, Any]:
        """Calculate demographic parity (equal positive prediction rate).

        Demographic parity is achieved when the positive prediction rate
        is equal across all groups.

        Args:
            predictions: List of {protected_attribute, outcome_field}
            protected_attribute: Group attribute
            outcome_field: Prediction field

        Returns:
            Metric result with per-group rates and parity status
        """
        grouped: dict[str, list[Any]] = defaultdict(list)
        for pred in predictions:
            group = str(pred.get(protected_attribute, "unknown"))
            grouped[group].append(pred.get(outcome_field))

        group_rates = {}
        for group, outcomes in grouped.items():
            total = len(outcomes)
            positive = sum(1 for o in outcomes if o in (True, 1, "yes", "positive", "approved"))
            group_rates[group] = positive / total if total else 0.0

        rates = list(group_rates.values())
        if len(rates) >= 2:
            parity_diff = max(rates) - min(rates)
            parity_ratio = min(rates) / max(rates) if max(rates) > 0 else 1.0
        else:
            parity_diff = 0.0
            parity_ratio = 1.0

        # Threshold: parity difference < 0.1 and ratio > 0.8
        is_fair = parity_diff < 0.1 and parity_ratio > 0.8

        return {
            "metric": "demographic_parity",
            "group_positive_rates": group_rates,
            "parity_difference": round(parity_diff, 4),
            "parity_ratio": round(parity_ratio, 4),
            "threshold_difference": 0.1,
            "threshold_ratio": 0.8,
            "is_fair": is_fair,
            "status": "pass" if is_fair else "fail",
        }

    @staticmethod
    def equal_opportunity(
        predictions: list[dict[str, Any]],
        protected_attribute: str,
        *,
        max_tpr_gap: float = 0.1,
    ) -> dict[str, Any]:
        """Calculate equal opportunity (equal true positive rate).

        Equal opportunity is achieved when TPR is equal across groups.

        Args:
            predictions: List of {protected_attribute, prediction, actual}
            protected_attribute: Group attribute
            max_tpr_gap: Maximum allowed TPR gap (default: 10%)

        Returns:
            Metric result with per-group TPR
        """
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for pred in predictions:
            group = str(pred.get(protected_attribute, "unknown"))
            grouped[group].append(pred)

        group_tpr = {}
        for group, preds in grouped.items():
            true_positives = sum(1 for p in preds if p.get("actual") in (True, 1, "yes") and p.get("prediction") == p.get("actual"))
            actual_positives = sum(1 for p in preds if p.get("actual") in (True, 1, "yes"))
            group_tpr[group] = true_positives / actual_positives if actual_positives else 0.0

        tpr_values = list(group_tpr.values())
        if len(tpr_values) >= 2:
            tpr_gap = max(tpr_values) - min(tpr_values)
        else:
            tpr_gap = 0.0

        is_fair = tpr_gap < max_tpr_gap

        return {
            "metric": "equal_opportunity",
            "group_tpr": group_tpr,
            "tpr_gap": round(tpr_gap, 4),
            "threshold_gap": max_tpr_gap,
            "is_fair": is_fair,
            "status": "pass" if is_fair else "fail",
        }

    @staticmethod
    def equalized_odds(
        predictions: list[dict[str, Any]],
        protected_attribute: str,
        *,
        max_gap: float = 0.1,
    ) -> dict[str, Any]:
        """Calculate equalized odds (equal TPR + FPR).

        Args:
            predictions: List of {protected_attribute, prediction, actual}
            protected_attribute: Group attribute
            max_gap: Maximum allowed gap (default: 10%)

        Returns:
            Metric result with per-group TPR and FPR
        """
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for pred in predictions:
            group = str(pred.get(protected_attribute, "unknown"))
            grouped[group].append(pred)

        group_stats = {}
        for group, preds in grouped.items():
            tp = sum(1 for p in preds if p.get("actual") in (True, 1) and p.get("prediction") == p.get("actual"))
            fn = sum(1 for p in preds if p.get("actual") in (True, 1) and p.get("prediction") != p.get("actual"))
            fp = sum(1 for p in preds if p.get("actual") in (False, 0) and p.get("prediction") != p.get("actual"))
            tn = sum(1 for p in preds if p.get("actual") in (False, 0) and p.get("prediction") == p.get("actual"))
            tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
            group_stats[group] = {"tpr": tpr, "fpr": fpr}

        tpr_values = [s["tpr"] for s in group_stats.values()]
        fpr_values = [s["fpr"] for s in group_stats.values()]
        tpr_gap = max(tpr_values) - min(tpr_values) if len(tpr_values) >= 2 else 0.0
        fpr_gap = max(fpr_values) - min(fpr_values) if len(fpr_values) >= 2 else 0.0
        max_gap_actual = max(tpr_gap, fpr_gap)

        is_fair = max_gap_actual < max_gap

        return {
            "metric": "equalized_odds",
            "group_stats": group_stats,
            "tpr_gap": round(tpr_gap, 4),
            "fpr_gap": round(fpr_gap, 4),
            "max_gap": round(max_gap_actual, 4),
            "threshold_gap": max_gap,
            "is_fair": is_fair,
            "status": "pass" if is_fair else "fail",
        }

    @staticmethod
    def disparate_impact(
        predictions: list[dict[str, Any]],
        protected_attribute: str,
        outcome_field: str = "prediction",
        *,
        min_ratio: float = 0.8,
    ) -> dict[str, Any]:
        """Calculate disparate impact (4/5ths rule).

        The 80% rule: the selection rate for any protected group should be
        at least 80% of the rate for the favored group.

        Args:
            predictions: List of {protected_attribute, outcome_field}
            protected_attribute: Group attribute
            min_ratio: Minimum acceptable ratio (default: 0.8 = 80% rule)

        Returns:
            Metric result with disparate impact ratio
        """
        grouped: dict[str, list[Any]] = defaultdict(list)
        for pred in predictions:
            group = str(pred.get(protected_attribute, "unknown"))
            grouped[group].append(pred.get(outcome_field))

        group_rates = {}
        for group, outcomes in grouped.items():
            total = len(outcomes)
            positive = sum(1 for o in outcomes if o in (True, 1, "yes", "positive", "approved"))
            group_rates[group] = positive / total if total else 0.0

        rates = list(group_rates.values())
        if len(rates) >= 2 and max(rates) > 0:
            di_ratio = min(rates) / max(rates)
        else:
            di_ratio = 1.0

        is_fair = di_ratio >= min_ratio
        favored_group = max(group_rates, key=group_rates.get) if group_rates else "none"
        disadvantaged_group = min(group_rates, key=group_rates.get) if group_rates else "none"

        return {
            "metric": "disparate_impact",
            "group_rates": group_rates,
            "disparate_impact_ratio": round(di_ratio, 4),
            "threshold_ratio": min_ratio,
            "favored_group": favored_group,
            "disadvantaged_group": disadvantaged_group,
            "is_fair": is_fair,
            "status": "pass" if is_fair else "fail",
        }

    @staticmethod
    def performance_distribution(
        predictions: list[dict[str, Any]],
        protected_attribute: str,
    ) -> dict[str, Any]:
        """Compare performance distribution (accuracy, error, confidence) across groups.

        Args:
            predictions: List of {protected_attribute, prediction, actual, confidence?}
            protected_attribute: Group attribute

        Returns:
            Performance distribution per group
        """
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for pred in predictions:
            group = str(pred.get(protected_attribute, "unknown"))
            grouped[group].append(pred)

        group_performance = {}
        for group, preds in grouped.items():
            total = len(preds)
            correct = sum(1 for p in preds if p.get("prediction") == p.get("actual"))
            errors = total - correct
            confidences = [p.get("confidence", 0.5) for p in preds if "confidence" in p]
            group_performance[group] = {
                "total": total,
                "accuracy": correct / total if total else 0.0,
                "error_rate": errors / total if total else 0.0,
                "avg_confidence": round(statistics.mean(confidences), 4) if confidences else None,
            }

        return {
            "metric": "performance_distribution",
            "group_performance": group_performance,
            "status": "computed",
        }

    @classmethod
    def calculate_all(
        cls,
        predictions: list[dict[str, Any]],
        protected_attribute: str,
    ) -> dict[str, Any]:
        """Calculate all fairness metrics at once.

        Args:
            predictions: List of prediction dicts
            protected_attribute: Group attribute

        Returns:
            All fairness metrics combined
        """
        return {
            "demographic_parity": cls.demographic_parity(predictions, protected_attribute),
            "equal_opportunity": cls.equal_opportunity(predictions, protected_attribute),
            "equalized_odds": cls.equalized_odds(predictions, protected_attribute),
            "disparate_impact": cls.disparate_impact(predictions, protected_attribute),
            "performance_distribution": cls.performance_distribution(predictions, protected_attribute),
            "overall_status": "pass",  # Computed below
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════
# 3. NIST AI RMF Alignment
# ═══════════════════════════════════════════════════════════════════════
class NISTAIRMFAlignment:
    """NIST AI Risk Management Framework (AI RMF 1.0) alignment.

    Maps HSAAI AI Evaluation Service to NIST AI RMF four functions:
      1. GOVERN — AI governance policies, accountability, risk ownership
      2. MAP — AI system context, intended usage, risk identification
      3. MEASURE — Bias metrics, fairness metrics, safety, performance
      4. MANAGE — Risk mitigation, evaluation workflows, approval processes
    """

    # NIST AI RMF Functions
    FUNCTION_GOVERN = "GOVERN"
    FUNCTION_MAP = "MAP"
    FUNCTION_MEASURE = "MEASURE"
    FUNCTION_MANAGE = "MANAGE"

    # Alignment mapping
    ALIGNMENT_MAP = {
        FUNCTION_GOVERN: {
            "description": "Establish policies, accountability, and risk ownership for AI systems",
            "controls": [
                {
                    "control_id": "GOVERN-1",
                    "name": "AI Governance Policies",
                    "description": "Documented policies for AI development, deployment, and use",
                    "implementation": "governance-service with policy_engine",
                    "status": "implemented",
                },
                {
                    "control_id": "GOVERN-2",
                    "name": "Accountability Tracking",
                    "description": "Clear ownership and accountability for AI system outcomes",
                    "implementation": "module_registry with owner_team + technical_owner",
                    "status": "implemented",
                },
                {
                    "control_id": "GOVERN-3",
                    "name": "Risk Ownership",
                    "description": "Assigned risk owners for each AI system",
                    "implementation": "ai_governance with risk_classification",
                    "status": "implemented",
                },
                {
                    "control_id": "GOVERN-4",
                    "name": "AI Ethics Board",
                    "description": "Independent ethics oversight",
                    "implementation": "AI Ethics Board (quarterly reviews)",
                    "status": "implemented",
                },
            ],
        },
        FUNCTION_MAP: {
            "description": "Identify AI system context, intended use, and risks",
            "controls": [
                {
                    "control_id": "MAP-1",
                    "name": "AI System Context",
                    "description": "Documented context for each AI system",
                    "implementation": "module_specification with module_analysis",
                    "status": "implemented",
                },
                {
                    "control_id": "MAP-2",
                    "name": "Intended Usage",
                    "description": "Clear documentation of intended use cases",
                    "implementation": "module_specification with capabilities",
                    "status": "implemented",
                },
                {
                    "control_id": "MAP-3",
                    "name": "Risk Identification",
                    "description": "Systematic identification of AI risks",
                    "implementation": "risk_management module with risk_register",
                    "status": "implemented",
                },
                {
                    "control_id": "MAP-4",
                    "name": "Impact Assessment",
                    "description": "Assessment of potential impacts on stakeholders",
                    "implementation": "ai_evaluation with bias_detection",
                    "status": "implemented",
                },
            ],
        },
        FUNCTION_MEASURE: {
            "description": "Measure AI system performance, bias, fairness, and safety",
            "controls": [
                {
                    "control_id": "MEASURE-1",
                    "name": "Bias Metrics",
                    "description": "Measurement of bias across protected attributes",
                    "implementation": "BiasDetectionEngine",
                    "status": "implemented",
                },
                {
                    "control_id": "MEASURE-2",
                    "name": "Fairness Metrics",
                    "description": "Fairness evaluation (demographic parity, equal opportunity)",
                    "implementation": "FairnessMetrics",
                    "status": "implemented",
                },
                {
                    "control_id": "MEASURE-3",
                    "name": "Safety Metrics",
                    "description": "AI safety controls and hallucination rate",
                    "implementation": "safety-layer + hallucination_detector",
                    "status": "implemented",
                },
                {
                    "control_id": "MEASURE-4",
                    "name": "Performance Metrics",
                    "description": "Accuracy, latency, cost, user satisfaction",
                    "implementation": "ai_evaluation with kpi_framework",
                    "status": "implemented",
                },
            ],
        },
        FUNCTION_MANAGE: {
            "description": "Manage AI risks through mitigation, workflows, and approvals",
            "controls": [
                {
                    "control_id": "MANAGE-1",
                    "name": "Risk Mitigation Actions",
                    "description": "Documented mitigation actions for identified risks",
                    "implementation": "risk_management with mitigation_plans",
                    "status": "implemented",
                },
                {
                    "control_id": "MANAGE-2",
                    "name": "Evaluation Workflows",
                    "description": "Structured evaluation workflows before deployment",
                    "implementation": "ai_evaluation with quality_gates",
                    "status": "implemented",
                },
                {
                    "control_id": "MANAGE-3",
                    "name": "Approval Processes",
                    "description": "Multi-level approval for AI deployment",
                    "implementation": "approval_workflow with governance_committee",
                    "status": "implemented",
                },
                {
                    "control_id": "MANAGE-4",
                    "name": "Continuous Monitoring",
                    "description": "Ongoing monitoring of AI systems in production",
                    "implementation": "monitoring-service with prometheus_metrics",
                    "status": "implemented",
                },
            ],
        },
    }

    @classmethod
    def get_alignment_report(cls) -> dict[str, Any]:
        """Generate NIST AI RMF alignment report."""
        total_controls = sum(
            len(fn["controls"]) for fn in cls.ALIGNMENT_MAP.values()
        )
        implemented = sum(
            1 for fn in cls.ALIGNMENT_MAP.values()
            for c in fn["controls"]
            if c["status"] == "implemented"
        )
        return {
            "framework": "NIST AI RMF 1.0",
            "total_functions": len(cls.ALIGNMENT_MAP),
            "total_controls": total_controls,
            "implemented_controls": implemented,
            "alignment_percentage": round(implemented / total_controls * 100, 1),
            "functions": cls.ALIGNMENT_MAP,
            "overall_status": "aligned" if implemented == total_controls else "partial",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def get_function_controls(cls, function: str) -> list[dict[str, Any]]:
        """Get controls for a specific NIST AI RMF function."""
        if function not in cls.ALIGNMENT_MAP:
            raise ValueError(f"Unknown function '{function}'. Must be one of {list(cls.ALIGNMENT_MAP.keys())}")
        return cls.ALIGNMENT_MAP[function]["controls"]


# ═══════════════════════════════════════════════════════════════════════
# 4. Responsible AI Controls
# ═══════════════════════════════════════════════════════════════════════
class ResponsibleAIControls:
    """Responsible AI controls for ethical AI deployment.

    Implements:
      - Explainability (SHAP, LIME, chain-of-thought)
      - Transparency (decision logging, model cards)
      - Fairness monitoring (continuous bias detection)
      - Safety controls (constitutional AI, kill switch)
    """

    CONTROLS = {
        "explainability": {
            "description": "AI decisions are explainable to affected users",
            "methods": ["SHAP", "LIME", "chain-of-thought", "feature-importance"],
            "status": "implemented",
            "implementation": "ai_governance.explainability",
        },
        "transparency": {
            "description": "Decision logging and model cards",
            "methods": ["decision-logging", "model-cards", "audit-trail"],
            "status": "implemented",
            "implementation": "audit-service + model-registry",
        },
        "fairness_monitoring": {
            "description": "Continuous bias detection in production",
            "methods": ["bias-detection", "fairness-metrics", "disparate-impact"],
            "status": "implemented",
            "implementation": "BiasDetectionEngine + FairnessMetrics",
        },
        "safety_controls": {
            "description": "Constitutional AI and kill switch",
            "methods": ["constitutional-ai", "kill-switch", "safety-layer"],
            "status": "implemented",
            "implementation": "safety-layer + ai_alignment",
        },
        "privacy_protection": {
            "description": "PII detection and data minimization",
            "methods": ["pii-detection", "data-minimization", "differential-privacy"],
            "status": "implemented",
            "implementation": "pii_detector + presidio",
        },
        "human_oversight": {
            "description": "Human-in-the-loop for sensitive decisions",
            "methods": ["human-review", "approval-workflow", "escalation"],
            "status": "implemented",
            "implementation": "approval-workflow + workflow-engine",
        },
    }

    @classmethod
    def get_all_controls(cls) -> dict[str, Any]:
        """Get all responsible AI controls."""
        return dict(cls.CONTROLS)

    @classmethod
    def get_control(cls, control_name: str) -> dict[str, Any]:
        """Get a specific control."""
        if control_name not in cls.CONTROLS:
            raise ValueError(f"Unknown control '{control_name}'")
        return cls.CONTROLS[control_name]


# ═══════════════════════════════════════════════════════════════════════
# 5. AI Evaluation Service v12
# ═══════════════════════════════════════════════════════════════════════
class AIEvaluationServiceV12:
    """v12 AI Evaluation Service with bias detection and responsible AI.

    Combines:
      - Quality evaluation (accuracy, task success, hallucination)
      - Bias detection (dataset, output, performance disparity)
      - Fairness metrics (demographic parity, equal opportunity, equalized odds)
      - NIST AI RMF alignment
      - Responsible AI controls
    """

    def __init__(self):
        self.bias_engine = BiasDetectionEngine()
        self._eval_results: list[dict[str, Any]] = []

    def evaluate_quality(
        self,
        target: str,
        eval_dataset: list[dict[str, Any]],
        *,
        metrics: list[str] | None = None,
    ) -> dict[str, Any]:
        """Evaluate AI quality (accuracy, task success, etc.).

        Args:
            target: Target AI system to evaluate
            eval_dataset: Evaluation dataset
            metrics: Metrics to compute (default: all)

        Returns:
            Quality evaluation result
        """
        if metrics is None:
            metrics = ["accuracy", "task_success_rate", "hallucination_rate"]

        results = {}
        for metric in metrics:
            if metric == "accuracy":
                correct = sum(1 for d in eval_dataset if d.get("prediction") == d.get("actual"))
                results["accuracy"] = correct / len(eval_dataset) if eval_dataset else 0.0
            elif metric == "task_success_rate":
                success = sum(1 for d in eval_dataset if d.get("success", False))
                results["task_success_rate"] = success / len(eval_dataset) if eval_dataset else 0.0
            elif metric == "hallucination_rate":
                halluc = sum(1 for d in eval_dataset if d.get("hallucination", False))
                results["hallucination_rate"] = halluc / len(eval_dataset) if eval_dataset else 0.0

        eval_result = {
            "eval_id": str(uuid.uuid4()),
            "target": target,
            "eval_type": "quality",
            "metrics": results,
            "sample_size": len(eval_dataset),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        }
        self._eval_results.append(eval_result)
        return eval_result

    def evaluate_bias(
        self,
        target: str,
        predictions: list[dict[str, Any]],
        protected_attribute: str,
    ) -> dict[str, Any]:
        """Evaluate bias across protected attributes.

        Args:
            target: Target AI system
            predictions: Prediction records with protected_attribute
            protected_attribute: Attribute to check (gender, ethnicity, etc.)

        Returns:
            Bias evaluation result
        """
        dataset_bias = self.bias_engine.analyze_dataset_bias(
            predictions, protected_attribute
        )
        output_bias = self.bias_engine.analyze_output_bias(
            predictions, protected_attribute
        )
        perf_disparity = self.bias_engine.analyze_performance_disparity(
            predictions, protected_attribute
        )

        eval_result = {
            "eval_id": str(uuid.uuid4()),
            "target": target,
            "eval_type": "bias",
            "protected_attribute": protected_attribute,
            "dataset_bias": dataset_bias,
            "output_bias": output_bias,
            "performance_disparity": perf_disparity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        }
        self._eval_results.append(eval_result)
        return eval_result

    def evaluate_fairness(
        self,
        target: str,
        predictions: list[dict[str, Any]],
        protected_attribute: str,
    ) -> dict[str, Any]:
        """Evaluate fairness metrics.

        Args:
            target: Target AI system
            predictions: Prediction records
            protected_attribute: Attribute to check

        Returns:
            Fairness evaluation result
        """
        fairness = FairnessMetrics.calculate_all(predictions, protected_attribute)
        # Compute overall status
        statuses = [
            fairness["demographic_parity"]["status"],
            fairness["equal_opportunity"]["status"],
            fairness["equalized_odds"]["status"],
            fairness["disparate_impact"]["status"],
        ]
        fairness["overall_status"] = "fail" if "fail" in statuses else "pass"
        fairness["eval_id"] = str(uuid.uuid4())
        fairness["target"] = target
        fairness["eval_type"] = "fairness"
        return fairness

    def get_responsible_ai_report(self) -> dict[str, Any]:
        """Get responsible AI controls report."""
        return {
            "controls": ResponsibleAIControls.get_all_controls(),
            "nist_ai_rmf": NISTAIRMFAlignment.get_alignment_report(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_all_evaluations(self) -> list[dict[str, Any]]:
        """Get all evaluation results."""
        return list(self._eval_results)
