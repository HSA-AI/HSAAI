"""
موصل Tableau Server لمنصة HSAAI
================================
يتيح هذا الموصل الوصول إلى Tableau Server عبر REST API الرسمية باستخدام
مصادقة Personal Access Token (PAT).

الإجراءات المدعومة:
    - list_workbooks  : سرد كتب العمل (workbooks) المتاحة للمستخدم
    - get_workbook    : جلب بيانات كتاب عمل معيّن (مع views)
    - list_views      : سرد العروض (views) في كتاب عمل محدد
    - get_view_image  : تنزيل صورة (PNG) لعرض معيّن
    - query_data      : تنفيذ استعلام بيانات عبر Tableau Catalog / Datasource

كما يدعم search() للبحث في workbooks.

الاستخدام:
    cfg = ConnectorConfig(
        name="tableau",
        display_name="Corporate Tableau Server",
        category="BI",
        base_url="https://tableau.corp.local",
        auth_strategy=AuthStrategy.API_KEY,
        api_version="3.21",
        secrets={
            "token_name": "my-pat",
            "token_secret": "...",
            "site_id": "Default",
        },
    )
    connector = TableauConnector(cfg)
    await connector.connect()
    workbooks = await connector.call("list_workbooks")
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


@connector("tableau", version="1.0.0", category="BI")
class TableauConnector(BaseConnector):
    """موصل Tableau Server عبر REST API مع مصادقة Personal Access Token."""

    #: إصدار REST API الافتراضي
    DEFAULT_API_VERSION: str = "3.21"

    #: نقطة نهاية المصادقة (sign in)
    SIGNIN_PATH: str = "/api/{version}/auth/signin"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "list_workbooks",
        "get_workbook",
        "list_views",
        "get_view_image",
        "query_data",
    )

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._token_name: str = self._get_secret("token_name", "")
        self._token_secret: str = self._get_secret("token_secret", "")
        # site_id اختياري — عند تركه فارغًا يُعتبر موقعًا افتراضيًا
        self._site_id: str = self._get_secret("site_id", "") or getattr(
            self.config, "site_id", "",
        )
        self._api_version: str = (
            self.config.api_version or self.DEFAULT_API_VERSION
        )
        self._credentials_token: Optional[str] = None  # رمز الجلسة من signin
        self._site_luid: Optional[str] = None  # LUID للموقع بعد signin
        self._user_luid: Optional[str] = None  # LUID للمستخدم بعد signin
        self._token_expires_at: float = 0.0

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
        """المصادقة مع Tableau Server عبر Personal Access Token (signin).

        يستدعي POST /api/{version}/auth/signin بـ credentials من نوع personalaccesstoken.
        يخزّن رمز الجلسة (credentialsToken) و LUID للموقع والمستخدم.

        Raises:
            ConnectorAuthenticationError: عند فقدان البيانات أو فشل signin.
        """
        if not self._token_name or not self._token_secret:
            raise ConnectorAuthenticationError(
                "tableau: token_name و token_secret مطلوبة للمصادقة",
            )

        signin_url = self.SIGNIN_PATH.format(version=self._api_version)
        body: dict[str, Any] = {
            "credentials": {
                "personalAccessTokenName": self._token_name,
                "personalAccessTokenSecret": self._token_secret,
                "site": {"contentUrl": self._site_id or ""},
            },
        }

        async with httpx.AsyncClient(timeout=self.config.connect_timeout) as auth_client:
            try:
                response = await auth_client.post(
                    f"{self.config.base_url.rstrip('/')}{signin_url}",
                    json=body,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
            except httpx.HTTPError as exc:
                raise ConnectorAuthenticationError(
                    f"tableau: فشل الاتصال بخادم Tableau: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"tableau: فشل signin (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ConnectorAuthenticationError(
                f"tableau: استجابة signin غير صالحة JSON: {exc}",
            ) from exc

        credentials = payload.get("credentials", {})
        self._credentials_token = credentials.get("token")
        site = credentials.get("site", {})
        self._site_luid = site.get("id")
        user = credentials.get("user", {})
        self._user_luid = user.get("id")
        estimated_expiry = int(credentials.get("estimatedTimeToExpiration", 240) * 60)
        self._token_expires_at = time.time() + max(60, estimated_expiry - 60)

        if not self._credentials_token or not self._site_luid:
            raise ConnectorAuthenticationError(
                "tableau: استجابة signin ناقصة (token/site id مفقود)",
            )

        # تحديث ترويسات العميل الدائم
        if self._client is not None:
            self._client.headers.update({
                "X-Tableau-Auth": self._credentials_token,
                "Accept": "application/json",
            })

        logger.info(
            "tableau: تم signin بنجاح — site_luid=%s user_luid=%s",
            self._site_luid, self._user_luid,
        )

    async def _ensure_token(self) -> None:
        """تجديد رمز الجلسة عند انتهاء صلاحيته."""
        if self._credentials_token is None or time.time() >= self._token_expires_at:
            await self.authenticate()

    def _api_path(self, resource: str) -> str:
        """بناء مسار API الكامل لمورد نسبي."""
        resource = resource if resource.startswith("/") else f"/{resource}"
        return f"/api/{self._api_version}{resource}"

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة Tableau Server عبر استدعاء خفيف على /serverInfo.

        نقطة النهاية /api/{version}/serverInfo لا تتطلب مصادقة وتُرجع
        إصدار الخادم ومعلومات المنتج.
        """
        start = time.monotonic()
        try:
            if self._client is None:
                raise ConnectorError("tableau: العميل غير مهيأ — استدعِ connect() أولاً")
            # /serverInfo لا يتطلب auth، لكن نستخدم /auth/session-info أيضًا للتحقق
            try:
                response = await self._client.get(self._api_path("/serverInfo"))
            except httpx.HTTPError as exc:
                raise ConnectorError(f"tableau: فشل الاتصال: {exc}") from exc

            latency_ms = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}
                server_info = payload.get("serverInfo", {})
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={
                        "http_status": 200,
                        "product_version": server_info.get("productVersion", {}).get("value"),
                        "rest_api_version": server_info.get("restApiVersion"),
                    },
                )
            if response.status_code == 401:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 401, "reason": "session_expired"},
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
        accept: str = "application/json",
    ) -> httpx.Response:
        """تنفيذ GET على Tableau REST API."""
        if self._client is None:
            raise ConnectorError("tableau: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()
        headers = {"Accept": accept}
        try:
            response = await self._client.get(
                self._api_path(resource), params=params or {}, headers=headers,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"tableau: فشل GET على {resource}: {exc}",
            ) from exc
        return response

    async def _api_post(
        self, resource: str, *, json_body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        """تنفيذ POST على Tableau REST API."""
        if self._client is None:
            raise ConnectorError("tableau: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()
        try:
            response = await self._client.post(
                self._api_path(resource), json=json_body or {}, params=params or {},
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"tableau: فشل POST على {resource}: {exc}",
            ) from exc
        return response

    def _handle_json(self, response: httpx.Response, resource: str, method: str) -> Any:
        """معالجة استجابة JSON من Tableau."""
        if response.status_code == 204:
            return {"status": "success", "no_content": True}
        if response.status_code >= 400:
            try:
                err_body = response.json()
                err = err_body.get("error", {})
                err_msg = err.get("message") or err.get("summary", response.text[:500])
                err_code = err.get("code", "")
            except ValueError:
                err_msg = response.text[:500]
                err_code = ""
            raise ConnectorError(
                f"tableau: خطأ API في {method} {resource} "
                f"(HTTP {response.status_code}) [{err_code}]: {err_msg}",
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError(
                f"tableau: استجابة غير صالحة JSON من {resource}: {exc}",
            ) from exc

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في workbooks على Tableau Server.

        يستخدم GET /api/{version}/sites/{site_luid}/workbooks مع فلتر
        filter=name:contains:[query] (OData-style).

        Args:
            query: نص البحث (غير حساس لحالة الأحرف).
            **kwargs:
                top (int): عدد النتاج (افتراضيًا 50).

        Returns:
            قائمة بنتائج البحث {id, name, project, owner, webpage_url}.
        """
        if not query or not query.strip():
            return []
        if not self._site_luid:
            raise ConnectorError(
                "tableau: search يتطلب site_luid — تأكد من signin ناجح",
            )
        top = int(kwargs.pop("top", 50))
        # التأكد من URL-encoding آمن للفلتر
        safe_query = query.replace(",", " ")
        params: dict[str, Any] = {
            "filter": f"name:contains:[{safe_query}]",
            "pageSize": str(max(1, min(top, 1000))),
        }
        response = await self._api_get(
            f"/sites/{self._site_luid}/workbooks", params=params,
        )
        data = self._handle_json(response, f"/sites/{self._site_luid}/workbooks", "GET")
        workbooks = data.get("workbooks", {}).get("workbook", [])
        return [
            {
                "type": "workbook",
                "id": wb.get("id"),
                "name": wb.get("name"),
                "project": (wb.get("project") or {}).get("name"),
                "owner": (wb.get("owner") or {}).get("name"),
                "webpage_url": wb.get("webpageUrl"),
            }
            for wb in workbooks
        ]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Tableau Server.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "list_workbooks": self._list_workbooks,
            "get_workbook": self._get_workbook,
            "list_views": self._list_views,
            "get_view_image": self._get_view_image,
            "query_data": self._query_data,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"tableau: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _list_workbooks(self, **kw: Any) -> dict[str, Any]:
        """سرد كتب العمل المتاحة للمستخدم.

        Args (via kwargs):
            top (int): عدد النتائج (افتراضيًا 100).
            project_id (str): اختياري — تقييد النتائج بمشروع محدد.
        """
        if not self._site_luid:
            raise ConnectorError("tableau: site_luid غير متوفر — استدعِ connect() أولاً")
        top = int(kw.get("top", 100))
        params: dict[str, Any] = {"pageSize": str(max(1, min(top, 1000)))}
        project_id = kw.get("project_id")
        if project_id:
            params["filter"] = f"projectName:eq:[{project_id}]"

        response = await self._api_get(
            f"/sites/{self._site_luid}/workbooks", params=params,
        )
        data = self._handle_json(response, "list_workbooks", "GET")
        workbooks = data.get("workbooks", {}).get("workbook", [])
        pagination = data.get("pagination", {})
        return {
            "count": len(workbooks),
            "total_available": int(pagination.get("totalAvailable", len(workbooks))),
            "workbooks": workbooks,
        }

    async def _get_workbook(self, **kw: Any) -> dict[str, Any]:
        """جلب بيانات كتاب عمل معيّن مع عروضه (views).

        Args (via kwargs):
            workbook_luid (str): معرف LUID لكتاب العمل (مطلوب).
            include_views (bool): جلب العروض (افتراضيًا True).
        """
        workbook_luid = kw.get("workbook_luid")
        if not workbook_luid:
            raise ConnectorError("tableau: get_workbook يتطلب 'workbook_luid'")
        include_views = bool(kw.get("include_views", True))

        response = await self._api_get(f"/sites/{self._site_luid}/workbooks/{workbook_luid}")
        workbook = self._handle_json(response, "get_workbook", "GET").get("workbook", {})

        result: dict[str, Any] = {"workbook": workbook}
        if include_views:
            try:
                views_resp = await self._api_get(
                    f"/sites/{self._site_luid}/workbooks/{workbook_luid}/views",
                )
                views_data = self._handle_json(views_resp, "get_workbook views", "GET")
                result["views"] = views_data.get("views", {}).get("view", [])
            except ConnectorError as exc:
                logger.warning("tableau: تعذّر جلب views لـ %s: %s", workbook_luid, exc)
                result["views"] = []
        return result

    async def _list_views(self, **kw: Any) -> dict[str, Any]:
        """سرد العروض (views) على مستوى الموقع أو في كتاب عمل محدد.

        Args (via kwargs):
            workbook_luid (str): اختياري — تقييد العروض بكتاب عمل محدد.
            top (int): عدد النتائج (افتراضيًا 100).
        """
        if not self._site_luid:
            raise ConnectorError("tableau: site_luid غير متوفر — استدعِ connect() أولاً")
        top = int(kw.get("top", 100))
        workbook_luid = kw.get("workbook_luid")
        params = {"pageSize": str(max(1, min(top, 1000)))}

        if workbook_luid:
            path = f"/sites/{self._site_luid}/workbooks/{workbook_luid}/views"
        else:
            path = f"/sites/{self._site_luid}/views"

        response = await self._api_get(path, params=params)
        data = self._handle_json(response, path, "GET")
        views = data.get("views", {}).get("view", [])
        return {"count": len(views), "views": views}

    async def _get_view_image(self, **kw: Any) -> dict[str, Any]:
        """تنزيل صورة (PNG) لعرض معيّن.

        Args (via kwargs):
            view_luid (str): معرف LUID للعرض (مطلوب).
            resolution (str): 'high' أو 'standard' (افتراضيًا 'high').
            max_age (int): أقصى عمر للصورة المخزّنة مؤقتًا (دقائق).

        Returns:
            {"view_luid": str, "content_type": str, "image_base64": str}.
        """
        view_luid = kw.get("view_luid")
        if not view_luid:
            raise ConnectorError("tableau: get_view_image يتطلب 'view_luid'")
        resolution = kw.get("resolution", "high")
        params: dict[str, Any] = {"resolution": resolution}
        if "max_age" in kw:
            params["maxAge"] = str(kw["max_age"])

        response = await self._api_get(
            f"/sites/{self._site_luid}/views/{view_luid}/image",
            params=params,
            accept="image/png",
        )
        if response.status_code != 200:
            raise ConnectorError(
                f"tableau: فشل تنزيل صورة العرض {view_luid} "
                f"(HTTP {response.status_code}): {response.text[:300]}",
            )
        content_type = response.headers.get("content-type", "image/png")
        image_b64 = base64.b64encode(response.content).decode("ascii")
        return {
            "view_luid": view_luid,
            "resolution": resolution,
            "content_type": content_type,
            "image_base64": image_b64,
        }

    async def _query_data(self, **kw: Any) -> dict[str, Any]:
        """تنفيذ استعلام بيانات على Tableau عبر Query View Data endpoint.

        يستخدم GET /api/{version}/sites/{site}/views/{view}/data الذي يُرجع
        بيانات العرض بصيغة CSV أو JSON.

        Args (via kwargs):
            view_luid (str): معرف العرض (مطلوب).
            format (str): 'csv' أو 'json' (افتراضيًا 'json').
            max_rows (int): أقصى عدد صفوف.

        Returns:
            {"view_luid": str, "format": str, "rows": list | str}.
        """
        view_luid = kw.get("view_luid")
        if not view_luid:
            raise ConnectorError("tableau: query_data يتطلب 'view_luid'")
        out_format = kw.get("format", "json")
        params: dict[str, Any] = {}
        if "max_rows" in kw:
            params["maxRows"] = str(kw["max_rows"])

        accept = "application/json" if out_format == "json" else "text/csv"
        response = await self._api_get(
            f"/sites/{self._site_luid}/views/{view_luid}/data",
            params=params,
            accept=accept,
        )
        if response.status_code != 200:
            raise ConnectorError(
                f"tableau: فشل query_data (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )
        if out_format == "json":
            try:
                rows = response.json()
            except ValueError:
                rows = response.text
        else:
            rows = response.text
        return {
            "view_luid": view_luid,
            "format": out_format,
            "rows": rows,
        }

    # ───────────────────────────────────────────────────────────────────
    #  Disconnect / Cleanup
    # ───────────────────────────────────────────────────────────────────
    async def disconnect(self) -> None:
        """تسجيل الخروج من Tableau Server وإغلاق العميل."""
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except Exception:
                pass
            self._health_task = None
        # محاولة signout (best-effort)
        if self._client is not None and self._credentials_token:
            try:
                await self._client.post(self._api_path("/auth/signout"))
            except Exception as exc:
                logger.warning("tableau: تعذّر signout: %s", exc)
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._credentials_token = None
        self._site_luid = None
        self._user_luid = None
        self.state = __import__(
            "packages.common.connectors.base", fromlist=["ConnectorState"],
        ).ConnectorState.DISCONNECTED
        logger.info("tableau: تم قطع الاتصال")

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
            "protocol": "Tableau Server REST API",
            "rest_api_version": self._api_version,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": False,
                "image_export": True,
                "data_query": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "site_id": self._site_id,
            "required_scopes": [
                "tableau:views:read",
                "tableau:workbooks:read",
                "tableau:metrics:read",
            ],
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:tableau:read",
            "bi:workbooks:read",
            "bi:views:read",
            "bi:views:export_image",
            "bi:views:query_data",
        ]
