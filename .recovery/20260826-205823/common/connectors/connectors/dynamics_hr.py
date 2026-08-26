"""
موصل Microsoft Dynamics 365 HR لمنصة HSAAI
=============================================
يتيح هذا الموصل الوصول إلى Microsoft Dynamics 365 Human Resources عبر
واجهة Dataverse OData v4 مع مصادقة OAuth2 (Azure AD client-credentials).

نقطة النهاية الأساسية:
    {base_url}/data/v9.2/   (مثال: https://contoso.crm.dynamics.com)

الكيانات الأساسية في Dataverse HR:
    - mshr_hcmworker                : الموظفون
    - mshr_hcmposition              : المناصب
    - mshr_hcmworkerleavebalance    : أرصدة الإجازات
    - mshr_payrollpaystatement      : قسائم الرواتب

الإجراءات المدعومة:
    - get_workers         : جلب قائمة الموظفين
    - get_positions       : جلب المناصب
    - get_leave_balances  : جلب أرصدة الإجازات لموظف
    - get_payroll         : جلب قسائم الرواتب لموظف

search() يبحث في mshr_hcmworker عبر حقول نصية (mshr_personnelnumber,
mshr_fullname, mshr_primaryemail) باستخدام OData $filter.

الاستخدام:
    cfg = ConnectorConfig(
        name="dynamics_hr",
        display_name="Dynamics 365 HR",
        category="HR",
        base_url="https://contoso.crm.dynamics.com",
        auth_strategy=AuthStrategy.OAUTH2_CLIENT_CREDENTIALS,
        secrets={
            "tenant_id": "...",
            "client_id": "...",
            "client_secret": "...",
        },
    )
    connector = DynamicsHRConnector(cfg)
    await connector.connect()
    workers = await connector.call("get_workers", top=100)
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


@connector("dynamics_hr", version="1.0.0", category="HR")
class DynamicsHRConnector(BaseConnector):
    """موصل Microsoft Dynamics 365 HR عبر Dataverse OData v4 و Azure AD OAuth2."""

    #: نقطة نهاية OAuth2 من Azure AD v2.0
    AZAD_TOKEN_URL_TEMPLATE: str = (
        "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    )

    #: نطاق Dataverse الافتراضي
    DATAVERSE_SCOPE_TEMPLATE: str = "{base_url}/.default"

    #: إصدار Dataverse Web API الافتراضي
    DATAVERSE_API_VERSION: str = "v9.2"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "get_workers",
        "get_positions",
        "get_leave_balances",
        "get_payroll",
    )

    #: خريطة الإجراءات إلى كيانات Dataverse HR
    ENTITY_MAP: dict[str, str] = {
        "get_workers": "mshr_hcmworker",
        "get_positions": "mshr_hcmposition",
        "get_leave_balances": "mshr_hcmworkerleavebalance",
        "get_payroll": "mshr_payrollpaystatement",
    }

    #: الحقول الافتراضية للكيانات الرئيسية
    DEFAULT_SELECT: dict[str, list[str]] = {
        "mshr_hcmworker": [
            "mshr_workerid", "mshr_personnelnumber", "mshr_fullname",
            "mshr_firstname", "mshr_lastname", "mshr_primaryemail",
            "mshr_employmentstartdate", "mshr_employmentenddate",
        ],
        "mshr_hcmposition": [
            "mshr_positionid", "mshr_jobid", "mshr_departmentnumber",
            "mshr_positiondescription", "mshr_availableforassignment",
            "mshr_validfrom", "mshr_validto",
        ],
        "mshr_hcmworkerleavebalance": [
            "mshr_workerid", "mshr_leaveplanid", "mshr_leavebalance",
            "mshr_leavetype", "mshr_validasofdate",
        ],
        "mshr_payrollpaystatement": [
            "mshr_paystatementid", "mshr_workerid", "mshr_personnelnumber",
            "mshr_payperiodstartdate", "mshr_payperiodenddate",
            "mshr_netpayamount", "mshr_grosspayamount",
        ],
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
        self._token_url: str = self.AZAD_TOKEN_URL_TEMPLATE.format(
            tenant_id=self._tenant_id or "common",
        )
        # النطاق الافتراضي: {base_url}/.default — يُستبدل إن أُعطي scope مخصص
        default_scope = self.DATAVERSE_SCOPE_TEMPLATE.format(
            base_url=self.config.base_url.rstrip("/"),
        )
        self._scope: str = self._get_secret("scope", default_scope)
        self._api_version: str = getattr(
            self.config, "api_version", self.DATAVERSE_API_VERSION,
        )
        self._api_path: str = f"/data/{self._api_version}"
        self._dataverse_base: str = self.config.base_url.rstrip("/")

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
        """مصادقة OAuth2 client-credentials مع Azure AD لـ Dataverse.

        يطلب access token بنطاق {base_url}/.default الذي يمنح الوصول
        إلى Dataverse Web API. التوكن يُخزَّن ويُستخدم في ترويسة
        Authorization: Bearer.

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل المصادقة.
        """
        if not self._tenant_id or not self._client_id or not self._client_secret:
            raise ConnectorAuthenticationError(
                "Dynamics 365 HR: tenant_id و client_id و client_secret مطلوبة للمصادقة",
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
                    headers={"Accept": "application/json"},
                )
            except httpx.HTTPError as exc:
                raise ConnectorAuthenticationError(
                    f"Dynamics 365 HR: فشل الاتصال بـ Azure AD: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"Dynamics 365 HR: فشل المصادقة (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        token_data = response.json()
        self._access_token = token_data.get("access_token")
        if not self._access_token:
            raise ConnectorAuthenticationError(
                "Dynamics 365 HR: لم يُرجع Azure AD access_token",
            )

        expires_in = int(token_data.get("expires_in", 3600))
        self._token_expires_at = time.time() + max(60, expires_in - 60)

        if self._client is not None:
            self._client.headers.update({
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
            })

        logger.info(
            "Dynamics 365 HR: تم الحصول على access token (ينتهي خلال %ss)", expires_in,
        )

    async def _ensure_token(self) -> None:
        """تجديد access token تلقائيًا عند اقتراب انتهاء صلاحيته."""
        if self._access_token is None or time.time() >= self._token_expires_at:
            await self.authenticate()

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة Dataverse عبر طلب OData على RetrieveTotalRecordCount.

        Returns:
            HealthResult مع حالة الخدمة وزمن الاستجابة.
        """
        start = time.monotonic()
        try:
            await self._ensure_token()
            if self._client is None:
                raise ConnectorError("Dynamics 365 HR: العميل غير مهيأ — استدعِ connect() أولاً")
            # استعلام خفيف: جلب أول صف فقط من mshr_hcmworker
            response = await self._client.get(
                f"{self._api_path}/mshr_hcmworker",
                params={"$top": "1", "$count": "true"},
            )
            latency_ms = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 200, "endpoint": "mshr_hcmworker"},
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
        count: bool = True,
    ) -> dict[str, str]:
        """بناء بارامترات استعلام OData v4 لـ Dataverse."""
        params: dict[str, str] = {
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
        if count:
            params["$count"] = "true"
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
        count: bool = True,
    ) -> dict[str, Any]:
        """تنفيذ طلب GET على كيان Dataverse وإرجاع النتائج بصورة موحدة.

        Raises:
            ConnectorError: عند فشل الطلب أو إرجاع الخادم لخطأ.
        """
        if self._client is None:
            raise ConnectorError("Dynamics 365 HR: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()

        params = self._build_odata_params(
            top=top, skip=skip, filter_expr=filter_expr,
            select=select, order_by=order_by, expand=expand, count=count,
        )
        try:
            response = await self._client.get(
                f"{self._api_path}/{entity}",
                params=params,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"Dynamics 365 HR: فشل GET على {entity}: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"Dynamics 365 HR: خطأ OData في {entity} "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )

        data = response.json()
        # OData v4 يعيد: {"@odata.context": ..., "@odata.count": n, "value": [...]}
        return {
            "entity": entity,
            "count": data.get("@odata.count", len(data.get("value", []))),
            "value": data.get("value", []),
            "next_link": data.get("@odata.nextLink"),
        }

    async def _odata_get_by_id(
        self, entity: str, record_id: str,
        *, select: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """جلب سجل واحد من كيان Dataverse عبر معرفه (primary key).

        Raises:
            ConnectorError: عند فشل الطلب أو عدم العثور على السجل.
        """
        if self._client is None:
            raise ConnectorError("Dynamics 365 HR: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()

        params: dict[str, str] = {}
        if select:
            params["$select"] = ",".join(select)
        try:
            response = await self._client.get(
                f"{self._api_path}/{entity}({record_id})",
                params=params,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"Dynamics 365 HR: فشل GET على {entity}({record_id}): {exc}",
            ) from exc

        if response.status_code == 404:
            raise ConnectorError(
                f"Dynamics 365 HR: السجل {entity}({record_id}) غير موجود",
            )
        if response.status_code >= 400:
            raise ConnectorError(
                f"Dynamics 365 HR: خطأ OData في {entity}({record_id}) "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )
        return response.json()

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في mshr_hcmworker عبر OData $filter.

        يطابق النص ضد mshr_personnelnumber و mshr_fullname و mshr_primaryemail
        باستخدام عامل OR في صيغة OData v4: startswith أو contains.

        Args:
            query: نص البحث (free-text).
            **kwargs:
                entity (str): اسم الكيان البديل (افتراضيًا 'mshr_hcmworker').
                fields (list[str]): الحقول المُسترجَعة.
                top (int): عدد النتائج (افتراضيًا 50).

        Returns:
            قائمة بالسجلات المطابقة.
        """
        entity: str = kwargs.pop("entity", "mshr_hcmworker")
        fields: Optional[list[str]] = kwargs.pop("fields", None) or self.DEFAULT_SELECT.get(entity)
        top: int = int(kwargs.pop("top", 50))

        # تنظيف النص لمنع حقن OData (مضاعفة علامات الاقتباس المفردة)
        safe_query = query.replace("'", "''").strip()
        if not safe_query:
            return []

        # بناء $filter: contains() على عدة حقول نصية
        filter_expr = (
            f"contains(mshr_personnelnumber, '{safe_query}') or "
            f"contains(mshr_fullname, '{safe_query}') or "
            f"contains(mshr_primaryemail, '{safe_query}')"
        )
        result = await self._odata_get(
            entity, top=top, filter_expr=filter_expr, select=fields,
            order_by="mshr_personnelnumber asc",
        )
        return result["value"]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Dynamics 365 HR.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "get_workers": self._get_workers,
            "get_positions": self._get_positions,
            "get_leave_balances": self._get_leave_balances,
            "get_payroll": self._get_payroll,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"Dynamics 365 HR: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _get_workers(self, **kw: Any) -> dict[str, Any]:
        """جلب قائمة الموظفين (mshr_hcmworker) من Dataverse HR.

        Args (via kwargs):
            top (int): عدد السجلات (افتراضيًا 100).
            skip (int): إزاحة الصفحات.
            filter (str): تعبير $filter مخصص.
            fields (list[str]): الحقول المُسترجَعة.
        """
        return await self._odata_get(
            "mshr_hcmworker",
            top=int(kw.get("top", 100)),
            skip=int(kw.get("skip", 0)),
            filter_expr=kw.get("filter"),
            select=kw.get("fields") or self.DEFAULT_SELECT["mshr_hcmworker"],
            order_by=kw.get("order_by", "mshr_personnelnumber asc"),
        )

    async def _get_positions(self, **kw: Any) -> dict[str, Any]:
        """جلب المناصب (mshr_hcmposition) من Dataverse HR.

        Args (via kwargs):
            top (int): عدد السجلات.
            skip (int): إزاحة الصفحات.
            filter (str): تعبير $filter مخصص.
            available_only (bool): جلب المناصب المتاحة للتعيين فقط.
        """
        filter_expr = kw.get("filter")
        if kw.get("available_only"):
            avail_filter = "mshr_availableforassignment eq true"
            filter_expr = f"({filter_expr}) and {avail_filter}" if filter_expr else avail_filter

        return await self._odata_get(
            "mshr_hcmposition",
            top=int(kw.get("top", 100)),
            skip=int(kw.get("skip", 0)),
            filter_expr=filter_expr,
            select=kw.get("fields") or self.DEFAULT_SELECT["mshr_hcmposition"],
            order_by=kw.get("order_by", "mshr_positionid asc"),
        )

    async def _get_leave_balances(self, **kw: Any) -> dict[str, Any]:
        """جلب أرصدة الإجازات لموظف (mshr_hcmworkerleavebalance).

        Args (via kwargs):
            worker_id (str): معرف الموظف (إلزامي).
            top (int): عدد السجلات.

        Raises:
            ConnectorError: عند فقدان worker_id.
        """
        worker_id: Optional[str] = kw.get("worker_id")
        if not worker_id:
            raise ConnectorError(
                "Dynamics 365 HR: 'worker_id' إلزامي لإجراء get_leave_balances",
            )
        # تنظيف معامل worker_id لمنع حقن OData
        safe_id = worker_id.replace("'", "''")
        filter_expr = f"_mshr_worker_value eq {safe_id} or mshr_workerid eq '{safe_id}'"
        return await self._odata_get(
            "mshr_hcmworkerleavebalance",
            top=int(kw.get("top", 100)),
            filter_expr=filter_expr,
            select=kw.get("fields") or self.DEFAULT_SELECT["mshr_hcmworkerleavebalance"],
        )

    async def _get_payroll(self, **kw: Any) -> dict[str, Any]:
        """جلب قسائم الرواتب لموظف (mshr_payrollpaystatement).

        Args (via kwargs):
            worker_id (str): معرف الموظف (إلزامي).
            personnel_number (str): رقم الموظف البديل.
            top (int): عدد السجلات.
            from_date (str): تاريخ بداية التصفية (YYYY-MM-DD).
            to_date (str): تاريخ نهاية التصفية.

        Raises:
            ConnectorError: عند فقدان worker_id أو personnel_number.
        """
        worker_id = kw.get("worker_id")
        personnel_number = kw.get("personnel_number")
        if not worker_id and not personnel_number:
            raise ConnectorError(
                "Dynamics 365 HR: 'worker_id' أو 'personnel_number' إلزامي لإجراء get_payroll",
            )

        filter_parts: list[str] = []
        if worker_id:
            filter_parts.append(f"_mshr_worker_value eq {worker_id.replace(chr(39), chr(39)*2)}")
        if personnel_number:
            filter_parts.append(
                f"mshr_personnelnumber eq '{personnel_number.replace(chr(39), chr(39)*2)}'",
            )
        from_date = kw.get("from_date")
        to_date = kw.get("to_date")
        if from_date and to_date:
            filter_parts.append(
                f"mshr_payperiodstartdate ge {from_date} and mshr_payperiodenddate le {to_date}",
            )
        elif from_date:
            filter_parts.append(f"mshr_payperiodstartdate ge {from_date}")
        elif to_date:
            filter_parts.append(f"mshr_payperiodenddate le {to_date}")

        filter_expr = " or ".join(filter_parts) if filter_parts else None
        return await self._odata_get(
            "mshr_payrollpaystatement",
            top=int(kw.get("top", 50)),
            filter_expr=filter_expr,
            select=kw.get("fields") or self.DEFAULT_SELECT["mshr_payrollpaystatement"],
            order_by=kw.get("order_by", "mshr_payperiodstartdate desc"),
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
            "protocol": "Dataverse OData v4 (Azure AD OAuth2 client-credentials)",
            "api_version": self._api_version,
            "api_path": self._api_path,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": False,
                "read": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "entities": sorted(self.ENTITY_MAP.values()),
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل (RBAC)."""
        return self.config.required_permissions or [
            "connector:dynamics_hr:read",
            "hr:workers:read",
            "hr:positions:read",
            "hr:leavebalances:read",
            "hr:payroll:read",
        ]
