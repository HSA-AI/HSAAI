"""
موصل Qlik Sense لمنصة HSAAI
============================
يتيح هذا الموصل الوصول إلى Qlik Sense (SaaS / Qlik Cloud) عبر:
  1. REST API (api.qlik.com) لمصادقة API Key وسرد التطبيقات.
  2. Qlik Engine JSON-RPC (websocket) لتقييم التعبيرات وسرد الأوراق.

الإجراءات المدعومة:
    - list_apps            : سرد التطبيقات (apps) في المستأجر
    - get_app              : جلب بيانات تطبيق معيّن
    - list_sheets          : سرد الأوراق (sheets) في تطبيق
    - evaluate_expression  : تقييم تعبير Qlik expression (HyperCube)

كما يدعم search() للبحث في apps.

الاستخدام:
    cfg = ConnectorConfig(
        name="qlik_sense",
        display_name="Qlik Cloud",
        category="BI",
        base_url="https://my-tenant.qlikcloud.com",
        auth_strategy=AuthStrategy.API_KEY,
        secrets={"api_key": "..."},
    )
    connector = QlikSenseConnector(cfg)
    await connector.connect()
    apps = await connector.call("list_apps")
"""
from __future__ import annotations

import json
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


@connector("qlik_sense", version="1.0.0", category="BI")
class QlikSenseConnector(BaseConnector):
    """موصل Qlik Sense عبر REST API + Qlik Engine JSON-RPC (websocket)."""

    #: مسار REST API لسرد التطبيقات
    REST_ITEMS_PATH: str = "/api/v1/items"

    #: مسار REST API لمعلومات تطبيق
    REST_APP_PATH: str = "/api/v1/apps/{app_id}"

    #: مسار مصادقة التحقق من API Key
    REST_ME_PATH: str = "/api/v1/me"

    #: URI لمحرك Qlik Engine (websocket)
    ENGINE_URI: str = "/app/{app_id}/identity/{identity}"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "list_apps",
        "get_app",
        "list_sheets",
        "evaluate_expression",
    )

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._api_key: str = self._get_secret("api_key", "")
        # websocket client — يُنشأ عند الحاجة لتقييم التعبيرات
        self._ws_client: Optional[httpx.AsyncClient] = None
        # معرّف فريد لجلسة websocket
        self._identity: str = f"hsaai-{int(time.time())}"

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
        """التحقق من صحة API Key عبر استدعاء /api/v1/me.

        Qlik Cloud يستخدم ترويسة Authorization: Bearer <api_key> لكل طلب.
        لا يحتاج الموصل إلى تبادل رمز، فقط التحقق من صحة المفتاح.

        Raises:
            ConnectorAuthenticationError: عند فقدان المفتاح أو فشل التحقق.
        """
        if not self._api_key:
            raise ConnectorAuthenticationError(
                "qlik_sense: api_key مطلوبة للمصادقة",
            )
        if self._client is None:
            raise ConnectorError(
                "qlik_sense: العميل غير مهيأ — استدعِ connect() أولاً",
            )
        self._client.headers.update({
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        # التحقق من صحة المفتاح
        try:
            response = await self._client.get(self.REST_ME_PATH)
        except httpx.HTTPError as exc:
            raise ConnectorAuthenticationError(
                f"qlik_sense: فشل الاتصال بـ /api/v1/me: {exc}",
            ) from exc
        if response.status_code == 401:
            raise ConnectorAuthenticationError(
                "qlik_sense: API Key غير صالح (401 Unauthorized)",
            )
        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"qlik_sense: فشل التحقق من API Key "
                f"(HTTP {response.status_code}): {response.text[:300]}",
            )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        user_name = (
            (payload.get("user") or {}).get("name")
            or (payload.get("user") or {}).get("subject")
        )
        logger.info("qlik_sense: تم التحقق من API Key — المستخدم: %s", user_name)

    async def _ensure_auth(self) -> None:
        """إعادة التحقق من المصادقة عند الحاجة."""
        if self._client is None or "Authorization" not in self._client.headers:
            await self.authenticate()

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة Qlik Cloud عبر استدعاء /api/v1/me.

        يُرجى ملاحظة أن /api/v1/me يتطلب مصادقة، لذا فهو يفحص الاتصال وصحة المفتاح.
        """
        start = time.monotonic()
        try:
            if self._client is None:
                raise ConnectorError("qlik_sense: العميل غير مهيأ — استدعِ connect() أولاً")
            await self._ensure_auth()
            response = await self._client.get(self.REST_ME_PATH)
            latency_ms = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 200, "endpoint": "/api/v1/me"},
                )
            if response.status_code == 401:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 401, "reason": "api_key_invalid"},
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
    #  REST API Helpers
    # ───────────────────────────────────────────────────────────────────
    async def _rest_get(
        self, path: str, *, params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """تنفيذ GET على REST API لـ Qlik Cloud.

        Raises:
            ConnectorError: عند فشل الطلب.
        """
        if self._client is None:
            raise ConnectorError(
                "qlik_sense: العميل غير مهيأ — استدعِ connect() أولاً",
            )
        await self._ensure_auth()
        try:
            response = await self._client.get(path, params=params or {})
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"qlik_sense: فشل GET على {path}: {exc}",
            ) from exc
        return self._handle_response(response, path, "GET")

    def _handle_response(
        self, response: httpx.Response, path: str, method: str,
    ) -> Any:
        """معالجة استجابة Qlik REST API."""
        if response.status_code == 204:
            return {"status": "success", "no_content": True}
        if response.status_code >= 400:
            try:
                err_body = response.json()
                err_msg = (
                    err_body.get("message")
                    or err_body.get("error", {}).get("message")
                    or response.text[:500]
                )
                err_code = (
                    err_body.get("code")
                    or err_body.get("error", {}).get("code", "")
                )
            except ValueError:
                err_msg = response.text[:500]
                err_code = ""
            raise ConnectorError(
                f"qlik_sense: خطأ REST API في {method} {path} "
                f"(HTTP {response.status_code}) [{err_code}]: {err_msg}",
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError(
                f"qlik_sense: استجابة غير صالحة JSON من {path}: {exc}",
            ) from exc

    # ───────────────────────────────────────────────────────────────────
    #  Qlik Engine (JSON-RPC over WebSocket)
    # ───────────────────────────────────────────────────────────────────
    async def _engine_rpc(
        self, app_id: str, method: str, params: list[Any] | None = None,
        *, handle: int = -1,
    ) -> Any:
        """تنفيذ استدعاء JSON-RPC واحد على Qlik Engine عبر WebSocket.

        Args:
            app_id: معرف التطبيق.
            method: اسم الطريقة (مثل 'Evaluate', 'GetObject', 'GetProperties').
            params: بارامترات الطريقة.
            handle: مقبض الكائن (-1 للكائن العام/Doc).

        Returns:
            نتيجة الطريقة (result field).

        Raises:
            ConnectorError: عند فشل الاتصال أو الطلب.
        """
        if not self._api_key:
            raise ConnectorError("qlik_sense: api_key غير متوفرة للاتصال بالمحرك")
        if self._client is None:
            raise ConnectorError("qlik_sense: العميل غير مهيأ")

        ws_scheme = "wss" if self.config.base_url.startswith("https") else "ws"
        host = self.config.base_url.split("://", 1)[-1].rstrip("/")
        ws_url = f"{ws_scheme}://{host}/app/{app_id}/identity/{self._identity}"

        request_body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "handle": handle,
            "params": params or [],
        }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.read_timeout),
                headers={"Authorization": f"Bearer {self._api_key}"},
            ) as ws_client:
                async with ws_client.websocket_connect(
                    ws_url,
                    subprotocols=["json"],
                ) as ws:
                    await ws.send_text(json.dumps(request_body))
                    raw = await ws.receive_text()
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"qlik_sense: فشل WebSocket JSON-RPC ({method}): {exc}",
            ) from exc
        except Exception as exc:
            raise ConnectorError(
                f"qlik_sense: خطأ في WebSocket ({method}): {exc}",
            ) from exc

        try:
            envelope = json.loads(raw)
        except ValueError as exc:
            raise ConnectorError(
                f"qlik_sense: استجابة WebSocket غير صالحة JSON: {exc}",
            ) from exc

        if "error" in envelope:
            err = envelope["error"]
            raise ConnectorError(
                f"qlik_sense: خطأ Engine JSON-RPC في '{method}' "
                f"[code={err.get('code')}, param={err.get('parameter')}]: "
                f"{err.get('message')}",
            )
        return envelope.get("result")

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في تطبيقات Qlik Sense.

        يستخدم GET /api/v1/items?type=app و qlik-cli يوفّر filter query،
        لكن REST API يدعم querystring 'q' على /api/v1/items?resourceType=app.
        نطبّق فلترة محلية على name للتوافق مع جميع الإصدارات.

        Args:
            query: نص البحث (غير حساس لحالة الأحرف).
            **kwargs:
                top (int): عدد النتائج (افتراضيًا 50).

        Returns:
            قائمة بنتائج البحث {id, name, description, owner, space}.
        """
        if not query or not query.strip():
            return []
        query_lower = query.strip().lower()
        top = int(kwargs.pop("top", 50))

        params = {
            "resourceType": "app",
            "limit": str(max(1, min(top * 5, 500))),  # نأخذ أكثر ثم نفلتر
        }
        data = await self._rest_get(self.REST_ITEMS_PATH, params=params)
        items = data.get("data", [])
        results: list[dict[str, Any]] = []
        for item in items:
            attrs = item.get("attributes", {}) or {}
            name = (attrs.get("name") or "").lower()
            if query_lower in name:
                results.append({
                    "type": "app",
                    "id": item.get("id"),
                    "name": attrs.get("name"),
                    "description": attrs.get("description"),
                    "owner": (item.get("owner") or {}).get("name"),
                    "space_id": (item.get("links") or {}).get("self"),
                })
            if len(results) >= top:
                break
        return results

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Qlik Sense.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "list_apps": self._list_apps,
            "get_app": self._get_app,
            "list_sheets": self._list_sheets,
            "evaluate_expression": self._evaluate_expression,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"qlik_sense: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _list_apps(self, **kw: Any) -> dict[str, Any]:
        """سرد التطبيقات المتاحة في المستأجر.

        Args (via kwargs):
            top (int): عدد النتائج (افتراضيًا 100).
            space_id (str): اختياري — تقييد التطبيقات بمساحة محددة.
        """
        top = int(kw.get("top", 100))
        params: dict[str, Any] = {
            "resourceType": "app",
            "limit": str(max(1, min(top, 500))),
        }
        space_id = kw.get("space_id")
        if space_id:
            params["spaceId"] = space_id

        data = await self._rest_get(self.REST_ITEMS_PATH, params=params)
        items = data.get("data", [])
        apps: list[dict[str, Any]] = []
        for item in items:
            attrs = item.get("attributes", {}) or {}
            apps.append({
                "id": item.get("id"),
                "name": attrs.get("name"),
                "description": attrs.get("description"),
                "resource_type": attrs.get("resourceType"),
                "owner": (item.get("owner") or {}).get("name"),
            })
        return {
            "count": len(apps),
            "total_available": data.get("meta", {}).get("paging", {}).get("total"),
            "apps": apps,
        }

    async def _get_app(self, **kw: Any) -> dict[str, Any]:
        """جلب بيانات تطبيق معيّن.

        Args (via kwargs):
            app_id (str): معرف التطبيق (مطلوب).
        """
        app_id = kw.get("app_id")
        if not app_id:
            raise ConnectorError("qlik_sense: get_app يتطلب 'app_id'")
        path = self.REST_APP_PATH.format(app_id=app_id)
        data = await self._rest_get(path)
        attrs = data.get("attributes", {}) or {}
        return {
            "app": {
                "id": data.get("id"),
                "name": attrs.get("name"),
                "description": attrs.get("description"),
                "owner": (data.get("owner") or {}).get("name"),
                "created_date": attrs.get("createdDate"),
                "modified_date": attrs.get("modifiedDate"),
                "published": attrs.get("published"),
            },
        }

    async def _list_sheets(self, **kw: Any) -> dict[str, Any]:
        """سرد الأوراق (sheets) في تطبيق معيّن عبر Qlik Engine.

        يستدعي GetObject على الـ Doc للحصول على قائمة الأوراق.

        Args (via kwargs):
            app_id (str): معرف التطبيق (مطلوب).
        """
        app_id = kw.get("app_id")
        if not app_id:
            raise ConnectorError("qlik_sense: list_sheets يتطلب 'app_id'")

        # GetTablesAndKeys غير صالح للأوراق؛ نستخدم GetObject list على
        # نوع "sheet" عبر CreateObject أو نستخدم Engine API: GetAllInfos.
        result = await self._engine_rpc(
            app_id, "GetAllInfos", [],
        )
        infos = (result or {}).get("qInfos", []) if isinstance(result, dict) else []
        sheets: list[dict[str, Any]] = []
        for info in infos:
            if (info.get("qType") or "").lower() == "sheet":
                sheets.append({
                    "id": info.get("qId"),
                    "type": info.get("qType"),
                })
        # محاولة جلب أسماء الأوراق
        for sheet in sheets:
            try:
                props = await self._engine_rpc(
                    app_id, "GetProperties", [{"qId": sheet["id"]}],
                )
                meta = (props or {}).get("qProp", {}) if isinstance(props, dict) else {}
                sheet["title"] = meta.get("qMetaDef", {}).get("title")
                sheet["description"] = meta.get("qMetaDef", {}).get("description")
            except ConnectorError as exc:
                logger.warning(
                    "qlik_sense: تعذّر جلب خصائص الورقة %s: %s", sheet.get("id"), exc,
                )
        return {"count": len(sheets), "sheets": sheets}

    async def _evaluate_expression(self, **kw: Any) -> dict[str, Any]:
        """تقييم تعبير Qlik expression ضد تطبيق معيّن.

        يستخدم Engine API: Evaluate (على مقبض -1 / Doc).
        يعمل هذا لـ Qlik expressions البسيطة مثل '=Sum(Sales)'.

        Args (via kwargs):
            app_id (str): معرف التطبيق (مطلوب).
            expression (str): تعبير Qlik (مثل 'Sum(Sales)') (مطلوب).

        Returns:
            {"app_id": str, "expression": str, "value": str}.
        """
        app_id = kw.get("app_id")
        expression = kw.get("expression")
        if not app_id or not expression:
            raise ConnectorError(
                "qlik_sense: evaluate_expression يتطلب 'app_id' و 'expression'",
            )
        # Evaluate على الـ Doc
        value = await self._engine_rpc(
            app_id, "Evaluate", [{"qExpression": expression}],
        )
        return {
            "app_id": app_id,
            "expression": expression,
            "value": value,
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
            "protocol": "Qlik Cloud REST API + Engine JSON-RPC (WebSocket)",
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": False,
                "engine_rpc": True,
                "evaluate_expression": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "required_scopes": [
                "apps:read",
                "users:read",
                "items:read",
                "engines:read",
            ],
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:qlik_sense:read",
            "bi:apps:read",
            "bi:sheets:read",
            "bi:apps:evaluate",
        ]
