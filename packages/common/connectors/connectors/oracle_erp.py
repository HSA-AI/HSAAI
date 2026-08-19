"""
موصل Oracle ERP Cloud لمنصة HSAAI
=====================================
يتيح هذا الموصل الوصول إلى Oracle ERP Cloud عبر واجهة REST API
مع مصادقة Basic Auth (username + password). يدمج الموصل قاطع الدائرة
(Circuit Breaker) وسياسة إعادة المحاولة الموروثة من BaseConnector،
إضافة إلى معالجة خاصة لأخطاء Oracle الشائعة (429, 503).

الإجراءات المدعومة:
    - get_invoices     : جلب الفواتير (Receivables)
    - get_payables     : جلب المستحقات (Payables)
    - get_receivables  : جلب الذمم المدينة
    - get_fixed_assets : جلب الأصول الثابتة

الاستخدام:
    cfg = ConnectorConfig(
        name="oracle_erp",
        display_name="Oracle ERP Cloud",
        category="ERP",
        base_url="https://fa-xxx.oraclecloud.com",
        auth_strategy=AuthStrategy.BASIC,
        secrets={
            "username": "...",
            "password": "...",
        },
    )
    connector = OracleERPConnector(cfg)
    await connector.connect()
    invoices = await connector.call("get_invoices", limit=100)
"""
from __future__ import annotations

import base64
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


