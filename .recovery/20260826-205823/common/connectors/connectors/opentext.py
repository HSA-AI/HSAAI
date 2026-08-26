"""
موصل OpenText Document Management لمنصة HSAAI
===============================================
يتيح هذا الموصل الوصول إلى OpenText Content Server (OTCS) عبر واجهة
REST API v2 مع مصادقة OTCS Ticket (نظام التوكن الخاص بـ OpenText).

نقطة النهاية الأساسية:
    {base_url}/api/v2/

آلية المصادقة OTCS Ticket:
    1. POST /api/v2/auth/apikey  (إن كان لديك API key مُولَّد مسبقًا)
    2. POST /api/v2/auth/credentials (باسم مستخدم/كلمة مرور) — احتياطيًا
    تُرجع الاستجابة تذكرة OTCS تُستخدم في ترويسة OTCSTicket لكل الطلبات.

الإجراءات المدعومة:
    - list_documents    : سرد المستندات في مجلد (subnodes)
    - get_document      : جلب بيانات مستند + تنزيل المحتوى (اختياري)
    - upload_document   : رفع مستند إلى مجلد
    - search_documents  : البحث في المستندات عبر Full-Text Search

search() يستخدم نقطة نهاية /api/v2/search مع استعلام FTS (Full-Text Search).

الاستخدام:
    cfg = ConnectorConfig(
        name="opentext",
        display_name="Corporate OpenText CS",
        category="Documents",
        base_url="https://otcs.corp.local",
        auth_strategy=AuthStrategy.API_KEY,
        secrets={
            "api_key": "GENERATED-API-KEY-XXXX",  # أو
            # "username": "...", "password": "...",  # fallback
        },
    )
    connector = OpenTextConnector(cfg)
    await connector.connect()
    docs = await connector.call("list_documents", node_id=2000, limit=50)
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


@connector("opentext", version="1.0.0", category="Documents")
class OpenTextConnector(BaseConnector):
    """موصل OpenText Content Server عبر REST API v2 و OTCS Ticket."""

    #: مسار REST API v2 الافتراضي
    DEFAULT_API_PATH: str = "/api/v2"

    #: اسم ترويسة OTCS Ticket
    OTCS_TICKET_HEADER: str = "OTCSTicket"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "list_documents",
        "get_document",
        "upload_document",
        "search_documents",
    )

    #: أنواع العقد في OpenText
    NODE_TYPES: dict[int, str] = {
        0: "Folder",
        144: "Document",
        749: "Folder (Project)",
        1: "Generation",
        136: "URL",
        4: "Discussion",
        13: "Category",
    }

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._otcs_ticket: Optional[str] = None
        self._ticket_expires_at: float = 0.0

        # مصادقة API Key (مُفضَّلة) أو اسم مستخدم/كلمة مرور (احتياطية)
        self._api_key: str = self._get_secret("api_key", "")
        self._username: str = self._get_secret("username", "")
        self._password: str = self._get_secret("password", "")
        self._api_path: str = getattr(
            self.config, "api_path", self.DEFAULT_API_PATH,
        )
        # مدة صلاحية التذكرة الافتراضية (8 ساعات بالثواني، OTCS الافتراضي)
        self._ticket_ttl: int = int(getattr(self.config, "ticket_ttl", 8 * 3600))
        self._otcs_base: str = self.config.base_url.rstrip("/")

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
        """مصادقة مع OpenText Content Server وجلب OTCS Ticket.

        يستخدم API Key (المُفضَّلة) إن وُجدت، خلاف ذلك يستخدم اسم المستخدم
        وكلمة المرور. تذكرة OTCS تُستخدم في ترويسة OTCSTicket لكل الطلبات.

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل المصادقة.
        """
        if not self._api_key and not (self._username and self._password):
            raise ConnectorAuthenticationError(
                "OpenText: 'api_key' مطلوبة للمصادقة (أو 'username'+'password' كاحتياطي)",
            )

        auth_url = f"{self._otcs_base}{self._api_path}/auth"
        async with httpx.AsyncClient(timeout=self.config.connect_timeout) as auth_client:
            try:
                if self._api_key:
                    # مصادقة API Key: POST /api/v2/auth/apikey
                    response = await auth_client.post(
                        f"{auth_url}/apikey",
                        json={"key": self._api_key},
                        headers={"Accept": "application/json"},
                    )
                else:
                    # مصادقة credentials: POST /api/v2/auth/credentials
                    response = await auth_client.post(
                        f"{auth_url}/credentials",
                        json={
                            "username": self._username,
                            "password": self._password,
                        },
                        headers={"Accept": "application/json"},
                    )
            except httpx.HTTPError as exc:
                raise ConnectorAuthenticationError(
                    f"OpenText: فشل الاتصال بخادم المصادقة: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"OpenText: فشل المصادقة (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        ticket_data = response.json()
        self._otcs_ticket = ticket_data.get("ticket")
        if not self._otcs_ticket:
            raise ConnectorAuthenticationError(
                "OpenText: لم يُرجع الخادم OTCS ticket",
            )

        # OTCS tickets صالحة عادة 8 ساعات افتراضيًا
        self._ticket_expires_at = time.time() + self._ticket_ttl

        if self._client is not None:
            self._client.headers.update({
                self.OTCS_TICKET_HEADER: self._otcs_ticket,
                "Accept": "application/json",
            })

        logger.info(
            "OpenText: تم الحصول على OTCS Ticket (ينتهي خلال %ss)",
            self._ticket_ttl,
        )

    async def _ensure_ticket(self) -> None:
        """تجديد OTCS Ticket تلقائيًا عند اقتراب انتهاء صلاحيته."""
        if self._otcs_ticket is None or time.time() >= self._ticket_expires_at:
            await self.authenticate()

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة OpenText Content Server عبر طلب /api/v2/nodes/0 (الجذر).

        Returns:
            HealthResult مع حالة الخدمة وزمن الاستجابة.
        """
        start = time.monotonic()
        try:
            await self._ensure_ticket()
            if self._client is None:
                raise ConnectorError("OpenText: العميل غير مهيأ — استدعِ connect() أولاً")
            # node 0 = Enterprise Workspace (الجذر)
            response = await self._client.get(
                f"{self._api_path}/nodes/0",
                params={"fields": "id,name"},
            )
            latency_ms = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 200, "node": "0"},
                )
            if response.status_code == 401:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 401, "reason": "ticket_expired"},
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
    #  OTCS REST Helpers
    # ───────────────────────────────────────────────────────────────────
    async def _otcs_get(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """تنفيذ طلب GET على OTCS REST API.

        Args:
            path: المسار بعد /api/v2/ (مثل 'nodes/2000').
            params: معاملات الاستعلام.

        Returns:
            قاموس JSON الخام من OTCS.

        Raises:
            ConnectorError: عند فشل الطلب.
        """
        if self._client is None:
            raise ConnectorError("OpenText: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token_safe()
        try:
            response = await self._client.get(
                f"{self._api_path}/{path}",
                params=params,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"OpenText: فشل GET على {path}: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"OpenText: خطأ REST في GET {path} "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )
        return response.json()

    async def _ensure_token_safe(self) -> None:
        """غلاف آمن لـ _ensure_ticket لا يرفع ConnectorAuthenticationError
        بصمت ضمن السياقات الداخلية."""
        try:
            await self._ensure_ticket()
        except ConnectorAuthenticationError:
            raise

    async def _otcs_post(
        self,
        path: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
        data: Optional[Any] = None,
        files: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """تنفيذ طلب POST على OTCS REST API.

        Args:
            path: المسار بعد /api/v2/.
            json_body: حمولة JSON.
            data: بيانات نموذج (form-data).
            files: ملفات multipart (للرفع).
            params: معاملات الاستعلام.

        Returns:
            قاموس JSON الخام من OTCS.

        Raises:
            ConnectorError: عند فشل الطلب.
        """
        if self._client is None:
            raise ConnectorError("OpenText: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_ticket()
        try:
            response = await self._client.post(
                f"{self._api_path}/{path}",
                json=json_body, data=data, files=files, params=params,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"OpenText: فشل POST على {path}: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"OpenText: خطأ REST في POST {path} "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )
        if response.content:
            try:
                return response.json()
            except ValueError:
                return {"status": "ok", "raw": response.text}
        return {"status": "ok"}

    async def _otcs_download(self, path: str) -> bytes:
        """تنزيل محتوى ثنائي من OTCS (للمستندات).

        Args:
            path: المسار بعد /api/v2/ (مثل 'nodes/2000/content').

        Returns:
            bytes: محتوى الملف.

        Raises:
            ConnectorError: عند فشل التنزيل.
        """
        if self._client is None:
            raise ConnectorError("OpenText: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_ticket()
        try:
            response = await self._client.get(f"{self._api_path}/{path}")
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"OpenText: فشل تنزيل {path}: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"OpenText: خطأ تنزيل {path} "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )
        return response.content

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في مستندات OpenText عبر Full-Text Search (FTS).

        يستخدم نقطة النهاية /api/v2/search مع المعامل 'query'.
        يدعم صيغة OpenText FTS المتقدمة (boolean, proximity, ...).

        Args:
            query: نص البحث FTS.
            **kwargs:
                node_id (int): قصر البحث على مجلد محدد (اختياري).
                limit (int): عدد النتائج (افتراضيًا 50).
                search_type (str): 'search' (افتراضي) أو 'search_promoted'.
                fields (list[str]): الحقول المُسترجَعة.

        Returns:
            قائمة بنتائج البحث (كل عنصر يحتوي على data Href, name, ...).
        """
        limit: int = int(kwargs.pop("limit", 50))
        node_id: Optional[int] = kwargs.pop("node_id", None)
        search_type: str = kwargs.pop("search_type", "search")
        fields: Optional[list[str]] = kwargs.pop("fields", None)

        if not query.strip():
            return []

        params: dict[str, Any] = {
            "query": query,
            "limit": str(max(1, min(limit, 200))),
        }
        if node_id is not None:
            params["scope"] = str(node_id)
        if fields:
            params["fields"] = ",".join(fields)

        try:
            result = await self._otcs_get(search_type, params=params)
        except ConnectorError:
            return []

        # OTCS /search يعيد: {"results": [{"data": {...}}, ...]}
        results = result.get("results", []) if isinstance(result, dict) else []
        return results

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على OpenText Content Server.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "list_documents": self._list_documents,
            "get_document": self._get_document,
            "upload_document": self._upload_document,
            "search_documents": self._search_documents,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"OpenText: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _list_documents(self, **kw: Any) -> dict[str, Any]:
        """سرد المستندات والعقد الفرعية في مجلد.

        Args (via kwargs):
            node_id (int): معرف المجلد (إلزامي).
            limit (int): عدد النتائج (افتراضيًا 50).
            page (int): رقم الصفحة (افتراضيًا 1).
            fields (list[str]): الحقول المُسترجَعة.
            type_filter (list[int]): تصفية حسب نوع العقدة (مثلاً [144] للمستندات).

        Raises:
            ConnectorError: عند فقدان node_id.
        """
        node_id: Optional[int] = kw.get("node_id")
        if node_id is None:
            raise ConnectorError("OpenText: 'node_id' إلزامي لإجراء list_documents")
        limit: int = int(kw.get("limit", 50))
        page: int = int(kw.get("page", 1))
        fields: Optional[list[str]] = kw.get("fields") or [
            "id", "name", "type", "type_name", "size", "modified",
            "modified_by", "parent_id", "container",
        ]
        type_filter: Optional[list[int]] = kw.get("type_filter")

        params: dict[str, Any] = {
            "limit": str(max(1, min(limit, 200))),
            "page": str(page),
            "fields": ",".join(fields),
        }
        if type_filter:
            params["type"] = ",".join(str(t) for t in type_filter)

        result = await self._otcs_get(f"nodes/{node_id}/nodes", params=params)
        # OTCS يعيد: {"data": [...], "range": {...}, "total_count": n}
        data = result.get("data", []) if isinstance(result, dict) else []
        return {
            "node_id": node_id,
            "count": len(data),
            "items": data,
            "total_count": result.get("total_count") if isinstance(result, dict) else None,
            "page": page,
        }

    async def _get_document(self, **kw: Any) -> dict[str, Any]:
        """جلب بيانات مستند (واختياريًا تنزيل محتواه).

        Args (via kwargs):
            node_id (int): معرف المستند (إلزامي).
            download_content (bool): تنزيل المحتوى الثنائي (افتراضيًا False).
            fields (list[str]): الحقول المُسترجَعة.

        Returns:
            قاموس يحتوي على 'metadata' و (إن طُلب) 'content' (base64-encoded).

        Raises:
            ConnectorError: عند فقدان node_id أو عدم العثور على المستند.
        """
        node_id: Optional[int] = kw.get("node_id")
        if node_id is None:
            raise ConnectorError("OpenText: 'node_id' إلزامي لإجراء get_document")
        download: bool = bool(kw.get("download_content", False))
        fields: Optional[list[str]] = kw.get("fields") or [
            "id", "name", "type", "type_name", "size", "modified",
            "modified_by", "parent_id", "description", "categories",
        ]

        metadata = await self._otcs_get(
            f"nodes/{node_id}", params={"fields": ",".join(fields)},
        )
        response: dict[str, Any] = {"metadata": metadata}

        if download:
            content = await self._otcs_download(f"nodes/{node_id}/content")
            import base64
            response["content_base64"] = base64.b64encode(content).decode("ascii")
            response["content_size"] = len(content)

        return response

    async def _upload_document(self, **kw: Any) -> dict[str, Any]:
        """رفع مستند إلى مجلد في OpenText.

        Args (via kwargs):
            parent_id (int): معرف المجلد الأب (إلزامي).
            name (str): اسم المستند (إلزامي).
            file_path (str): المسار المحلي للملف (يُستخدم إن لم يُقدَّم content).
            content (bytes): محتوى الملف الثنائي (بديل عن file_path).
            description (str): وصف المستند (اختياري).
            categories (dict): قيم التصنيفات (اختياري).

        Raises:
            ConnectorError: عند فقدان الحقول الإلزامية أو فشل الرفع.
        """
        parent_id: Optional[int] = kw.get("parent_id")
        name: Optional[str] = kw.get("name")
        if parent_id is None or not name:
            raise ConnectorError(
                "OpenText: 'parent_id' و 'name' إلزامية لرفع مستند",
            )

        # قراءة المحتوى من المسار أو من المعامل المباشر
        content: Optional[bytes] = kw.get("content")
        file_path: Optional[str] = kw.get("file_path")
        if content is None and file_path:
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
            except OSError as exc:
                raise ConnectorError(
                    f"OpenText: فشل قراءة الملف '{file_path}': {exc}",
                ) from exc
        if content is None:
            raise ConnectorError(
                "OpenText: يجب توفير 'content' (bytes) أو 'file_path' لرفع مستند",
            )

        # OTCS يتوقع multipart/form-data مع file (role=file) و name
        form_data: dict[str, Any] = {
            "type": "144",  # Document
            "name": name,
            "parent_id": str(parent_id),
        }
        if kw.get("description"):
            form_data["description"] = kw["description"]

        files = {"file": (name, content, "application/octet-stream")}
        try:
            result = await self._otcs_post(
                "nodes", data=form_data, files=files,
            )
        except ConnectorError as exc:
            raise ConnectorError(
                f"OpenText: فشل رفع المستند '{name}' إلى المجلد {parent_id}: {exc}",
            ) from exc

        return {
            "status": "uploaded",
            "name": name,
            "parent_id": parent_id,
            "node": result.get("data") or result,
        }

    async def _search_documents(self, **kw: Any) -> dict[str, Any]:
        """البحث المتقدم في مستندات OpenText (مغلف لـ search).

        Args (via kwargs):
            query (str): استعلام FTS (إلزامي).
            node_id (int): قصر البحث على مجلد.
            limit (int): عدد النتائج.
            fields (list[str]): الحقول المُسترجَعة.
        """
        query: Optional[str] = kw.get("query")
        if not query:
            raise ConnectorError("OpenText: 'query' إلزامي لإجراء search_documents")
        results = await self.search(query, **kw)
        return {
            "query": query,
            "count": len(results),
            "results": results,
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
            "protocol": "OpenText Content Server REST API v2 (OTCS Ticket)",
            "api_path": self._api_path,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "read": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "auth_methods": ["api_key", "credentials"],
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل (RBAC)."""
        return self.config.required_permissions or [
            "connector:opentext:read",
            "connector:opentext:write",
            "dms:documents:read",
            "dms:documents:write",
            "dms:search:execute",
        ]
