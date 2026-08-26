"""
موصل Oracle HCM Cloud لمنصة HSAAI
====================================
يتيح هذا الموصل الوصول إلى Oracle HCM Cloud عبر واجهة REST API
مع مصادقة OAuth2 (client-credentials). يغطي الموصل الكيانات الأساسية
لإدارة الموارد البشرية: الموظفون، التعيينات، الرواتب، وبطاقات الوقت.

نقطة النهاية الأساسية:
    {base_url}/hcmRestApi/resources/11.13.18.05/

الإجراءات المدعومة:
    - get_employees    : جلب قائمة الموظفين (Workers)
    - get_assignments  : جلب تعيينات موظف
    - get_payrolls     : جلب سجلات الرواتب
    - get_time_cards   : جلب بطاقات الوقت

search() يبحث في Workers عبر الحقول النصية (PersonNumber, DisplayName, Email).

الاستخدام:
    cfg = ConnectorConfig(
        name="oracle_hcm",
        display_name="Oracle HCM Cloud",
        category="HR",
        base_url="https://fa-xxx.oraclecloud.com",
        auth_strategy=AuthStrategy.OAUTH2_CLIENT_CREDENTIALS,
        secrets={
            "client_id": "...",
            "client_secret": "...",
            "token_url": "https://fa-xxx.oraclecloud.com/hcmRestApi/oauth/token",
        },
    )
    connector = OracleHCMConnector(cfg)
    await connector.connect()
    employees = await connector.call("get_employees", limit=100)
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


@connector("oracle_hcm", version="1.0.0", category="HR")
class OracleHCMConnector(BaseConnector):
    """موصل Oracle HCM Cloud عبر REST API و OAuth2 client-credentials."""

    #: مسار REST API الافتراضي لإصدار HCM 11.13.18.05
    DEFAULT_REST_PATH: str = "/hcmRestApi/resources/11.13.18.05"

    #: الحد الأقصى لعدد السجلات المُسترجَعة في طلب واحد
    MAX_LIMIT: int = 1000

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "get_employees",
        "get_assignments",
        "get_payrolls",
        "get_time_cards",
    )

    #: خريطة الإجراءات إلى موارد REST في HCM
    RESOURCE_MAP: dict[str, str] = {
        "get_employees": "workers",
        "get_assignments": "assignments",
        "get_payrolls": "payrollRecords",
        "get_time_cards": "timeCards",
    }

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        self._client_id: str = self._get_secret("client_id", "")
        self._client_secret: str = self._get_secret("client_secret", "")
        default_token_url = (
            f"{self.config.base_url.rstrip('/')}/hcmRestApi/oauth/token"
        )
        self._token_url: str = self._get_secret("token_url", default_token_url)
        self._rest_path: str = getattr(
            self.config, "rest_path", self.DEFAULT_REST_PATH,
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
        """مصادقة OAuth2 (client-credentials) مع Oracle HCM Cloud.

        يستخدم نقطة نهاية /hcmRestApi/oauth/token مع grant_type=client_credentials
        والمصادقة Basic عبر client_id:client_secret.

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل المصادقة.
        """
        if not self._client_id or not self._client_secret:
            raise ConnectorAuthenticationError(
                "Oracle HCM: client_id و client_secret مطلوبان للمصادقة OAuth2",
            )

        # المصادقة عبر Basic Auth (client_id:client_secret)
        auth_pair = (self._client_id, self._client_secret)
        async with httpx.AsyncClient(timeout=self.config.connect_timeout) as auth_client:
            try:
                response = await auth_client.post(
                    self._token_url,
                    data={"grant_type": "client_credentials"},
                    auth=auth_pair,
                    headers={"Accept": "application/json"},
                )
            except httpx.HTTPError as exc:
                raise ConnectorAuthenticationError(
                    f"Oracle HCM: فشل الاتصال بخادم التوكن: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"Oracle HCM: فشل المصادقة (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        token_data = response.json()
        self._access_token = token_data.get("access_token")
        if not self._access_token:
            raise ConnectorAuthenticationError(
                "Oracle HCM: لم يُرجع الخادم access_token",
            )

        expires_in = int(token_data.get("expires_in", 3600))
        # هامش أمان 60 ثانية
        self._token_expires_at = time.time() + max(60, expires_in - 60)

        if self._client is not None:
            self._client.headers.update({
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
            })

        logger.info(
            "Oracle HCM: تم الحصول على access token (ينتهي خلال %ss)", expires_in,
        )

    async def _ensure_token(self) -> None:
        """تجديد access token تلقائيًا عند اقتراب انتهاء صلاحيته."""
        if self._access_token is None or time.time() >= self._token_expires_at:
            await self.authenticate()

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة Oracle HCM عبر طلب GET على جذر واجهة REST.

        Returns:
            HealthResult مع حالة الخدمة وزمن الاستجابة.
        """
        start = time.monotonic()
        try:
            await self._ensure_token()
            if self._client is None:
                raise ConnectorError("Oracle HCM: العميل غير مهيأ — استدعِ connect() أولاً")
            response = await self._client.get(
                f"{self._rest_path}/",
                params={"limit": "1"},
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
    #  REST Helpers
    # ───────────────────────────────────────────────────────────────────
    async def _rest_get(
        self,
        resource: str,
        *,
        limit: int = 100,
        offset: int = 0,
        q: Optional[str] = None,
        fields: Optional[list[str]] = None,
        expand: Optional[str] = None,
        order_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """تنفيذ طلب GET على مورد REST في Oracle HCM.

        Args:
            resource: اسم المورد (مثل 'workers').
            limit: عدد السجلات (1..1000).
            offset: إزاحة الصفحات (pagination).
            q: صيغة بحث Oracle FND:q (مثل "PersonNumber='1001'").
            fields: قائمة الحقول (onlyData=true يُرجع بيانات فقط دون روابط).
            expand: مورد فرعي للتوسيع (مثل 'assignments').
            order_by: حقل الترتيب (مثل 'PersonNumber:asc').

        Returns:
            قاموس موحد: {resource, count, items, has_more, total_results, next_link}.

        Raises:
            ConnectorError: عند فشل الطلب أو إرجاع الخادم لخطأ.
        """
        if self._client is None:
            raise ConnectorError("Oracle HCM: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()

        params: dict[str, str] = {
            "limit": str(max(1, min(limit, self.MAX_LIMIT))),
            "offset": str(max(0, offset)),
        }
        if q:
            params["q"] = q
        if fields:
            params["fields"] = ",".join(fields)
            params["onlyData"] = "true"
        if expand:
            params["expand"] = expand
        if order_by:
            params["orderBy"] = order_by

        try:
            response = await self._client.get(
                f"{self._rest_path}/{resource}",
                params=params,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"Oracle HCM: فشل GET على {resource}: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"Oracle HCM: خطأ REST في {resource} "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )

        data = response.json()
        # Oracle HCM REST يعيد: {"items": [...], "count": n, "hasMore": bool, ...}
        items = data.get("items", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        return {
            "resource": resource,
            "count": data.get("count", len(items)) if isinstance(data, dict) else len(items),
            "items": items,
            "has_more": data.get("hasMore", False) if isinstance(data, dict) else False,
            "total_results": data.get("totalResults") if isinstance(data, dict) else None,
            "next_link": data.get("links", [{}])[0].get("href")
            if isinstance(data, dict) and data.get("links") else None,
        }

    async def _rest_get_by_id(
        self, resource: str, record_id: str,
        *, expand: Optional[str] = None,
    ) -> dict[str, Any]:
        """جلب سجل واحد من مورد REST عبر معرفه.

        Args:
            resource: اسم المورد (مثل 'workers').
            record_id: معرف السجل (مثل '1001' لـ PersonNumber).
            expand: مورد فرعي للتوسيع.

        Returns:
            قاموس السجل.

        Raises:
            ConnectorError: عند فشل الطلب.
        """
        if self._client is None:
            raise ConnectorError("Oracle HCM: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()

        params: dict[str, str] = {}
        if expand:
            params["expand"] = expand

        try:
            response = await self._client.get(
                f"{self._rest_path}/{resource}/{record_id}",
                params=params,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"Oracle HCM: فشل GET على {resource}/{record_id}: {exc}",
            ) from exc

        if response.status_code == 404:
            raise ConnectorError(
                f"Oracle HCM: السجل {resource}/{record_id} غير موجود",
            )
        if response.status_code >= 400:
            raise ConnectorError(
                f"Oracle HCM: خطأ REST في {resource}/{record_id} "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )

        return response.json()

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في Workers عبر صيغة Oracle FND:q.

        يطابق النص ضد PersonNumber و DisplayName و Email (إن توفّر).
        يستخدم عامل OR في صيغة Oracle: q=PersonNumber='X' OR DisplayName like '%X%'

        Args:
            query: نص البحث (free-text).
            **kwargs:
                resource (str): اسم المورد (افتراضيًا 'workers').
                fields (list[str]): الحقول المُسترجَعة.
                limit (int): عدد النتائج (افتراضيًا 50).

        Returns:
            قائمة بالسجلات المطابقة.
        """
        resource: str = kwargs.pop("resource", "workers")
        fields: list[str] = kwargs.pop(
            "fields", ["PersonId", "PersonNumber", "DisplayName", "FirstName", "LastName"],
        )
        limit: int = int(kwargs.pop("limit", 50))

        # تنظيف النص لمنع حقن صيغة Oracle q (إزالة علامات الاقتباس المفردة)
        safe_query = query.replace("'", "''").strip()
        if not safe_query:
            return []

        # بناء صيغة q: تطابق تام في PersonNumber أو تطابق جزئي في DisplayName
        q_expr = (
            f"PersonNumber='{safe_query}' OR "
            f"DisplayName like '*{safe_query}*' OR "
            f"correlationPersonNumber='{safe_query}'"
        )
        result = await self._rest_get(
            resource, limit=limit, q=q_expr, fields=fields,
        )
        return result["items"]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Oracle HCM.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "get_employees": self._get_employees,
            "get_assignments": self._get_assignments,
            "get_payrolls": self._get_payrolls,
            "get_time_cards": self._get_time_cards,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"Oracle HCM: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _get_employees(self, **kw: Any) -> dict[str, Any]:
        """جلب قائمة الموظفين (Workers) من Oracle HCM.

        Args (via kwargs):
            limit (int): عدد السجلات (افتراضيًا 100).
            offset (int): إزاحة الصفحات.
            fields (list[str]): الحقول المُسترجَعة.
            order_by (str): حقل الترتيب.
        """
        return await self._rest_get(
            "workers",
            limit=int(kw.get("limit", 100)),
            offset=int(kw.get("offset", 0)),
            fields=kw.get("fields") or [
                "PersonId", "PersonNumber", "DisplayName",
                "FirstName", "LastName", "DateOfBirth", "Gender",
            ],
            order_by=kw.get("order_by", "PersonNumber:asc"),
        )

    async def _get_assignments(self, **kw: Any) -> dict[str, Any]:
        """جلب تعيينات موظف (Assignments) عبر PersonNumber أو AssignmentId.

        Args (via kwargs):
            person_number (str): معرف الشخص (إلزامي).
            limit (int): عدد السجلات.
            expand (str): مورد فرعي للتوسيع.

        Raises:
            ConnectorError: عند فقدان person_number.
        """
        person_number: Optional[str] = kw.get("person_number")
        if not person_number:
            raise ConnectorError("Oracle HCM: 'person_number' إلزامي لإجراء get_assignments")
        # جلب تعيينات الشخص عبر expand على مورد workers
        return await self._rest_get(
            "workers",
            limit=int(kw.get("limit", 50)),
            q=f"PersonNumber='{person_number.replace(chr(39), chr(39)*2)}'",
            expand=kw.get("expand", "assignments"),
            fields=["PersonId", "PersonNumber", "DisplayName"],
        )

    async def _get_payrolls(self, **kw: Any) -> dict[str, Any]:
        """جلب سجلات الرواتب (Payroll Records) من Oracle HCM.

        Args (via kwargs):
            limit (int): عدد السجلات (افتراضيًا 100).
            offset (int): إزاحة الصفحات.
            person_number (str): تصفية حسب الشخص (اختياري).
            from_date (str): تاريخ بداية التصفية (YYYY-MM-DD).
            to_date (str): تاريخ نهاية التصفية.
        """
        limit = int(kw.get("limit", 100))
        offset = int(kw.get("offset", 0))
        person_number = kw.get("person_number")
        from_date = kw.get("from_date")
        to_date = kw.get("to_date")

        q_parts: list[str] = []
        if person_number:
            q_parts.append(
                f"PersonNumber='{person_number.replace(chr(39), chr(39)*2)}'",
            )
        if from_date and to_date:
            q_parts.append(
                f"payrollDate between '{from_date}' and '{to_date}'",
            )
        elif from_date:
            q_parts.append(f"payrollDate >= '{from_date}'")
        elif to_date:
            q_parts.append(f"payrollDate <= '{to_date}'")

        q_expr = " AND ".join(q_parts) if q_parts else None
        return await self._rest_get(
            "payrollRecords",
            limit=limit,
            offset=offset,
            q=q_expr,
            fields=kw.get("fields") or [
                "PayrollRelationshipId", "PersonNumber", "PayrollName",
                "PayrollDate", "NetPayAmount", "GrossEarningsAmount",
            ],
            order_by=kw.get("order_by", "PayrollDate:desc"),
        )

    async def _get_time_cards(self, **kw: Any) -> dict[str, Any]:
        """جلب بطاقات الوقت (Time Cards) من Oracle HCM.

        Args (via kwargs):
            limit (int): عدد السجلات.
            offset (int): إزاحة الصفحات.
            person_number (str): تصفية حسب الشخص (إلزامي للوصول المقيّد).
            start_date (str): تاريخ بداية الأسبوع (YYYY-MM-DD).
            end_date (str): تاريخ نهاية الأسبوع.
        """
        person_number: Optional[str] = kw.get("person_number")
        if not person_number:
            raise ConnectorError(
                "Oracle HCM: 'person_number' إلزامي لإجراء get_time_cards (قيود Oracle HCM)",
            )

        q_parts = [
            f"PersonNumber='{person_number.replace(chr(39), chr(39)*2)}'",
        ]
        start_date = kw.get("start_date")
        end_date = kw.get("end_date")
        if start_date and end_date:
            q_parts.append(f"timeCardStartDate between '{start_date}' and '{end_date}'")

        return await self._rest_get(
            "timeCards",
            limit=int(kw.get("limit", 50)),
            offset=int(kw.get("offset", 0)),
            q=" AND ".join(q_parts),
            fields=kw.get("fields") or [
                "timeCardId", "PersonNumber", "timeCardStartDate",
                "timeCardEndDate", "timeCardStatus", "approvedBy",
            ],
            order_by=kw.get("order_by", "timeCardStartDate:desc"),
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
            "protocol": "Oracle HCM REST API (OAuth2 client-credentials)",
            "rest_path": self._rest_path,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": False,
                "read": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "resources": sorted(self.RESOURCE_MAP.values()),
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل (RBAC)."""
        return self.config.required_permissions or [
            "connector:oracle_hcm:read",
            "hr:workers:read",
            "hr:payroll:read",
            "hr:timecards:read",
        ]