@connector("oracle_erp", version="1.0.0", category="ERP")
class OracleERPConnector(BaseConnector):
    """موصل Oracle ERP Cloud عبر REST API و Basic Auth."""

    #: مسار REST API الافتراضي
    DEFAULT_REST_PATH: str = "/fscmRestApi/resources/11.13.18.05"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "get_invoices",
        "get_payables",
        "get_receivables",
        "get_fixed_assets",
    )

    #: خريطة الإجراءات إلى موارد REST
    RESOURCE_MAP: dict[str, str] = {
        "get_invoices": "receivablesInvoices",
        "get_payables": "invoices",
        "get_receivables": "receivablesInvoices",
        "get_fixed_assets": "assetBooks",
    }

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._username: str = self._get_secret("username", "")
        self._password: str = self._get_secret("password", "")
        self._rest_path: str = getattr(
            self.config, "rest_path", self.DEFAULT_REST_PATH,
        )
        self._basic_auth_header: Optional[str] = None

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
        """تجهيز ترويسة Basic Auth لاستخدامها في كل طلب.

        يتحقق من وجود بيانات الاعتماد ويبني ترويسة Authorization.
        لا يحتاج Oracle ERP Cloud إلى تبادل توكنات لمصادقة Basic.

        Raises:
            ConnectorAuthenticationError: عند فقدان username أو password.
        """
        if not self._username or not self._password:
            raise ConnectorAuthenticationError(
                "Oracle ERP: username و password مطلوبان لمصادقة Basic",
            )

        # بناء ترويسة Basic Auth: base64(username:password)
        credentials = f"{self._username}:{self._password}".encode("utf-8")
        encoded = base64.b64encode(credentials).decode("ascii")
        self._basic_auth_header = f"Basic {encoded}"

        if self._client is not None:
            self._client.headers.update({
                "Authorization": self._basic_auth_header,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "REST-Framework-Version": getattr(
                    self.config, "rest_framework_version", "11",
                ),
            })

        logger.info("Oracle ERP: تم تجهيز ترويسة Basic Auth بنجاح")

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة Oracle ERP عبر طلب وصف الخدمة (service description).

        Oracle ERP يكشف endpoint الموارد الجذري كبديل صحي خفيف.
        """
        start = time.monotonic()
        try:
            if self._client is None:
                raise ConnectorError("Oracle ERP: العميل غير مهيأ")
            response = await self._client.get(
                f"{self._rest_path}/",
                params={"limit": "1"},
            )
            latency_ms = (time.monotonic() - start) * 1000
            # 200 = سليم، 401 = اعتمادات سيئة، لكن الخدمة متاحة
            if response.status_code == 200:
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 200},
                )
            if response.status_code == 401:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 401, "reason": "invalid_credentials"},
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
    #  REST Helpers (with explicit retry + circuit breaker integration)
    # ───────────────────────────────────────────────────────────────────
    async def _rest_get(
        self,
        resource: str,
        *,
        limit: int = 100,
        offset: int = 0,
        q_param: Optional[str] = None,
        fields: Optional[list[str]] = None,
        order_by: Optional[str] = None,
        expand: Optional[str] = None,
    ) -> dict[str, Any]:
        """تنفيذ GET على مورد REST مع إعادة محاولة صريحة.

        تستخدم هذه الدالة سياسة إعادة المحاولة الموروثة (self._retry_policy)
        للتعامل مع 429/503 من Oracle بشكل صريح، إضافة إلى قاطع الدائرة
        الموروث من BaseConnector.

        Raises:
            ConnectorError: عند استنفاد المحاولات أو فشل دائم.
        """
        if self._client is None:
            raise ConnectorError("Oracle ERP: العميل غير مهيأ — استدعِ connect() أولاً")
        if self._basic_auth_header is None:
            await self.authenticate()

        params: dict[str, str] = {
            "limit": str(max(1, min(limit, 500))),
            "offset": str(max(0, offset)),
        }
        if q_param:
            params["q"] = q_param
        if fields:
            params["fields"] = ",".join(fields)
        if order_by:
            params["orderBy"] = order_by
        if expand:
            params["expand"] = expand

        url = f"{self._rest_path}/{resource}"
        last_error: Optional[Exception] = None
        for attempt in range(self._retry_policy.max_retries + 1):
            try:
                response = await self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self._retry_policy.max_retries:
                    delay = self._retry_policy.delay(attempt)
                    logger.warning(
                        "Oracle ERP: محاولة %d فشلت في GET %s: %s. إعادة المحاولة خلال %.2fs",
                        attempt + 1, resource, exc, delay,
                    )
                    await self._sleep(delay)
                    continue
                raise ConnectorError(
                    f"Oracle ERP: فشل GET على {resource} بعد {attempt + 1} محاولات: {exc}",
                ) from exc

            # معالجة خاصة للأخطاء القابلة لإعادة المحاولة
            if response.status_code in self._retry_policy.retry_on_status:
                if attempt < self._retry_policy.max_retries:
                    delay = self._retry_policy.delay(attempt)
                    logger.warning(
                        "Oracle ERP: GET %s أعاد HTTP %d. إعادة المحاولة خلال %.2fs",
                        resource, response.status_code, delay,
                    )
                    await self._sleep(delay)
                    continue
                raise ConnectorError(
                    f"Oracle ERP: {resource} أعاد HTTP {response.status_code} بعد "
                    f"{attempt + 1} محاولات: {response.text[:500]}",
                )

            if response.status_code >= 400:
                raise ConnectorError(
                    f"Oracle ERP: خطأ في {resource} (HTTP {response.status_code}): "
                    f"{response.text[:500]}",
                )

            data = response.json()
            # Oracle REST يعيد: {"items": [...], "count": n, "hasMore": bool, "links": [...]}
            return {
                "resource": resource,
                "count": data.get("count", len(data.get("items", []))),
                "value": data.get("items", []),
                "has_more": data.get("hasMore", False),
                "links": data.get("links", []),
                "total_results": data.get("totalResults"),
            }

        # لن يصل التنفيذ هنا نظريًا، لكن للأمان
        raise ConnectorError(
            f"Oracle ERP: فشل GET على {resource} - استنفدت المحاولات: {last_error}",
        )

    @staticmethod
    async def _sleep(seconds: float) -> None:
        """غلاف asyncio.sleep لسهلة الـ mock في الاختبارات."""
        import asyncio
        await asyncio.sleep(seconds)

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في موارد Oracle ERP باستخدام بارامتر q (FQL).

        يستخدم Oracle صيغة مخصصة للبحث: q=InvoiceNumber='INV-001'
        أو q=InvoiceNumber contains 'INV'.

        Args:
            query: استعلام بحث (يُمرر كما هو إلى بارامتر q إذا بدأ بـ q=،
                وإلا يُحول إلى contains على حقل 'Description' الافتراضي).
            **kwargs:
                resource (str): المورد المستهدف (افتراضيًا 'receivablesInvoices').
                search_field (str): الحقل المستخدم للبحث النصي (افتراضيًا 'Description').
                limit (int): عدد النتائج (افتراضيًا 50).
        """
        resource: str = kwargs.pop("resource", "receivablesInvoices")
        search_field: str = kwargs.pop("search_field", "Description")
        limit: int = int(kwargs.pop("limit", 50))

        safe_query = query.replace("'", "\\'").strip()
        if not safe_query:
            return []
        # إذا كان الاستعلام يبدأ بـ q= فإنه يُمرر كما هو (FQL متقدم)
        if safe_query.lower().startswith("q="):
            q_param = safe_query[2:]
        else:
            q_param = f"{search_field} contains '{safe_query}'"

        result = await self._rest_get(resource, limit=limit, q_param=q_param)
        return result["value"]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Oracle ERP.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        if action not in self.SUPPORTED_ACTIONS:
            raise ConnectorError(
                f"Oracle ERP: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(self.SUPPORTED_ACTIONS)}",
            )
        resource = self.RESOURCE_MAP[action]
        return await self._rest_get(
            resource,
            limit=int(kwargs.get("limit", kwargs.get("top", 100))),
            offset=int(kwargs.get("offset", kwargs.get("skip", 0))),
            q_param=kwargs.get("q") or kwargs.get("filter"),
            fields=kwargs.get("fields"),
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
            "protocol": "REST (Fusion REST API)",
            "rest_framework_version": getattr(
                self.config, "rest_framework_version", "11",
            ),
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": False,
                "circuit_breaker": True,
                "retry": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "resources": list(set(self.RESOURCE_MAP.values())),
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:oracle_erp:read",
            "fin:invoices:read",
            "fin:payables:read",
        ]
