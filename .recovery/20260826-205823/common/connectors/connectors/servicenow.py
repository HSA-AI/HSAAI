"""
موصل ServiceNow (ITSM) لمنصة HSAAI
====================================
يتيح هذا الموصل الوصول إلى ServiceNow عبر Table API
(/api/now/table/) مع مصادقة Basic Auth (username:password).

الإجراءات المدعومة:
    - create_incident        : إنشاء تذكرة incident جديدة
    - get_incident           : جلب incident بواسطة sys_id
    - update_incident        : تحديث incident موجود
    - list_incidents         : سرد الـ incidents مع فلترة
    - create_change_request  : إنشاء طلب تغيير (change_request)
    - search_kb              : البحث في قاعدة المعرفة (Knowledge Base)

الاستخدام:
    cfg = ConnectorConfig(
        name="servicenow",
        display_name="Corporate ServiceNow",
        category="ITSM",
        base_url="https://instance.service-now.com",
        auth_strategy=AuthStrategy.BASIC,
        secrets={
            "username": "...",
            "password": "...",
        },
    )
    connector = ServiceNowConnector(cfg)
    await connector.connect()
    inc = await connector.call("create_incident", short_description="...", urgency="2")
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


@connector("servicenow", version="1.0.0", category="ITSM")
class ServiceNowConnector(BaseConnector):
    """موصل ServiceNow (ITSM) عبر Table API و Basic Auth."""

    #: مسار Table API الافتراضي
    TABLE_API_PATH: str = "/api/now/table"

    #: مسار بحث قاعدة المعرفة
    KB_SEARCH_PATH: str = "/api/now/kb/search"

    #: الجداول الافتراضية
    INCIDENT_TABLE: str = "incident"
    CHANGE_REQUEST_TABLE: str = "change_request"
    KB_TABLE: str = "kb_knowledge"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "create_incident",
        "get_incident",
        "update_incident",
        "list_incidents",
        "create_change_request",
        "search_kb",
    )

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._username: str = self._get_secret("username", "")
        self._password: str = self._get_secret("password", "")
        self._basic_auth_header: Optional[str] = None
        # التأكد من خلو base_url من الشرطة المائلة الزائدة
        self._base_url: str = self.config.base_url.rstrip("/")
        # إصدار Table API قابل للتجاوز من الإعدادات
        self._api_version: str = getattr(self.config, "api_version", "now") or "now"

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
        """تجهيز ترويسة Basic Auth لاستخدامها في كل طلب إلى ServiceNow.

        يستخدم ServiceNow Table API مصادقة HTTP Basic مع username/password
        أو مع client_id/client_secret لتطبيقات OAuth المسجلة. هنا نستخدم
        Basic Auth القياسي مع بيانات الاعتماد من secrets.

        Raises:
            ConnectorAuthenticationError: عند فقدان username أو password.
        """
        if not self._username or not self._password:
            raise ConnectorAuthenticationError(
                "ServiceNow: username و password مطلوبان لمصادقة Basic",
            )

        credentials = f"{self._username}:{self._password}".encode("utf-8")
        encoded = base64.b64encode(credentials).decode("ascii")
        self._basic_auth_header = f"Basic {encoded}"

        # تحديث ترويسات العميل إن كان مهيأً
        if self._client is not None:
            self._client.headers.update({
                "Authorization": self._basic_auth_header,
                "Accept": "application/json",
                "Content-Type": "application/json",
            })

        logger.info("ServiceNow: تم تجهيز ترويسة Basic Auth للمستخدم '%s'", self._username)

    def _ensure_auth(self) -> None:
        """التأكد من وجود ترويسة المصادقة وتحديثها على العميل."""
        if not self._basic_auth_header:
            raise ConnectorAuthenticationError(
                "ServiceNow: المصادقة غير مهيأة — استدعِ connect() أولاً",
            )
        if self._client is not None and "Authorization" not in self._client.headers:
            self._client.headers.update({
                "Authorization": self._basic_auth_header,
                "Accept": "application/json",
                "Content-Type": "application/json",
            })

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة ServiceNow عبر طلب خفيف على جدول sys_user.

        نطلب سجلًا واحدًا فقط للتحقق من صحة بيانات الاعتماد ووصول الشبكة.
        """
        start = time.monotonic()
        try:
            if self._client is None:
                raise ConnectorError("ServiceNow: العميل غير مهيأ — استدعِ connect() أولاً")
            self._ensure_auth()
            response = await self._client.get(
                f"{self.TABLE_API_PATH}/sys_user",
                params={"sysparm_limit": "1", "sysparm_exclude_reference_link": "true"},
            )
            latency_ms = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 200, "endpoint": "sys_user"},
                )
            if response.status_code == 401:
                return HealthResult(
                    status=HealthStatus.UNHEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 401, "reason": "invalid_credentials"},
                    error="بيانات اعتماد غير صالحة",
                )
            if response.status_code == 403:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 403, "reason": "insufficient_permissions"},
                    error="صلاحيات غير كافية",
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
    async def _table_request(
        self,
        method: str,
        table: str,
        *,
        sys_id: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> Any:
        """تنفيذ طلب على Table API لجدول محدد.

        Args:
            method: HTTP method (GET/POST/PATCH/DELETE/PUT).
            table: اسم الجدول (مثل 'incident').
            sys_id: معرف السجل (للعمليات على سجل محدد).
            params: معاملات الاستعلام (sysparm_*).
            json_body: محتوى الطلب JSON.

        Returns:
            استجابة JSON من ServiceNow.

        Raises:
            ConnectorError: عند فشل الطلب أو استجابة خطأ.
        """
        if self._client is None:
            raise ConnectorError("ServiceNow: العميل غير مهيأ — استدعِ connect() أولاً")
        self._ensure_auth()

        url = f"{self.TABLE_API_PATH}/{table}"
        if sys_id:
            url = f"{url}/{sys_id}"

        try:
            response = await self._client.request(
                method,
                url,
                params=params,
                json=json_body,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"ServiceNow: فشل {method} على {url}: {exc}",
            ) from exc

        return self._handle_response(response, url, method)

    def _handle_response(
        self, response: httpx.Response, url: str, method: str,
    ) -> Any:
        """معالجة استجابة ServiceNow وإرجاع JSON أو رفع خطأ مفهوم."""
        if response.status_code == 204 or response.status_code == 200 and not response.content:
            return {"status": "success", "no_content": True}
        if response.status_code >= 400:
            try:
                error_body = response.json()
                err = error_body.get("error", {})
                err_msg = err.get("message", err.get("detail", response.text[:500]))
                err_code = err.get("code", response.status_code)
            except ValueError:
                err_msg = response.text[:500]
                err_code = response.status_code
            raise ConnectorError(
                f"ServiceNow: خطأ في {method} {url} "
                f"(HTTP {response.status_code}) [{err_code}]: {err_msg}",
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError(
                f"ServiceNow: استجابة غير صالحة JSON من {url}: {exc}",
            ) from exc

    @staticmethod
    def _build_sysparm(params: dict[str, Any]) -> dict[str, str]:
        """تحويل معاملات بيثون إلى sysparm_* المعتمدة في ServiceNow."""
        out: dict[str, str] = {}
        # الأسماء المباشرة
        for key in ("sysparm_query", "sysparm_display_value",
                    "sysparm_exclude_reference_link", "sysparm_view",
                    "sysparm_limit", "sysparm_offset", "sysparm_fields"):
            if key in params and params[key] is not None:
                out[key] = str(params[key])
        # اختصارات شائعة
        if "limit" in params:
            out.setdefault("sysparm_limit", str(params["limit"]))
        if "offset" in params:
            out.setdefault("sysparm_offset", str(params["offset"]))
        if "fields" in params and isinstance(params["fields"], list):
            out.setdefault("sysparm_fields", ",".join(params["fields"]))
        if "display_value" in params:
            out.setdefault("sysparm_display_value", str(params["display_value"]))
        return out

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في incidents و knowledge base في ServiceNow.

        Args:
            query: نص البحث (يدعم ترميز ServiceNow query).
            **kwargs:
                target (str): 'incidents' (افتراضي) أو 'kb' أو 'both'.
                limit (int): عدد النتائج (افتراضيًا 25).

        Returns:
            قائمة بالنتائج الموحدة.
        """
        target: str = kwargs.pop("target", "incidents")
        limit: int = int(kwargs.pop("limit", 25))
        results: list[dict[str, Any]] = []

        if target in ("incidents", "both"):
            # بحث في incidents عبر sysparm_query بترميز LIKE
            encoded = query.replace("'", "''").replace("^", "^EQ^")
            sysparm = self._build_sysparm({
                "sysparm_query": f"short_descriptionLIKE{encoded}^ORdescriptionLIKE{encoded}",
                "limit": limit,
                "display_value": True,
            })
            data = await self._table_request(
                "GET", self.INCIDENT_TABLE, params=sysparm,
            )
            for rec in data.get("result", []):
                results.append({
                    "source": "incident",
                    "sys_id": rec.get("sys_id"),
                    "number": rec.get("number"),
                    "short_description": rec.get("short_description"),
                    "state": rec.get("state"),
                    "priority": rec.get("priority"),
                    "opened_at": rec.get("opened_at"),
                    "url": rec.get("sys_scope") or None,
                })

        if target in ("kb", "both"):
            # بحث في قاعدة المعرفة عبر endpoint مخصص
            if self._client is None:
                raise ConnectorError("ServiceNow: العميل غير مهيأ")
            self._ensure_auth()
            try:
                response = await self._client.get(
                    self.KB_SEARCH_PATH,
                    params={"q": query, "limit": str(limit)},
                )
            except httpx.HTTPError as exc:
                raise ConnectorError(
                    f"ServiceNow: فشل بحث KB: {exc}",
                ) from exc
            kb_data = self._handle_response(response, self.KB_SEARCH_PATH, "GET")
            for rec in kb_data.get("result", kb_data.get("articles", [])):
                results.append({
                    "source": "kb",
                    "sys_id": rec.get("sys_id"),
                    "number": rec.get("number"),
                    "short_description": rec.get("short_description"),
                    "kb_article": rec.get("article_id") or rec.get("id"),
                    "kb_category": rec.get("kb_category"),
                })

        return results

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على ServiceNow.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "create_incident": self._create_incident,
            "get_incident": self._get_incident,
            "update_incident": self._update_incident,
            "list_incidents": self._list_incidents,
            "create_change_request": self._create_change_request,
            "search_kb": self._search_kb,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"ServiceNow: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _create_incident(self, **kw: Any) -> dict[str, Any]:
        """إنشاء incident جديد في ServiceNow.

        Args (via kwargs):
            short_description (str): وصف مختصر (مطلوب).
            description (str): وصف مفصل.
            urgency (str): 1/2/3.
            impact (str): 1/2/3.
            priority (str): 1/2/3/4/5.
            caller_id (str): sys_id أو اسم المستخدم المتصل.
            category (str): تصنيف الحادثة.
            assignment_group (str): مجموعة الإسناد.
            extra (dict): حقول إضافية تُمرَّر كما هي.
        """
        short_description = kw.get("short_description")
        if not short_description:
            raise ConnectorError(
                "ServiceNow: create_incident يتطلب 'short_description'",
            )
        body: dict[str, Any] = {
            "short_description": short_description,
        }
        for field in ("description", "urgency", "impact", "priority",
                      "caller_id", "category", "assignment_group",
                      "subcategory", "contact_type", "state"):
            if field in kw and kw[field] is not None:
                body[field] = kw[field]
        extra = kw.get("extra")
        if isinstance(extra, dict):
            body.update(extra)

        params = {"sysparm_input_display_value": "true"}
        data = await self._table_request(
            "POST", self.INCIDENT_TABLE, json_body=body, params=params,
        )
        result = data.get("result", data)
        logger.info("ServiceNow: تم إنشاء incident %s", result.get("number"))
        return {
            "status": "created",
            "sys_id": result.get("sys_id"),
            "number": result.get("number"),
            "incident": result,
        }

    async def _get_incident(self, **kw: Any) -> dict[str, Any]:
        """جلب incident بواسطة sys_id أو رقمه (number).

        Args (via kwargs):
            sys_id (str): معرف السجل.
            number (str): رقم الحادثة (بديل — يُستخدم للبحث أولاً).
            display_value (bool): إرجاع القيم المعروضة (افتراضيًا True).
        """
        sys_id = kw.get("sys_id")
        number = kw.get("number")
        if not sys_id and not number:
            raise ConnectorError(
                "ServiceNow: get_incident يتطلب 'sys_id' أو 'number'",
            )
        display_value = kw.get("display_value", True)

        if not sys_id and number:
            # البحث بواسطة الرقم للحصول على sys_id
            sysparm = self._build_sysparm({
                "sysparm_query": f"number={number}",
                "limit": 1,
                "display_value": display_value,
            })
            data = await self._table_request(
                "GET", self.INCIDENT_TABLE, params=sysparm,
            )
            results = data.get("result", [])
            if not results:
                raise ConnectorError(
                    f"ServiceNow: لا يوجد incident بالرقم '{number}'",
                )
            return {"incident": results[0]}

        sysparm = self._build_sysparm({"display_value": display_value})
        data = await self._table_request(
            "GET", self.INCIDENT_TABLE, sys_id=sys_id, params=sysparm,
        )
        return {"incident": data.get("result", data)}

    async def _update_incident(self, **kw: Any) -> dict[str, Any]:
        """تحديث incident موجود.

        Args (via kwargs):
            sys_id (str): معرف السجل (مطلوب).
            fields (dict): الحقول المراد تحديثها.
            work_notes (str): ملاحظات عمل تُضاف للسجل.
        """
        sys_id = kw.get("sys_id")
        if not sys_id:
            raise ConnectorError("ServiceNow: update_incident يتطلب 'sys_id'")
        fields: dict[str, Any] = dict(kw.get("fields") or {})
        if "work_notes" in kw and kw["work_notes"]:
            fields["work_notes"] = kw["work_notes"]
        if not fields:
            raise ConnectorError(
                "ServiceNow: update_incident يتطلب 'fields' أو 'work_notes'",
            )
        params = {"sysparm_input_display_value": "true"}
        data = await self._table_request(
            "PATCH", self.INCIDENT_TABLE, sys_id=sys_id,
            json_body=fields, params=params,
        )
        result = data.get("result", data)
        return {"status": "updated", "sys_id": sys_id, "incident": result}

    async def _list_incidents(self, **kw: Any) -> dict[str, Any]:
        """سرد الـ incidents مع دعم الفلترة والترقيم.

        Args (via kwargs):
            query (str): استعلام ServiceNow (sysparm_query) اختياري.
            limit (int): عدد النتائج (افتراضيًا 50).
            offset (int): إزاحة للترقيم.
            fields (list[str]): الحقول المُعادة.
            display_value (bool): إرجاع القيم المعروضة.
            state (str): فلتر سريع على الحالة.
            active (bool): فلتر سريع على النشاط.
        """
        sysparm_query = kw.get("query", "")
        if "state" in kw and kw["state"] is not None:
            sysparm_query = (
                f"{sysparm_query}^{sysparm_query}state={kw['state']}"
                if sysparm_query else f"state={kw['state']}"
            )
        if "active" in kw and kw["active"] is not None:
            active_val = "true" if kw["active"] else "false"
            sysparm_query = (
                f"{sysparm_query}^active={active_val}"
                if sysparm_query else f"active={active_val}"
            )
        params = self._build_sysparm({
            "sysparm_query": sysparm_query or None,
            "limit": kw.get("limit", 50),
            "offset": kw.get("offset", 0),
            "fields": kw.get("fields"),
            "display_value": kw.get("display_value", True),
        })
        data = await self._table_request(
            "GET", self.INCIDENT_TABLE, params=params,
        )
        return {
            "count": len(data.get("result", [])),
            "incidents": data.get("result", []),
        }

    async def _create_change_request(self, **kw: Any) -> dict[str, Any]:
        """إنشاء طلب تغيير (change_request) في ServiceNow.

        Args (via kwargs):
            short_description (str): وصف مختصر (مطلوب).
            description (str): وصف مفصل.
            type (str): normal/standard/emergency.
            priority (str): 1-5.
            assignment_group (str): مجموعة الإسناد.
            risk (str): مستوى المخاطر.
            extra (dict): حقول إضافية.
        """
        short_description = kw.get("short_description")
        if not short_description:
            raise ConnectorError(
                "ServiceNow: create_change_request يتطلب 'short_description'",
            )
        body: dict[str, Any] = {"short_description": short_description}
        for field in ("description", "type", "priority",
                      "assignment_group", "risk", "impact", "urgency",
                      "category", "state", "assigned_to"):
            if field in kw and kw[field] is not None:
                body[field] = kw[field]
        extra = kw.get("extra")
        if isinstance(extra, dict):
            body.update(extra)
        params = {"sysparm_input_display_value": "true"}
        data = await self._table_request(
            "POST", self.CHANGE_REQUEST_TABLE, json_body=body, params=params,
        )
        result = data.get("result", data)
        logger.info(
            "ServiceNow: تم إنشاء change_request %s", result.get("number"),
        )
        return {
            "status": "created",
            "sys_id": result.get("sys_id"),
            "number": result.get("number"),
            "change_request": result,
        }

    async def _search_kb(self, **kw: Any) -> dict[str, Any]:
        """البحث في قاعدة المعرفة في ServiceNow.

        Args (via kwargs):
            query (str): نص البحث.
            limit (int): عدد النتائج (افتراضيًا 25).
        """
        query = kw.get("query")
        if not query:
            raise ConnectorError("ServiceNow: search_kb يتطلب 'query'")
        results = await self.search(
            query, target="kb", limit=int(kw.get("limit", 25)),
        )
        return {"query": query, "count": len(results), "results": results}

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
            "protocol": "ServiceNow Table API (REST)",
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "read": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "tables": [
                self.INCIDENT_TABLE,
                self.CHANGE_REQUEST_TABLE,
                self.KB_TABLE,
            ],
            "required_roles": ["itil", "knowledge"],
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:servicenow:read",
            "connector:servicenow:write",
            "itsm:incident:create",
            "itsm:incident:read",
            "itsm:incident:update",
            "itsm:change:create",
            "kb:search",
        ]
