"""
HSAAI Self-Modifying Architecture Monitor — v0.4.0

The cognitive organism observes its own architecture and suggests
structural changes to improve performance, reduce cost, or add
capabilities. Like biological adaptation — the system reshapes itself.
"""
from __future__ import annotations
import logging, time, json
from dataclasses import dataclass, field, asdict
from typing import Any
logger = logging.getLogger("hsaai.self_modifying")

@dataclass
class ArchitectureObservation:
    """An observation about the system's own architecture."""
    timestamp: float = 0.0
    service: str = ""
    metric: str = ""
    value: float = 0.0
    threshold: float = 0.0
    status: str = ""  # healthy, warning, critical
    recommendation: str = ""

@dataclass
class ArchitectureChange:
    """A proposed architecture change."""
    change_id: str = ""
    change_type: str = ""  # scale, split, merge, add, remove, restructure
    target: str = ""
    description: str = ""
    rationale: str = ""
    expected_impact: str = ""
    risk_level: str = "low"
    estimated_cost: float = 0.0
    estimated_benefit: float = 0.0
    status: str = "proposed"  # proposed, approved, implementing, deployed, rolled_back
    proposed_at: float = 0.0


class SelfModifyingArchitectureMonitor:
    """
    Monitors the system's own architecture and proposes structural changes.
    The cognitive organism adapts its own body.
    """
    def __init__(self):
        self._observations: list[ArchitectureObservation] = []
        self._changes: list[ArchitectureChange] = []
        self._change_counter = 0
        self._service_baselines: dict[str, dict] = {}

    def set_baseline(self, service: str, metrics: dict):
        """Set baseline metrics for a service."""
        self._service_baselines[service] = {**metrics, "set_at": time.time()}

    async def observe(self, service: str, metric: str, value: float,
                      threshold: float, unit: str = "") -> ArchitectureObservation:
        """Observe a system metric and assess its status."""
        status = "healthy"
        recommendation = ""
        if value > threshold * 1.5:
            status = "critical"
            recommendation = f"{service}.{metric} = {value:.2f}{unit} (threshold: {threshold:.2f}) — URGENT action needed."
        elif value > threshold:
            status = "warning"
            recommendation = f"{service}.{metric} = {value:.2f}{unit} — approaching threshold, monitor closely."

        obs = ArchitectureObservation(
            timestamp=time.time(), service=service, metric=metric,
            value=value, threshold=threshold, status=status,
            recommendation=recommendation,
        )
        self._observations.append(obs)
        if len(self._observations) > 10000:
            self._observations = self._observations[-5000:]
        return obs

    async def propose_changes(self) -> list[ArchitectureChange]:
        """Analyze observations and propose architecture changes."""
        changes = []
        # Check for services that need scaling
        service_metrics = {}
        for obs in self._observations[-1000:]:
            key = f"{obs.service}.{obs.metric}"
            service_metrics[key] = obs

        for key, obs in service_metrics.items():
            if obs.status == "critical":
                if "latency" in obs.metric or "response_time" in obs.metric:
                    changes.append(await self._propose_change(
                        "scale", obs.service,
                        f"Scale {obs.service} horizontally — add 2 replicas",
                        f"{obs.metric} = {obs.value:.0f}ms exceeds threshold {obs.threshold:.0f}ms",
                        "Reduce latency by 40-60%",
                        "low", 5000, 50000,
                    ))
                elif "error_rate" in obs.metric:
                    changes.append(await self._propose_change(
                        "restructure", obs.service,
                        f"Investigate and restructure {obs.service} — high error rate",
                        f"Error rate {obs.value*100:.1f}% exceeds threshold {obs.threshold*100:.1f}%",
                        "Reduce errors by 80%, improve reliability",
                        "medium", 10000, 100000,
                    ))
                elif "memory" in obs.metric or "cpu" in obs.metric:
                    changes.append(await self._propose_change(
                        "scale", obs.service,
                        f"Increase resources for {obs.service} — {obs.metric} critical",
                        f"{obs.metric} = {obs.value:.1f}% exceeds threshold {obs.threshold:.1f}%",
                        "Prevent OOM/crashes, improve stability",
                        "low", 2000, 20000,
                    ))

        # Check for services that could be split
        for service, baseline in self._service_baselines.items():
            endpoints = baseline.get("endpoint_count", 0)
            if endpoints > 25:
                changes.append(await self._propose_change(
                    "split", service,
                    f"Split {service} into 2-3 smaller services — {endpoints} endpoints is too many",
                    f"Service has {endpoints} endpoints — violating single responsibility",
                    "Improve maintainability, independent scaling, fault isolation",
                    "medium", 50000, 200000,
                ))

        if changes:
            logger.info("🔧 ARCHITECTURE CHANGES PROPOSED: %d changes", len(changes))
        return changes

    async def _propose_change(self, change_type, target, description,
                              rationale, impact, risk, cost, benefit) -> ArchitectureChange:
        self._change_counter += 1
        return ArchitectureChange(
            change_id=f"arch-change-{self._change_counter:04d}",
            change_type=change_type, target=target,
            description=description, rationale=rationale,
            expected_impact=impact, risk_level=risk,
            estimated_cost=cost, estimated_benefit=benefit,
            proposed_at=time.time(),
        )

    def list_changes(self, status: str | None = None) -> list[dict]:
        changes = self._changes
        if status:
            changes = [c for c in changes if c.status == status]
        return [asdict(c) for c in changes]

    def stats(self) -> dict:
        return {
            "observations": len(self._observations),
            "changes_proposed": len(self._changes),
            "services_monitored": len(self._service_baselines),
            "critical_observations": sum(1 for o in self._observations[-1000:] if o.status == "critical"),
        }

architecture_monitor = SelfModifyingArchitectureMonitor()
__all__ = ["SelfModifyingArchitectureMonitor", "ArchitectureObservation",
           "ArchitectureChange", "architecture_monitor"]
