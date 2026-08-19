"""
موصل Microsoft Teams لمنصة HSAAI
==================================
يتيح هذا الموصل الوصول إلى Microsoft Teams عبر Microsoft Graph API
مع مصادقة OAuth2 من Azure AD (client credentials flow).

الإجراءات المدعومة:
    - send_message   : إرسال رسالة نصية إلى قناة أو محادثة
    - list_channels  : سرد القنوات في فريق محدد
    - create_meeting : إنشاء اجتماع Teams عبر Graph (onlineMeetings)
    - send_card      : إرسال Adaptive Card / MessageCard إلى قناة

search() للبحث في رسائل القنوات عبر Graph search.

الاستخدام:
    cfg = ConnectorConfig(
        name="microsoft_teams",
        display_name="Corporate Teams",
        category="Collaboration",
        base_url="https://graph.microsoft.com",
        auth_strategy=AuthStrategy.OAUTH2_CLIENT_CREDENTIALS,
        secrets={
            "tenant_id": "...",
            "client_id": "...",
            "client_secret": "...",
        },
    )
    connector = MSTeamsConnector(cfg)
    await connector.connect()
    await connector.call("send_message", team_id="...", channel_id="...", text="Hello")
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


@connector("microsoft_teams", version="1.0.0", category="Collaboration")
class MSTeamsConnector(BaseConnector):
    """موصل Microsoft Teams عبر Microsoft Graph API و OAuth2."""

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
        "send_message",
        "list_channels",
        "create_meeting",
        "send_card",
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

        يستخدم تدفق client_credentials للحصول على access token للوصول
        إلى Microsoft Graph API نيابة عن التطبيق (application permissions).

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل المصادقة.
        """
        if not self._tenant_id or not self._client_id or not self._client_secret:
            raise ConnectorAuthenticationError(
                "Microsoft Teams: tenant_id و client_id و client_secret مطلوبة للمصادقة",
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
                    f"Microsoft Teams: فشل الاتصال بـ Azure AD: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"Microsoft Teams: فشل المصادقة (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        token_payload = response.json()
        self._access_token = token_payload.get("access_token")
        if not self._access_token:
            raise ConnectorAuthenticationError(
                "Microsoft Teams: لم يُرجع Azure AD access_token",
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
            "Microsoft Teams: تم الحصول على access token (ينتهي خلال %ss)",
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
        """فحص صحة Graph API عبر طلب خفيف على /teams (أعلى 1 نتيجة)."""
        start = time.monotonic()
        try:
            await self._ensure_token()
            if self._client is None:
                raise ConnectorError("Microsoft Teams: العميل غير مهيأ")
            response = await self._client.get(
                self._graph_url("/teams"),
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
                    error="token غير صالح أو منتهي",
                )
            if response.status_code == 403:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 403, "reason": "insufficient_permissions"},
                    error="صلاحيات تطبيق غير كافية (تأكد من إضافة Team.ReadBasic.All)",
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
            raise ConnectorError("Microsoft Teams: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()
        try:
            response = await self._client.get(self._graph_url(path), params=params or {})
        except httpx.HTTPError as exc:
            raise ConnectorError(f"Microsoft Teams: فشل GET على {path}: {exc}") from exc
        return self._handle_response(response, path, "GET")

    async def _graph_post(
        self, path: str, *,
        json_body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """تنفيذ POST على Graph API."""
        if self._client is None:
            raise ConnectorError("Microsoft Teams: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()
        try:
            response = await self._client.post(
                self._graph_url(path), json=json_body or {}, params=params or {},
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(f"Microsoft Teams: فشل POST على {path}: {exc}") from exc
        return self._handle_response(response, path, "POST")

    def _handle_response(
        self, response: httpx.Response, path: str, method: str,
    ) -> Any:
        """معالجة استجابة Graph API وإرجاع JSON أو رفع خطأ مفهوم."""
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
                f"Microsoft Teams: خطأ Graph API في {method} {path} "
                f"(HTTP {response.status_code}) [{err_code}]: {err_msg}",
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError(
                f"Microsoft Teams: استجابة غير صالحة JSON من {path}: {exc}",
            ) from exc

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في رسائل قنوات Teams عبر Microsoft Graph search API.

        يستخدم POST /search/query مع entityTypes=['chatMessage'].

        Args:
            query: نص البحث.
            **kwargs:
                team_id (str): تقييد البحث على فريق محدد.
                top (int): عدد النتائج (افتراضيًا 25).

        Returns:
            قائمة بنتائج البحث (hits).
        """
        top: int = int(kwargs.pop("top", 25))
        team_id: Optional[str] = kwargs.pop("team_id", None)

        request_body: dict[str, Any] = {
            "requests": [
                {
                    "entityTypes": ["chatMessage"],
                    "query": {
                        "queryString": query,
                        "queryTemplate": "{searchTerms}",
                    },
                    "from": 0,
                    "size": max(1, min(top, 1000)),
                    "fields": [
                        "id", "body", "from", "createdDateTime",
                        "channelIdentity", "messageType",
                    ],
                }
            ],
        }
        if team_id:
            # تقييد البحث على فريق عبر template
            request_body["requests"][0]["query"]["queryTemplate"] = (
                f"teamId:{team_id} {{searchTerms}}"
            )

        if self._client is None:
            raise ConnectorError("Microsoft Teams: العميل غير مهيأ")
        await self._ensure_token()
        try:
            response = await self._client.post(
                self._graph_url("/search/query"),
                json=request_body,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(f"Microsoft Teams: فشل search: {exc}") from exc
        data = self._handle_response(response, "/search/query", "POST")
        all_hits: list[dict[str, Any]] = []
        for container in data.get("value", []):
            for hit_container in container.get("hitsContainers", []):
                for hit in hit_container.get("hits", []):
                    all_hits.append({
                        "id": hit.get("resource", {}).get("id"),
                        "body": hit.get("resource", {}).get("body", {}).get("content"),
                        "from": hit.get("resource", {}).get("from"),
                        "created": hit.get("resource", {}).get("createdDateTime"),
                        "channel_id": hit.get("resource", {}).get("channelIdentity", {}).get("channelId"),
                        "team_id": hit.get("resource", {}).get("channelIdentity", {}).get("teamId"),
                    })
        return all_hits

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Microsoft Teams.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "send_message": self._send_message,
            "list_channels": self._list_channels,
            "create_meeting": self._create_meeting,
            "send_card": self._send_card,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"Microsoft Teams: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _send_message(self, **kw: Any) -> dict[str, Any]:
        """إرسال رسالة نصية إلى قناة في Teams.

        Args (via kwargs):
            team_id (str): معرف الفريق (مطلوب).
            channel_id (str): معرف القناة (مطلوب).
            text (str): نص الرسالة (مطلوب).
            subject (str): موضوع الرسالة (اختياري).
        """
        team_id = kw.get("team_id")
        channel_id = kw.get("channel_id")
        text = kw.get("text")
        if not team_id or not channel_id or not text:
            raise ConnectorError(
                "Microsoft Teams: send_message يتطلب 'team_id' و 'channel_id' و 'text'",
            )
        body: dict[str, Any] = {
            "body": {"contentType": "text", "content": text},
        }
        if kw.get("subject"):
            body["subject"] = kw["subject"]
        path = f"/teams/{team_id}/channels/{channel_id}/messages"
        data = await self._graph_post(path, json_body=body)
        return {
            "status": "sent",
            "message_id": data.get("id"),
            "message": data,
        }

    async def _list_channels(self, **kw: Any) -> dict[str, Any]:
        """سرد القنوات في فريق محدد.

        Args (via kwargs):
            team_id (str): معرف الفريق (مطلوب).
            top (int): عدد النتائج (افتراضيًا 50).
            filter_membership (str): فلترة حسب العضوية (private/public/shared).
        """
        team_id = kw.get("team_id")
        if not team_id:
            raise ConnectorError("Microsoft Teams: list_channels يتطلب 'team_id'")
        top = int(kw.get("top", 50))
        params: dict[str, Any] = {"$top": str(max(1, min(top, 999)))}
        if kw.get("filter_membership"):
            params["$filter"] = f"membershipType eq '{kw['filter_membership']}'"
        data = await self._graph_get(f"/teams/{team_id}/channels", params=params)
        return {
            "team_id": team_id,
            "count": len(data.get("value", [])),
            "channels": data.get("value", []),
        }

    async def _create_meeting(self, **kw: Any) -> dict[str, Any]:
        """إنشاء اجتماع Teams عبر Graph API (onlineMeetings).

        يتطلب Application Permission OnlineMeetings.ReadWrite.All
        أو تفويض Delegated. النوع النموذجي هو application permissions
        مع policy مسجلة مسبقًا.

        Args (via kwargs):
            user_id (str): UPN أو objectId للمستخدم المنظِّم (مطلوب).
            subject (str): موضوع الاجتماع (مطلوب).
            start (str): وقت البدء ISO 8601 (مثل 2024-01-01T10:00:00Z).
            end (str): وقت الانتهاء ISO 8601.
            attendees (list[str]): قائمة ببريد المشاركين.
            join_url (str): اختياري للاجتماعات الحالية.
        """
        user_id = kw.get("user_id")
        subject = kw.get("subject")
        start = kw.get("start")
        end = kw.get("end")
        if not user_id or not subject or not start or not end:
            raise ConnectorError(
                "Microsoft Teams: create_meeting يتطلب 'user_id' و 'subject' و 'start' و 'end'",
            )
        attendees_raw = kw.get("attendees") or []
        attendees = [
            {
                "upn": email,
                "role": "attendee",
            }
            for email in attendees_raw
        ]
        body: dict[str, Any] = {
            "startDateTime": start,
            "endDateTime": end,
            "subject": subject,
            "participants": {"attendees": attendees},
        }
        if kw.get("join_url"):
            body["joinMeetingIdSettings"] = {"joinMeetingId": kw["join_url"]}
        data = await self._graph_post(f"/users/{user_id}/onlineMeetings", json_body=body)
        return {
            "status": "created",
            "meeting_id": data.get("id"),
            "join_url": data.get("joinUrl"),
            "meeting": data,
        }

    async def _send_card(self, **kw: Any) -> dict[str, Any]:
        """إرسال Adaptive Card أو MessageCard إلى قناة.

        Args (via kwargs):
            team_id (str): معرف الفريق (مطلوب).
            channel_id (str): معرف القناة (مطلوب).
            card (dict): كائن Adaptive Card أو MessageCard.
            card_type (str): 'adaptive' (افتراضي) أو 'message'.
        """
        team_id = kw.get("team_id")
        channel_id = kw.get("channel_id")
        card = kw.get("card")
        if not team_id or not channel_id or not card:
            raise ConnectorError(
                "Microsoft Teams: send_card يتطلب 'team_id' و 'channel_id' و 'card'",
            )
        card_type = kw.get("card_type", "adaptive")
        if card_type == "adaptive":
            # Adaptive Card عبر attachment
            body = {
                "body": {"contentType": "html", "content": "<attachment>attachment</attachment>"},
                "attachments": [
                    {
                        "id": str(int(time.time() * 1000)),
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "contentUrl": None,
                        "content": card,
                        "name": None,
                        "thumbnailUrl": None,
                    }
                ],
            }
        else:
            # MessageCard تقليدية
            body = {
                "body": {"contentType": "html", "content": "<attachment>attachment</attachment>"},
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.teams.card.o365connector",
                        "content": card,
                    }
                ],
            }
        path = f"/teams/{team_id}/channels/{channel_id}/messages"
        data = await self._graph_post(path, json_body=body)
        return {
            "status": "sent",
            "message_id": data.get("id"),
            "card_type": card_type,
            "message": data,
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
                "read": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "required_scopes": [
                "Team.ReadBasic.All",
                "ChannelMessage.Read.All",
                "ChannelMessage.Send",
                "OnlineMeetings.ReadWrite.All",
            ],
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:microsoft_teams:read",
            "connector:microsoft_teams:write",
            "teams:message:send",
            "teams:channel:read",
            "teams:meeting:create",
        ]
