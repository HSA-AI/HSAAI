"""
HSAAI Connector Registry — Dynamic Discovery & Registration
=============================================================
Central registry for all connectors. Supports:
  - Class registration (via @connector decorator)
  - Instance registration (auto on BaseConnector.__init__)
  - Dynamic loading from config (add connectors without code changes)
  - Health aggregation
  - Metrics aggregation
"""
from __future__ import annotations

import importlib
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from .base import (
    BaseConnector, ConnectorConfig, ConnectorState,
    HealthResult, HealthStatus, ConnectorMetrics,
)

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """
    Singleton registry holding all connector classes and instances.

    Usage:
        # Register a class (usually via @connector decorator)
        ConnectorRegistry.register_class("sap_s4hana", SAPS4HANAConnector, "1.0.0", "ERP")

        # Instantiate from config (no code change needed)
        cfg = ConnectorConfig(name="sap_s4hana", display_name="SAP S/4HANA", ...)
        instance = ConnectorRegistry.create("sap_s4hana", cfg)

        # Use
        await instance.connect()
        result = await instance.call("get_sales_orders", top=10)

        # Aggregate health
        health_report = ConnectorRegistry.health_all()
    """

    _classes: dict[str, tuple[type, str, str]] = {}  # name -> (cls, version, category)
    _instances: dict[str, BaseConnector] = {}  # name -> instance

    @classmethod
    def register_class(cls, name: str, connector_cls: type,
                       version: str = "1.0.0", category: str = "generic") -> None:
        """Register a connector CLASS (called by @connector decorator)."""
        cls._classes[name] = (connector_cls, version, category)
        logger.debug(f"Registered connector class: {name} v{version} ({category})")

    @classmethod
    def register(cls, instance: BaseConnector) -> None:
        """Register a connector INSTANCE (called automatically by BaseConnector.__init__)."""
        name = instance.config.name
        cls._instances[name] = instance
        logger.debug(f"Registered connector instance: {name}")

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister a connector (both class and instance)."""
        cls._classes.pop(name, None)
        instance = cls._instances.pop(name, None)
        if instance:
            logger.info(f"Unregistered connector: {name}")

    @classmethod
    def get_class(cls, name: str) -> Optional[tuple[type, str, str]]:
        return cls._classes.get(name)

    @classmethod
    def get_instance(cls, name: str) -> Optional[BaseConnector]:
        return cls._instances.get(name)

    @classmethod
    def list_classes(cls) -> list[dict]:
        """List all registered connector CLASSES (catalog)."""
        return [
            {"name": name, "version": ver, "category": cat, "class": cls.__name__}
            for name, (cls, ver, cat) in sorted(cls._classes.items())
        ]

    @classmethod
    def list_instances(cls) -> list[dict]:
        """List all registered connector INSTANCES (running)."""
        return [
            {
                "name": inst.config.name,
                "display_name": inst.config.display_name,
                "category": inst.config.category,
                "version": inst.config.version,
                "state": inst.state.value,
                "base_url": inst.config.base_url,
                "last_health": inst.get_health().model_dump() if inst.get_health() else None,
            }
            for inst in sorted(cls._instances.values(), key=lambda i: i.config.name)
        ]

    @classmethod
    def create(cls, name: str, config: ConnectorConfig) -> BaseConnector:
        """Instantiate a registered connector class by name."""
        if name not in cls._classes:
            raise KeyError(f"Connector '{name}' not registered. Available: {list(cls._classes.keys())}")
        connector_cls, _, _ = cls._classes[name]
        instance = connector_cls(config)
        return instance

    @classmethod
    async def connect_all(cls) -> dict[str, bool]:
        """Connect all registered instances. Returns map of name -> success."""
        results = {}
        for name, inst in cls._instances.items():
            try:
                await inst.connect()
                results[name] = True
            except Exception as e:
                logger.error(f"Failed to connect '{name}': {e}")
                results[name] = False
        return results

    @classmethod
    async def disconnect_all(cls) -> None:
        """Disconnect all registered instances gracefully."""
        for inst in cls._instances.values():
            try:
                await inst.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting '{inst.config.name}': {e}")

    @classmethod
    def health_all(cls) -> dict[str, Any]:
        """Aggregate health status of all connectors."""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": len(cls._instances),
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "unknown": 0,
            "connectors": {},
        }
        for name, inst in cls._instances.items():
            h = inst.get_health()
            if h is None:
                report["unknown"] += 1
                status = "unknown"
            else:
                status = h.status.value
                report[status] = report.get(status, 0) + 1
            report["connectors"][name] = {
                "state": inst.state.value,
                "health": h.model_dump() if h else None,
                "metrics": inst.get_metrics().model_dump(),
            }
        return report

    @classmethod
    def metrics_all(cls) -> dict[str, ConnectorMetrics]:
        """Get metrics for all connectors."""
        return {name: inst.get_metrics() for name, inst in cls._instances.items()}

    @classmethod
    def discover(cls, package_path: str = "packages.common.connectors.connectors") -> int:
        """
        Auto-discover and register all connector classes in a package.
        Call this at startup to load all connectors.
        """
        import pkgutil
        try:
            pkg = importlib.import_module(package_path)
        except ImportError as e:
            logger.warning(f"Cannot import connectors package '{package_path}': {e}")
            return 0

        count = 0
        for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
            full_name = f"{package_path}.{modname}"
            try:
                importlib.import_module(full_name)
                count += 1
            except Exception as e:
                logger.error(f"Failed to import connector '{full_name}': {e}")
        logger.info(f"Discovered {count} connector modules from '{package_path}'")
        return count

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (for testing)."""
        cls._classes.clear()
        cls._instances.clear()


# ═══════════════════════════════════════════════════════════════════════════
#  Singleton instance for convenient access
# ═══════════════════════════════════════════════════════════════════════════
registry = ConnectorRegistry
