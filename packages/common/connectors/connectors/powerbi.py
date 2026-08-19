"""
موصل Microsoft Power BI لمنصة HSAAI
====================================
يتيح هذا الموصل الوصول إلى Microsoft Power BI عبر REST API الرسمية
(api.powerbi.com/v1.0/myorg) مع مصادقة OAuth2 من Azure AD باستخدام
تدفّق client_credentials.

الإجراءات المدعومة:
    - list_dashboards  : سرد لوحات المعلومات (dashboards) في المؤسسة
    - get_dashboard    : جلب بيانات لوحة معيّنة (مع tiles)
    - list_reports     : سرد التقارير (reports)
    - get_report       : جلب بيانات تقرير معيّن
    - list_datasets    : سرد مجموعات البيانات (datasets)
    - execute_query    : تنفيذ استعلام DAX ضد dataset

كما يدعم search() للبحث في dashboards و reports.

الاستخدام:
    cfg = ConnectorConfig(
        name="powerbi",
        display_name="Corporate Power BI",
        category="BI",
        base_url="https://api.powerbi.com/v1.0/myorg",
        auth_strategy=AuthStrategy.OAUTH2_CLIENT_CREDENTIALS,
        secrets={
            "tenant_id": "...",
            "client_id": "...",
            "client_secret": "...",
        },
    )
    connector = PowerBIConnector(cfg)
    await connector.connect()
    dashboards = await connector.call("list_dashboards")
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


@connector("powerbi", version="1.0.0", category="BI")
class PowerBIConnector(BaseConnector):
    """موصل Microsoft Power BI عبر REST API مع مصادقة Azure AD OAuth2."""

    #: نقطة نهاية OAuth2 من Azure AD v2.0
    AZAD_TOKEN_URL_TEMPLATE: str = (
        "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    )

    #: نطاق Power BI REST API
    POWERBI_SCOPE: str = "https://analysis.windows.net/powerbi/api/.default"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "list_dashboards",
        "get_dashboard",
        "list_reports",
        "get_report",
        "list_datasets",
        "execute_query",
    )

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
        # مجموعة عمل اختيارية (Power BI workspace / group)
        self._group_id: Optional[str] = getattr(self.config, "group_id", None) or None
        # تحديد ما إذا كان يجب استخدام نقطة النهاية الإدارية (/admin)
        self._use_admin_endpoints: bool = bool(
            getattr(self.config, "use_admin_endpoints", False),
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
        """مصادقة OAuth2 client-credentials مع Azure AD لـ Power BI REST API.

        يتطلب وجود tenant_id و client_id و client_secret في config.secrets.
        يخزّن access_token محليًا ويحدّث ترويسة Authorization في self._client.

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل المصادقة.
        """
        if not self._tenant_id or not self._client_id or not self._client_secret:
            raise ConnectorAuthenticationError(
                "powerbi: tenant_id و client_id و client_secret مطلوبة للمصادقة",
            )

        async with httpx.AsyncClient(timeout=self.config.connect_timeout) as auth_client:
            try:
                response = await auth_client.post(
                    self._token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "scope": self.POWERBI_SCOPE,
                    },
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
            except httpx.HTTPError as exc:
                raise ConnectorAuthenticationError(
                    f"powerbi: فشل الاتصال بـ Azure AD: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"powerbi: فشل المصادقة (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        token_payload = response.json()
        self._access_token = token_payload.get("access_token")
        if not self._access_token:
            raise ConnectorAuthenticationError(
                "powerbi: لم يُرجع Azure AD access_token",
            )
        expires_in = int(token_payload.get("expires_in", 3600))
        self._token_expires_at = time.time() + max(60, expires_in - 60)

        if self._client is not None:
            self._client.headers.update({
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
            })

        logger.info(
            "powerbi: تم الحصول على access token (ينتهي خلال %ss)", expires_in,
        )

    async def _ensure_token(self) -> None:
        """تجديد access token عند انتهاء صلاحيته."""
        if self._access_token is None or time.time() >= self._token_expires_at:
            await self.authenticate()

    def _api_path(self, resource: str) -> str:
        """بناء مسار API الكامل للنطاق myorg مع دعم group_id و admin.

        Args:
            resource: مسار المورد النسبي (مثل '/dashboards').

        Returns:
            المسار الكامل جاهز للطلب من self._client.
        """
        resource = resource if resource.startswith("/") else f"/{resource}"
        if self._use_admin_endpoints:
            base = "/admin"
        elif self._group_id:
            base = f"/groups/{self._group_id}"
        else:
            base = ""
        return f"{base}{resource}"

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة Power BI REST API عبر طلب خفيف على /dashboards.

        يستخدم endpoint /dashboards?$top=1 كفحص خفيف (يتطلب صلاحية Dashboard.Read).
        """
        start = time.monotonic()
        try:
            await self._ensure_token()
            if self._client is None:
                raise ConnectorError("powerbi: العميل غير مهيأ — استدعِ connect() أولاً")
            response = await self._client.get(
                self._api_path("/dashboards"),
                params={"$top": "1"},
            )
            latency_ms = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={
                        "http_status": 200,
                        "api": "v1.0/myorg",
                        "group_id": self._group_id,
                    },
                )
            if response.status_code == 401:
                # قد تكون المصادقة قد انتهت — نُحدّثها ونعيد الفحص لاحقًا
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 401, "reason": "token_expired_or_invalid"},
                )
            if response.status_code == 403:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 403, "reason": "insufficient_permissions"},
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
    #  HTTP Helpers
    # ───────────────────────────────────────────────────────────────────
    async def _api_get(
        self, resource: str, *, params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """تنفيذ GET على Power BI REST API مع معالجة الأخطاء.

        Raises:
            ConnectorError: عند فشل الطلب.
        """
        if self._client is None:
            raise ConnectorError(
                "powerbi: العميل غير مهيأ — استدعِ connect() أولاً",
            )
        await self._ensure_token()
        try:
            response = await self._client.get(
                self._api_path(resource), params=params or {},
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"powerbi: فشل GET على {resource}: {exc}",
            ) from exc
        return self._handle_response(response, resource, "GET")

    async def _api_post(
        self, resource: str, *, json_body: Optional[dict[str, Any]] = None,
    ) -> Any:
        """تنفيذ POST على Power BI REST API مع معالجة الأخطاء."""
        if self._client is None:
            raise ConnectorError(
                "powerbi: العميل غير مهيأ — استدعِ connect() أولاً",
            )
        await self._ensure_token()
        try:
            response = await self._client.post(
                self._api_path(resource), json=json_body or {},
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"powerbi: فشل POST على {resource}: {exc}",
            ) from exc
        return self._handle_response(response, resource, "POST")

    def _handle_response(
        self, response: httpx.Response, resource: str, method: str,
    ) -> Any:
        """معالجة استجابة Power BI API وإرجاع JSON أو رفع خطأ مفهوم."""
        # 204 No Content
        if response.status_code == 204:
            return {"status": "success", "no_content": True}
        # معالجة الأخطاء
        if response.status_code >= 400:
            try:
                error_body = response.json()
                err = error_body.get("error", {})
                err_msg = err.get("message", response.text[:500])
                err_code = err.get("code", "")
            except ValueError:
                err_msg = response.text[:500]
                err_code = ""
            raise ConnectorError(
                f"powerbi: خطأ API في {method} {resource} "
                f"(HTTP {response.status_code}) [{err_code}]: {err_msg}",
            )
        # JSON عادي
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError(
                f"powerbi: استجابة غير صالحة JSON من {resource}: {exc}",
            ) from exc

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في dashboards و reports في Power BI.

        بما أن Power BI REST API لا يوفّر بحثًا نصيًا مباشرًا، يجلب الموصل
        قوائم dashboards و reports ثم يصفّيها محليًا بالاسم (name/displayName).

        Args:
            query: نص البحث (غير حساس لحالة الأحرف).
            **kwargs:
                kind (str): 'dashboards' أو 'reports' أو 'all' (افتراضيًا 'all').
                top (int): حد أقصى لعدد النتائج من كل نوع (افتراضيًا 50).

        Returns:
            قائمة بنتائج البحث مع نوع كل عنصر.
        """
        if not query or not query.strip():
            return []
        query_lower = query.strip().lower()
        kind: str = kwargs.pop("kind", "all")
        top: int = int(kwargs.pop("top", 50))

        results: list[dict[str, Any]] = []

        if kind in ("dashboards", "all"):
            try:
                data = await self._api_get("/dashboards", params={"$top": str(top)})
                for item in data.get("value", []):
                    name = (item.get("displayName") or item.get("name") or "").lower()
                    if query_lower in name:
                        results.append({
                            "type": "dashboard",
                            "id": item.get("id"),
                            "name": item.get("displayName"),
                            "workspace_id": item.get("workspaceId"),
                            "embed_url": item.get("embedUrl"),
                        })
            except ConnectorError as exc:
                logger.warning("powerbi: تعذّر جلب dashboards أثناء search: %s", exc)

        if kind in ("reports", "all"):
            try:
                data = await self._api_get("/reports", params={"$top": str(top)})
                for item in data.get("value", []):
                    name = (item.get("name") or item.get("displayName") or "").lower()
                    if query_lower in name:
                        results.append({
                            "type": "report",
                            "id": item.get("id"),
                            "name": item.get("name"),
                            "report_type": item.get("reportType"),
                            "workspace_id": item.get("datasetWorkspaceId"),
                            "embed_url": item.get("embedUrl"),
                        })
            except ConnectorError as exc:
                logger.warning("powerbi: تعذّر جلب reports أثناء search: %s", exc)

        return results[:top]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Power BI.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "list_dashboards": self._list_dashboards,
            "get_dashboard": self._get_dashboard,
            "list_reports": self._list_reports,
            "get_report": self._get_report,
            "list_datasets": self._list_datasets,
            "execute_query": self._execute_query,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"powerbi: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _list_dashboards(self, **kw: Any) -> dict[str, Any]:
        """سرد لوحات المعلومات في المؤسسة أو مجموعة عمل محددة.

        Args (via kwargs):
            top (int): عدد النتائج (افتراضيًا 100).
        """
        top = int(kw.get("top", 100))
        data = await self._api_get(
            "/dashboards", params={"$top": str(max(1, min(top, 1000)))},
        )
        dashboards = data.get("value", [])
        return {"count": len(dashboards), "dashboards": dashboards}

    async def _get_dashboard(self, **kw: Any) -> dict[str, Any]:
        """جلب بيانات لوحة معيّنة مع tiles الخاصة بها.

        Args (via kwargs):
            dashboard_id (str): معرف اللوحة (مطلوب).
            include_tiles (bool): جلب tiles أيضًا (افتراضيًا True).
        """
        dashboard_id = kw.get("dashboard_id")
        if not dashboard_id:
            raise ConnectorError("powerbi: get_dashboard يتطلب 'dashboard_id'")
        include_tiles = bool(kw.get("include_tiles", True))

        dashboard = await self._api_get(f"/dashboards/{dashboard_id}")
        result: dict[str, Any] = {"dashboard": dashboard}
        if include_tiles:
            try:
                tiles_data = await self._api_get(
                    f"/dashboards/{dashboard_id}/tiles",
                )
                result["tiles"] = tiles_data.get("value", [])
            except ConnectorError as exc:
                logger.warning("powerbi: تعذّر جلب tiles للوحة %s: %s", dashboard_id, exc)
                result["tiles"] = []
        return result

    async def _list_reports(self, **kw: Any) -> dict[str, Any]:
        """سرد التقارير في المؤسسة أو مجموعة عمل محددة.

        Args (via kwargs):
            top (int): عدد النتائج (افتراضيًا 100).
        """
        top = int(kw.get("top", 100))
        data = await self._api_get(
            "/reports", params={"$top": str(max(1, min(top, 1000)))},
        )
        reports = data.get("value", [])
        return {"count": len(reports), "reports": reports}

    async def _get_report(self, **kw: Any) -> dict[str, Any]:
        """جلب بيانات تقرير معيّن.

        Args (via kwargs):
            report_id (str): معرف التقرير (مطلوب).
        """
        report_id = kw.get("report_id")
        if not report_id:
            raise ConnectorError("powerbi: get_report يتطلب 'report_id'")
        report = await self._api_get(f"/reports/{report_id}")
        return {"report": report}

    async def _list_datasets(self, **kw: Any) -> dict[str, Any]:
        """سرد مجموعات البيانات (datasets) في المؤسسة أو مجموعة عمل محددة.

        Args (via kwargs):
            top (int): عدد النتائج (افتراضيًا 100).
            include_tables (bool): جلب جداول كل dataset (افتراضيًا False).
        """
        top = int(kw.get("top", 100))
        include_tables = bool(kw.get("include_tables", False))
        data = await self._api_get(
            "/datasets", params={"$top": str(max(1, min(top, 1000)))},
        )
        datasets = data.get("value", [])
        if include_tables:
            for ds in datasets:
                ds_id = ds.get("id")
                if not ds_id:
                    continue
                try:
                    tables_data = await self._api_get(
                        f"/datasets/{ds_id}/tables",
                    )
                    ds["tables"] = tables_data.get("value", [])
                except ConnectorError as exc:
                    logger.warning(
                        "powerbi: تعذّر جلب جداول dataset %s: %s", ds_id, exc,
                    )
                    ds["tables"] = []
        return {"count": len(datasets), "datasets": datasets}

    async def _execute_query(self, **kw: Any) -> dict[str, Any]:
        """تنفيذ استعلام DAX ضد dataset معيّن.

        Args (via kwargs):
            dataset_id (str): معرف الـ dataset (مطلوب).
            query (str): استعلام DAX بصيغة XMLA أو DAX بسيط (مطلوب).
            impersonated_user_name (str): اختياري — تنفيذ الاستعلام باسم مستخدم.

        Returns:
            {"dataset_id": str, "tables": list[dict], "rows_total": int}.
        """
        dataset_id = kw.get("dataset_id")
        dax_query = kw.get("query")
        if not dataset_id or not dax_query:
            raise ConnectorError(
                "powerbi: execute_query يتطلب 'dataset_id' و 'query'",
            )

        body: dict[str, Any] = {"queries": [{"query": dax_query}]}
        impersonated = kw.get("impersonated_user_name")
        if impersonated:
            body["impersonatedUserName"] = impersonated

        data = await self._api_post(
            f"/datasets/{dataset_id}/executeQueries", json_body=body,
        )
        results = data.get("results", [])
        tables_out: list[dict[str, Any]] = []
        rows_total = 0
        for res in results:
            for tbl in res.get("tables", []):
                rows = tbl.get("rows", [])
                rows_total += len(rows)
                tables_out.append({
                    "name": tbl.get("name"),
                    "rows": rows,
                    "row_count": len(rows),
                })
        return {
            "dataset_id": dataset_id,
            "tables": tables_out,
            "rows_total": rows_total,
        }

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
            "protocol": "Power BI REST API v1.0",
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": False,
                "dax_query": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "group_id": self._group_id,
            "admin_endpoints": self._use_admin_endpoints,
            "required_scopes": [
                "Dataset.Read.All",
                "Dashboard.Read.All",
                "Report.Read.All",
                "Capacity.Read.All",
            ],
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:powerbi:read",
            "bi:dashboards:read",
            "bi:reports:read",
            "bi:datasets:read",
            "bi:datasets:execute_query",
        ]
