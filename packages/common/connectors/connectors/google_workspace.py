"""
موصل Google Workspace لمنصة HSAAI
====================================
يتيح هذا الموصل الوصول إلى Gmail و Google Drive و Google Calendar
عبر Google REST APIs مع مصادقة Service Account (JWT → access token).

يوقّع الموصل JWT باستخدام مفتاح Service Account الخاص (RS256) ثم
يستبدله بـ access token عبر https://oauth2.googleapis.com/token،
ثم يستدعي Google APIs عبر httpx.AsyncClient.

الإجراءات المدعومة:
    - send_email    : إرسال بريد عبر Gmail
    - list_emails   : سرد رسائل Gmail
    - list_files    : سرد ملفات Google Drive
    - upload_file   : رفع ملف إلى Drive
    - create_event  : إنشاء حدث في Google Calendar

search() للبحث في رسائل Gmail (q parameter) و ملفات Drive (q=...).

الاستخدام:
    cfg = ConnectorConfig(
        name="google_workspace",
        display_name="Corporate Google Workspace",
        category="Collaboration",
        base_url="https://www.googleapis.com",
        auth_strategy=AuthStrategy.JWT,
        secrets={
            "client_email": "svc@project.iam.gserviceaccount.com",
            "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
            "subject": "user@company.com",  # DWD: تفويض نيابة عن مستخدم
        },
    )
    connector = GoogleWorkspaceConnector(cfg)
    await connector.connect()
    await connector.call("send_email", to=["x@y.com"], subject="...", body="...")
"""
from __future__ import annotations

import base64
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

# ─────────────────────────────────────────────────────────────────────
#  مكتبة توقيع JWT (PyJWT) مع تراجع إلى cryptography
# ─────────────────────────────────────────────────────────────────────
try:
    import jwt as _pyjwt  # PyJWT
    _HAS_PYJWT = True
except ImportError:  # pragma: no cover
    _pyjwt = None
    _HAS_PYJWT = False

try:
    from cryptography.hazmat.primitives import hashes as _crypto_hashes
    from cryptography.hazmat.primitives import serialization as _crypto_serialization
    from cryptography.hazmat.primitives.asymmetric import padding as _crypto_padding
    from cryptography.hazmat.primitives.asymmetric import rsa as _crypto_rsa
    _HAS_CRYPTOGRAPHY = True
except ImportError:  # pragma: no cover
    _crypto_hashes = None
    _crypto_serialization = None
    _crypto_padding = None
    _crypto_rsa = None
    _HAS_CRYPTOGRAPHY = False


