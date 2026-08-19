"""
موصل SAP S/4HANA لمنصة HSAAI
=================================
يتيح هذا الموصل الوصول إلى بيانات SAP S/4HANA عبر بروتوكول OData v4
مع مصادقة OAuth2 (client-credentials) وإدارة CSRF tokens للعمليات الكتابية.

الإجراءات المدعومة:
    - get_sales_orders        : جلب أوامر المبيعات
    - get_purchase_orders     : جلب أوامر الشراء
    - get_materials           : جلب المواد/المنتجات
    - get_business_partners   : جلب شركاء الأعمال
    - post_journal_entry      : ترحيل قيد محاسبي

الاستخدام:
    cfg = ConnectorConfig(
        name="sap_s4hana",
        display_name="SAP S/4HANA",
        category="ERP",
        base_url="https://my-s4.sap.com",
        auth_strategy=AuthStrategy.OAUTH2_CLIENT_CREDENTIALS,
        secrets={
            "client_id": "...",
            "client_secret": "...",
            "token_url": "https://my-s4.sap.com/sap/bc/sec/oauth2/token",
        },
    )
    connector = SAPS4HANAConnector(cfg)
    await connector.connect()
    orders = await connector.call("get_sales_orders", top=50)
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


@connector("sap_s4hana", version="1.0.0", category="ERP")
class SAPS4HANAConnector(BaseConnector):
    """موصل SAP S/4HANA عبر بروتوكول OData v4 مع OAuth2 و CSRF tokens."""

    #: المسار الافتراضي لخدمات OData v4 في SAP
    DEFAULT_ODATA_PATH: str = "/sap/opu/odata4/sap"

    #: قائمة الإجراءات المدعومة (تُستخدم في metadata والتحقق)
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "get_sales_orders",
        "get_purchase_orders",
        "get_materials",
        "get_business_partners",
        "post_journal_entry",
    )

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._csrf_token: Optional[str] = None

        # بيانات الاعتماد تُستخرج من config.secrets (SecretStr)
        self._client_id: str = self._get_secret("client_id", "")
        self._client_secret: str = self._get_secret("client_secret", "")
        default_token_url = (
            f"{self.config.base_url.rstrip('/')}/sap/bc/sec/oauth2/token"
        )
        self._token_url: str = self._get_secret("token_url", default_token_url)
        self._service_path: str = getattr(
            self.config, "service_path", self.DEFAULT_ODATA_PATH,
        )

    def _get_secret(self, key: str, default: str = "") -> str:
        """استرجاع سر من config.secrets بأمان دون تسجيله في السجلات."""
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
        """مصادقة OAuth2 (client-credentials) وجلب access token من خادم SAP.

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل المصادقة.
        """
        if not self._client_id or not self._client_secret:
            raise ConnectorAuthenticationError(
                "SAP S/4HANA: client_id و client_secret مطلوبان للمصادقة",
            )

        async with httpx.AsyncClient(timeout=self.config.connect_timeout) as auth_client:
            try:
                response = await auth_client.post(
                    self._token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                    headers={"Accept": "application/json"},
                )
            except httpx.HTTPError as exc:
                raise ConnectorAuthenticationError(
                    f"SAP S/4HANA: فشل الاتصال بخادم التوكن: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"SAP S/4HANA: فشل المصادقة (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        token_data = response.json()
        self._access_token = token_data.get("access_token")
        if not self._access_token:
            raise ConnectorAuthenticationError(
                "SAP S/4HANA: لم يُرجع الخادم access_token",
            )

        expires_in = int(token_data.get("expires_in", 3600))
        # هامش أمان 60 ثانية لتجنب استخدام توكن على وشك الانتهاء
        self._token_expires_at = time.time() + max(60, expires_in - 60)

        # تثبيت ترويسات المصادقة على عميل httpx الرئيسي
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }
        sap_client = getattr(self.config, "sap_client", None)
        if sap_client:
            headers["sap-client"] = str(sap_client)
        if self._client is not None:
            self._client.headers.update(headers)

        # إعادة ضبط CSRF token عند تجديد التوكن
        self._csrf_token = None

        logger.info(
            "SAP S/4HANA: تم الحصول على access token (ينتهي خلال %ss)", expires_in,
        )

    async def _ensure_token(self) -> None:
        """تجديد access token تلقائيًا عند اقتراب انتهاء صلاحيته."""
        if self._access_token is None or time.time() >= self._token_expires_at:
            await self.authenticate()

    async def _fetch_csrf_token(self) -> str:
        """جلب CSRF token عبر طلب HEAD مع ترويسة X-CSRF-Token: Fetch.

        ضروري لكل عمليات POST/PATCH/DELETE في SAP OData.

        Returns:
            قيمة CSRF token.

        Raises:
            ConnectorError: إذا لم يُرجع الخادم التوكِن.
        """
        if self._client is None:
            raise ConnectorError("SAP S/4HANA: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()
        try:
            response = await self._client.head(
                f"{self._service_path}/",
                headers={"X-CSRF-Token": "Fetch"},
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"SAP S/4HANA: فشل جلب CSRF token: {exc}",
            ) from exc

        token = response.headers.get("x-csrf-token")
        if not token:
            raise ConnectorError(
                "SAP S/4HANA: لم يُرجع الخادم ترويسة X-CSRF-Token",
            )
        self._csrf_token = token
        self._client.headers.update({"X-CSRF-Token": token})
        return token

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة SAP S/4HANA عبر طلب البيانات الوصفية لجذر خدمة OData.

        Returns:
            HealthResult مع حالة الخدمة وزمن الاستجابة.
        """
        start = time.monotonic()
        try:
            await self._ensure_token()
            assert self._client is not None  # for type checker
            response = await self._client.get(
                f"{self._service_path}/",
                params={"$format": "json"},
            )
            latency_ms = (time.monotonic() - start) * 1000
            # 200 = سليم، 401 = التوكن انتهى لكن الخدمة متاحة (degraded)
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
    #  OData Helpers
    # ───────────────────────────────────────────────────────────────────
    def _build_odata_params(
        self,
        top: int = 50,
        skip: int = 0,
        filter_expr: Optional[str] = None,
        select: Optional[list[str]] = None,
        order_by: Optional[str] = None,
        expand: Optional[str] = None,
    ) -> dict[str, str]:
        """بناء بارامترات استعلام OData v4 ($filter, $select, $top, ...)."""
        params: dict[str, str] = {
            "$format": "json",
            "$top": str(max(1, min(top, 5000))),
            "$skip": str(max(0, skip)),
        }
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
        """تنفيذ طلب GET على OData entity set وإرجاع النتائج بصورة موحدة.

        Raises:
            ConnectorError: عند فشل الطلب أو إرجاع الخادم لخطأ.
        """
        if self._client is None:
            raise ConnectorError("SAP S/4HANA: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()
        params = self._build_odata_params(
            top=top, skip=skip, filter_expr=filter_expr,
            select=select, order_by=order_by, expand=expand,
        )
        try:
            response = await self._client.get(
                f"{self._service_path}/{entity_set}",
                params=params,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"SAP S/4HANA: فشل GET على {entity_set}: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"SAP S/4HANA: خطأ OData في {entity_set} "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )

        data = response.json()
        # OData v4 يعيد: {"@odata.context": ..., "@odata.count": n, "value": [...]}
        return {
            "entity_set": entity_set,
            "count": data.get("@odata.count", len(data.get("value", []))),
            "value": data.get("value", []),
            "next_link": data.get("@odata.nextLink"),
        }

    async def _odata_post(
        self, entity_set: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        """تنفيذ طلب POST على OData entity set مع CSRF token.

        Raises:
            ConnectorError: عند فشل الإنشاء.
        """
        if self._client is None:
            raise ConnectorError("SAP S/4HANA: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()
        if not self._csrf_token:
            await self._fetch_csrf_token()
        try:
            response = await self._client.post(
                f"{self._service_path}/{entity_set}",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-CSRF-Token": self._csrf_token or "",
                },
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"SAP S/4HANA: فشل POST على {entity_set}: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"SAP S/4HANA: خطأ في إنشاء {entity_set} "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )
        if response.content:
            try:
                return response.json()
            except ValueError:
                return {"status": "created", "raw": response.text}
        return {"status": "created"}

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في OData entities باستخدام $filter عبر حقول نصية.

        Args:
            query: نص البحث (free-text).
            **kwargs:
                entity_set (str): اسم الـ entity set (افتراضيًا 'A_SalesOrder').
                fields (list[str]): الحقول التي يُبحث فيها (افتراضيًا
                    ['SalesOrder', 'SoldToParty']).
                top (int): عدد النتائج (افتراضيًا 50).

        Returns:
            قائمة بالسجلات المطابقة.
        """
        entity_set: str = kwargs.pop("entity_set", "A_SalesOrder")
        fields: list[str] = kwargs.pop(
            "fields", ["SalesOrder", "SoldToParty"],
        )
        top: int = int(kwargs.pop("top", 50))
        # تنظيف النص لمنع حقن OData
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
        """تنفيذ إجراء مُسماً على SAP S/4HANA.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "get_sales_orders": self._get_sales_orders,
            "get_purchase_orders": self._get_purchase_orders,
            "get_materials": self._get_materials,
            "get_business_partners": self._get_business_partners,
            "post_journal_entry": self._post_journal_entry,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"SAP S/4HANA: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _get_sales_orders(self, **kw: Any) -> dict[str, Any]:
        """جلب أوامر المبيعات من A_SalesOrder."""
        return await self._odata_get(
            "A_SalesOrder",
            top=int(kw.get("top", 50)),
            skip=int(kw.get("skip", 0)),
            filter_expr=kw.get("filter"),
            order_by=kw.get("order_by", "SalesOrder desc"),
        )

    async def _get_purchase_orders(self, **kw: Any) -> dict[str, Any]:
        """جلب أوامر الشراء من A_PurchaseOrder."""
        return await self._odata_get(
            "A_PurchaseOrder",
            top=int(kw.get("top", 50)),
            skip=int(kw.get("skip", 0)),
            filter_expr=kw.get("filter"),
        )

    async def _get_materials(self, **kw: Any) -> dict[str, Any]:
        """جلب المواد/المنتجات من A_Product."""
        return await self._odata_get(
            "A_Product",
            top=int(kw.get("top", 50)),
            skip=int(kw.get("skip", 0)),
            filter_expr=kw.get("filter"),
            select=["Product", "ProductType", "BaseUnit", "ProductGroup", "CreationDate"],
        )

    async def _get_business_partners(self, **kw: Any) -> dict[str, Any]:
        """جلب شركاء الأعمال من A_BusinessPartner."""
        return await self._odata_get(
            "A_BusinessPartner",
            top=int(kw.get("top", 50)),
            skip=int(kw.get("skip", 0)),
            filter_expr=kw.get("filter"),
            select=["BusinessPartner", "BusinessPartnerFullName", "CityName", "Country"],
        )

    async def _post_journal_entry(self, **kw: Any) -> dict[str, Any]:
        """ترحيل قيد محاسبي إلى A_JournalEntry.

        Args (via kwargs):
            payload (dict): حمولة القيد المتوافقة مع SAP API_JournalEntry.

        Raises:
            ConnectorError: عند فقدان حقول إلزامية.
        """
        payload: dict[str, Any] = kw.get("payload") or kw
        required_fields = {"CompanyCode", "DocumentDate", "PostingDate", "DocumentType"}
        missing = required_fields - set(payload.keys())
        if missing:
            raise ConnectorError(
                f"SAP S/4HANA: حقول إلزامية مفقودة في قيد اليومية: {missing}",
            )
        return await self._odata_post("A_JournalEntry", payload)

    # ───────────────────────────────────────────────────────────────────
    #  Metadata & Permissions
    # ───────────────────────────────────────────────────────────────────
    def metadata(self) -> dict[str, Any]:
        """إرجاع البيانات الوصفية للموصل (اسم، إصدار، إجراءات، قدرات)."""
        return {
            "name": self.config.name,
            "display_name": self.config.display_name,
            "category": self.config.category,
            "version": self.config.version,
            "base_url": self.config.base_url,
            "auth_strategy": self.config.auth_strategy.value,
            "protocol": "OData v4",
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "entity_sets": [
                "A_SalesOrder",
                "A_PurchaseOrder",
                "A_Product",
                "A_BusinessPartner",
                "A_JournalEntry",
            ],
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل (RBAC)."""
        return self.config.required_permissions or [
            "connector:sap_s4hana:read",
            "connector:sap_s4hana:write",
        ]
