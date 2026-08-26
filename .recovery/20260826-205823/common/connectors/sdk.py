"""
HSAAI Enterprise Connector SDK
================================
SDK for adding new connectors in minutes.

A connector can be added in 3 ways:
  1. Programmatic — subclass BaseConnector and use @connector decorator
  2. Config-only   — register a YAML/JSON config that uses the GenericRESTConnector
  3. Dynamic       — POST to /v1/connectors/admin/create with config JSON

This SDK provides helpers for all three approaches.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

from .base import (
    BaseConnector, ConnectorConfig, HealthResult, HealthStatus,
    AuthStrategy, connector,
)


# ═══════════════════════════════════════════════════════════════════════════
#  SDK Models
# ═══════════════════════════════════════════════════════════════════════════
class ConnectorManifest(BaseModel):
    """Manifest describing a connector (for YAML/JSON config-driven registration)."""
    name: str = Field(..., description="Unique connector name (e.g. 'sap_s4hana')")
    display_name: str
    category: str = "custom"
    version: str = "1.0.0"
    base_url: str
    api_version: Optional[str] = None
    auth_strategy: AuthStrategy = AuthStrategy.NONE
    credentials_ref: Optional[str] = None

    # Optional capabilities
    supports_search: bool = False
    supports_sync: bool = False
    supports_execute: bool = True

    # Actions schema (name → params schema)
    actions: dict[str, dict] = Field(default_factory=dict)

    # Connector-specific config
    config: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
#  Generic REST Connector — config-driven, no code needed
# ═══════════════════════════════════════════════════════════════════════════
@connector("generic_rest", version="1.0.0", category="Generic")
class GenericRESTConnector(BaseConnector):
    """
    A config-driven REST connector that can talk to any REST API.
    Configure actions via the manifest; no Python code needed.

    Example manifest (YAML):
        name: my_api
        display_name: My Custom API
        base_url: https://api.example.com
        auth_strategy: bearer
        credentials_ref: my_api_token
        actions:
          get_users:
            method: GET
            path: /users
            params:
              limit: integer
          create_user:
            method: POST
            path: /users
            body:
              name: string
              email: string
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self._manifest: Optional[ConnectorManifest] = None
        # Load manifest from config.extra if provided
        if hasattr(config, "manifest"):
            self._manifest = ConnectorManifest(**config.manifest)  # type: ignore

    async def authenticate(self) -> None:
        """Authenticate based on the configured strategy."""
        if self.config.auth_strategy == AuthStrategy.NONE:
            return
        # Real implementations would fetch tokens here
        # For now, we just validate that credentials are present
        if not self.config.credentials_ref:
            raise ValueError(f"credentials_ref required for {self.config.auth_strategy}")

    async def health(self) -> HealthResult:
        """Check upstream health by hitting a health endpoint."""
        import time
        start = time.monotonic()
        try:
            response = await self._client.get("/health")
            latency = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency,
                )
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=latency,
                error=f"HTTP {response.status_code}",
            )
        except Exception as e:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=(time.monotonic() - start) * 1000,
                error=str(e),
            )

    async def search(self, query: str, **kwargs) -> list[dict]:
        """Search via GET /search?q=query."""
        response = await self._client.get("/search", params={"q": query, **kwargs})
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else data.get("results", [])

    async def execute(self, action: str, **kwargs) -> dict:
        """Execute a named action defined in the manifest."""
        if not self._manifest or action not in self._manifest.actions:
            # Default: treat action as a path
            response = await self._client.get(f"/{action}", params=kwargs)
            response.raise_for_status()
            return response.json()

        action_def = self._manifest.actions[action]
        method = action_def.get("method", "GET").upper()
        path = action_def.get("path", f"/{action}")
        body = kwargs.pop("body", None) or kwargs

        if method == "GET":
            response = await self._client.get(path, params=kwargs)
        elif method == "POST":
            response = await self._client.post(path, json=body)
        elif method == "PUT":
            response = await self._client.put(path, json=body)
        elif method == "DELETE":
            response = await self._client.delete(path, params=kwargs)
        elif method == "PATCH":
            response = await self._client.patch(path, json=body)
        else:
            raise ValueError(f"Unsupported method: {method}")

        response.raise_for_status()
        return response.json()

    def metadata(self) -> dict:
        return {
            "name": self.config.name,
            "display_name": self.config.display_name,
            "category": self.config.category,
            "version": self.config.version,
            "base_url": self.config.base_url,
            "auth_strategy": self.config.auth_strategy.value,
            "actions": list(self._manifest.actions.keys()) if self._manifest else [],
            "capabilities": {
                "search": True,
                "sync": False,
                "execute": True,
            },
        }

    def permissions(self) -> list[str]:
        return self.config.required_permissions or [f"connector:{self.config.name}:use"]