def _b64url_encode(data: bytes) -> str:
    """ترميز base64url بدون حشو."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """فك ترميز base64url مع إضافة الحشو إن لزم."""
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _sign_rs256(payload: dict[str, Any], private_key_pem: str) -> str:
    """توقيع JWT بخوارزمية RS256 باستخدام PyJWT أو cryptography كتراجع.

    Args:
        payload: حمولة JWT (claims).
        private_key_pem: مفتاح RSA الخاص بصيغة PEM.

    Returns:
        سلسلة JWT مُوقَّعة (header.payload.signature).

    Raises:
        ConnectorError: عند عدم توفّر مكتبة توقيع أو فشل التوقيع.
    """
    header = {"alg": "RS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    if _HAS_PYJWT:
        try:
            return _pyjwt.encode(  # type: ignore[union-attr]
                payload, private_key_pem, algorithm="RS256",
            )
        except Exception as exc:
            logger.warning("Google Workspace: فشل PyJWT، التراجع إلى cryptography: %s", exc)

    if not _HAS_CRYPTOGRAPHY:
        raise ConnectorError(
            "Google Workspace: مطلوب تثبيت PyJWT أو cryptography لتوقيع JWT",
        )

    try:
        private_key = _crypto_serialization.load_pem_private_key(  # type: ignore[union-attr]
            private_key_pem.encode("utf-8"), password=None,
        )
        if not isinstance(private_key, _crypto_rsa.RSAPrivateKey):  # type: ignore[union-attr]
            raise ConnectorError(
                "Google Workspace: المفتاح الخاص ليس مفتاح RSA صالح",
            )
        signature = private_key.sign(
            signing_input,
            _crypto_padding.PKCS1v15(),  # type: ignore[union-attr]
            _crypto_hashes.SHA256(),  # type: ignore[union-attr]
        )
        sig_b64 = _b64url_encode(signature)
        return f"{header_b64}.{payload_b64}.{sig_b64}"
    except ConnectorError:
        raise
    except Exception as exc:
        raise ConnectorError(
            f"Google Workspace: فشل توقيع JWT: {exc}",
        ) from exc


@connector("google_workspace", version="1.0.0", category="Collaboration")
class GoogleWorkspaceConnector(BaseConnector):
    """موصل Google Workspace (Gmail + Drive + Calendar) عبر Service Account."""

    #: نقطة نهاية OAuth2 لتبديل JWT بـ access token
    OAUTH_TOKEN_URL: str = "https://oauth2.googleapis.com/token"

    #: نقاط نهاية Google APIs
    GMAIL_API_BASE: str = "https://gmail.googleapis.com/gmail/v1"
    DRIVE_API_BASE: str = "https://www.googleapis.com/drive/v3"
    CALENDAR_API_BASE: str = "https://www.googleapis.com/calendar/v3"

    #: نطاقات Google API الافتراضية
    DEFAULT_SCOPES: list[str] = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/calendar",
    ]

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "send_email",
        "list_emails",
        "list_files",
        "upload_file",
        "create_event",
    )

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._client_email: str = self._get_secret("client_email", "")
        self._private_key: str = self._get_secret("private_key", "")
        # subject = المستخدم الذي يُنفَّذ التفويض نيابة عنه (Domain-Wide Delegation)
        self._subject: str = self._get_secret("subject", "")
        # النطاقات قابلة للتجاوز من الإعدادات
        extra = getattr(self.config, "scopes", None)
        if isinstance(extra, list) and extra:
            self._scopes: list[str] = list(extra)
        else:
            self._scopes = list(self.DEFAULT_SCOPES)

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
        """مصادقة Service Account عبر توقيع JWT واستبداله بـ access token.

        يبني الموصل JWT يحتوي على claims موسعة (iss, scope, aud, iat, exp, sub)
        ويوقِّعه بمفتاح Service Account الخاص (RS256)، ثم يرسله إلى
        https://oauth2.googleapis.com/token مع grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer
        للحصول على access token صالح لمدة ساعة.

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل التوقيع/التبديل.
        """
        if not self._client_email or not self._private_key:
            raise ConnectorAuthenticationError(
                "Google Workspace: client_email و private_key مطلوبان لمصادقة Service Account",
            )

        now = int(time.time())
        payload: dict[str, Any] = {
            "iss": self._client_email,
            "scope": " ".join(self._scopes),
            "aud": self.OAUTH_TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        }
        if self._subject:
            payload["sub"] = self._subject  # تفويض نيابة عن مستخدم (DWD)

        try:
            signed_jwt = _sign_rs256(payload, self._private_key)
        except ConnectorError as exc:
            raise ConnectorAuthenticationError(str(exc)) from exc

        async with httpx.AsyncClient(timeout=self.config.connect_timeout) as auth_client:
            try:
                response = await auth_client.post(
                    self.OAUTH_TOKEN_URL,
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": signed_jwt,
                    },
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
            except httpx.HTTPError as exc:
                raise ConnectorAuthenticationError(
                    f"Google Workspace: فشل الاتصال بخادم OAuth2: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"Google Workspace: فشل تبديل JWT (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        token_payload = response.json()
        self._access_token = token_payload.get("access_token")
        if not self._access_token:
            raise ConnectorAuthenticationError(
                "Google Workspace: لم يُرجع خادم OAuth2 access_token",
            )
        expires_in = int(token_payload.get("expires_in", 3600))
        self._token_expires_at = time.time() + max(60, expires_in - 60)

        if self._client is not None:
            self._client.headers.update({
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
            })

        logger.info(
            "Google Workspace: تم الحصول على access token للعميل '%s' (ينتهي خلال %ss)",
            self._client_email, expires_in,
        )

    async def _ensure_token(self) -> None:
        """تجديد access token عند انتهاء صلاحيته."""
        if self._access_token is None or time.time() >= self._token_expires_at:
            await self.authenticate()

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة الموصل عبر التحقق من صلاحية access token.

        يستخدم endpoint tokeninfo في Google OAuth2 لفحص خفيف دون استهلاك حصة API.
        """
        start = time.monotonic()
        try:
            await self._ensure_token()
            if self._access_token is None:
                raise ConnectorError("Google Workspace: access token غير متوفر")
            async with httpx.AsyncClient(timeout=self.config.health_check_timeout) as client:
                response = await client.get(
                    f"https://www.googleapis.com/oauth2/v1/tokeninfo",
                    params={"access_token": self._access_token},
                )
            latency_ms = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                info = response.json()
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={
                        "http_status": 200,
                        "scope": info.get("scope", "")[:100],
                        "expires_in": info.get("expires_in"),
                        "audience": info.get("audience") or info.get("issued_to"),
                    },
                )
            if response.status_code == 400:
                return HealthResult(
                    status=HealthStatus.UNHEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 400, "reason": "invalid_token"},
                    error="token غير صالح أو منتهي",
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
    #  Google API Helpers
    # ───────────────────────────────────────────────────────────────────
    async def _api_request(
        self,
        method: str,
        base_url: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
        content: Optional[bytes] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """تنفيذ طلب على أحد Google APIs.

        Args:
            method: HTTP method.
            base_url: عنوان API الأساسي (Gmail/Drive/Calendar).
            path: مسار الطلب (يبدأ بـ /).
            params: معاملات الاستعلام.
            json_body: محتوى JSON (للطلبات العادية).
            content: محتوى ثنائي (للرفع متعدد الأجزاء).
            headers: ترويسات إضافية.
        """
        if self._client is None:
            raise ConnectorError("Google Workspace: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()
        url = f"{base_url.rstrip('/')}{path}"
        try:
            response = await self._client.request(
                method, url,
                params=params, json=json_body,
                content=content, headers=headers or {},
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"Google Workspace: فشل {method} على {url}: {exc}",
            ) from exc
        return self._handle_response(response, url, method)

    def _handle_response(
        self, response: httpx.Response, url: str, method: str,
    ) -> Any:
        """معالجة استجابة Google API وإرجاع JSON أو رفع خطأ مفهوم."""
        if response.status_code == 204:
            return {"status": "success", "no_content": True}
        if response.status_code >= 400:
            try:
                error_body = response.json()
                err = error_body.get("error", {})
                err_msg = err.get("message", response.text[:500])
                err_code = err.get("code", response.status_code)
                err_status = err.get("status", "")
            except ValueError:
                err_msg = response.text[:500]
                err_code = response.status_code
                err_status = ""
            raise ConnectorError(
                f"Google Workspace: خطأ Google API في {method} {url} "
                f"(HTTP {response.status_code}) [{err_code}/{err_status}]: {err_msg}",
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError(
                f"Google Workspace: استجابة غير صالحة JSON من {url}: {exc}",
            ) from exc

    def _gmail_user(self, user_id: Optional[str]) -> str:
        """تطبيع معرّف المستخدم لـ Gmail (special-me فقط)."""
        return user_id or self._subject or "me"

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في رسائل Gmail و ملفات Drive.

        Args:
            query: نص البحث (يدعم صيغة Gmail q أو Drive q).
            **kwargs:
                target (str): 'emails' (افتراضي) أو 'files' أو 'both'.
                user_id (str): معرف مستخدم Gmail (افتراضيًا 'me' أو subject).
                limit (int): عدد النتائج (افتراضيًا 25).

        Returns:
            قائمة بالنتائج الموحدة.
        """
        target: str = kwargs.pop("target", "emails")
        limit: int = int(kwargs.pop("limit", 25))
        results: list[dict[str, Any]] = []

        if target in ("emails", "both"):
            user_id = self._gmail_user(kwargs.get("user_id"))
            data = await self._api_request(
                "GET", self.GMAIL_API_BASE,
                f"/users/{user_id}/messages",
                params={"q": query, "maxResults": str(max(1, min(limit, 500)))},
            )
            for msg_ref in data.get("messages", []):
                # جلب بيانات مختصرة لكل رسالة
                msg = await self._api_request(
                    "GET", self.GMAIL_API_BASE,
                    f"/users/{user_id}/messages/{msg_ref.get('id')}",
                    params={"format": "metadata", "metadataHeaders": ["Subject", "From"]},
                )
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                results.append({
                    "source": "gmail",
                    "id": msg.get("id"),
                    "thread_id": msg.get("threadId"),
                    "subject": headers.get("Subject"),
                    "from": headers.get("From"),
                    "snippet": msg.get("snippet"),
                    "internal_date": msg.get("internalDate"),
                })

        if target in ("files", "both"):
            data = await self._api_request(
                "GET", self.DRIVE_API_BASE, "/files",
                params={
                    "q": query,
                    "pageSize": str(max(1, min(limit, 1000))),
                    "fields": "files(id,name,mimeType,modifiedTime,size,webViewLink)",
                },
            )
            for f in data.get("files", []):
                results.append({
                    "source": "drive",
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "mime_type": f.get("mimeType"),
                    "size": f.get("size"),
                    "modified_time": f.get("modifiedTime"),
                    "web_view_link": f.get("webViewLink"),
                })

        return results

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Google Workspace.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "send_email": self._send_email,
            "list_emails": self._list_emails,
            "list_files": self._list_files,
            "upload_file": self._upload_file,
            "create_event": self._create_event,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"Google Workspace: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _send_email(self, **kw: Any) -> dict[str, Any]:
        """إرسال بريد عبر Gmail.

        Args (via kwargs):
            to (list[str]): المستلمون (مطلوب).
            subject (str): الموضوع (مطلوب).
            body (str): المحتوى (مطلوب).
            cc (list[str]): نسخة.
            bcc (list[str]): نسخة مخفية.
            body_type (str): 'text' أو 'html' (افتراضيًا 'text').
            user_id (str): معرف المستخدم (افتراضيًا 'me' أو subject).
            attachments (list[dict]): مرفقات بصيغة {filename, content_base64, mime_type}.
        """
        to = kw.get("to")
        subject = kw.get("subject")
        body_text = kw.get("body")
        if not to or not subject or body_text is None:
            raise ConnectorError(
                "Google Workspace: send_email يتطلب 'to' و 'subject' و 'body'",
            )
        body_type = kw.get("body_type", "text")
        user_id = self._gmail_user(kw.get("user_id"))

        # بناء رسالة RFC 2822
        lines: list[str] = [
            f"To: {', '.join(to)}",
            f"Subject: {subject}",
        ]
        if kw.get("cc"):
            lines.append(f"Cc: {', '.join(kw['cc'])}")
        if kw.get("bcc"):
            lines.append(f"Bcc: {', '.join(kw['bcc'])}")
        if body_type == "html":
            lines.append("Content-Type: text/html; charset=utf-8")
        else:
            lines.append("Content-Type: text/plain; charset=utf-8")
        lines.append("")
        lines.append(body_text)
        raw_msg = "\r\n".join(lines)
        raw_b64 = base64.urlsafe_b64encode(raw_msg.encode("utf-8")).decode("ascii")

        data = await self._api_request(
            "POST", self.GMAIL_API_BASE,
            f"/users/{user_id}/messages:send",
            json_body={"raw": raw_b64},
        )
        return {
            "status": "sent",
            "message_id": data.get("id"),
            "thread_id": data.get("threadId"),
        }

    async def _list_emails(self, **kw: Any) -> dict[str, Any]:
        """سرد رسائل Gmail.

        Args (via kwargs):
            user_id (str): معرف المستخدم (افتراضيًا 'me' أو subject).
            limit (int): عدد النتائج (افتراضيًا 50).
            query (str): فلتر Gmail q (مثل 'is:unread').
            label_ids (list[str]): فلترة بالتصنيفات (مثل ['INBOX']).
        """
        user_id = self._gmail_user(kw.get("user_id"))
        limit = int(kw.get("limit", 50))
        params: dict[str, Any] = {"maxResults": str(max(1, min(limit, 500)))}
        if kw.get("query"):
            params["q"] = kw["query"]
        if kw.get("label_ids"):
            params["labelIds"] = ",".join(kw["label_ids"])
        data = await self._api_request(
            "GET", self.GMAIL_API_BASE,
            f"/users/{user_id}/messages",
            params=params,
        )
        messages: list[dict[str, Any]] = []
        for msg_ref in data.get("messages", []):
            msg = await self._api_request(
                "GET", self.GMAIL_API_BASE,
                f"/users/{user_id}/messages/{msg_ref.get('id')}",
                params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
            )
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            messages.append({
                "id": msg.get("id"),
                "thread_id": msg.get("threadId"),
                "subject": headers.get("Subject"),
                "from": headers.get("From"),
                "date": headers.get("Date"),
                "snippet": msg.get("snippet"),
                "label_ids": msg.get("labelIds", []),
            })
        return {
            "user_id": user_id,
            "count": len(messages),
            "emails": messages,
        }

    async def _list_files(self, **kw: Any) -> dict[str, Any]:
        """سرد ملفات Google Drive.

        Args (via kwargs):
            limit (int): عدد النتائج (افتراضيًا 100).
            query (str): فلتر Drive q (مثل "mimeType='application/pdf'").
            fields (list[str]): الحقول المطلوبة.
            order_by (str): ترتيب (مثل 'modifiedTime desc').
            page_size (int): حجم الصفحة (مستخدم داخليًا).
        """
        limit = int(kw.get("limit", 100))
        query = kw.get("query")
        params: dict[str, Any] = {
            "pageSize": str(max(1, min(limit, 1000))),
            "fields": kw.get("fields") and ",".join(kw["fields"]) or
            "files(id,name,mimeType,size,modifiedTime,createdTime,webViewLink,parents)",
        }
        if query:
            params["q"] = query
        if kw.get("order_by"):
            params["orderBy"] = kw["order_by"]
        data = await self._api_request(
            "GET", self.DRIVE_API_BASE, "/files", params=params,
        )
        return {
            "count": len(data.get("files", [])),
            "files": data.get("files", []),
            "next_page_token": data.get("nextPageToken"),
        }

    async def _upload_file(self, **kw: Any) -> dict[str, Any]:
        """رفع ملف إلى Google Drive (رفع بسيط متعدد الأجزاء).

        Args (via kwargs):
            name (str): اسم الملف في Drive (مطلوب).
            content_base64 (str): محتوى الملف مُرمَّز base64 (مطلوب).
            mime_type (str): نوع MIME (افتراضيًا application/octet-stream).
            description (str): وصف اختياري.
            parent_folder_id (str): معرف المجلد الأب.
        """
        name = kw.get("name")
        content_b64 = kw.get("content_base64")
        if not name or not content_b64:
            raise ConnectorError(
                "Google Workspace: upload_file يتطلب 'name' و 'content_base64'",
            )
        mime_type = kw.get("mime_type", "application/octet-stream")
        try:
            content = base64.b64decode(content_b64)
        except Exception as exc:
            raise ConnectorError(
                f"Google Workspace: فشل فك ترميز base64: {exc}",
            ) from exc

        metadata: dict[str, Any] = {"name": name, "mimeType": mime_type}
        if kw.get("description"):
            metadata["description"] = kw["description"]
        if kw.get("parent_folder_id"):
            metadata["parents"] = [kw["parent_folder_id"]]

        # بناء طلب multipart/related يدويًا
        boundary = f"hsaai_boundary_{int(time.time() * 1000)}"
        body_parts: list[bytes] = []
        body_parts.append(f"--{boundary}\r\n".encode("ascii"))
        body_parts.append(b"Content-Type: application/json; charset=UTF-8\r\n\r\n")
        body_parts.append(json.dumps(metadata).encode("utf-8"))
        body_parts.append(f"\r\n--{boundary}\r\n".encode("ascii"))
        body_parts.append(f"Content-Type: {mime_type}\r\n\r\n".encode("ascii"))
        body_parts.append(content)
        body_parts.append(f"\r\n--{boundary}--\r\n".encode("ascii"))
        body_bytes = b"".join(body_parts)

        # طلب الرفع يستخدم upload endpoint خاص
        if self._client is None:
            raise ConnectorError("Google Workspace: العميل غير مهيأ")
        await self._ensure_token()
        url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
        try:
            response = await self._client.post(
                url,
                content=body_bytes,
                headers={
                    "Content-Type": f"multipart/related; boundary={boundary}",
                    "Authorization": f"Bearer {self._access_token}",
                },
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"Google Workspace: فشل رفع الملف: {exc}",
            ) from exc
        data = self._handle_response(response, url, "POST")
        return {
            "status": "uploaded",
            "file_id": data.get("id"),
            "name": data.get("name"),
            "mime_type": data.get("mimeType"),
            "file": data,
        }

    async def _create_event(self, **kw: Any) -> dict[str, Any]:
        """إنشاء حدث في Google Calendar.

        Args (via kwargs):
            calendar_id (str): معرف التقويم (افتراضيًا 'primary').
            summary (str): عنوان الحدث (مطلوب).
            start (str): وقت البدء ISO 8601 (مثل 2024-01-01T10:00:00Z).
            end (str): وقت الانتياه ISO 8601.
            timezone (str): المنطقة الزمنية (مثل 'Asia/Riyadh').
            description (str): وصف الحدث.
            location (str): الموقع.
            attendees (list[str]): قائمة ببريد المشاركين.
            send_updates (str): 'all'/'externalOnly'/'none' (افتراضيًا 'all').
        """
        calendar_id = kw.get("calendar_id", "primary")
        summary = kw.get("summary")
        start = kw.get("start")
        end = kw.get("end")
        if not summary or not start or not end:
            raise ConnectorError(
                "Google Workspace: create_event يتطلب 'summary' و 'start' و 'end'",
            )
        tz = kw.get("timezone")
        start_obj: dict[str, Any] = {"dateTime": start}
        end_obj: dict[str, Any] = {"dateTime": end}
        if tz:
            start_obj["timeZone"] = tz
            end_obj["timeZone"] = tz
        event: dict[str, Any] = {
            "summary": summary,
            "start": start_obj,
            "end": end_obj,
        }
        if kw.get("description"):
            event["description"] = kw["description"]
        if kw.get("location"):
            event["location"] = kw["location"]
        if kw.get("attendees"):
            event["attendees"] = [{"email": e} for e in kw["attendees"]]
        params: dict[str, Any] = {
            "sendUpdates": kw.get("send_updates", "all"),
        }
        data = await self._api_request(
            "POST", self.CALENDAR_API_BASE,
            f"/calendars/{calendar_id}/events",
            params=params, json_body=event,
        )
        return {
            "status": "created",
            "event_id": data.get("id"),
            "html_link": data.get("htmlLink"),
            "hangout_link": data.get("hangoutLink"),
            "event": data,
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
            "protocol": "Google REST APIs (Gmail + Drive + Calendar) + JWT",
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "read": True,
                "upload": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "scopes": list(self._scopes),
            "service_account_email": self._client_email,
            "delegated_user": self._subject or None,
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:google_workspace:read",
            "connector:google_workspace:write",
            "gmail:send",
            "gmail:read",
            "drive:read",
            "drive:write",
            "calendar:event:create",
        ]
