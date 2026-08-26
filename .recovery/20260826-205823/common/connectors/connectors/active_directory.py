"""
موصل Microsoft Active Directory / LDAP لمنصة HSAAI
=====================================================
يتيح هذا الموصل الوصول إلى Microsoft Active Directory أو أي خادم LDAP
متوافق عبر LDAPS (LDAP over SSL على المنفذ 636) باستخدام مكتبة ldap3.

الإجراءات المدعومة:
    - get_user           : جلب مستخدم عبر DN أو sAMAccountName
    - search_users       : البحث عن مستخدمين بصيغة LDAP filter
    - get_groups         : جلب المجموعات التي ينتمي إليها مستخدم
    - authenticate_user  : التحقق من صحة بيانات اعتماد مستخدم (bind)

ملاحظات:
    - مكتبة ldap3 متزامنة، لذا يُغلّف الموصل استدعاءاتها بـ asyncio.to_thread
      لجعلها متوافقة مع البنية async للـ BaseConnector.
    - إذا لم تكن مكتبة ldap3 مثبتة، يبقى الموصل قابلاً للاستيراد لكنه
      يرفع ConnectorError عند connect().

الاستخدام:
    cfg = ConnectorConfig(
        name="active_directory",
        display_name="Corporate Active Directory",
        category="Identity",
        base_url="ldaps://dc01.corp.local:636",
        auth_strategy=AuthStrategy.BASIC,
        secrets={
            "bind_dn": "CORP\\\\svc-ldap",
            "bind_password": "...",
        },
    )
    connector = ActiveDirectoryConnector(cfg)
    await connector.connect()
    user = await connector.call("get_user", username="ahmed.ali")
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

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

# محاولة استيراد ldap3 مع fallback أنيق
try:
    import ldap3
    from ldap3 import (
        ALL as LDAP3_ALL,
        SUBTREE as LDAP3_SUBTREE,
        Connection as LDAP3Connection,
        Server as LDAP3Server,
        Tls as LDAP3Tls,
    )
    import ssl as _ssl
    _LDAP3_AVAILABLE = True
except ImportError:  # pragma: no cover - defensive
    ldap3 = None  # type: ignore[assignment]
    LDAP3_ALL = None  # type: ignore[assignment]
    LDAP3_SUBTREE = None  # type: ignore[assignment]
    LDAP3Connection = None  # type: ignore[assignment]
    LDAP3Server = None  # type: ignore[assignment]
    LDAP3Tls = None  # type: ignore[assignment]
    _ssl = None  # type: ignore[assignment]
    _LDAP3_AVAILABLE = False
    logger.warning(
        "active_directory: مكتبة ldap3 غير مثبتة — الموصل قابل للاستيراد "
        "لكن لن يعمل حتى تُثبت: pip install ldap3",
    )


@connector("active_directory", version="1.0.0", category="Identity")
class ActiveDirectoryConnector(BaseConnector):
    """موصل Active Directory / LDAP عبر LDAPS باستخدام مكتبة ldap3."""

    #: المنفذ الافتراضي لـ LDAPS
    DEFAULT_LDAPS_PORT: int = 636

    #: قاعدة البحث الافتراضية (تُستبدل من config.search_base)
    DEFAULT_SEARCH_BASE: str = "DC=corp,DC=local"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "get_user",
        "search_users",
        "get_groups",
        "authenticate_user",
    )

    #: الحقول القياسية المُسترجعة من مستخدم AD
    DEFAULT_USER_ATTRIBUTES: tuple[str, ...] = (
        "sAMAccountName", "userPrincipalName", "displayName", "givenName",
        "sn", "mail", "telephoneNumber", "title", "department",
        "memberOf", "distinguishedName", "userAccountControl",
        "whenCreated", "whenChanged", "lastLogon",
    )

    #: الحقول القياسية المُسترجعة من مجموعة AD
    DEFAULT_GROUP_ATTRIBUTES: tuple[str, ...] = (
        "cn", "distinguishedName", "description", "member", "groupType",
    )

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        # حذف العميل httpx لأن LDAP لا يستخدم HTTP
        self._client = None  # type: ignore[assignment]

        self._bind_dn: str = self._get_secret("bind_dn", "")
        self._bind_password: str = self._get_secret("bind_password", "")
        self._search_base: str = getattr(
            self.config, "search_base", self.DEFAULT_SEARCH_BASE,
        )
        self._ldap_server: Any = None  # LDAP3Server instance
        self._ldap_connection: Any = None  # LDAP3Connection instance
        # خيارات TLS
        self._validate_cert: bool = bool(
            getattr(self.config, "validate_cert", True),
        )
        self._ldap_url: str = self.config.base_url

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
        """إنشاء اتصال LDAP مُصادَق (bind) بخادم Active Directory.

        يقوم ببناء LDAP3Server (مع TLS) ثم Connection مع bind باستخدام
        bind_dn و bind_password. الـ bind المتزامن يُغلَّف بـ asyncio.to_thread.

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد أو فشل الـ bind.
            ConnectorError: إذا لم تكن مكتبة ldap3 متوفرة.
        """
        if not _LDAP3_AVAILABLE:
            raise ConnectorError(
                "active_directory: مكتبة ldap3 غير مثبتة. ثبّتها عبر: pip install ldap3",
            )
        if not self._bind_dn or not self._bind_password:
            raise ConnectorAuthenticationError(
                "active_directory: bind_dn و bind_password مطلوبان للمصادقة",
            )

        # بناء خادم LDAP مع TLS
        tls_config = LDAP3Tls(
            validate=_ssl.CERT_REQUIRED if self._validate_cert else _ssl.CERT_NONE,
            version=_ssl.PROTOCOL_TLS_CLIENT,
        )
        self._ldap_server = LDAP3Server(
            self._ldap_url,
            use_ssl=True,
            tls=tls_config,
            get_info=LDAP3_ALL,
            connect_timeout=int(self.config.connect_timeout),
        )

        # بناء الاتصال (دون bind تلقائي — سنفعل bind يدويًا للتحكم بالأخطاء)
        self._ldap_connection = LDAP3Connection(
            server=self._ldap_server,
            user=self._bind_dn,
            password=self._bind_password,
            auto_bind=False,
            read_only=True,
            receive_timeout=self.config.read_timeout,
        )

        # تنفيذ الـ bind في thread منفصل (ldap3 متزامن)
        try:
            bind_ok = await asyncio.to_thread(self._ldap_connection.bind)
        except Exception as exc:
            raise ConnectorAuthenticationError(
                f"active_directory: فشل bind إلى {self._ldap_url}: {exc}",
            ) from exc

        if not bind_ok:
            result = self._ldap_connection.result
            raise ConnectorAuthenticationError(
                f"active_directory: فشل bind — رمز: {result.get('result')} "
                f"({result.get('description')}, {result.get('message')})",
            )

        logger.info(
            "active_directory: تم الـ bind بنجاح إلى %s كـ %s",
            self._ldap_url, self._bind_dn,
        )

    async def _ensure_bound(self) -> None:
        """التأكد من أن الاتصال ما زال مفتوحًا ومُصادَقًا، وإعادة الـ bind عند الحاجة."""
        if self._ldap_connection is None:
            await self.authenticate()
            return
        if not self._ldap_connection.bound:
            await self.authenticate()

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة خادم Active Directory عبر جلب server info والتحقق من الـ bind.

        Returns:
            HealthResult مع حالة الخادم وزمن الاستجابة.
        """
        start = time.monotonic()
        try:
            if not _LDAP3_AVAILABLE:
                return HealthResult(
                    status=HealthStatus.UNHEALTHY,
                    connector=self.config.name,
                    latency_ms=0.0,
                    error="ldap3 library not installed",
                )
            await self._ensure_bound()
            # إجراء بحث خفيف للتحقق من الاستجابة
            ok, _, _, _ = await asyncio.to_thread(
                self._ldap_connection.search,
                search_base=self._search_base,
                search_filter="(objectClass=domain)",
                search_scope=LDAP3_SUBTREE,
                attributes=["distinguishedName"],
                size_limit=1,
            )
            latency_ms = (time.monotonic() - start) * 1000
            if ok:
                server_info = self._ldap_server.info or {}
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={
                        "server": self._ldap_url,
                        "naming_contexts": server_info.get("naming_contexts", [])[:3],
                        "domain_functionality": server_info.get("domain_functionality"),
                    },
                )
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=latency_ms,
                error=f"LDAP search failed: {self._ldap_connection.result}",
            )
        except Exception as exc:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=(time.monotonic() - start) * 1000,
                error=str(exc),
            )

    # ───────────────────────────────────────────────────────────────────
    #  LDAP Helpers
    # ───────────────────────────────────────────────────────────────────
    async def _ldap_search(
        self,
        search_filter: str,
        *,
        attributes: Optional[list[str]] = None,
        search_base: Optional[str] = None,
        size_limit: int = 100,
    ) -> list[dict[str, Any]]:
        """تنفيذ LDAP search بصورة async (عبر to_thread) وإرجاع النتائج مُنسَّقة.

        Args:
            search_filter: فلتر LDAP بصيغة RFC 4515 (مثل '(sAMAccountName=ahmed*)').
            attributes: قائمة السمات المطلوبة (افتراضيًا: DEFAULT_USER_ATTRIBUTES).
            search_base: قاعدة البحث (افتراضيًا: self._search_base).
            size_limit: الحد الأقصى للنتائج.

        Returns:
            قائمة من {dn: str, attributes: dict[str, list[Any]]}.

        Raises:
            ConnectorError: عند فشل البحث.
        """
        if not _LDAP3_AVAILABLE:
            raise ConnectorError(
                "active_directory: ldap3 غير متوفرة. ثبّتها عبر: pip install ldap3",
            )
        if self._ldap_connection is None:
            raise ConnectorError(
                "active_directory: الاتصال غير مهيأ — استدعِ connect() أولاً",
            )
        await self._ensure_bound()

        attrs = attributes or list(self.DEFAULT_USER_ATTRIBUTES)
        base = search_base or self._search_base

        try:
            success, response = await asyncio.to_thread(
                self._ldap_connection.search,
                search_base=base,
                search_filter=search_filter,
                search_scope=LDAP3_SUBTREE,
                attributes=attrs,
                size_limit=size_limit,
                time_limit=int(self.config.read_timeout),
            )
        except Exception as exc:
            raise ConnectorError(
                f"active_directory: فشل LDAP search '{search_filter}': {exc}",
            ) from exc

        if not success:
            result = self._ldap_connection.result or {}
            # noSuchObject (32) ليست خطأ فادحًا — تعني عدم وجود نتائج
            if result.get("result") == 32:
                return []
            raise ConnectorError(
                f"active_directory: خطأ LDAP search '{search_filter}': "
                f"{result.get('description')} ({result.get('result')}): "
                f"{result.get('message')}",
            )

        results: list[dict[str, Any]] = []
        for entry in response or []:
            if entry.get("type") != "searchResEntry":
                continue
            raw_attrs = entry.get("attributes", {}) or {}
            # ldap3 يُرجع السمات بصيغة dict[str, list[Any]]
            clean_attrs = {
                key: (vals[0] if isinstance(vals, list) and len(vals) == 1 else vals)
                for key, vals in raw_attrs.items()
            }
            results.append({
                "dn": entry.get("dn", ""),
                "attributes": clean_attrs,
            })
        return results

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في مستخدمي/مجموعات AD باستخدام استعلام نصي حر.

        يحوّل النص إلى فلتر LDAP يبحث في: sAMAccountName, displayName,
        givenName, sn, mail, userPrincipalName.

        Args:
            query: نص البحث.
            **kwargs:
                object_class (str): 'user' أو 'group' (افتراضيًا 'user').
                size_limit (int): الحد الأقصى للنتائج (افتراضيًا 100).
                search_base (str): قاعدة بحث مخصصة.

        Returns:
            قائمة بالنتائج {dn, attributes}.
        """
        object_class: str = kwargs.pop("object_class", "user")
        size_limit: int = int(kwargs.pop("size_limit", 100))
        search_base: Optional[str] = kwargs.pop("search_base", None)

        # تنظيف النص لمنع حقن LDAP (تجاوز الأقواس)
        safe_query = query.replace("\\", "\\5c").replace("*", "\\2a")
        safe_query = safe_query.replace("(", "\\28").replace(")", "\\29")
        safe_query = safe_query.replace("\x00", "\\00").strip()
        if not safe_query:
            return []

        # بناء فلتر LDAP مركّب: (&(objectClass=user)(|(sAMAccountName=*q*)(...)))
        if object_class == "group":
            fields = ["cn", "description", "displayName"]
        else:
            fields = [
                "sAMAccountName", "displayName", "givenName",
                "sn", "mail", "userPrincipalName",
            ]
        sub_filters = "".join(
            f"({f}=*{safe_query}*)" for f in fields
        )
        search_filter = (
            f"(&(objectClass={object_class})(|{sub_filters}))"
        )
        attrs = list(
            self.DEFAULT_GROUP_ATTRIBUTES if object_class == "group"
            else self.DEFAULT_USER_ATTRIBUTES
        )
        return await self._ldap_search(
            search_filter,
            attributes=attrs,
            search_base=search_base,
            size_limit=size_limit,
        )

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Active Directory.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "get_user": self._get_user,
            "search_users": self._search_users,
            "get_groups": self._get_groups,
            "authenticate_user": self._authenticate_user,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"active_directory: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _get_user(self, **kw: Any) -> dict[str, Any]:
        """جلب مستخدم عبر sAMAccountName أو distinguishedName.

        Args (via kwargs):
            username (str): sAMAccountName أو userPrincipalName.
            dn (str): distinguishedName مباشر (بديل).
            attributes (list[str]): سمات مخصصة.
        """
        username: Optional[str] = kw.get("username")
        dn: Optional[str] = kw.get("dn")
        attributes: Optional[list[str]] = kw.get("attributes")
        if dn:
            # البحث مباشرةً في الـ DN
            search_filter = "(objectClass=*)"
            results = await self._ldap_search(
                search_filter,
                attributes=attributes,
                search_base=dn,
                size_limit=1,
            )
        elif username:
            # sAMAccountName أو userPrincipalName
            safe_user = username.replace("\\", "\\5c").replace("*", "\\2a")
            safe_user = safe_user.replace("(", "\\28").replace(")", "\\29")
            search_filter = (
                f"(&(objectClass=user)(|"
                f"(sAMAccountName={safe_user})"
                f"(userPrincipalName={safe_user})"
                f"))"
            )
            results = await self._ldap_search(
                search_filter, attributes=attributes, size_limit=1,
            )
        else:
            raise ConnectorError(
                "active_directory: get_user يتطلب 'username' أو 'dn'",
            )

        if not results:
            return {"found": False, "user": None}
        return {"found": True, "user": results[0]}

    async def _search_users(self, **kw: Any) -> dict[str, Any]:
        """البحث عن مستخدمين باستخدام فلتر LDAP مخصص.

        Args (via kwargs):
            filter (str): فلتر LDAP بصيغة RFC 4515.
            size_limit (int): الحد الأقصى للنتائج (افتراضيًا 100).
            attributes (list[str]): سمات مخصصة.
        """
        filter_expr: Optional[str] = kw.get("filter")
        if not filter_expr:
            raise ConnectorError(
                "active_directory: search_users يتطلب بارامتر 'filter'",
            )
        size_limit = int(kw.get("size_limit", 100))
        attributes: Optional[list[str]] = kw.get("attributes")
        # ضمان قصر البحث على المستخدمين
        if "objectClass=user" not in filter_expr:
            filter_expr = f"(&(objectClass=user){filter_expr})"
        results = await self._ldap_search(
            filter_expr, attributes=attributes, size_limit=size_limit,
        )
        return {
            "count": len(results),
            "users": results,
        }

    async def _get_groups(self, **kw: Any) -> dict[str, Any]:
        """جلب المجموعات التي ينتمي إليها مستخدم.

        Args (via kwargs):
            username (str): sAMAccountName للمستخدم.
            dn (str): distinguishedName للمستخدم (بديل).
        """
        # جلب المستخدم مع memberOf
        user_result = await self._get_user(
            username=kw.get("username"),
            dn=kw.get("dn"),
            attributes=["memberOf", "primaryGroupID", "distinguishedName"],
        )
        if not user_result.get("found"):
            return {"count": 0, "groups": []}
        member_of = user_result["user"]["attributes"].get("memberOf", [])
        if isinstance(member_of, str):
            member_of = [member_of]
        # جلب تفاصيل كل مجموعة
        groups: list[dict[str, Any]] = []
        for group_dn in member_of:
            try:
                group_results = await self._ldap_search(
                    "(objectClass=group)",
                    attributes=list(self.DEFAULT_GROUP_ATTRIBUTES),
                    search_base=group_dn,
                    size_limit=1,
                )
                if group_results:
                    groups.append(group_results[0])
            except ConnectorError as exc:
                logger.warning(
                    "active_directory: تعذّر جلب المجموعة %s: %s", group_dn, exc,
                )
        return {"count": len(groups), "groups": groups}

    async def _authenticate_user(self, **kw: Any) -> dict[str, Any]:
        """التحقق من صحة بيانات اعتماد مستخدم عبر LDAP bind منفصل.

        لا يُعيد استخدام اتصال الـ bind الخاص بالموصل؛ بل ينشئ اتصالاً
        مؤقتًا باسم المستخدم وكلمة المرور المُقدَّمة للتحقق.

        Args (via kwargs):
            username (str): sAMAccountName أو userPrincipalName أو DN.
            password (str): كلمة المرور المراد التحقق منها.

        Returns:
            {"authenticated": bool, "user_dn": str | None, "error": str | None}.
        """
        if not _LDAP3_AVAILABLE:
            raise ConnectorError(
                "active_directory: ldap3 غير متوفرة. ثبّتها عبر: pip install ldap3",
            )
        username: Optional[str] = kw.get("username")
        password: Optional[str] = kw.get("password")
        if not username or not password:
            raise ConnectorError(
                "active_directory: authenticate_user يتطلب 'username' و 'password'",
            )

        # محاولة استنتاج الـ DN من sAMAccountName إن لزم
        user_dn = username
        if "@" not in username and "=" not in username:
            # ابحث عن الـ DN أولاً عبر اتصال الموصل
            user_lookup = await self._get_user(
                username=username,
                attributes=["distinguishedName"],
            )
            if user_lookup.get("found"):
                user_dn = user_lookup["user"]["attributes"].get(
                    "distinguishedName", username,
                )

        # إنشاء اتصال مؤقت باسم المستخدم (لا يُخزَّن)
        tls_config = LDAP3Tls(
            validate=_ssl.CERT_REQUIRED if self._validate_cert else _ssl.CERT_NONE,
            version=_ssl.PROTOCOL_TLS_CLIENT,
        )
        server = LDAP3Server(
            self._ldap_url, use_ssl=True, tls=tls_config,
            connect_timeout=int(self.config.connect_timeout),
        )
        test_conn = LDAP3Connection(
            server=server,
            user=user_dn,
            password=password,
            auto_bind=False,
            read_only=True,
            receive_timeout=self.config.read_timeout,
        )

        try:
            bind_ok = await asyncio.to_thread(test_conn.bind)
        except Exception as exc:
            return {
                "authenticated": False,
                "user_dn": user_dn,
                "error": f"bind exception: {exc}",
            }
        finally:
            try:
                await asyncio.to_thread(test_conn.unbind)
            except Exception:
                pass

        if bind_ok:
            return {"authenticated": True, "user_dn": user_dn, "error": None}
        result = test_conn.result or {}
        return {
            "authenticated": False,
            "user_dn": user_dn,
            "error": (
                f"LDAP bind failed: {result.get('description')} "
                f"({result.get('result')})"
            ),
        }

    # ───────────────────────────────────────────────────────────────────
    #  Disconnect / Cleanup
    # ───────────────────────────────────────────────────────────────────
    async def disconnect(self) -> None:
        """إغلاق اتصال LDAP وعكس الموارد."""
        # إلغاء مهمة health check الموروثة
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None
        if self._ldap_connection is not None:
            try:
                if self._ldap_connection.bound:
                    await asyncio.to_thread(self._ldap_connection.unbind)
                logger.info("active_directory: تم إغلاق اتصال LDAP")
            except Exception as exc:
                logger.warning("active_directory: خطأ أثناء unbind: %s", exc)
            finally:
                self._ldap_connection = None
        self.state = __import__(
            "packages.common.connectors.base", fromlist=["ConnectorState"],
        ).ConnectorState.DISCONNECTED

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
            "protocol": "LDAPS (LDAP v3 over TLS)",
            "ldap3_available": _LDAP3_AVAILABLE,
            "search_base": self._search_base,
            "validate_cert": self._validate_cert,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": False,
                "authenticate": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "user_attributes": list(self.DEFAULT_USER_ATTRIBUTES),
            "group_attributes": list(self.DEFAULT_GROUP_ATTRIBUTES),
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل (Identity Management)."""
        return self.config.required_permissions or [
            "connector:active_directory:read",
            "identity:users:read",
            "identity:groups:read",
            "identity:authenticate",
        ]
