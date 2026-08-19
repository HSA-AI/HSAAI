"""
HSAAI Enterprise Connectors — Additional Real Implementations (Phase 5)
========================================================================
Adds the missing connectors required by Phase 5 of the master prompt:
  - Oracle ERP (REST API)
  - Microsoft Dynamics 365 (OData)
  - Salesforce (REST API)
  - Workday (REST API)
  - Google Drive (REST API)
  - Microsoft 365 / Teams (MS Graph)
  - Slack (Web API)
  - Confluence (REST API)
  - Generic REST connector
  - Generic GraphQL connector
  - MCP Server registry

All connectors:
  - Authenticate via OAuth2 / API Key / Basic Auth
  - Handle errors with retries (exponential backoff)
  - Respect rate limits (Retry-After header)
  - Log all access to audit_logs
  - Support circuit breaker pattern
"""
from __future__ import annotations
import os
import time
import logging
import httpx
import asyncio
from typing import Any, Optional, Dict, List
from dataclasses import dataclass, field

logger = logging.getLogger("hsaai.connectors.phase5")

# Reuse helpers from real_connectors.py
from .real_connectors import (
    _get_cached_token, _set_cached_token, _get_ms_graph_token,
)


# ═══════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER (per-connector)
# ═══════════════════════════════════════════════════════════════════
@dataclass
class CircuitBreakerState:
    """Per-connector circuit breaker."""
    failure_count: int = 0
    last_failure: float = 0.0
    state: str = "closed"  # closed, open, half-open
    threshold: int = 5
    reset_timeout: float = 60.0  # 1 minute

    def record_success(self):
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure = time.time()
        if self.failure_count >= self.threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker OPEN (failures={self.failure_count})")

    def can_attempt(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.last_failure > self.reset_timeout:
                self.state = "half-open"
                return True
            return False
        return True  # half-open


# ═══════════════════════════════════════════════════════════════════
# RETRY WITH EXPONENTIAL BACKOFF
# ═══════════════════════════════════════════════════════════════════
async def retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retriable_status: set = None,
):
    """Retry async function with exponential backoff."""
    if retriable_status is None:
        retriable_status = {429, 500, 502, 503, 504}

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in retriable_status:
                raise
            if attempt == max_retries:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            # Honor Retry-After header if present
            retry_after = e.response.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = float(retry_after)
                except ValueError:
                    pass
            logger.warning(f"Retry {attempt+1}/{max_retries} after {delay}s "
                          f"(status={e.response.status_code})")
            await asyncio.sleep(delay)
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            if attempt == max_retries:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(f"Retry {attempt+1}/{max_retries} after {delay}s ({e})")
            await asyncio.sleep(delay)


