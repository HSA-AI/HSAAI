"""
موصل Microsoft Dynamics 365 لمنصة HSAAI
===========================================
يتيح هذا الموصل الوصول إلى Microsoft Dynamics 365 (Customer Engagement /
Finance & Operations) عبر OData v4 مع مصادقة OAuth2 من Azure AD
(client credentials flow).

الإجراءات المدعومة:
    - get_accounts      : جلب الحسابات
    - get_contacts      : جلب جهات الاتصال
    - get_opportunities : جلب الفرص
    - get_invoices      : جلب الفواتير

الاستخدام:
    cfg = ConnectorConfig(
        name="dynamics_365",
        display_name="Microsoft Dynamics 365",
        category="ERP",
        base_url="https://myorg.crm.dynamics.com",
        auth_strategy=AuthStrategy.OAUTH2_CLIENT_CREDENTIALS,
        secrets={
            "tenant_id": "...",
            "client_id": "...",
            "client_secret": "...",
        },
    )
    connector = Dynamics365Connector(cfg)
    await connector.connect()
    accounts = await connector.call("get_accounts", top=50)
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from packages.common.connectors import (
    AuthStrategy,
    BaseConnector,
    ConnectorAuthenticationError,
    ConnectorConfig,
    ConnectorError,
    HealthResult,
    HealthStatus,
    connector,
)

logger = logging.getLogger(__name__)


@connector("dynamics_365", version="1.0.0", category="ERP")
class Dynamics365Connector(BaseConnector):
    """موصل Microsoft Dynamics 365 عبر OData v4 و Azure AD OAuth2."""

    #: نقطة نهاية OAuth2 من Azure AD v2.0
    AZAD_TOKEN_URL_TEMPLATE: str = (
        "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    )

    #: النطاق (scope) الافتراضي لـ Dynamics 365 CE
    DEFAULT_SCOPE_TEMPLATE: str = "https://{resource_host}/.default"

    #: المسار الافتراضي لـ OData v4 في Dynamics 365 CE
    DEFAULT_API_PATH: str = "/api/data/v9.2"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "get_accounts",
        "get_contacts",
        "get_opportunities",
        "get_invoices",
    )

    #: خريطة الإجراءات إلى أسماء أجهزة Dynamics (entity sets)
    ENTITY_MAP: dict[str, str] = {
        "get_accounts": "accounts",
        "get_contacts": "contacts",
        "get_opportunities": "opportunities",
        "get_invoices": "invoices",
    }

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        self._tenant_id: str = self._get_secret("tenant_id", "")
        self._client_id: str = self._get_secret("client_id", "")
        self._client_secret: str = self._get_secret("client_secret", "")
        self._api_path: str = getattr(
            self.config, "api_path", self.DEFAULT_API_PATH,
        )
        # بناء token URL و scope بناءً على tenant و base_url
        self._token_url: str = self.AZAD_TOKEN_URL_TEMPLATE.format(
            tenant_id=self._tenant_id or "common",
        )
        # استخراج host من base_url لتحديد scope
        from urllib.parse import urlparse
        host = urlparse(self.config.base_url).hostname or ""
        self._scope: str = self._get_secret(
            "scope", self.DEFAULT_SCOPE_TEMPLATE.format(resource_host=host),
        )

    def _get_secret(self, key: str, default: str = "") -> str:
        """استرجاع سر من config.secrets بأمان."""
        secret = self.config.secrets.get(key)
        if secret is None:
            return default
        try:
            return secret.get_secret_value()
        except Exception:
            return default

    # ───────────────────────────────────────────────────────────────────
    #  Authentication
    # ───────────────────────────────────────────────────────────────────
    async def authenticate(self) -> None:
        """مصادقة OAuth2 client-credentials مع Azure AD لـ Dynamics 365.

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل المصادقة.
        """
        if not self._tenant_id or not self._client_id or not self._client_secret:
            raise ConnectorAuthenticationError(
                "Dynamics 365: tenant_id و client_id و client_secret مطلوبة للمصادقة",
            )

        async with httpx.AsyncClient(timeout=self.config.connect_timeout) as auth_client:
            try:
                response = await auth_client.post(
                    self._token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "scope": self._scope,
                    },
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
            except httpx.HTTPError as exc:
                raise ConnectorAuthenticationError(
                    f"Dynamics 365: فشل الاتصال بـ Azure AD: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"Dynamics 365: فشل المصادقة (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        token_payload = response.json()
        self._access_token = token_payload.get("access_token")
        if not self._access_token:
            raise ConnectorAuthenticationError(
                "Dynamics 365: لم يُرجع Azure AD access_token",
            )
        expires_in = int(token_payload.get("expires_in", 3600))
        self._token_expires_at = time.time() + max(60, expires_in - 60)

        if self._client is not None:
            self._client.headers.update({
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
                # ترويسة خاصة بـ Dynamics لمنع إرجاع بيانات متابعة الـ redirects
                "Prefer": 'odata.maxpagesize=500',
            })

        logger.info(
            "Dynamics 365: تم الحصول على access token (ينتهي خلال %ss)", expires_in,
        )

    async def _ensure_token(self) -> None:
        """تجديد access token عند انتهاء صلاحيته."""
        if self._access_token is None or time.time() >= self._token_expires_at:
            await self.authenticate()

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة Dynamics 365 عبر طلب WhoAmI endpoint الخفيف.

        يكشف Dynamics 365 endpoint 'WhoAmI' الذي يُرجع هوية المستخدم الحالي،
        وهو مثالي كفحص صحة (لا يتطلب استعلامات معقدة).
        """
        start = time.monotonic()
        try:
            await self._ensure_token()
            assert self._client is not None
            response = await self._client.get(f"{self._api_path}/WhoAmI")
            latency_ms = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                whoami = response.json()
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={
                        "http_status": 200,
                        "user_id": whoami.get("UserId"),
                        "organization_id": whoami.get("OrganizationId"),
                    },
                )
            if response.status_code == 401:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 401, "reason": "token_expired"},
                )
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=latency_ms,
                error=f"HTTP {response.status_code}: {response.text[:200]}",
            )
        except Exception as exc:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=(time.monotonic() - start) * 1000,
                error=str(exc),
            )

    # ───────────────────────────────────────────────────────────────────
    #  OData v4 Helpers
    # ───────────────────────────────────────────────────────────────────
    def _build_odata_params(
        self,
        top: int = 50,
        skip: int = 0,
        filter_expr: Optional[str] = None,
        select: Optional[list[str]] = None,
        order_by: Optional[str] = None,
        expand: Optional[str] = None,
        count: bool = True,
    ) -> dict[str, str]:
        """بناء بارامترات استعلام OData v4 الخاصة بـ Dynamics 365."""
        params: dict[str, str] = {
            "$top": str(max(1, min(top, 5000))),
            "$skip": str(max(0, skip)),
        }
        if count:
            params["$count"] = "true"
        if filter_expr:
            params["$filter"] = filter_expr
        if select:
            params["$select"] = ",".join(select)
        if order_by:
            params["$orderby"] = order_by
        if expand:
            params["$expand"] = expand
        return params

    async def _odata_get(
        self,
        entity_set: str,
        *,
        top: int = 50,
        skip: int = 0,
        filter_expr: Optional[str] = None,
        select: Optional[list[str]] = None,
        order_by: Optional[str] = None,
        expand: Optional[str] = None,
    ) -> dict[str, Any]:
        """تنفيذ GET على OData entity set في Dynamics 365.

        Raises:
            ConnectorError: عند فشل الطلب.
        """
        if self._client is None:
            raise ConnectorError(
                "Dynamics 365: العميل غير مهيأ — استدعِ connect() أولاً",
            )
        await self._ensure_token()
        params = self._build_odata_params(
            top=top, skip=skip, filter_expr=filter_expr,
            select=select, order_by=order_by, expand=expand,
        )
        try:
            response = await self._client.get(
                f"{self._api_path}/{entity_set}",
                params=params,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"Dynamics 365: فشل GET على {entity_set}: {exc}",
            ) from exc

        if response.status_code >= 400:
            # Dynamics يُرجع أخطاء OData بصيغة {"error": {"message": "..."}}
            try:
                error_body = response.json()
                err_msg = error_body.get("error", {}).get("message", response.text[:500])
            except ValueError:
                err_msg = response.text[:500]
            raise ConnectorError(
                f"Dynamics 365: خطأ OData في {entity_set} "
                f"(HTTP {response.status_code}): {err_msg}",
            )

        data = response.json()
        # OData v4 في Dynamics: {"@odata.context": ..., "@odata.count": n, "value": [...]}
        return {
            "entity_set": entity_set,
            "count": data.get("@odata.count", len(data.get("value", []))),
            "value": data.get("value", []),
            "next_link": data.get("@odata.nextLink"),
        }

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في كيانات Dynamics باستخدام $filter عبر contains.

        Args:
            query: نص البحث.
            **kwargs:
                entity_set (str): اسم الكيان (افتراضيًا 'accounts').
                fields (list[str]): الحقول التي يُبحث فيها (افتراضيًا
                    ['name', 'emailaddress1', 'telephone1']).
                top (int): عدد النتائج (افتراضيًا 50).
        """
        entity_set: str = kwargs.pop("entity_set", "accounts")
        fields: list[str] = kwargs.pop(
            "fields", ["name", "emailaddress1", "telephone1"],
        )
        top: int = int(kwargs.pop("top", 50))
        safe_query = query.replace("'", "''").strip()
        if not safe_query:
            return []
        sub_filters = [f"contains({f}, '{safe_query}')" for f in fields]
        filter_expr = " or ".join(sub_filters)
        result = await self._odata_get(
            entity_set, top=top, filter_expr=filter_expr,
        )
        return result["value"]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Dynamics 365.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        if action not in self.SUPPORTED_ACTIONS:
            raise ConnectorError(
                f"Dynamics 365: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(self.SUPPORTED_ACTIONS)}",
            )
        entity_set = self.ENTITY_MAP[action]
        return await self._odata_get(
            entity_set,
            top=int(kwargs.get("top", 50)),
            skip=int(kwargs.get("skip", 0)),
            filter_expr=kwargs.get("filter"),
            select=kwargs.get("select"),
            order_by=kwargs.get("order_by"),
            expand=kwargs.get("expand"),
        )

    # ───────────────────────────────────────────────────────────────────
    #  Metadata & Permissions
    # ───────────────────────────────────────────────────────────────────
    def metadata(self) -> dict[str, Any]:
        """إرجاع البيانات الوصفية للموصل."""
        return {
            "name": self.config.name,
            "display_name": self.config.display_name,
            "category": self.config.category,
            "version": self.config.version,
            "base_url": self.config.base_url,
            "auth_strategy": self.config.auth_strategy.value,
            "protocol": "OData v4",
            "api_version": "9.2",
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": False,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "entity_sets": list(self.ENTITY_MAP.values()),
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:dynamics_365:read",
            "crm:accounts:read",
            "crm:contacts:read",
        ]
