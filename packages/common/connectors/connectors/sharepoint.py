"""
موصل Microsoft SharePoint / Graph API لمنصة HSAAI
====================================================
يتيح هذا الموصل الوصول إلى Microsoft SharePoint عبر Microsoft Graph API
مع مصادقة OAuth2 من Azure AD (client credentials flow).

الإجراءات المدعومة:
    - list_files    : سرد الملفات في مسار/مكتبة محددة
    - download_file : تنزيل محتوى ملف (binary stream)
    - upload_file   : رفع ملف إلى مكتبة مستندات
    - search_files  : البحث في الملفات عبر MS Graph search API
    - list_sites    : سرد مواقع SharePoint المتاحة

الاستخدام:
    cfg = ConnectorConfig(
        name="sharepoint",
        display_name="Corporate SharePoint",
        category="Documents",
        base_url="https://graph.microsoft.com",
        auth_strategy=AuthStrategy.OAUTH2_CLIENT_CREDENTIALS,
        secrets={
            "tenant_id": "...",
            "client_id": "...",
            "client_secret": "...",
        },
    )
    connector = SharePointConnector(cfg)
    await connector.connect()
    files = await connector.call("list_files", site_id="contoso.sharepoint.com,abc,def", folder_path="/Shared Documents")
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


@connector("sharepoint", version="1.0.0", category="Documents")
class SharePointConnector(BaseConnector):
    """موصل Microsoft SharePoint عبر Microsoft Graph API."""

    #: نقطة نهاية OAuth2 من Azure AD v2.0
    AZAD_TOKEN_URL_TEMPLATE: str = (
        "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    )

    #: نطاق Graph API
    GRAPH_SCOPE: str = "https://graph.microsoft.com/.default"

    #: إصدار Graph API
    GRAPH_API_VERSION: str = "v1.0"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "list_files",
        "download_file",
        "upload_file",
        "search_files",
        "list_sites",
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
        # التأكد من أن base_url يشير إلى Graph API
        self._graph_base: str = self.config.base_url.rstrip("/")
        self._graph_path: str = f"/{self.GRAPH_API_VERSION}"

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
        """مصادقة OAuth2 client-credentials مع Azure AD لـ Graph API.

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل المصادقة.
        """
        if not self._tenant_id or not self._client_id or not self._client_secret:
            raise ConnectorAuthenticationError(
                "SharePoint: tenant_id و client_id و client_secret مطلوبة للمصادقة",
            )

        async with httpx.AsyncClient(timeout=self.config.connect_timeout) as auth_client:
            try:
                response = await auth_client.post(
                    self._token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "scope": self.GRAPH_SCOPE,
                    },
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
            except httpx.HTTPError as exc:
                raise ConnectorAuthenticationError(
                    f"SharePoint: فشل الاتصال بـ Azure AD: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"SharePoint: فشل المصادقة (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        token_payload = response.json()
        self._access_token = token_payload.get("access_token")
        if not self._access_token:
            raise ConnectorAuthenticationError(
                "SharePoint: لم يُرجع Azure AD access_token",
            )
        expires_in = int(token_payload.get("expires_in", 3600))
        self._token_expires_at = time.time() + max(60, expires_in - 60)

        if self._client is not None:
            self._client.headers.update({
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
                "ConsistencyLevel": "eventual",  # مطلوب لبعض استعلامات Graph
            })

        logger.info(
            "SharePoint: تم الحصول على access token (ينتهي خلال %ss)", expires_in,
        )

    async def _ensure_token(self) -> None:
        """تجديد access token عند انتهاء صلاحيته."""
        if self._access_token is None or time.time() >= self._token_expires_at:
            await self.authenticate()

    def _graph_url(self, path: str) -> str:
        """بناء URL كامل لـ Graph API من مسار نسبي."""
        if path.startswith("/"):
            return f"{self._graph_path}{path}"
        return f"{self._graph_path}/{path}"

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة Graph API عبر طلب بسيط على $metadata.

        نستخدم endpoint /sites?search=* كفحص خفيف (يتطلب صلاحية Sites.Read).
        """
        start = time.monotonic()
        try:
            await self._ensure_token()
            assert self._client is not None
            response = await self._client.get(
                self._graph_url("/sites"),
                params={"$top": "1"},
            )
            latency_ms = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 200, "api": self.GRAPH_API_VERSION},
                )
            if response.status_code == 401:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 401, "reason": "token_expired"},
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
    #  Graph API Helpers
    # ───────────────────────────────────────────────────────────────────
    async def _graph_get(
        self, path: str, *, params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """تنفيذ GET على Graph API مع معالجة الأخطاء.

        Raises:
            ConnectorError: عند فشل الطلب.
        """
        if self._client is None:
            raise ConnectorError(
                "SharePoint: العميل غير مهيأ — استدعِ connect() أولاً",
            )
        await self._ensure_token()
        try:
            response = await self._client.get(
                self._graph_url(path), params=params or {},
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"SharePoint: فشل GET على {path}: {exc}",
            ) from exc
        return self._handle_response(response, path, "GET")

    def _handle_response(
        self, response: httpx.Response, path: str, method: str,
    ) -> Any:
        """معالجة استجابة Graph API وإرجاع JSON أو رفع خطأ مفهوم."""
        # 204 No Content — نجاح بلا محتوى (شائع في DELETE/PATCH)
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
                f"SharePoint: خطأ Graph API في {method} {path} "
                f"(HTTP {response.status_code}) [{err_code}]: {err_msg}",
            )
        # محتوى ثنائي (لتنزيل الملفات)
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return {"binary": True, "content": response.content,
                    "content_type": content_type}
        # JSON عادي
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError(
                f"SharePoint: استجابة غير صالحة JSON من {path}: {exc}",
            ) from exc

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في محتوى SharePoint عبر Microsoft Graph search API.

        يستخدم POST /search/query مع entityTypes=['driveItem', 'site', 'list'].

        Args:
            query: نص البحث (KQL مدعومة جزئيًا).
            **kwargs:
                entity_types (list[str]): أنواع الكيانات (افتراضيًا
                    ['driveItem']).
                site_id (str): تقييد البحث على موقع محدد.
                top (int): عدد النتائج (افتراضيًا 25، حد أقصى 1000).

        Returns:
            قائمة بنتائج البحث (hits).
        """
        entity_types: list[str] = kwargs.pop(
            "entity_types", ["driveItem"],
        )
        site_id: Optional[str] = kwargs.pop("site_id", None)
        top: int = int(kwargs.pop("top", 25))

        # بناء طلب البحث بصيغة Graph search
        request_body: dict[str, Any] = {
            "requests": [
                {
                    "entityTypes": entity_types,
                    "query": {
                        "queryString": query,
                        "queryTemplate": "{searchTerms}",
                    },
                    "from": 0,
                    "size": max(1, min(top, 1000)),
                    "fields": [
                        "id", "name", "webUrl", "fileType", "lastModifiedDateTime",
                        "createdDateTime", "size", "parentReference",
                    ],
                }
            ],
        }
        # تقييد البحث بموقع محدد
        if site_id:
            request_body["requests"][0]["sharePointOneDriveOptions"] = {
                "includeContent": "privateContent",
            }
            # إضافة فلتر للموقع عبر queryTemplate
            request_body["requests"][0]["query"]["queryTemplate"] = (
                f"siteid:{site_id} {{searchTerms}}"
            )

        if self._client is None:
            raise ConnectorError(
                "SharePoint: العميل غير مهيأ — استدعِ connect() أولاً",
            )
        await self._ensure_token()
        try:
            response = await self._client.post(
                self._graph_url("/search/query"),
                json=request_body,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"SharePoint: فشل search: {exc}",
            ) from exc
        data = self._handle_response(response, "/search/query", "POST")
        # استخراج hits من الاستجابة
        hitscontainers = data.get("value", [])
        all_hits: list[dict[str, Any]] = []
        for container in hitscontainers:
            for hit in container.get("hitsContainers", []):
                all_hits.extend(hit.get("hits", []))
        return all_hits

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على SharePoint.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "list_files": self._list_files,
            "download_file": self._download_file,
            "upload_file": self._upload_file,
            "search_files": self._search_files,
            "list_sites": self._list_sites,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"SharePoint: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _list_sites(self, **kw: Any) -> dict[str, Any]:
        """سرد مواقع SharePoint المتاحة للمستأجر.

        Args (via kwargs):
            top (int): عدد النتائج (افتراضيًا 50).
            search (str): نص بحث لتصفية المواقع.
        """
        top = int(kw.get("top", 50))
        search = kw.get("search")
        params: dict[str, Any] = {"$top": str(max(1, min(top, 500)))}
        if search:
            params["search"] = search
        data = await self._graph_get("/sites", params=params)
        return {
            "count": len(data.get("value", [])),
            "sites": data.get("value", []),
        }

    async def _list_files(self, **kw: Any) -> dict[str, Any]:
        """سرد الملفات في مكتبة/مجلد محدد.

        Args (via kwargs):
            site_id (str): معرف موقع SharePoint (مطلوب).
            drive_id (str): معرف المكتبة/الـ drive. إن لم يُمرَّر،
                يُجلب الـ drive الافتراضي للموقع.
            folder_path (str): مسار المجلد داخل المكتبة
                (افتراضيًا: جذر المكتبة).
            top (int): عدد النتائج (افتراضيًا 50).
        """
        site_id = kw.get("site_id")
        if not site_id:
            raise ConnectorError("SharePoint: list_files يتطلب 'site_id'")
        drive_id = kw.get("drive_id")
        folder_path: str = kw.get("folder_path", "/").strip() or "/"
        top = int(kw.get("top", 50))

        # جلب drive الافتراضي للموقع إن لم يُمرَّر
        if not drive_id:
            drive_data = await self._graph_get(f"/sites/{site_id}/drive")
            drive_id = drive_data.get("id")
            if not drive_id:
                raise ConnectorError(
                    f"SharePoint: تعذّر جلب الـ drive الافتراضي للموقع {site_id}",
                )

        # بناء مسار API: /drives/{drive_id}/root:{folder_path}:/children
        # أو /drives/{drive_id}/items/{item_id}/children للمجلدات الجذر
        if folder_path in ("/", ""):
            path_segment = "/root/children"
        else:
            # تطبيع المسار: يجب أن يبدأ بـ /
            normalized = folder_path if folder_path.startswith("/") else f"/{folder_path}"
            path_segment = f"/root:{normalized}:/children"

        params = {
            "$top": str(max(1, min(top, 1000))),
            "$select": "id,name,size,file,folder,lastModifiedDateTime,webUrl",
            "$orderby": "name asc",
        }
        data = await self._graph_get(
            f"/drives/{drive_id}{path_segment}", params=params,
        )
        return {
            "site_id": site_id,
            "drive_id": drive_id,
            "folder_path": folder_path,
            "count": len(data.get("value", [])),
            "files": data.get("value", []),
        }

    async def _download_file(self, **kw: Any) -> dict[str, Any]:
        """تنزيل محتوى ملف ثنائي من SharePoint.

        Args (via kwargs):
            drive_id (str): معرف المكتبة.
            item_id (str): معرف الملف. (بديل: site_id + path)
            site_id (str): معرف الموقع (بديل عن drive_id).
            path (str): مسار الملف داخل المكتبة (بديل عن item_id).

        Returns:
            {"name": str, "size": int, "content_type": str,
             "content_base64": str}  — المحتوى مُرمَّز base64 للنقل الآمن.
        """
        drive_id = kw.get("drive_id")
        item_id = kw.get("item_id")
        site_id = kw.get("site_id")
        path = kw.get("path")

        if drive_id and item_id:
            url = f"/drives/{drive_id}/items/{item_id}/content"
        elif drive_id and path:
            normalized = path if path.startswith("/") else f"/{path}"
            url = f"/drives/{drive_id}/root:{normalized}:/content"
        elif site_id and path:
            normalized = path if path.startswith("/") else f"/{path}"
            url = f"/sites/{site_id}/drive/root:{normalized}:/content"
        else:
            raise ConnectorError(
                "SharePoint: download_file يتطلب (drive_id + item_id) "
                "أو (drive_id + path) أو (site_id + path)",
            )

        # جلب معلومات الملف أولاً
        meta_url = url.rsplit("/content", 1)[0]
        try:
            meta = await self._graph_get(meta_url)
        except ConnectorError:
            meta = {}

        # تنزيل المحتوى الثنائي
        if self._client is None:
            raise ConnectorError("SharePoint: العميل غير مهيأ")
        await self._ensure_token()
        try:
            response = await self._client.get(self._graph_url(url))
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"SharePoint: فشل تنزيل الملف: {exc}",
            ) from exc
        if response.status_code >= 400:
            raise ConnectorError(
                f"SharePoint: خطأ تنزيل الملف (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )
        content_b64 = base64.b64encode(response.content).decode("ascii")
        return {
            "name": meta.get("name", path or item_id or "unknown"),
            "size": meta.get("size", len(response.content)),
            "content_type": response.headers.get(
                "content-type", "application/octet-stream",
            ),
            "content_base64": content_b64,
        }

    async def _upload_file(self, **kw: Any) -> dict[str, Any]:
        """رفع ملف إلى مكتبة مستندات SharePoint.

        للملفات الأصغر من 4MB يستخدم رفعًا مباشرًا (PUT /content).
        للملفات الأكبر يُنصح باستخدام جلسة رفع (createUploadSession)
        لكنه خارج نطاق هذا الموصل.

        Args (via kwargs):
            drive_id (str): معرف المكتبة (مطلوب إن لم يُمرَّر site_id).
            site_id (str): معرف الموقع (بديل — يستخدم الـ drive الافتراضي).
            path (str): مسار الوجهة داخل المكتبة بما في ذلك اسم الملف.
            content_base64 (str): محتوى الملف مُرمَّز base64.
            content_type (str): نوع MIME (افتراضيًا application/octet-stream).

        Returns:
            بيانات الملف المُنشأ (id, name, webUrl, size).
        """
        drive_id = kw.get("drive_id")
        site_id = kw.get("site_id")
        path = kw.get("path")
        content_b64 = kw.get("content_base64")
        if not path or not content_b64:
            raise ConnectorError(
                "SharePoint: upload_file يتطلب 'path' و 'content_base64'",
            )

        # فك ترميز المحتوى
        try:
            content = base64.b64decode(content_b64)
        except Exception as exc:
            raise ConnectorError(
                f"SharePoint: فشل فك ترميز base64: {exc}",
            ) from exc

        # حد أماني للرفع المباشر: 4MB (حد Graph API)
        if len(content) > 4 * 1024 * 1024:
            raise ConnectorError(
                "SharePoint: الملف يتجاوز 4MB — استخدم createUploadSession "
                "(غير مدعوم في هذا الموصل)",
            )

        # جلب drive_id من site_id إن لزم
        if not drive_id and site_id:
            drive_data = await self._graph_get(f"/sites/{site_id}/drive")
            drive_id = drive_data.get("id")
        if not drive_id:
            raise ConnectorError(
                "SharePoint: upload_file يتطلب 'drive_id' أو 'site_id'",
            )

        normalized = path if path.startswith("/") else f"/{path}"
        url = f"/drives/{drive_id}/root:{normalized}:/content"
        content_type = kw.get(
            "content_type", "application/octet-stream",
        )

        if self._client is None:
            raise ConnectorError("SharePoint: العميل غير مهيأ")
        await self._ensure_token()
        try:
            response = await self._client.put(
                self._graph_url(url),
                content=content,
                headers={
                    "Content-Type": content_type,
                    "Authorization": f"Bearer {self._access_token}",
                },
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"SharePoint: فشل رفع الملف: {exc}",
            ) from exc
        return self._handle_response(response, url, "PUT")

    async def _search_files(self, **kw: Any) -> dict[str, Any]:
        """البحث في ملفات SharePoint وإرجاعها مُنسَّقة.

        Args (via kwargs):
            query (str): نص البحث.
            site_id (str): تقييد البحث على موقع محدد.
            top (int): عدد النتائج (افتراضيًا 25).
        """
        query = kw.get("query")
        if not query:
            raise ConnectorError("SharePoint: search_files يتطلب 'query'")
        hits = await self.search(
            query,
            entity_types=["driveItem", "listItem"],
            site_id=kw.get("site_id"),
            top=int(kw.get("top", 25)),
        )
        return {
            "query": query,
            "count": len(hits),
            "results": hits,
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
            "protocol": "Microsoft Graph REST API",
            "graph_api_version": self.GRAPH_API_VERSION,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "download": True,
                "upload": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "required_scopes": [
                "Sites.Read.All",
                "Files.Read.All",
                "Files.ReadWrite.All",
            ],
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:sharepoint:read",
            "connector:sharepoint:write",
            "documents:read",
            "documents:write",
        ]
