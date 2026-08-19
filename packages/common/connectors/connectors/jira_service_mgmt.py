"""
موصل Jira Service Management لمنصة HSAAI
==========================================
يتيح هذا الموصل الوصول إلى Jira Service Management (JSM) عبر
REST API v3 مع مصادقة API Token (Basic Auth: email:api_token).

الإجراءات المدعومة:
    - create_ticket : إنشاء تذكرة طلب عميل (Customer Request)
    - get_ticket    : جلب تذكرة بواسطة issueId/issueKey
    - update_ticket : تحديث تذكرة موجودة (PUT على /rest/api/3/issue)
    - list_tickets  : سرد التذاكر مع فلترة JQL
    - add_comment   : إضافة تعليق على تذكرة
    - get_sla       : جلب معلومات SLA لتذكرة JSM

search() ينفذ بحث JQL عبر /rest/api/3/search.

الاستخدام:
    cfg = ConnectorConfig(
        name="jira_service_management",
        display_name="Corporate JSM",
        category="ITSM",
        base_url="https://your-domain.atlassian.net",
        auth_strategy=AuthStrategy.BASIC,
        secrets={
            "email": "user@company.com",
            "api_token": "...",
        },
    )
    connector = JiraServiceManagementConnector(cfg)
    await connector.connect()
    ticket = await connector.call("create_ticket", summary="...", service_desk_id=1, request_type_id=10)
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


@connector("jira_service_management", version="1.0.0", category="ITSM")
class JiraServiceManagementConnector(BaseConnector):
    """موصل Jira Service Management عبر REST API v3 و API Token."""

    #: مسارات API
    JSM_API_PATH: str = "/rest/servicedeskapi"
    REST_API_V3_PATH: str = "/rest/api/3"

    #: ترويسة مطلوبة لـ JSM API
    JSM_ACCEPT_PROFILE: str = "application/json"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "create_ticket",
        "get_ticket",
        "update_ticket",
        "list_tickets",
        "add_comment",
        "get_sla",
    )

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._email: str = self._get_secret("email", "")
        self._api_token: str = self._get_secret("api_token", "")
        self._basic_auth_header: Optional[str] = None
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
        """تجهيز ترويسة Basic Auth لمصادقة Jira API Token.

        تستخدم Atlassian Cloud مصادقة Basic Auth مع البريد الإلكتروني
        كمستخدم و API Token كلمة مرور.

        Raises:
            ConnectorAuthenticationError: عند فقدان email أو api_token.
        """
        if not self._email or not self._api_token:
            raise ConnectorAuthenticationError(
                "Jira Service Management: email و api_token مطلوبان "
                "لمصادقة API Token",
            )

        credentials = f"{self._email}:{self._api_token}".encode("utf-8")
        encoded = base64.b64encode(credentials).decode("ascii")
        self._basic_auth_header = f"Basic {encoded}"

        if self._client is not None:
            self._client.headers.update({
                "Authorization": self._basic_auth_header,
                "Accept": self.JSM_ACCEPT_PROFILE,
                "Content-Type": "application/json",
                "X-ExperimentalApi": "opt-in",  # مطلوب لبعض endpoints في JSM
            })

        logger.info(
            "Jira Service Management: تم تجهيز API Token للمستخدم '%s'",
            self._email,
        )

    def _ensure_auth(self) -> None:
        """التأكد من وجود ترويسة المصادقة."""
        if not self._basic_auth_header:
            raise ConnectorAuthenticationError(
                "Jira Service Management: المصادقة غير مهيأة — استدعِ connect() أولاً",
            )
        if self._client is not None and "Authorization" not in self._client.headers:
            self._client.headers.update({
                "Authorization": self._basic_auth_header,
                "Accept": self.JSM_ACCEPT_PROFILE,
                "Content-Type": "application/json",
                "X-ExperimentalApi": "opt-in",
            })

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة Jira عبر استدعاء /rest/api/3/serverInfo (خفيف وغير مُكلِّف)."""
        start = time.monotonic()
        try:
            if self._client is None:
                raise ConnectorError(
                    "Jira Service Management: العميل غير مهيأ — استدعِ connect() أولاً",
                )
            self._ensure_auth()
            response = await self._client.get(f"{self.REST_API_V3_PATH}/serverInfo")
            latency_ms = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                info = {}
                try:
                    info = response.json()
                except ValueError:
                    pass
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={
                        "http_status": 200,
                        "server_title": info.get("serverTitle"),
                        "version": info.get("version"),
                    },
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
    async def _rest_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> Any:
        """تنفيذ طلب على REST API v3 (عام)."""
        return await self._raw_request(
            f"{self.REST_API_V3_PATH}{path}", method, params=params, json_body=json_body,
        )

    async def _jsm_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> Any:
        """تنفيذ طلب على JSM Service Desk API."""
        return await self._raw_request(
            f"{self.JSM_API_PATH}{path}", method, params=params, json_body=json_body,
        )

    async def _raw_request(
        self,
        url: str,
        method: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> Any:
        """تنفيذ طلب HTTP خام مع معالجة الأخطاء."""
        if self._client is None:
            raise ConnectorError(
                "Jira Service Management: العميل غير مهيأ — استدعِ connect() أولاً",
            )
        self._ensure_auth()
        try:
            response = await self._client.request(
                method, url, params=params, json=json_body,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"Jira Service Management: فشل {method} على {url}: {exc}",
            ) from exc
        return self._handle_response(response, url, method)

    def _handle_response(
        self, response: httpx.Response, url: str, method: str,
    ) -> Any:
        """معالجة استجابة Jira وإرجاع JSON أو رفع خطأ مفهوم."""
        if response.status_code == 204:
            return {"status": "success", "no_content": True}
        if response.status_code >= 400:
            try:
                error_body = response.json()
                # تنسيقات أخطاء Jira الشائعة
                err_msgs: list[str] = []
                if isinstance(error_body.get("errorMessages"), list):
                    err_msgs.extend(error_body["errorMessages"])
                if isinstance(error_body.get("errors"), dict):
                    for k, v in error_body["errors"].items():
                        err_msgs.append(f"{k}: {v}")
                if "message" in error_body:
                    err_msgs.append(str(error_body["message"]))
                err_msg = "; ".join(err_msgs) or response.text[:500]
            except ValueError:
                err_msg = response.text[:500]
            raise ConnectorError(
                f"Jira Service Management: خطأ في {method} {url} "
                f"(HTTP {response.status_code}): {err_msg}",
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError(
                f"Jira Service Management: استجابة غير صالحة JSON من {url}: {exc}",
            ) from exc

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في تذاكر Jira عبر JQL.

        Args:
            query: نص JQL (مثل 'project = IT AND status != Closed').
            **kwargs:
                fields (list[str]): الحقول المطلوبة (افتراضيًا summary,status,priority).
                limit (int): عدد النتائج (افتراضيًا 50، حد أقصى 100).
                expand (list[str]): حقول موسعة.

        Returns:
            قائمة بالتذاكر الموحدة (key, id, summary, status, priority).
        """
        fields: list[str] = kwargs.pop(
            "fields", ["summary", "status", "priority", "issuetype", "created"],
        )
        limit: int = int(kwargs.pop("limit", 50))
        expand: Optional[list[str]] = kwargs.pop("expand", None)

        params: dict[str, Any] = {
            "jql": query,
            "maxResults": max(1, min(limit, 100)),
            "fields": ",".join(fields) if isinstance(fields, list) else str(fields),
        }
        if expand:
            params["expand"] = ",".join(expand) if isinstance(expand, list) else str(expand)

        data = await self._rest_request("GET", "/search", params=params)
        issues = data.get("issues", [])
        return [
            {
                "id": issue.get("id"),
                "key": issue.get("key"),
                "summary": issue.get("fields", {}).get("summary"),
                "status": issue.get("fields", {}).get("status", {}).get("name"),
                "priority": issue.get("fields", {}).get("priority", {}).get("name"),
                "issuetype": issue.get("fields", {}).get("issuetype", {}).get("name"),
                "created": issue.get("fields", {}).get("created"),
                "url": f"{self._base_url}/browse/{issue.get('key')}",
            }
            for issue in issues
        ]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Jira Service Management.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "create_ticket": self._create_ticket,
            "get_ticket": self._get_ticket,
            "update_ticket": self._update_ticket,
            "list_tickets": self._list_tickets,
            "add_comment": self._add_comment,
            "get_sla": self._get_sla,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"Jira Service Management: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _create_ticket(self, **kw: Any) -> dict[str, Any]:
        """إنشاء تذكرة طلب عميل (Customer Request) في JSM.

        يستخدم /rest/servicedeskapi/request لإنشاء طلب عميل.
        لتذكرة Jira عادية، استخدم project + issuetype عبر REST API v3.

        Args (via kwargs):
            service_desk_id (int): معرف مكتب الخدمة (مطلوب لطلب JSM).
            request_type_id (int): معرف نوع الطلب.
            summary (str): عنوان الطلب.
            description (str): وصف الطلب.
            project_key (str): مفتاح مشروع Jira (بديل — لإنشاء issue عادي).
            issuetype (str): نوع التذكرة (مثل 'IT Help').
            extra_fields (dict): حقول إضافية مخصصة.
        """
        service_desk_id = kw.get("service_desk_id")
        project_key = kw.get("project_key")

        if service_desk_id:
            # إنشاء customer request عبر JSM API
            request_type_id = kw.get("request_type_id")
            if not request_type_id:
                raise ConnectorError(
                    "Jira Service Management: create_ticket يتطلب 'request_type_id' "
                    "عند استخدام 'service_desk_id'",
                )
            summary = kw.get("summary", "")
            description = kw.get("description", "")
            field_values: list[dict[str, Any]] = [
                {"fieldId": "summary", "value": summary},
            ]
            if description:
                field_values.append({"fieldId": "description", "value": description})
            for k, v in (kw.get("extra_fields") or {}).items():
                field_values.append({"fieldId": k, "value": v})

            body = {
                "serviceDeskId": str(service_desk_id),
                "requestTypeId": int(request_type_id),
                "requestFieldValues": field_values,
            }
            data = await self._jsm_request("POST", "/request", json_body=body)
            return {
                "status": "created",
                "id": data.get("issueKey") or data.get("id"),
                "issue_key": data.get("issueKey"),
                "request": data,
            }

        if project_key:
            # إنشاء issue عادي عبر REST API v3
            summary = kw.get("summary")
            if not summary:
                raise ConnectorError(
                    "Jira Service Management: create_ticket يتطلب 'summary'",
                )
            issuetype = kw.get("issuetype", "Task")
            fields: dict[str, Any] = {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issuetype},
            }
            if kw.get("description"):
                fields["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": kw["description"]}],
                        }
                    ],
                }
            for k, v in (kw.get("extra_fields") or {}).items():
                fields[k] = v
            body = {"fields": fields}
            data = await self._rest_request("POST", "/issue", json_body=body)
            return {
                "status": "created",
                "id": data.get("id"),
                "issue_key": data.get("key"),
                "url": f"{self._base_url}/browse/{data.get('key')}",
            }

        raise ConnectorError(
            "Jira Service Management: create_ticket يتطلب 'service_desk_id' أو 'project_key'",
        )

    async def _get_ticket(self, **kw: Any) -> dict[str, Any]:
        """جلب تذكرة بواسطة issueKey أو issueId.

        Args (via kwargs):
            issue_key (str): مفتاح التذكرة (مثل 'IT-123').
            issue_id (str): معرف التذكرة (بديل).
            fields (list[str]): الحقول المطلوبة.
        """
        issue_key = kw.get("issue_key") or kw.get("issue_id")
        if not issue_key:
            raise ConnectorError(
                "Jira Service Management: get_ticket يتطلب 'issue_key' أو 'issue_id'",
            )
        params: dict[str, Any] = {}
        fields = kw.get("fields")
        if fields:
            params["fields"] = ",".join(fields) if isinstance(fields, list) else str(fields)
        data = await self._rest_request("GET", f"/issue/{issue_key}", params=params or None)
        return {"ticket": data}

    async def _update_ticket(self, **kw: Any) -> dict[str, Any]:
        """تحديث تذكرة موجودة (PUT /rest/api/3/issue/{issueKey}).

        Args (via kwargs):
            issue_key (str): مفتاح التذكرة (مطلوب).
            fields (dict): الحقول المراد تحديثها بصيغة Jira.
            summary (str): اختصار لتحديث العنوان.
            description (str): اختصار لتحديث الوصف (يُحوَّل إلى Atlassian Document Format).
        """
        issue_key = kw.get("issue_key")
        if not issue_key:
            raise ConnectorError(
                "Jira Service Management: update_ticket يتطلب 'issue_key'",
            )
        fields: dict[str, Any] = dict(kw.get("fields") or {})
        if "summary" in kw and kw["summary"]:
            fields["summary"] = kw["summary"]
        if "description" in kw and kw["description"]:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": kw["description"]}],
                    }
                ],
            }
        if not fields:
            raise ConnectorError(
                "Jira Service Management: update_ticket يتطلب 'fields' أو 'summary' أو 'description'",
            )
        await self._rest_request("PUT", f"/issue/{issue_key}", json_body={"fields": fields})
        return {"status": "updated", "issue_key": issue_key}

    async def _list_tickets(self, **kw: Any) -> dict[str, Any]:
        """سرد التذاكر مع فلترة JQL.

        Args (via kwargs):
            jql (str): استعلام JQL (مطلوب).
            fields (list[str]): الحقول المطلوبة.
            limit (int): عدد النتائج (افتراضيًا 50).
            expand (list[str]): حقول موسعة.
        """
        jql = kw.get("jql")
        if not jql:
            raise ConnectorError(
                "Jira Service Management: list_tickets يتطلب 'jql'",
            )
        results = await self.search(
            jql,
            fields=kw.get("fields", ["summary", "status", "priority", "issuetype", "created"]),
            limit=int(kw.get("limit", 50)),
            expand=kw.get("expand"),
        )
        return {"jql": jql, "count": len(results), "tickets": results}

    async def _add_comment(self, **kw: Any) -> dict[str, Any]:
        """إضافة تعليق على تذكرة.

        Args (via kwargs):
            issue_key (str): مفتاح التذكرة (مطلوب).
            body (str): نص التعليق.
            visibility (dict): رؤية التعليق (اختياري).
        """
        issue_key = kw.get("issue_key")
        body_text = kw.get("body")
        if not issue_key or not body_text:
            raise ConnectorError(
                "Jira Service Management: add_comment يتطلب 'issue_key' و 'body'",
            )
        comment_body: dict[str, Any] = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body_text}],
                    }
                ],
            },
        }
        if "visibility" in kw and kw["visibility"]:
            comment_body["visibility"] = kw["visibility"]
        data = await self._rest_request(
            "POST", f"/issue/{issue_key}/comment", json_body=comment_body,
        )
        return {"status": "added", "issue_key": issue_key, "comment": data}

    async def _get_sla(self, **kw: Any) -> dict[str, Any]:
        """جلب معلومات SLA لتذكرة JSM.

        Args (via kwargs):
            issue_id (str): معرف التذكرة (مطلوب — وليس issue_key).
        """
        issue_id = kw.get("issue_id")
        if not issue_id:
            raise ConnectorError(
                "Jira Service Management: get_sla يتطلب 'issue_id' (الرقمي)",
            )
        # endpoint SLA في JSM
        data = await self._jsm_request(
            "GET", f"/request/{issue_id}/sla",
        )
        return {"issue_id": issue_id, "sla": data.get("values", [])}

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
            "protocol": "Atlassian Jira REST API v3 + Service Desk API",
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "read": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "required_scopes": [
                "read:jira-work",
                "write:jira-work",
                "servicedesk:agent:read",
                "servicedesk:request:write",
            ],
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:jira_service_management:read",
            "connector:jira_service_management:write",
            "itsm:ticket:create",
            "itsm:ticket:read",
            "itsm:ticket:update",
            "itsm:sla:read",
        ]
