"""
موصل Microsoft Azure AD / Entra ID لمنصة HSAAI
=================================================
يتيح هذا الموصل الوصول إلى Microsoft Azure Active Directory (Entra ID)
عبر Microsoft Graph API مع مصادقة OAuth2 (client-credentials).

نقطة النهاية الأساسية:
    https://graph.microsoft.com/v1.0/

الإجراءات المدعومة:
    - list_users      : سرد المستخدمين في الـ tenant
    - get_user        : جلب مستخدم عبر userPrincipalName أو id
    - list_groups     : سرد المجموعات
    - create_user     : إنشاء مستخدم جديد
    - reset_password  : إعادة تعيين كلمة مرور مستخدم

search() يستخدم Graph API $search عبر حقول displayName, mail, userPrincipalName.

الاستخدام:
    cfg = ConnectorConfig(
        name="azure_ad",
        display_name="Corporate Azure AD",
        category="Identity",
        base_url="https://graph.microsoft.com",
        auth_strategy=AuthStrategy.OAUTH2_CLIENT_CREDENTIALS,
        secrets={
            "tenant_id": "...",
            "client_id": "...",
            "client_secret": "...",
        },
    )
    connector = AzureADConnector(cfg)
    await connector.connect()
    users = await connector.call("list_users", top=50)
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


@connector("azure_ad", version="1.0.0", category="Identity")
class AzureADConnector(BaseConnector):
    """موصل Microsoft Azure AD / Entra ID عبر Microsoft Graph API و OAuth2."""

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
        "list_users",
        "get_user",
        "list_groups",
        "create_user",
        "reset_password",
    )

    #: الحقول الافتراضية المُسترجَعة للمستخدم
    DEFAULT_USER_SELECT: list[str] = [
        "id", "userPrincipalName", "displayName", "givenName", "surname",
        "mail", "jobTitle", "department", "mobilePhone", "accountEnabled",
        "createdDateTime", "userType",
    ]

    #: الحقول الافتراضية المُسترجَعة للمجموعة
    DEFAULT_GROUP_SELECT: list[str] = [
        "id", "displayName", "description", "mailEnabled", "securityEnabled",
        "groupTypes", "createdDateTime",
    ]

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
        """مصادقة OAuth2 client-credentials مع Azure AD لـ MS Graph API.

        يطلب access token بنطاق https://graph.microsoft.com/.default.
        التوكن يُخزَّن ويُستخدم في ترويسة Authorization: Bearer.

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل المصادقة.
        """
        if not self._tenant_id or not self._client_id or not self._client_secret:
            raise ConnectorAuthenticationError(
                "Azure AD: tenant_id و client_id و client_secret مطلوبة للمصادقة",
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
                    headers={"Accept": "application/json"},
                )
            except httpx.HTTPError as exc:
                raise ConnectorAuthenticationError(
                    f"Azure AD: فشل الاتصال بـ Azure AD: {exc}",
                ) from exc

        if response.status_code != 200:
            raise ConnectorAuthenticationError(
                f"Azure AD: فشل المصادقة (HTTP {response.status_code}): "
                f"{response.text[:300]}",
            )

        token_data = response.json()
        self._access_token = token_data.get("access_token")
        if not self._access_token:
            raise ConnectorAuthenticationError(
                "Azure AD: لم يُرجع Azure AD access_token",
            )

        expires_in = int(token_data.get("expires_in", 3600))
        self._token_expires_at = time.time() + max(60, expires_in - 60)

        if self._client is not None:
            self._client.headers.update({
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            })

        logger.info(
            "Azure AD: تم الحصول على access token (ينتهي خلال %ss)", expires_in,
        )

    async def _ensure_token(self) -> None:
        """تجديد access token تلقائيًا عند اقتراب انتهاء صلاحيته."""
        if self._access_token is None or time.time() >= self._token_expires_at:
            await self.authenticate()

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة Graph API عبر طلب /organization (خفيف وسريع).

        Returns:
            HealthResult مع حالة الخدمة وزمن الاستجابة.
        """
        start = time.monotonic()
        try:
            await self._ensure_token()
            if self._client is None:
                raise ConnectorError("Azure AD: العميل غير مهيأ — استدعِ connect() أولاً")
            response = await self._client.get(
                f"{self._graph_path}/organization",
                params={"$top": "1"},
            )
            latency_ms = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 200, "endpoint": "organization"},
                )
            if response.status_code == 401:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 401, "reason": "token_expired"},
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
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        consistency_level: Optional[str] = None,
    ) -> dict[str, Any]:
        """تنفيذ طلب GET على Graph API.

        Args:
            path: المسار بعد /v1.0/ (مثل 'users').
            params: معاملات الاستعلام ($filter, $select, $search, $top, ...).
            consistency_level: ترويسة ConsistencyLevel (مطلوبة لـ $search و
                بعض استعلامات $count المتقدمة).

        Returns:
            قاموس Graph API الخام (يحتوي عادةً على 'value' و '@odata.context').

        Raises:
            ConnectorError: عند فشل الطلب.
        """
        if self._client is None:
            raise ConnectorError("Azure AD: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()

        headers: dict[str, str] = {}
        if consistency_level:
            headers["ConsistencyLevel"] = consistency_level

        try:
            response = await self._client.get(
                f"{self._graph_path}/{path}",
                params=params,
                headers=headers or None,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"Azure AD: فشل GET على {path}: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"Azure AD: خطأ Graph API في GET {path} "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )
        return response.json()

    async def _graph_post(
        self, path: str, payload: dict[str, Any],
        *, params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """تنفيذ طلب POST على Graph API (لإنشاء موارد).

        Args:
            path: المسار بعد /v1.0/.
            payload: حمولة JSON للمورد الجديد.
            params: معاملات استعلام اختيارية.

        Returns:
            قاموس المورد المُنشأ (عادةً 201 Created).

        Raises:
            ConnectorError: عند فشل الإنشاء.
        """
        if self._client is None:
            raise ConnectorError("Azure AD: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()

        try:
            response = await self._client.post(
                f"{self._graph_path}/{path}",
                json=payload,
                params=params,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"Azure AD: فشل POST على {path}: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"Azure AD: خطأ Graph API في POST {path} "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )
        if response.content:
            try:
                return response.json()
            except ValueError:
                return {"status": "created", "raw": response.text}
        return {"status": "created"}

    async def _graph_patch(
        self, path: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        """تنفيذ طلب PATCH على Graph API (لتحديث مورد).

        Args:
            path: المسار بعد /v1.0/.
            payload: الحقول المُحدَّثة.

        Returns:
            قاموس الحالة (عادةً 204 No Content).

        Raises:
            ConnectorError: عند فشل التحديث.
        """
        if self._client is None:
            raise ConnectorError("Azure AD: العميل غير مهيأ — استدعِ connect() أولاً")
        await self._ensure_token()

        try:
            response = await self._client.patch(
                f"{self._graph_path}/{path}",
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"Azure AD: فشل PATCH على {path}: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"Azure AD: خطأ Graph API في PATCH {path} "
                f"(HTTP {response.status_code}): {response.text[:500]}",
            )
        if response.content:
            try:
                return response.json()
            except ValueError:
                return {"status": "updated", "raw": response.text}
        return {"status": "updated"}

    # ───────────────────────────────────────────────────────────────────
    #  Search (via Graph $search)
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في المستخدمين عبر Graph API $search.

        يستخدم $search مع صيغة Microsoft: "displayName:query OR mail:query OR
        userPrincipalName:query". يتطلب ترويسة ConsistencyLevel: eventual.

        Args:
            query: نص البحث.
            **kwargs:
                entity (str): 'users' (افتراضي) أو 'groups' أو 'applications'.
                fields (list[str]): الحقول المُسترجَعة عبر $select.
                top (int): عدد النتائج (افتراضيًا 25، حد Graph 999).

        Returns:
            قائمة بالسجلات المطابقة.
        """
        entity: str = kwargs.pop("entity", "users")
        fields: list[str] = kwargs.pop("fields", self.DEFAULT_USER_SELECT)
        top: int = int(kwargs.pop("top", 25))

        # تنظيف النص لمنع حقن صيغة $search (إزالة علامات الاقتباس المزدوجة)
        safe_query = query.replace('"', "").strip()
        if not safe_query:
            return []

        # صيغة Graph $search: "field1:value" OR "field2:value"
        if entity == "users":
            search_expr = (
                f'"displayName:{safe_query}" OR '
                f'"mail:{safe_query}" OR '
                f'"userPrincipalName:{safe_query}"'
            )
        elif entity == "groups":
            search_expr = f'"displayName:{safe_query}" OR "description:{safe_query}"'
        else:
            search_expr = f'"displayName:{safe_query}"'

        params: dict[str, Any] = {
            "$search": search_expr,
            "$select": ",".join(fields),
            "$top": str(max(1, min(top, 999))),
            "$count": "true",
        }
        result = await self._graph_get(
            entity, params=params, consistency_level="eventual",
        )
        return result.get("value", [])

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Azure AD عبر Graph API.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "list_users": self._list_users,
            "get_user": self._get_user,
            "list_groups": self._list_groups,
            "create_user": self._create_user,
            "reset_password": self._reset_password,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"Azure AD: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _list_users(self, **kw: Any) -> dict[str, Any]:
        """سرد المستخدمين في الـ tenant.

        Args (via kwargs):
            top (int): عدد النتائج (افتراضيًا 50، حد Graph 999).
            skip (int): إزاحة الصفحات (يتطلب $count=true).
            filter (str): تعبير $filter مخصص.
            fields (list[str]): الحقول المُسترجَعة.
            search (str): نص $search اختياري (يتطلب ConsistencyLevel).
        """
        top: int = int(kw.get("top", 50))
        skip: int = int(kw.get("skip", 0))
        fields: list[str] = kw.get("fields", self.DEFAULT_USER_SELECT)
        filter_expr: Optional[str] = kw.get("filter")
        search_expr: Optional[str] = kw.get("search")

        params: dict[str, Any] = {
            "$top": str(max(1, min(top, 999))),
            "$select": ",".join(fields),
        }
        if skip > 0:
            params["$skip"] = str(skip)
            params["$count"] = "true"
        if filter_expr:
            params["$filter"] = filter_expr
            params["$count"] = "true"
        if search_expr:
            params["$search"] = search_expr

        consistency = "eventual" if (search_expr or skip > 0) else None
        result = await self._graph_get(
            "users", params=params, consistency_level=consistency,
        )
        return {
            "entity": "users",
            "count": len(result.get("value", [])),
            "value": result.get("value", []),
            "total": result.get("@odata.count"),
            "next_link": result.get("@odata.nextLink"),
        }

    async def _get_user(self, **kw: Any) -> dict[str, Any]:
        """جلب مستخدم عبر userPrincipalName أو id.

        Args (via kwargs):
            user_id (str): userPrincipalName أو object id (إلزامي).
            fields (list[str]): الحقول المُسترجَعة.

        Raises:
            ConnectorError: عند فقدان user_id أو عدم العثور على المستخدم.
        """
        user_id: Optional[str] = kw.get("user_id")
        if not user_id:
            raise ConnectorError("Azure AD: 'user_id' إلزامي لإجراء get_user")
        fields: list[str] = kw.get("fields", self.DEFAULT_USER_SELECT)
        # تنظيف user_id لمنع حقن المسار
        safe_id = user_id.replace("'", "").replace("/", "")
        try:
            result = await self._graph_get(
                f"users/{safe_id}",
                params={"$select": ",".join(fields)},
            )
        except ConnectorError as exc:
            if "404" in str(exc):
                raise ConnectorError(
                    f"Azure AD: المستخدم '{user_id}' غير موجود",
                ) from exc
            raise
        return result

    async def _list_groups(self, **kw: Any) -> dict[str, Any]:
        """سرد المجموعات في الـ tenant.

        Args (via kwargs):
            top (int): عدد النتائج (افتراضيًا 50).
            skip (int): إزاحة الصفحات.
            filter (str): تعبير $filter مخصص.
            fields (list[str]): الحقول المُسترجَعة.
        """
        top: int = int(kw.get("top", 50))
        skip: int = int(kw.get("skip", 0))
        fields: list[str] = kw.get("fields", self.DEFAULT_GROUP_SELECT)
        filter_expr: Optional[str] = kw.get("filter")

        params: dict[str, Any] = {
            "$top": str(max(1, min(top, 999))),
            "$select": ",".join(fields),
        }
        if skip > 0:
            params["$skip"] = str(skip)
            params["$count"] = "true"
        if filter_expr:
            params["$filter"] = filter_expr
            params["$count"] = "true"

        consistency = "eventual" if (skip > 0 or filter_expr) else None
        result = await self._graph_get(
            "groups", params=params, consistency_level=consistency,
        )
        return {
            "entity": "groups",
            "count": len(result.get("value", [])),
            "value": result.get("value", []),
            "total": result.get("@odata.count"),
            "next_link": result.get("@odata.nextLink"),
        }

    async def _create_user(self, **kw: Any) -> dict[str, Any]:
        """إنشاء مستخدم جديد في Azure AD.

        Args (via kwargs):
            user_principal_name (str): UPN (إلزامي، مثل 'ahmed@contoso.com').
            display_name (str): الاسم الكامل (إلزامي).
            mail_nickname (str): اسم البريد المختصر (افتراضيًا جزء UPN قبل @).
            password (str): كلمة المرور الأولية (إلزامي — يجب أن تفي
                بسياسة كلمات مرور Azure AD).
            account_enabled (bool): تفعيل الحساب (افتراضيًا True).
            given_name (str): الاسم الأول (اختياري).
            surname (str): اسم العائلة (اختياري).
            job_title (str): المسمى الوظيفي (اختياري).
            department (str): القسم (اختياري).
            usage_location (str): رمز الدولة (مطلوب لتعيين التراخيص، مثل 'SA').

        Raises:
            ConnectorError: عند فقدان الحقول الإلزامية أو فشل الإنشاء.
        """
        upn: Optional[str] = kw.get("user_principal_name")
        display_name: Optional[str] = kw.get("display_name")
        password: Optional[str] = kw.get("password")
        if not upn or not display_name or not password:
            raise ConnectorError(
                "Azure AD: 'user_principal_name', 'display_name', 'password' إلزامية لإنشاء مستخدم",
            )

        mail_nickname: str = kw.get("mail_nickname") or upn.split("@")[0]
        payload: dict[str, Any] = {
            "accountEnabled": bool(kw.get("account_enabled", True)),
            "displayName": display_name,
            "mailNickname": mail_nickname,
            "userPrincipalName": upn,
            "passwordProfile": {
                "forceChangePasswordNextSignIn": True,
                "password": password,
            },
        }
        # حقول اختيارية
        optional_fields = ("given_name", "surname", "job_title", "department",
                          "usage_location", "mobile_phone", "street_address",
                          "city", "state", "country", "postal_code")
        field_map = {
            "given_name": "givenName",
            "surname": "surname",
            "job_title": "jobTitle",
            "department": "department",
            "usage_location": "usageLocation",
            "mobile_phone": "mobilePhone",
            "street_address": "streetAddress",
            "city": "city",
            "state": "state",
            "country": "country",
            "postal_code": "postalCode",
        }
        for src, dst in field_map.items():
            value = kw.get(src)
            if value:
                payload[dst] = value

        return await self._graph_post("users", payload)

    async def _reset_password(self, **kw: Any) -> dict[str, Any]:
        """إعادة تعيين كلمة مرور مستخدم في Azure AD.

        Args (via kwargs):
            user_id (str): userPrincipalName أو object id (إلزامي).
            new_password (str): كلمة المرور الجديدة (إلزامي).
            force_change (bool): إجبار المستخدم على تغييرها عند تسجيل الدخول
                التالي (افتراضيًا True).

        Raises:
            ConnectorError: عند فقدان الحقول الإلزامية أو فشل التحديث.
        """
        user_id: Optional[str] = kw.get("user_id")
        new_password: Optional[str] = kw.get("new_password")
        if not user_id or not new_password:
            raise ConnectorError(
                "Azure AD: 'user_id' و 'new_password' إلزامية لإعادة تعيين كلمة المرور",
            )
        safe_id = user_id.replace("'", "").replace("/", "")
        payload = {
            "passwordProfile": {
                "forceChangePasswordNextSignIn": bool(kw.get("force_change", True)),
                "password": new_password,
            },
        }
        return await self._graph_patch(f"users/{safe_id}", payload)

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
            "protocol": "Microsoft Graph API (Azure AD OAuth2 client-credentials)",
            "graph_api_version": self.GRAPH_API_VERSION,
            "graph_scope": self.GRAPH_SCOPE,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "read": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "endpoints": [
                "users", "groups", "organization", "applications",
                "servicePrincipals", "directoryRoles",
            ],
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل (RBAC)."""
        return self.config.required_permissions or [
            "connector:azure_ad:read",
            "connector:azure_ad:write",
            "aad:users:read",
            "aad:users:write",
            "aad:groups:read",
            "aad:password:reset",
        ]