# ═══════════════════════════════════════════════════════════════════════════
#  SDK Helpers
# ═══════════════════════════════════════════════════════════════════════════
def register_from_manifest(manifest: ConnectorManifest) -> None:
    """
    Register a connector from a manifest (no code needed).
    Uses GenericRESTConnector under the hood.
    """
    from .registry import ConnectorRegistry
    config = ConnectorConfig(
        name=manifest.name,
        display_name=manifest.display_name,
        category=manifest.category,
        version=manifest.version,
        base_url=manifest.base_url,
        api_version=manifest.api_version,
        auth_strategy=manifest.auth_strategy,
        credentials_ref=manifest.credentials_ref,
        **manifest.config,
    )
    # Attach manifest to config for the GenericRESTConnector to pick up
    config.__dict__["manifest"] = manifest.model_dump()
    instance = ConnectorRegistry.create("generic_rest", config)
    return instance


def register_from_yaml(yaml_path: str | Path) -> None:
    """Register a connector from a YAML manifest file."""
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    manifest = ConnectorManifest(**data)
    return register_from_manifest(manifest)


def register_from_json(json_path: str | Path) -> None:
    """Register a connector from a JSON manifest file."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    with open(path) as f:
        data = json.load(f)
    manifest = ConnectorManifest(**data)
    return register_from_manifest(manifest)


def scaffold_connector(name: str, category: str, base_url: str,
                       output_dir: str | Path = ".") -> Path:
    """
    Scaffold a new connector Python file with boilerplate.
    Returns the path to the created file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    class_name = "".join(p.capitalize() for p in name.split("_")) + "Connector"
    file_path = output_dir / f"{name}.py"

    template = f'''"""
{class_name} — {name} connector for HSAAI
Category: {category}
"""
from __future__ import annotations

from packages.common.connectors import (
    BaseConnector, ConnectorConfig, HealthResult, HealthStatus,
    AuthStrategy, connector,
)


@connector("{name}", version="1.0.0", category="{category}")
class {class_name}(BaseConnector):
    """
    Connector for {name} ({category}).

    Auto-inherits: retry, circuit breaker, rate limiting, caching,
    audit logging, metrics, health checks, discovery.
    """

    async def authenticate(self) -> None:
        """TODO: Implement authentication (OAuth2/Basic/API Key/mTLS)."""
        # Example: fetch OAuth2 token
        # response = await self._client.post("/oauth/token", data={{...}})
        # self._token = response.json()["access_token"]
        pass

    async def health(self) -> HealthResult:
        """Check if {name} is healthy."""
        import time
        start = time.monotonic()
        try:
            response = await self._client.get("/health")
            latency = (time.monotonic() - start) * 1000
            return HealthResult(
                status=HealthStatus.HEALTHY if response.status_code == 200 else HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=latency,
                error=None if response.status_code == 200 else f"HTTP {{response.status_code}}",
            )
        except Exception as e:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=(time.monotonic() - start) * 1000,
                error=str(e),
            )

    async def search(self, query: str, **kwargs) -> list[dict]:
        """Search {name}."""
        response = await self._client.get("/search", params={{"q": query, **kwargs}})
        response.raise_for_status()
        return response.json().get("results", [])

    async def execute(self, action: str, **kwargs) -> dict:
        """Execute an action on {name}."""
        # TODO: Implement action routing
        response = await self._client.post(f"/{{action}}", json=kwargs)
        response.raise_for_status()
        return response.json()

    def metadata(self) -> dict:
        return {{
            "name": self.config.name,
            "display_name": self.config.display_name,
            "category": self.config.category,
            "version": self.config.version,
            "base_url": self.config.base_url,
            "capabilities": {{"search": True, "execute": True, "sync": False}},
            "actions": [],  # TODO: list supported actions
        }}

    def permissions(self) -> list[str]:
        return [f"connector:{{self.config.name}}:use"]
'''
    file_path.write_text(template, encoding="utf-8")
    return file_path


__all__ = [
    "ConnectorManifest",
    "GenericRESTConnector",
    "register_from_manifest",
    "register_from_yaml",
    "register_from_json",
    "scaffold_connector",
]
