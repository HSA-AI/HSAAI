"""
موصل SAP SuccessFactors لمنصة HSAAI
=======================================
يتيح هذا الموصل الوصول إلى بيانات الموارد البشرية في SAP SuccessFactors
عبر بروتوكول OData v2 مع مصادقة OAuth2.

الإجراءات المدعومة:
    - get_employees          : جلب بيانات الموظفين
    - get_time_off_balances  : جلب أرصدة الإجازات
    - get_compensation       : جلب بيانات التعويضات/الرواتب
    - get_performance_reviews: جلب تقييمات الأداء

الاستخدام:
    cfg = ConnectorConfig(
        name="sap_successfactors",
        display_name="SAP SuccessFactors",
        category="HR",
        base_url="https://api.successfactors.eu",
        auth_strategy=AuthStrategy.OAUTH2_PASSWORD,
        secrets={
            "client_id": "...",
            "client_secret": "...",
            "username": "...",
            "password": "...",
            "company_id": "...",
        },
    )
    connector = SAPSuccessFactorsConnector(cfg)
    await connector.connect()
    employees = await connector.call("get_employees", top=100)
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


@connector("sap_successfactors", version="1.0.0", category="HR")
class SAPSuccessFactorsConnector(BaseConnector):
    """موصل SAP SuccessFactors عبر بروتوكول OData v2."""

    #: المسار الافتراضي لخدمة OData v2 في SuccessFactors
    DEFAULT_ODATA_PATH: str = "/odata/v2"

    #: إصدار API الافتراضي
    DEFAULT_API_VERSION: str = "v2"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "get_employees",
        "get_time_off_balances",
        "get_compensation",
        "get_performance_reviews",
    )

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        self._client_id: str = self._get_secret("client_id", "")
        self._client_secret: str = self._get_secret("client_secret", "")
        self._username: str = self._get_secret("username", "")
        self._password: str = self._get_secret("password", "")
        self._company_id: str = self._get_secret("company_id", "")
        self._service_path: str = getattr(
            self.config, "service_path", self.DEFAULT_ODATA_PATH,
        )
        # قد يكون token_url مستقلًا عن base_url (SFSF يستخدم /oauth/token)
        default_token_url = (
            f"{self.config.base_url.rstrip('/')}/oauth/token"
        )
        self._token_url: str = self._get_secret("token_url", default_token_url)

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
        """مصادقة OAuth2 مع SuccessFactors.

        يدعم الموصل مسارين:
            1. password grant (مع username/password/company_id) — الأكثر شيوعًا.
            2. client_credentials (مع client_id/client_secret فقط).

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل المصادقة.
        """
        if not self._client_id:
            raise ConnectorAuthenticationError(
                "SuccessFactors: client_id مطلوب للمصادقة",
            )

        # اختيار الـ grant المناسب
        if self._username and self._password:
            grant_type = "password"
            token_data: dict[str, str] = {
                "grant_type": grant_type,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "username": self._username,
                "password": self._password,
                "company_id": self._company_id,
            }
        else:
            grant_type = "client_credentials"
            token_data = {
                "grant_type": grant_type,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }

        async with httpx.AsyncClient(timeout=self.config.connect_timeout) as auth_client:
            try:
                response = await auth_client.post(
                    self._token_url,
                    data=token_data,
                    headers={"Accept": "application/json"},
                )
            except httpx.HTTPError as exc:
                raise ConnectorAuthenticationError(
                    f"SuccessFactors: فشل الاتصال بخادم التوكن: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"SuccessFactors: فشل المصادقة (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        token_payload = response.json()
        self._access_token = token_payload.get("access_token")
        if not self._access_token:
            raise ConnectorAuthenticationError(
                "SuccessFactors: لم يُرجع الخادم access_token",
            )
        expires_in = int(token_payload.get("expires_in", 3600))
        self._token_expires_at = time.time() + max(60, expires_in - 60)

        if self._client is not None:
            self._client.headers.update({
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
            })

        logger.info(
            "SuccessFactors: تم الحصول على access token عبر %s (ينتهي خلال %ss)",
            grant_type, expires_in,
        )

    async def _ensure_token(self) -> None:
        """تجديد access token عند انتهاء صلاحيته."""
        if self._access_token is None or time.time() >= self._token_expires_at:
            await self.authenticate()

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة SuccessFactors عبر طلب البيانات الوصفية لـ OData service.

        نستخدم endpoint الـ metadata الخاص بـ User entity لأنه خفيف وسريع.
        """
        start = time.monotonic()
        try:
            await self._ensure_token()
            assert self._client is not None
            response = await self._client.get(
                f"{self._service_path}/User",
                params={"$top": "1", "$format": "json"},
            )
            latency_ms = (time.monotonic() - start) * 1000
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
    #  OData v2 Helpers
    # ───────────────────────────────────────────────────────────────────
    def _build_odata_v2_params(
        self,
        top: int = 50,
        skip: int = 0,
        filter_expr: Optional[str] = None,
        select: Optional[list[str]] = None,
        order_by: Optional[str] = None,
        expand: Optional[str] = None,
        inlinecount: str = "allpages",
    ) -> dict[str, str]:
        """بناء بارامترات استعلام OData v2.

        ملاحظة: OData v2 يستخدم substringof بدل contains، و $inlinecount بدل $count.
        """
        params: dict[str, str] = {
            "$format": "json",
            "$top": str(max(1, min(top, 1000))),
            "$skip": str(max(0, skip)),
            "$inlinecount": inlinecount,
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
        entity: str,
        *,
        top: int = 50,
        skip: int = 0,
        filter_expr: Optional[str] = None,
        select: Optional[list[str]] = None,
        order_by: Optional[str] = None,
        expand: Optional[str] = None,
    ) -> dict[str, Any]:
        """تنفيذ طلب GET على OData v2 entity.

        Raises:
            ConnectorError: عند فشل الطلب.
        """
        if self._client is None:
            raise ConnectorError(
                "SuccessFactors: العميل غير مهيأ — استدعِ connect() أولاً",
            )
        await self._ensure_token()
        params = self._build_odata_v2_params(
            top=top, skip=skip, filter_expr=filter_expr,
            select=select, order_by=order_by, expand=expand,
        )
        try:
            response = await self._client.get(
                f"{self._service_path}/{entity}",
                params=params,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"SuccessFactors: فشل GET على {entity}: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"SuccessFactors: خطأ OData في {entity} "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )

        data = response.json()
        # OData v2 يعيد: {"d": {"results": [...]}}
        results = (
            data.get("d", {}).get("results", [])
            if isinstance(data, dict) else []
        )
        count: Any = data.get("d", {}).get("__count", len(results))
        try:
            count_int = int(count)
        except (TypeError, ValueError):
            count_int = len(results)
        return {
            "entity": entity,
            "count": count_int,
            "value": results,
            "next_link": data.get("d", {}).get("__next"),
        }

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في كيان الموظف (User) باستخدام substringof عبر حقول نصية.

        Args:
            query: نص البحث (free-text).
            **kwargs:
                entity (str): اسم الكيان (افتراضيًا 'User').
                fields (list[str]): الحقول التي يُبحث فيها (افتراضيًا
                    ['username', 'firstName', 'lastName', 'email']).
                top (int): عدد النتائج (افتراضيًا 50).

        Returns:
            قائمة بالموظفين المطابقين.
        """
        entity: str = kwargs.pop("entity", "User")
        fields: list[str] = kwargs.pop(
            "fields",
            ["username", "firstName", "lastName", "email"],
        )
        top: int = int(kwargs.pop("top", 50))
        safe_query = query.replace("'", "''").strip()
        if not safe_query:
            return []
        # OData v2: substringof('text', Field) returns true/false
        sub_filters = [f"substringof('{safe_query}', {f})" for f in fields]
        filter_expr = " or ".join(sub_filters)
        result = await self._odata_get(
            entity, top=top, filter_expr=filter_expr,
        )
        return result["value"]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على SuccessFactors.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "get_employees": self._get_employees,
            "get_time_off_balances": self._get_time_off_balances,
            "get_compensation": self._get_compensation,
            "get_performance_reviews": self._get_performance_reviews,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"SuccessFactors: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _get_employees(self, **kw: Any) -> dict[str, Any]:
        """جلب بيانات الموظفين من كيان User."""
        return await self._odata_get(
            "User",
            top=int(kw.get("top", 50)),
            skip=int(kw.get("skip", 0)),
            filter_expr=kw.get("filter"),
            select=[
                "userId", "username", "firstName", "lastName",
                "email", "status", "department", "division", "jobCode",
                "title", "location", "hireDate", "managerId",
            ],
            order_by=kw.get("order_by", "lastName asc, firstName asc"),
        )

    async def _get_time_off_balances(self, **kw: Any) -> dict[str, Any]:
        """جلب أرصدة الإجازات من كيان TimeAccount أو EmpTimeAccountBalance.

        يُفضل تمرير user_id لتحديد الموظف؛ وإلا فتُجلب الأرصدة العامة.
        """
        user_id = kw.get("user_id")
        entity = "EmpTimeAccountBalance"
        filter_parts: list[str] = []
        if user_id:
            filter_parts.append(f"userId eq '{user_id}'")
        time_account_type = kw.get("time_account_type")
        if time_account_type:
            filter_parts.append(f"timeAccountType eq '{time_account_type}'")
        filter_expr = " and ".join(filter_parts) if filter_parts else None
        return await self._odata_get(
            entity,
            top=int(kw.get("top", 50)),
            skip=int(kw.get("skip", 0)),
            filter_expr=filter_expr,
            select=["userId", "timeAccountType", "balance", "unit", "validFrom", "validTo"],
        )

    async def _get_compensation(self, **kw: Any) -> dict[str, Any]:
        """جلب بيانات التعويض/الراتب من كيان EmpCompensationNonRecurring."""
        user_id = kw.get("user_id")
        filter_parts: list[str] = []
        if user_id:
            filter_parts.append(f"userId eq '{user_id}'")
        filter_expr = " and ".join(filter_parts) if filter_parts else None
        return await self._odata_get(
            "EmpCompensationNonRecurring",
            top=int(kw.get("top", 50)),
            skip=int(kw.get("skip", 0)),
            filter_expr=filter_expr,
            select=[
                "userId", "payComponent", "payComponentValue",
                "currencyCode", "startDate", "endDate",
            ],
        )

    async def _get_performance_reviews(self, **kw: Any) -> dict[str, Any]:
        """جلب تقييمات الأداء من كيان PerformanceForm أو FormReview."""
        user_id = kw.get("user_id")
        filter_parts: list[str] = []
        if user_id:
            filter_parts.append(f"userId eq '{user_id}'")
        status = kw.get("status")
        if status:
            filter_parts.append(f"status eq '{status}'")
        filter_expr = " and ".join(filter_parts) if filter_parts else None
        return await self._odata_get(
            "PerformanceForm",
            top=int(kw.get("top", 50)),
            skip=int(kw.get("skip", 0)),
            filter_expr=filter_expr,
            select=[
                "formId", "userId", "formName", "status",
                "startDate", "dueDate", "completionDate",
                "rating", "previousRating",
            ],
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
            "protocol": "OData v2",
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": False,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "entities": [
                "User",
                "EmpTimeAccountBalance",
                "EmpCompensationNonRecurring",
                "PerformanceForm",
            ],
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل (HR Sensitive Data)."""
        return self.config.required_permissions or [
            "connector:sap_successfactors:read",
            "hr:employee:read",
            "hr:compensation:read",
        ]
