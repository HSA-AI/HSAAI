"""
HSAAI Enterprise Connector Framework
=====================================
Production-grade connector framework with 17 built-in capabilities.

Quick start:
    from packages.common.connectors import BaseConnector, ConnectorConfig, connector, registry

    @connector("my_service", version="1.0.0", category="Custom")
    class MyConnector(BaseConnector):
        async def authenticate(self): ...
        async def health(self): ...
        async def search(self, query): ...
        async def execute(self, action, **kwargs): ...
        def metadata(self): ...
        def permissions(self): ...

    # At startup
    registry.discover()  # auto-loads all @connector-decorated classes
    await registry.connect_all()

    # Use
    result = await registry.get_instance("my_service").call("some_action", param=1)
"""
from .base import (
    BaseConnector, ConnectorConfig, HealthResult, ConnectorMetrics,
    ConnectorState, HealthStatus, AuthStrategy, CircuitBreakerState, Severity,
    CircuitBreaker, CircuitBreakerOpenError, RateLimiter, RetryPolicy,
    ResponseCache, AuditLogger, connector,
    ConnectorError, RateLimitExceededError, ConnectorNotConnectedError,
    ConnectorAuthenticationError,
)
from .registry import ConnectorRegistry, registry

__version__ = "1.0.0"
__all__ = [
    "BaseConnector", "ConnectorConfig", "HealthResult", "ConnectorMetrics",
    "ConnectorState", "HealthStatus", "AuthStrategy", "CircuitBreakerState", "Severity",
    "CircuitBreaker", "CircuitBreakerOpenError", "RateLimiter", "RetryPolicy",
    "ResponseCache", "AuditLogger", "connector",
    "ConnectorRegistry", "registry",
    "ConnectorError", "RateLimitExceededError",
    "ConnectorNotConnectedError", "ConnectorAuthenticationError",
]