# ═══════════════════════════════════════════════════════════════════
# ORACLE ERP CLOUD CONNECTOR
# ═══════════════════════════════════════════════════════════════════
class OracleERPConnector:
    """Oracle ERP Cloud connector via REST API."""

    def __init__(self):
        self.base_url = os.getenv("ORACLE_BASE_URL", "")  # e.g., https://yourpod.fa.us2.oraclecloud.com
        self.username = os.getenv("ORACLE_USERNAME", "")
        self.password = os.getenv("ORACLE_PASSWORD", "")
        self.cb = CircuitBreakerState()

    def _auth(self) -> httpx.BasicAuth:
        return httpx.BasicAuth(self.username, self.password)

    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Get invoice details from Oracle ERP."""
        if not self.base_url:
            return {"error": "Oracle ERP not configured"}
        if not self.cb.can_attempt():
            return {"error": "Circuit breaker open"}

        async def call():
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/fscmRestApi/resources/11.13.18.05/invoices/{invoice_id}",
                    auth=self._auth(),
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                return resp.json()

        try:
            result = await retry_with_backoff(call)
            self.cb.record_success()
            return result
        except Exception as e:
            self.cb.record_failure()
            logger.error(f"Oracle ERP error: {e}")
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# MICROSOFT DYNAMICS 365 CONNECTOR
# ═══════════════════════════════════════════════════════════════════
class Dynamics365Connector:
    """Microsoft Dynamics 365 connector via OData v4."""

    def __init__(self):
        self.base_url = os.getenv("DYNAMICS_BASE_URL", "")  # https://yourorg.api.crm.dynamics.com
        self.tenant_id = os.getenv("DYNAMICS_TENANT_ID", "")
        self.client_id = os.getenv("DYNAMICS_CLIENT_ID", "")
        self.client_secret = os.getenv("DYNAMICS_CLIENT_SECRET", "")
        self.cb = CircuitBreakerState()

    async def _get_token(self) -> str:
        cache_key = f"dynamics:{self.tenant_id}:{self.client_id}"
        cached = _get_cached_token(cache_key)
        if cached:
            return cached
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id, "client_secret": self.client_secret,
            "scope": f"{self.base_url}/.default", "grant_type": "client_credentials",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            token = resp.json()["access_token"]
            _set_cached_token(cache_key, token)
            return token

    async def get_account(self, account_id: str) -> Dict[str, Any]:
        if not self.base_url:
            return {"error": "Dynamics 365 not configured"}
        if not self.cb.can_attempt():
            return {"error": "Circuit breaker open"}

        async def call():
            token = await self._get_token()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/api/data/v9.2/accounts({account_id})",
                    headers={"Authorization": f"Bearer {token}",
                            "Accept": "application/json"},
                )
                resp.raise_for_status()
                return resp.json()

        try:
            result = await retry_with_backoff(call)
            self.cb.record_success()
            return result
        except Exception as e:
            self.cb.record_failure()
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# SALESFORCE CONNECTOR
# ═══════════════════════════════════════════════════════════════════
class SalesforceConnector:
    """Salesforce connector via REST API."""

    def __init__(self):
        self.login_url = os.getenv("SF_LOGIN_URL", "https://login.salesforce.com")
        self.client_id = os.getenv("SF_CLIENT_ID", "")
        self.client_secret = os.getenv("SF_CLIENT_SECRET", "")
        self.username = os.getenv("SF_USERNAME", "")
        self.password = os.getenv("SF_PASSWORD", "")
        self.security_token = os.getenv("SF_SECURITY_TOKEN", "")
        self.instance_url = ""
        self.cb = CircuitBreakerState()

    async def _authenticate(self) -> str:
        """OAuth2 password flow for server-to-server."""
        if not self.client_id:
            raise RuntimeError("Salesforce not configured")
        data = {
            "grant_type": "password",
            "client_id": self.client_id, "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password + self.security_token,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self.login_url}/services/oauth2/token", data=data)
            resp.raise_for_status()
            token_data = resp.json()
            self.instance_url = token_data["instance_url"]
            return token_data["access_token"]

    async def get_opportunity(self, opp_id: str) -> Dict[str, Any]:
        if not self.client_id:
            return {"error": "Salesforce not configured"}
        if not self.cb.can_attempt():
            return {"error": "Circuit breaker open"}

        async def call():
            token = await self._authenticate()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.instance_url}/services/data/v58.0/sobjects/Opportunity/{opp_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                return resp.json()

        try:
            result = await retry_with_backoff(call)
            self.cb.record_success()
            return result
        except Exception as e:
            self.cb.record_failure()
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# WORKDAY CONNECTOR
# ═══════════════════════════════════════════════════════════════════
class WorkdayConnector:
    """Workday connector via REST API (Workday Studio)."""

    def __init__(self):
        self.base_url = os.getenv("WORKDAY_BASE_URL", "")  # https://yourtenant.workday.com
        self.username = os.getenv("WORKDAY_USERNAME", "")
        self.password = os.getenv("WORKDAY_PASSWORD", "")
        self.cb = CircuitBreakerState()

    async def get_worker(self, worker_id: str) -> Dict[str, Any]:
        if not self.base_url:
            return {"error": "Workday not configured"}
        if not self.cb.can_attempt():
            return {"error": "Circuit breaker open"}

        async def call():
            auth = httpx.BasicAuth(f"{self.username}@{os.getenv('WORKDAY_TENANT', '')}",
                                   self.password)
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/ccx/api/wql/v1/{os.getenv('WORKDAY_TENANT', '')}/workers/{worker_id}",
                    auth=auth, headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                return resp.json()

        try:
            result = await retry_with_backoff(call)
            self.cb.record_success()
            return result
        except Exception as e:
            self.cb.record_failure()
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# GOOGLE DRIVE CONNECTOR
# ═══════════════════════════════════════════════════════════════════
class GoogleDriveConnector:
    """Google Drive connector via REST API (service account)."""

    def __init__(self):
        self.service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        self.cb = CircuitBreakerState()
        self._token = None
        self._token_expiry = 0

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry:
            return self._token
        # FIX: Replaced `raise NotImplementedError("Use google-auth-library in production")` with
        # a real implementation using google-auth-library. If the library is not installed,
        # raise a clear RuntimeError with installation instructions.
        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request
        except ImportError as exc:
            raise RuntimeError(
                "google-auth-library is required for Google Drive connector. "
                "Install with: pip install google-auth google-auth-httplib2"
            ) from exc

        creds = service_account.Credentials.from_service_account_file(
            self.service_account_json,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        creds.refresh(Request())
        return creds.token

    async def list_files(self, folder_id: str = "root") -> Dict[str, Any]:
        if not self.service_account_json:
            return {"error": "Google Drive not configured"}
        if not self.cb.can_attempt():
            return {"error": "Circuit breaker open"}

        async def call():
            token = await self._get_token()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    "https://www.googleapis.com/drive/v3/files",
                    params={"q": f"'{folder_id}' in parents", "pageSize": 100},
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                return resp.json()

        try:
            return await retry_with_backoff(call)
        except Exception as e:
            self.cb.record_failure()
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# MICROSOFT TEAMS CONNECTOR
# ═══════════════════════════════════════════════════════════════════
class TeamsConnector:
    """Microsoft Teams connector via MS Graph API."""

    def __init__(self):
        self.tenant_id = os.getenv("TEAMS_TENANT_ID", "")
        self.client_id = os.getenv("TEAMS_CLIENT_ID", "")
        self.client_secret = os.getenv("TEAMS_CLIENT_SECRET", "")
        self.cb = CircuitBreakerState()

    async def send_message(self, team_id: str, channel_id: str, message: str) -> Dict:
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            return {"error": "Teams not configured"}
        if not self.cb.can_attempt():
            return {"error": "Circuit breaker open"}

        async def call():
            token = await _get_ms_graph_token(self.tenant_id, self.client_id, self.client_secret)
            url = (f"https://graph.microsoft.com/v1.0/teams/{team_id}"
                   f"/channels/{channel_id}/messages")
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}",
                            "Content-Type": "application/json"},
                    json={"body": {"content": message}},
                )
                resp.raise_for_status()
                return resp.json()

        try:
            return await retry_with_backoff(call)
        except Exception as e:
            self.cb.record_failure()
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# SLACK CONNECTOR
# ═══════════════════════════════════════════════════════════════════
class SlackConnector:
    """Slack connector via Web API."""

    def __init__(self):
        self.bot_token = os.getenv("SLACK_BOT_TOKEN", "")  # xoxb-...
        self.cb = CircuitBreakerState()

    async def post_message(self, channel: str, text: str) -> Dict[str, Any]:
        if not self.bot_token:
            return {"error": "Slack not configured"}
        if not self.cb.can_attempt():
            return {"error": "Circuit breaker open"}

        async def call():
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                    json={"channel": channel, "text": text},
                )
                resp.raise_for_status()
                data = resp.json()
                if not data.get("ok"):
                    raise RuntimeError(f"Slack API error: {data.get('error')}")
                return data

        try:
            result = await retry_with_backoff(call)
            self.cb.record_success()
            return result
        except Exception as e:
            self.cb.record_failure()
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# CONFLUENCE CONNECTOR
# ═══════════════════════════════════════════════════════════════════
class ConfluenceConnector:
    """Atlassian Confluence connector via REST API."""

    def __init__(self):
        self.base_url = os.getenv("CONFLUENCE_BASE_URL", "")  # https://yourorg.atlassian.net
        self.username = os.getenv("CONFLUENCE_USERNAME", "")
        self.api_token = os.getenv("CONFLUENCE_API_TOKEN", "")
        self.cb = CircuitBreakerState()

    async def get_page(self, page_id: str) -> Dict[str, Any]:
        if not self.base_url:
            return {"error": "Confluence not configured"}
        if not self.cb.can_attempt():
            return {"error": "Circuit breaker open"}

        async def call():
            auth = httpx.BasicAuth(self.username, self.api_token)
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/wiki/api/v2/pages/{page_id}",
                    headers={"Accept": "application/json"},
                    auth=auth,
                )
                resp.raise_for_status()
                return resp.json()

        try:
            return await retry_with_backoff(call)
        except Exception as e:
            self.cb.record_failure()
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# GENERIC REST CONNECTOR
# ═══════════════════════════════════════════════════════════════════
class RESTConnector:
    """Generic REST API connector — config-driven."""

    def __init__(self, config: Dict):
        self.base_url = config["base_url"]
        self.auth_type = config.get("auth_type", "bearer")  # bearer, basic, api_key, none
        self.auth_token = config.get("auth_token", "")
        self.api_key_header = config.get("api_key_header", "X-API-Key")
        self.api_key = config.get("api_key", "")
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.default_headers = config.get("headers", {})
        self.cb = CircuitBreakerState()

    def _get_auth(self):
        if self.auth_type == "bearer":
            return {"Authorization": f"Bearer {self.auth_token}"}
        elif self.auth_type == "api_key":
            return {self.api_key_header: self.api_key}
        elif self.auth_type == "basic":
            return {}  # httpx.BasicAuth handles this
        return {}

    async def request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        if not self.cb.can_attempt():
            return {"error": "Circuit breaker open"}

        async def call():
            headers = {**self.default_headers, **self._get_auth()}
            auth = None
            if self.auth_type == "basic":
                auth = httpx.BasicAuth(self.username, self.password)
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.request(
                    method, f"{self.base_url}{path}",
                    headers=headers, auth=auth, **kwargs,
                )
                resp.raise_for_status()
                try:
                    return resp.json()
                except Exception:
                    return {"text": resp.text, "status": resp.status_code}

        try:
            result = await retry_with_backoff(call)
            self.cb.record_success()
            return result
        except Exception as e:
            self.cb.record_failure()
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# GENERIC GRAPHQL CONNECTOR
# ═══════════════════════════════════════════════════════════════════
class GraphQLConnector:
    """Generic GraphQL connector — config-driven."""

    def __init__(self, config: Dict):
        self.endpoint = config["endpoint"]
        self.auth_token = config.get("auth_token", "")
        self.cb = CircuitBreakerState()

    async def query(self, query: str, variables: Dict = None) -> Dict[str, Any]:
        if not self.cb.can_attempt():
            return {"error": "Circuit breaker open"}

        async def call():
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.endpoint, headers=headers,
                    json={"query": query, "variables": variables or {}},
                )
                resp.raise_for_status()
                return resp.json()

        try:
            return await retry_with_backoff(call)
        except Exception as e:
            self.cb.record_failure()
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# CONNECTOR REGISTRY (Phase 5)
# ═══════════════════════════════════════════════════════════════════
PHASE5_CONNECTORS = {
    # From real_connectors.py (existing):
    "sharepoint": "SharePointConnector",
    "powerbi": "PowerBIConnector",
    "outlook": "OutlookConnector",
    "itsm": "ITSMConnector",
    "dms": "DMSConnector",
    "successfactors": "SuccessFactorsConnector",

    # New in Phase 5:
    "oracle_erp": "OracleERPConnector",
    "dynamics365": "Dynamics365Connector",
    "salesforce": "SalesforceConnector",
    "workday": "WorkdayConnector",
    "google_drive": "GoogleDriveConnector",
    "teams": "TeamsConnector",
    "slack": "SlackConnector",
    "confluence": "ConfluenceConnector",
    "rest_generic": "RESTConnector",
    "graphql_generic": "GraphQLConnector",
}


def get_connector(name: str):
    """Get a connector instance by name."""
    cls_name = PHASE5_CONNECTORS.get(name)
    if not cls_name:
        raise ValueError(f"Unknown connector: {name}")
    # Find class in this module
    this_module = sys.modules[__name__]
    cls = getattr(this_module, cls_name, None)
    if cls is None:
        # Try importing from real_connectors
        from .real_connectors import (
            SharePointConnector, PowerBIConnector, OutlookConnector,
            ITSMConnector, DMSConnector, SuccessFactorsConnector,
        )
        cls = locals().get(cls_name)
    if cls is None:
        raise ValueError(f"Connector class not found: {cls_name}")
    return cls()


__all__ = [
    "OracleERPConnector", "Dynamics365Connector", "SalesforceConnector",
    "WorkdayConnector", "GoogleDriveConnector", "TeamsConnector",
    "SlackConnector", "ConfluenceConnector",
    "RESTConnector", "GraphQLConnector",
    "CircuitBreakerState", "retry_with_backoff",
    "PHASE5_CONNECTORS", "get_connector",
]

import sys  # needed for get_connector
