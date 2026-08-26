"""
موصل Microsoft Outlook لمنصة HSAAI
====================================
يتيح هذا الموصل الوصول إلى بريد Microsoft Outlook والتقويم عبر
Microsoft Graph API مع مصادقة OAuth2 من Azure AD (client credentials).

الإجراءات المدعومة:
    - send_mail    : إرسال بريد إلكتروني
    - list_emails  : سرد الرسائل في صندوق مستخدم
    - get_email    : جلب رسالة محددة بالمعرف
    - create_event : إنشاء حدث في التقويم
    - list_events  : سرد الأحداث في التقويم

search() للبحث في الرسائل عبر $search parameter في Graph API.

الاستخدام:
    cfg = ConnectorConfig(
        name="outlook",
        display_name="Corporate Outlook",
        category="Email",
        base_url="https://graph.microsoft.com",
        auth_strategy=AuthStrategy.OAUTH2_CLIENT_CREDENTIALS,
        secrets={
            "tenant_id": "...",
            "client_id": "...",
            "client_secret": "...",
        },
    )
    connector = OutlookConnector(cfg)
    await connector.connect()
    await connector.call("send_mail", user_id="user@company.com",
        subject="...", body="...", to=["x@y.com"])
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


@connector("outlook", version="1.0.0", category="Email")
class OutlookConnector(BaseConnector):
    """موصل Microsoft Outlook (بريد + تقويم) عبر Microsoft Graph API."""

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
        "send_mail",
        "list_emails",
        "get_email",
        "create_event",
        "list_events",
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

        يتطلب Application Permissions مثل Mail.Send و Mail.ReadBasic.All
        و Calendars.ReadWrite مع موافقة المسؤول.

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل المصادقة.
        """
        if not self._tenant_id or not self._client_id or not self._client_secret:
            raise ConnectorAuthenticationError(
                "Outlook: tenant_id و client_id و client_secret مطلوبة للمصادقة",
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
                    f"Outlook: فشل الاتصال بـ Azure AD: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"Outlook: فشل المصادقة (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        token_payload = response.json()
        self._access_token = token_payload.get("access_token")
        if not self._access_token:
            raise ConnectorAuthenticationError(
                "Outlook: لم يُرجع Azure AD access_token",
            )
        expires_in = int(token_payload.get("expires_in", 3600))
        self._token_expires_at = time.time() + max(60, expires_in - 60)

        if self._client is not None:
            self._client.headers.update({
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "ConsistencyLevel": "eventual",
            })

        logger.info(
            "Outlook: تم الحصول على access token (ينتهي خلال %ss)",
            expires_in,
        )

    async def _ensure_token(self) -> None:
        """تجديد access token عند انتهاء صلاحيته."""
        if self._access_token is None or time.time() >= self._token_expires_at:
            await self.authenticate()

    def _graph_url(self, path: str) -> str:
        """بناء مسار Graph API نسبي."""
        if path.startswith("/"):
            return f"{self._graph_path}{path}"
        return f"{self._graph_path}/{path}"

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة Graph API عبر طلب /organization (خفيف وآمن)."""
        start = time.monotonic()
        try:
            await self._ensure_token()
            if self._client is None:
                raise ConnectorError("Outlook: العميل غير مهيأ")
            response = await self._client.get(
                self._graph_url("/organization"),
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
                    status=HealthStatus.UNHEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 401, "reason": "token_invalid"},
                    error="token غير صالح",
                )
            if response.status_code == 403:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 403, "reason": "insufficient_permissions"},
                    error="صلاحيات تطبيق غير كافية",
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
        """تنفيذ GET على Graph API مع معالجة الأخطاء."""
        if self._client is None:
            raise ConnectorError("Outlook: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()
        try:
            response = await self._client.get(self._graph_url(path), params=params or {})
        except httpx.HTTPError as exc:
            raise ConnectorError(f"Outlook: فشل GET على {path}: {exc}") from exc
        return self._handle_response(response, path, "GET")

    async def _graph_post(
        self, path: str, *, json_body: Optional[dict[str, Any]] = None,
    ) -> Any:
        """تنفيذ POST على Graph API."""
        if self._client is None:
            raise ConnectorError("Outlook: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()
        try:
            response = await self._client.post(self._graph_url(path), json=json_body or {})
        except httpx.HTTPError as exc:
            raise ConnectorError(f"Outlook: فشل POST على {path}: {exc}") from exc
        return self._handle_response(response, path, "POST")

    def _handle_response(
        self, response: httpx.Response, path: str, method: str,
    ) -> Any:
        """معالجة استجابة Graph API وإرجاع JSON أو رفع خطأ مفهوم."""
        if response.status_code == 202:
            # Accepted — شائع في sendMail
            return {"status": "accepted"}
        if response.status_code == 204:
            return {"status": "success", "no_content": True}
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
                f"Outlook: خطأ Graph API في {method} {path} "
                f"(HTTP {response.status_code}) [{err_code}]: {err_msg}",
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError(
                f"Outlook: استجابة غير صالحة JSON من {path}: {exc}",
            ) from exc

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في رسائل البريد عبر $search parameter في Graph API.

        يستخدم GET /users/{id}/messages?$search="{query}" مع
        ترويسة ConsistencyLevel: eventual.

        Args:
            query: نص البحث (يدعم KQL مثل 'from:alice subject:report').
            **kwargs:
                user_id (str): UPN أو objectId للمستخدم (مطلوب).
                folder (str): اسم المجلد (افتراضيًا 'inbox' أو 'all').
                top (int): عدد النتائج (افتراضيًا 25).

        Returns:
            قائمة بالرسائل الموحدة.
        """
        user_id = kwargs.pop("user_id", None)
        if not user_id:
            raise ConnectorError("Outlook: search يتطلب 'user_id'")
        top: int = int(kwargs.pop("top", 25))
        folder: str = kwargs.pop("folder", "all")

        if folder and folder != "all":
            path = f"/users/{user_id}/mailFolders/{folder}/messages"
        else:
            path = f"/users/{user_id}/messages"

        params: dict[str, Any] = {
            "$top": str(max(1, min(top, 1000))),
            "$select": "id,subject,from,bodyPreview,receivedDateTime,hasAttachments",
            "$search": f'"{query}"',
            "$count": "true",
        }
        # ترويسة ConsistencyLevel مطلوبة لـ $search
        if self._client is None:
            raise ConnectorError("Outlook: العميل غير مهيأ")
        await self._ensure_token()
        self._client.headers["ConsistencyLevel"] = "eventual"
        try:
            response = await self._client.get(self._graph_url(path), params=params)
        except httpx.HTTPError as exc:
            raise ConnectorError(f"Outlook: فشل search: {exc}") from exc
        data = self._handle_response(response, path, "GET")
        return [
            {
                "id": msg.get("id"),
                "subject": msg.get("subject"),
                "from": msg.get("from", {}).get("emailAddress", {}).get("address"),
                "preview": msg.get("bodyPreview"),
                "received": msg.get("receivedDateTime"),
                "has_attachments": msg.get("hasAttachments", False),
            }
            for msg in data.get("value", [])
        ]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Outlook.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "send_mail": self._send_mail,
            "list_emails": self._list_emails,
            "get_email": self._get_email,
            "create_event": self._create_event,
            "list_events": self._list_events,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"Outlook: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _send_mail(self, **kw: Any) -> dict[str, Any]:
        """إرسال بريد إلكتروني نيابة عن مستخدم.

        Args (via kwargs):
            user_id (str): UPN أو objectId للمرسل (مطلوب).
            subject (str): موضوع البريد (مطلوب).
            body (str): محتوى البريد (مطلوب).
            body_type (str): 'text' أو 'html' (افتراضيًا 'text').
            to (list[str]): قائمة المستلمين (مطلوب).
            cc (list[str]): قائمة المستلمين نسخة.
            bcc (list[str]): قائمة المستلمين نسخة مخفية.
            reply_to (list[str]): عنوان الرد.
            attachments (list[dict]): مرفقات بصيغة {name, content_base64, content_type}.
            save_to_sent (bool): حفظ في المُرسَل (افتراضيًا True).
        """
        user_id = kw.get("user_id")
        subject = kw.get("subject")
        body_text = kw.get("body")
        to = kw.get("to")
        if not user_id or not subject or not body_text or not to:
            raise ConnectorError(
                "Outlook: send_mail يتطلب 'user_id' و 'subject' و 'body' و 'to'",
            )
        body_type = kw.get("body_type", "text")
        message: dict[str, Any] = {
            "subject": subject,
            "body": {"contentType": body_type, "content": body_text},
            "toRecipients": [{"emailAddress": {"address": email}} for email in to],
        }
        if kw.get("cc"):
            message["ccRecipients"] = [
                {"emailAddress": {"address": e}} for e in kw["cc"]
            ]
        if kw.get("bcc"):
            message["bccRecipients"] = [
                {"emailAddress": {"address": e}} for e in kw["bcc"]
            ]
        if kw.get("reply_to"):
            message["replyTo"] = [
                {"emailAddress": {"address": e}} for e in kw["reply_to"]
            ]
        if kw.get("attachments"):
            message["attachments"] = [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": att.get("name", "attachment"),
                    "contentBytes": att["content_base64"],
                    "contentType": att.get("content_type", "application/octet-stream"),
                }
                for att in kw["attachments"]
            ]
        body = {
            "message": message,
            "saveToSentItems": bool(kw.get("save_to_sent", True)),
        }
        path = f"/users/{user_id}/sendMail"
        result = await self._graph_post(path, json_body=body)
        return {"status": "sent", "user_id": user_id, "subject": subject, **result}

    async def _list_emails(self, **kw: Any) -> dict[str, Any]:
        """سرد الرسائل في صندوق مستخدم.

        Args (via kwargs):
            user_id (str): UPN أو objectId (مطلوب).
            folder (str): المجلد (افتراضيًا 'inbox').
            top (int): عدد النتائج (افتراضيًا 50).
            fields (list[str]): الحقول المُعادة.
            order_by (str): ترتيب (مثل 'receivedDateTime desc').
            filter_query (str): فلتر OData (مثل 'hasAttachments eq true').
        """
        user_id = kw.get("user_id")
        if not user_id:
            raise ConnectorError("Outlook: list_emails يتطلب 'user_id'")
        folder = kw.get("folder", "inbox")
        top = int(kw.get("top", 50))
        path = f"/users/{user_id}/mailFolders/{folder}/messages"
        params: dict[str, Any] = {
            "$top": str(max(1, min(top, 999))),
            "$select": ",".join(kw.get("fields") or [
                "id", "subject", "from", "bodyPreview",
                "receivedDateTime", "isRead", "hasAttachments",
            ]),
            "$orderby": kw.get("order_by", "receivedDateTime desc"),
        }
        if kw.get("filter_query"):
            params["$filter"] = kw["filter_query"]
        data = await self._graph_get(path, params=params)
        return {
            "user_id": user_id,
            "folder": folder,
            "count": len(data.get("value", [])),
            "emails": data.get("value", []),
        }

    async def _get_email(self, **kw: Any) -> dict[str, Any]:
        """جلب رسالة محددة بالمعرف.

        Args (via kwargs):
            user_id (str): UPN أو objectId (مطلوب).
            message_id (str): معرف الرسالة (مطلوب).
            fields (list[str]): الحقول المُعادة.
        """
        user_id = kw.get("user_id")
        message_id = kw.get("message_id")
        if not user_id or not message_id:
            raise ConnectorError(
                "Outlook: get_email يتطلب 'user_id' و 'message_id'",
            )
        params: dict[str, Any] = {}
        if kw.get("fields"):
            params["$select"] = ",".join(kw["fields"])
        data = await self._graph_get(
            f"/users/{user_id}/messages/{message_id}",
            params=params or None,
        )
        return {"email": data}

    async def _create_event(self, **kw: Any) -> dict[str, Any]:
        """إنشاء حدث في تقويم مستخدم.

        Args (via kwargs):
            user_id (str): UPN أو objectId (مطلوب).
            subject (str): موضوع الحدث (مطلوب).
            start (str): وقت البدء ISO 8601 (مطلوب).
            end (str): وقت الانتهاء ISO 8601 (مطلوب).
            timezone (str): المنطقة الزمنية (افتراضيًا 'UTC').
            body (str): وصف الحدث.
            body_type (str): 'text' أو 'html'.
            location (str): اسم الموقع.
            attendees (list[str]): قائمة ببريد المشاركين.
            is_online (bool): تحويل إلى اجتماع Teams.
        """
        user_id = kw.get("user_id")
        subject = kw.get("subject")
        start = kw.get("start")
        end = kw.get("end")
        if not user_id or not subject or not start or not end:
            raise ConnectorError(
                "Outlook: create_event يتطلب 'user_id' و 'subject' و 'start' و 'end'",
            )
        tz = kw.get("timezone", "UTC")
        body: dict[str, Any] = {
            "subject": subject,
            "start": {"dateTime": start, "timeZone": tz},
            "end": {"dateTime": end, "timeZone": tz},
        }
        if kw.get("body"):
            body["body"] = {
                "contentType": kw.get("body_type", "text"),
                "content": kw["body"],
            }
        if kw.get("location"):
            body["location"] = {"displayName": kw["location"]}
        if kw.get("attendees"):
            body["attendees"] = [
                {"emailAddress": {"address": email}, "type": "required"}
                for email in kw["attendees"]
            ]
        if kw.get("is_online"):
            body["isOnlineMeeting"] = True
            body["onlineMeetingProvider"] = "teamsForBusiness"
        data = await self._graph_post(
            f"/users/{user_id}/events", json_body=body,
        )
        return {
            "status": "created",
            "event_id": data.get("id"),
            "online_meeting_url": data.get("onlineMeeting", {}).get("joinUrl"),
            "event": data,
        }

    async def _list_events(self, **kw: Any) -> dict[str, Any]:
        """سرد الأحداث في تقويم مستخدم.

        Args (via kwargs):
            user_id (str): UPN أو objectId (مطلوب).
            top (int): عدد النتائج (افتراضيًا 50).
            start (str): من تاريخ (ISO 8601) لفلتر زمني.
            end (str): إلى تاريخ (ISO 8601).
            order_by (str): ترتيب (افتراضيًا 'start/dateTime').
        """
        user_id = kw.get("user_id")
        if not user_id:
            raise ConnectorError("Outlook: list_events يتطلب 'user_id'")
        top = int(kw.get("top", 50))
        params: dict[str, Any] = {
            "$top": str(max(1, min(top, 999))),
            "$select": "id,subject,start,end,organizer,attendees,location,onlineMeeting",
            "$orderby": kw.get("order_by", "start/dateTime"),
        }
        start = kw.get("start")
        end = kw.get("end")
        if start and end:
            params["$filter"] = (
                f"start/dateTime ge '{start}' and end/dateTime le '{end}'"
            )
        data = await self._graph_get(f"/users/{user_id}/events", params=params)
        return {
            "user_id": user_id,
            "count": len(data.get("value", [])),
            "events": data.get("value", []),
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
            "protocol": "Microsoft Graph REST API (Mail + Calendar)",
            "graph_api_version": self.GRAPH_API_VERSION,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "read": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "required_scopes": [
                "Mail.Send",
                "Mail.ReadBasic.All",
                "Mail.Read",
                "Calendars.ReadWrite",
                "Calendars.Read",
            ],
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:outlook:read",
            "connector:outlook:write",
            "email:send",
            "email:read",
            "calendar:event:create",
            "calendar:event:read",
        ]
