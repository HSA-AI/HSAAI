"""
موصل REST API عام لمنصة HSAAI
================================
موصل عام قابل للتخصيص لأي REST API. يدعم أنواع المصادقة:
    - bearer   : Bearer Token (Authorization: Bearer <token>)
    - basic    : HTTP Basic Auth (username:password)
    - api_key  : API Key في ترويسة أو معامل
    - none     : بدون مصادقة

الإجراءات المدعومة:
    - get    : GET request
    - post   : POST request
    - put    : PUT request
    - delete : DELETE request
    - patch  : PATCH request

search() ينفذ GET {base_url}/search?q={query} (مع تخصيص المسار).

الاستخدام:
    cfg = ConnectorConfig(
        name="rest_api",
        display_name="Custom REST API",
        category="Integration",
        base_url="https://api.example.com",
        auth_strategy=AuthStrategy.BEARER,  # أو BASIC / API_KEY / NONE
        secrets={
            "token": "abc123",          # للـ bearer
            # أو "username", "password"  # للـ basic
            # أو "api_key", "api_key_header"  # للـ api_key
        },
    )
    connector = RestApiConnector(cfg)
    await connector.connect()
    data = await connector.call("get", path="/users/123")
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


@connector("rest_api", version="1.0.0", category="Integration")
class RestApiConnector(BaseConnector):
    """موصل REST API عام يدعم bearer/basic/api_key/none auth."""

    #: المسار الافتراضي للبحث
    DEFAULT_SEARCH_PATH: str = "/search"

    #: اسم ترويسة API Key الافتراضي
    DEFAULT_API_KEY_HEADER: str = "X-API-Key"

    #: ترويسة Bearer الافتراضية
    BEARER_HEADER: str = "Authorization"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "get", "post", "put", "delete", "patch",
    )

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        # استخراج بيانات الاعتماد حسب استراتيجية المصادقة
        self._token: str = self._get_secret("token", "")
        self._username: str = self._get_secret("username", "")
        self._password: str = self._get_secret("password", "")
        self._api_key: str = self._get_secret("api_key", "")
        # اسم ترويسة API Key قابل للتجاوز
        self._api_key_header: str = getattr(
            self.config, "api_key_header", self.DEFAULT_API_KEY_HEADER,
        )
        # موقع API Key: 'header' (افتراضي) أو 'query'
        self._api_key_location: str = getattr(
            self.config, "api_key_location", "header",
        )
        # اسم معامل API Key في query (إن كان location='query')
        self._api_key_query_param: str = getattr(
            self.config, "api_key_query_param", "api_key",
        )
        # مسار البحث القابل للتخصيص
        self._search_path: str = getattr(
            self.config, "search_path", self.DEFAULT_SEARCH_PATH,
        )
        # مسار فحص الصحة القابل للتخصيص
        self._health_path: Optional[str] = getattr(
            self.config, "health_path", None,
        )
        self._auth_header: Optional[str] = None
        self._base_url: str = self.config.base_url.rstrip("/")

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
        """تجهيز ترويسة المصادقة بناءً على auth_strategy.

        الاستراتيجيات المدعومة:
            - BEARER  : Authorization: Bearer <token>
            - BASIC   : Authorization: Basic <base64(user:pass)>
            - API_KEY : <api_key_header>: <api_key>  (أو ?api_key= في query)
            - NONE    : بدون مصادقة

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد المطلوبة.
        """
        strategy = self.config.auth_strategy

        if strategy == AuthStrategy.NONE:
            self._auth_header = None
            logger.info("REST API: لا مصادقة مطلوبة")
            return

        if strategy == AuthStrategy.BEARER:
            if not self._token:
                raise ConnectorAuthenticationError(
                    "REST API: 'token' مطلوب لمصادقة Bearer",
                )
            self._auth_header = f"Bearer {self._token}"
            if self._client is not None:
                self._client.headers.update({
                    self.BEARER_HEADER: self._auth_header,
                    "Accept": "application/json",
                })
            logger.info("REST API: تم تجهيز مصادقة Bearer")
            return

        if strategy == AuthStrategy.BASIC:
            if not self._username or not self._password:
                raise ConnectorAuthenticationError(
                    "REST API: 'username' و 'password' مطلوبان لمصادقة Basic",
                )
            credentials = f"{self._username}:{self._password}".encode("utf-8")
            encoded = base64.b64encode(credentials).decode("ascii")
            self._auth_header = f"Basic {encoded}"
            if self._client is not None:
                self._client.headers.update({
                    self.BEARER_HEADER: self._auth_header,
                    "Accept": "application/json",
                })
            logger.info("REST API: تم تجهيز مصادقة Basic")
            return

        if strategy == AuthStrategy.API_KEY:
            if not self._api_key:
                raise ConnectorAuthenticationError(
                    "REST API: 'api_key' مطلوب لمصادقة API Key",
                )
            if self._api_key_location == "header":
                if self._client is not None:
                    self._client.headers.update({
                        self._api_key_header: self._api_key,
                        "Accept": "application/json",
                    })
            logger.info(
                "REST API: تم تجهيز API Key في %s",
                self._api_key_location,
            )
            return

        # استراتيجيات OAuth2 الكاملة تتطلب token endpoint خارج هذا الموصل العام
        raise ConnectorAuthenticationError(
            f"REST API: استراتيجية المصادقة '{strategy.value}' غير مدعومة في "
            f"الموصل العام — استخدم bearer/basic/api_key/none",
        )

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة REST API.

        إن طُلب 'health_path' في الإعدادات، يُجرى GET عليه؛ خلاف ذلك
        يُجرى GET على base_url نفسها للتحقق من الوصول.
        """
        start = time.monotonic()
        try:
            if self._client is None:
                raise ConnectorError("REST API: العميل غير مهيأ — استدعِ connect() أولاً")
            path = self._health_path or "/"
            try:
                response = await self._client.get(path)
            except httpx.HTTPError as exc:
                raise ConnectorError(f"REST API: فشل فحص الصحة: {exc}") from exc
            latency_ms = (time.monotonic() - start) * 1000
            # اعتبار أي استجابة 2xx أو 3xx أو 401 (يعني الخادم يعمل لكن المصادقة مطلوبة) صحية
            if response.status_code < 500:
                healthy = response.status_code < 400
                status = HealthStatus.HEALTHY if healthy else HealthStatus.DEGRADED
                return HealthResult(
                    status=status,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={
                        "http_status": response.status_code,
                        "health_path": path,
                    },
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
    #  Request Helpers
    # ───────────────────────────────────────────────────────────────────
    def _merge_query_params(
        self, params: Optional[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        """دمج معاملات API Key في query إن كان location='query'."""
        if (self.config.auth_strategy == AuthStrategy.API_KEY
                and self._api_key_location == "query" and self._api_key):
            params = dict(params or {})
            params.setdefault(self._api_key_query_param, self._api_key)
        return params

    async def _request(
        self,
        method: str,
        *,
        path: str = "",
        url: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        data: Optional[Any] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """تنفيذ طلب HTTP عام على REST API.

        Args:
            method: HTTP method (GET/POST/PUT/DELETE/PATCH).
            path: مسار نسبي من base_url (مثل '/users/123').
            url: URL مطلق بديل عن path.
            params: معاملات الاستعلام.
            json_body: محتوى JSON.
            data: محتوى نصي/ثنائي خام.
            headers: ترويسات إضافية.
            timeout: مهلة اختيارية (ثواني).

        Returns:
            استجابة موحدة: {status_code, headers, body, elapsed_ms}.
        """
        if self._client is None:
            raise ConnectorError("REST API: العميل غير مهيأ — استدعِ connect() أولاً")

        # تحديد URL النهائي
        if url is None:
            if not path:
                raise ConnectorError(
                    "REST API: يجب تمرير 'path' أو 'url'",
                )
            # httpx AsyncClient مع base_url يدعم المسارات النسبية
            target = path
        else:
            target = url

        merged_params = self._merge_query_params(params)
        merged_headers = headers or {}

        start = time.monotonic()
        try:
            if timeout is not None:
                # استخدام مهلة مخصصة
                response = await self._client.request(
                    method, target,
                    params=merged_params, json=json_body, data=data,
                    headers=merged_headers,
                    timeout=httpx.Timeout(timeout),
                )
            else:
                response = await self._client.request(
                    method, target,
                    params=merged_params, json=json_body, data=data,
                    headers=merged_headers,
                )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"REST API: فشل {method} {target}: {exc}",
            ) from exc

        elapsed_ms = (time.monotonic() - start) * 1000
        return self._format_response(response, target, method, elapsed_ms)

    def _format_response(
        self, response: httpx.Response, target: str,
        method: str, elapsed_ms: float,
    ) -> dict[str, Any]:
        """تنسيق استجابة HTTP إلى قاموس موحد مع معالجة الأخطاء."""
        # استخراج المحتوى بأمان
        body: Any
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            try:
                body = response.json()
            except ValueError:
                body = response.text
        elif response.content:
            body = response.text
        else:
            body = None

        # الأخطاء 4xx/5xx تُرفع كـ ConnectorError
        if response.status_code >= 400:
            err_msg = (
                body.get("error") if isinstance(body, dict)
                else (body if isinstance(body, str) else None)
            ) or response.text[:500]
            raise ConnectorError(
                f"REST API: خطأ في {method} {target} "
                f"(HTTP {response.status_code}): {err_msg}",
            )

        return {
            "status_code": response.status_code,
            "ok": response.is_success,
            "elapsed_ms": round(elapsed_ms, 2),
            "headers": dict(response.headers),
            "body": body,
        }

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث عبر GET {base_url}{search_path}?q={query}.

        يُتوقَّع أن تُرجع API قائمة JSON. إن أرجعت كائنًا يحتوي على مفتاح
        قائمة (مثل 'results' أو 'data' أو 'items')، يُستخرَج تلقائيًا.

        Args:
            query: نص البحث.
            **kwargs:
                search_path (str): مسار بحث مخصص (افتراضيًا '/search').
                query_param (str): اسم معامل البحث (افتراضيًا 'q').
                extra_params (dict): معاملات إضافية.
                limit (int): عدد النتائج (يُضاف كمعامل limit).

        Returns:
            قائمة بنتائج البحث.
        """
        search_path: str = kwargs.pop("search_path", self._search_path)
        query_param: str = kwargs.pop("query_param", "q")
        extra_params: dict[str, Any] = kwargs.pop("extra_params", {}) or {}
        limit: Optional[int] = kwargs.pop("limit", None)

        params: dict[str, Any] = {query_param: query, **extra_params}
        if limit is not None:
            params["limit"] = limit

        result = await self._request("GET", path=search_path, params=params)
        body = result.get("body")
        # محاولة استخراج قائمة من جسم الاستجابة
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            for key in ("results", "data", "items", "records", "hits"):
                if isinstance(body.get(key), list):
                    return body[key]
            # إن كانت dict واحدة، نُعيدها في قائمة
            return [body]
        return []

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء HTTP عام.

        args (via kwargs):
            path (str): مسار نسبي (مثل '/users/123').
            url (str): URL مطلق بديل.
            params (dict): معاملات الاستعلام.
            json (Any): محتوى JSON.
            data (Any): محتوى خام.
            headers (dict): ترويسات إضافية.
            timeout (float): مهلة اختيارية.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم أو فشل الطلب.
        """
        handlers = {
            "get": self._get,
            "post": self._post,
            "put": self._put,
            "delete": self._delete,
            "patch": self._patch,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"REST API: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _get(self, **kw: Any) -> dict[str, Any]:
        """GET request."""
        return await self._request(
            "GET",
            path=kw.get("path"),
            url=kw.get("url"),
            params=kw.get("params"),
            headers=kw.get("headers"),
            timeout=kw.get("timeout"),
        )

    async def _post(self, **kw: Any) -> dict[str, Any]:
        """POST request."""
        return await self._request(
            "POST",
            path=kw.get("path"),
            url=kw.get("url"),
            params=kw.get("params"),
            json_body=kw.get("json"),
            data=kw.get("data"),
            headers=kw.get("headers"),
            timeout=kw.get("timeout"),
        )

    async def _put(self, **kw: Any) -> dict[str, Any]:
        """PUT request."""
        return await self._request(
            "PUT",
            path=kw.get("path"),
            url=kw.get("url"),
            params=kw.get("params"),
            json_body=kw.get("json"),
            data=kw.get("data"),
            headers=kw.get("headers"),
            timeout=kw.get("timeout"),
        )

    async def _delete(self, **kw: Any) -> dict[str, Any]:
        """DELETE request."""
        return await self._request(
            "DELETE",
            path=kw.get("path"),
            url=kw.get("url"),
            params=kw.get("params"),
            headers=kw.get("headers"),
            timeout=kw.get("timeout"),
        )

    async def _patch(self, **kw: Any) -> dict[str, Any]:
        """PATCH request."""
        return await self._request(
            "PATCH",
            path=kw.get("path"),
            url=kw.get("url"),
            params=kw.get("params"),
            json_body=kw.get("json"),
            data=kw.get("data"),
            headers=kw.get("headers"),
            timeout=kw.get("timeout"),
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
            "protocol": "HTTP/REST (generic)",
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "read": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "http_methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "search_path": self._search_path,
            "health_path": self._health_path,
            "api_key_location": self._api_key_location,
            "customizable": True,
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        # الصلاحيات عامة لأن الموصل قابل للتخصيص لأي API
        return self.config.required_permissions or [
            "connector:rest_api:read",
            "connector:rest_api:write",
            "http:get",
            "http:post",
            "http:put",
            "http:delete",
            "http:patch",
        ]
