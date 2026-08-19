"""
موصل GraphQL عام لمنصة HSAAI
==============================
موصل عام قابل للتخصيص لأي GraphQL endpoint. يدعم أنواع المصادقة:
    - bearer   : Bearer Token (Authorization: Bearer <token>)
    - api_key  : API Key في ترويسة قابلة للتخصيص (افتراضيًا X-API-Key)
    - none     : بدون مصادقة

الإجراءات المدعومة:
    - query   : تنفيذ GraphQL query (read-only)
    - mutate  : تنفيذ GraphQL mutation (write)

search() ينفذ query قابلة للتخصيص (موجودة في config.search_query) مع
معامل $search String. إن لم تُحدَّد query بحث، يُستخدم قالب افتراضي بسيط.

الاستخدام:
    cfg = ConnectorConfig(
        name="graphql",
        display_name="Custom GraphQL API",
        category="Integration",
        base_url="https://api.example.com/graphql",
        auth_strategy=AuthStrategy.BEARER,
        secrets={"token": "abc123"},
        # اختياري: قالب بحث مخصص
        search_query=\"\"\"
        query Search($search: String!) {
            search(query: $search) {
                id
                name
                description
            }
        }
        \"\"\",
    )
    connector = GraphQLConnector(cfg)
    await connector.connect()
    result = await connector.call("query", query="query { users { id name } }")
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


@connector("graphql", version="1.0.0", category="Integration")
class GraphQLConnector(BaseConnector):
    """موصل GraphQL عام يدعم bearer/api_key/none auth."""

    #: اسم ترويسة API Key الافتراضي
    DEFAULT_API_KEY_HEADER: str = "X-API-Key"

    #: ترويسة Bearer الافتراضية
    BEARER_HEADER: str = "Authorization"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "query",
        "mutate",
    )

    #: قالب البحث الافتراضي (إن لم يُحدَّد في config.search_query)
    DEFAULT_SEARCH_QUERY: str = """query Search($search: String!, $first: Int) {
  search(query: $search, first: $first) {
    edges {
      node {
        id
        name
      }
    }
  }
}"""

    #: قالب فحص الصحة الافتراضي (introspection بسيط)
    DEFAULT_HEALTH_QUERY: str = "query { __typename }"

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._token: str = self._get_secret("token", "")
        self._api_key: str = self._get_secret("api_key", "")
        # اسم ترويسة API Key قابل للتجاوز
        self._api_key_header: str = getattr(
            self.config, "api_key_header", self.DEFAULT_API_KEY_HEADER,
        )
        # قالب بحث قابل للتخصيص
        self._search_query: str = getattr(
            self.config, "search_query", self.DEFAULT_SEARCH_QUERY,
        )
        # قالب فحص الصحة قابل للتخصيص
        self._health_query: str = getattr(
            self.config, "health_query", self.DEFAULT_HEALTH_QUERY,
        )
        # مسار GraphQL الافتراضي (إن لم يكن موجودًا في base_url)
        self._graphql_path: str = getattr(self.config, "graphql_path", "/graphql")
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
        """تجهيز ترويسات المصادقة بناءً على auth_strategy.

        الاستراتيجيات المدعومة:
            - BEARER  : Authorization: Bearer <token>
            - API_KEY : <api_key_header>: <api_key>
            - NONE    : بدون مصادقة

        ملاحظة: لا تُجرى طلبات شبكة هنا؛ التحقق الفعلي يحدث عند أول استدعاء
        عبر ردود الخادم (401/403 تُعالَج عبر آلية إعادة المحاولة في BaseConnector).

        Raises:
            ConnectorAuthenticationError: عند فقدان بيانات الاعتماد المطلوبة.
        """
        strategy = self.config.auth_strategy

        if strategy == AuthStrategy.NONE:
            logger.info("GraphQL: لا مصادقة مطلوبة")
            return

        if strategy == AuthStrategy.BEARER:
            if not self._token:
                raise ConnectorAuthenticationError(
                    "GraphQL: 'token' مطلوب لمصادقة Bearer",
                )
            if self._client is not None:
                self._client.headers.update({
                    self.BEARER_HEADER: f"Bearer {self._token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                })
            logger.info("GraphQL: تم تجهيز مصادقة Bearer")
            return

        if strategy == AuthStrategy.API_KEY:
            if not self._api_key:
                raise ConnectorAuthenticationError(
                    "GraphQL: 'api_key' مطلوب لمصادقة API Key",
                )
            if self._client is not None:
                self._client.headers.update({
                    self._api_key_header: self._api_key,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                })
            logger.info(
                "GraphQL: تم تجهيز API Key في الترويسة '%s'",
                self._api_key_header,
            )
            return

        # استراتيجيات OAuth2 تتطلب token endpoint خارج هذا الموصل العام
        raise ConnectorAuthenticationError(
            f"GraphQL: استراتيجية المصادقة '{strategy.value}' غير مدعومة في "
            f"الموصل العام — استخدم bearer/api_key/none",
        )

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة GraphQL endpoint عبر تنفيذ query بسيط (__typename).

        إن كان health_query مخصصًا في config، يُستخدم بدلاً من الافتراضي.

        Returns:
            HealthResult: HEALTHY إذا أرجع الخادم 200 بلا errors،
                DEGRADED إذا أرجع 200 مع GraphQL errors،
                UNHEALTHY خلاف ذلك.
        """
        start = time.monotonic()
        try:
            if self._client is None:
                raise ConnectorError("GraphQL: العميل غير مهيأ — استدعِ connect() أولاً")
            payload = {"query": self._health_query}
            try:
                response = await self._client.post(
                    self._graphql_path,
                    json=payload,
                )
            except httpx.HTTPError as exc:
                raise ConnectorError(f"GraphQL: فشل فحص الصحة: {exc}") from exc

            latency_ms = (time.monotonic() - start) * 1000
            if response.status_code == 200:
                data = response.json()
                # GraphQL يُرجع 200 حتى عند وجود أخطاء
                if isinstance(data, dict) and data.get("errors"):
                    return HealthResult(
                        status=HealthStatus.DEGRADED,
                        connector=self.config.name,
                        latency_ms=latency_ms,
                        details={"http_status": 200, "graphql_errors": len(data["errors"])},
                        error=str(data["errors"][:1]),
                    )
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 200, "health_query": self._health_query[:50]},
                )
            if response.status_code == 401:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={"http_status": 401, "reason": "auth_failed"},
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
    #  GraphQL Helpers
    # ───────────────────────────────────────────────────────────────────
    async def _execute_graphql(
        self,
        query: str,
        *,
        variables: Optional[dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """تنفيذ طلب GraphQL على الـ endpoint.

        Args:
            query: نص الـ GraphQL query/mutation.
            variables: متغيرات GraphQL (اختياري).
            operation_name: اسم العملية (إن كان في الـ query عدة عمليات).

        Returns:
            قاموس GraphQL الخام: {"data": {...}, "errors": [...]}.

        Raises:
            ConnectorError: عند فشل الطلب الشبكي أو إرجاع الخادم لخطأ غير GraphQL.
        """
        if self._client is None:
            raise ConnectorError("GraphQL: العميل غير مهيأ — استدعِ connect() أولاً")
        if not query or not query.strip():
            raise ConnectorError("GraphQL: 'query' لا يمكن أن يكون فارغًا")

        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        if operation_name:
            payload["operationName"] = operation_name

        try:
            response = await self._client.post(
                self._graphql_path,
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"GraphQL: فشل تنفيذ الطلب: {exc}",
            ) from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"GraphQL: خطأ HTTP {response.status_code}: {response.text[:500]}",
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ConnectorError(
                f"GraphQL: الاستجابة ليست JSON صالحًا: {response.text[:300]}",
            ) from exc

        # GraphQL يعيد 200 دائمًا تقريبًا؛ الأخطاء في حقل "errors"
        if not isinstance(data, dict):
            raise ConnectorError(
                f"GraphQL: استجابة غير متوقعة: {str(data)[:300]}",
            )
        return data

    def _has_graphql_errors(self, result: dict[str, Any]) -> bool:
        """التحقق من وجود أخطاء GraphQL في الاستجابة."""
        errors = result.get("errors")
        return bool(errors) and isinstance(errors, list) and len(errors) > 0

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث عبر تنفيذ GraphQL search query قابل للتخصيص.

        يستخدم config.search_query (أو القالب الافتراضي) مع تمرير معامل
        $search (String!) و $first (Int).

        Args:
            query: نص البحث.
            **kwargs:
                search_query (str): قالب GraphQL مخصص لهذا الاستدعاء فقط.
                variables (dict): متغيرات إضافية تُدمج مع {search, first}.
                first (int): عدد النتائج (افتراضيًا 20).
                operation_name (str): اسم العملية.

        Returns:
            قائمة بنتائج البحث (تُستخرَج من data.search.edges[].node أو
            من أول قائمة في data إن لم تتطابق البنية).
        """
        search_query: str = kwargs.pop("search_query", self._search_query)
        first: int = int(kwargs.pop("first", 20))
        extra_vars: dict[str, Any] = kwargs.pop("variables", {}) or {}
        operation_name: Optional[str] = kwargs.pop("operation_name", None)

        if not query.strip():
            return []

        variables: dict[str, Any] = {
            "search": query,
            "first": first,
            **extra_vars,
        }
        try:
            result = await self._execute_graphql(
                search_query,
                variables=variables,
                operation_name=operation_name,
            )
        except ConnectorError:
            return []

        if self._has_graphql_errors(result):
            logger.warning(
                "GraphQL search: أخطاء في الاستجابة: %s",
                result.get("errors"),
            )
            return []

        data = result.get("data") or {}
        return self._extract_search_results(data)

    def _extract_search_results(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """استخراج قائمة نتائج من بيانات GraphQL بنيوية متعددة.

        يدعم الأنماط الشائعة:
            - data.search.edges[].node  (Relay-style)
            - data.search.nodes[]       (بسيط)
            - data.search[]             (قائمة مباشرة)
            - data.items[] / data.results[]
        """
        if not isinstance(data, dict):
            return []

        # نمط Relay: data.search.edges[].node
        search_obj = data.get("search")
        if isinstance(search_obj, dict):
            edges = search_obj.get("edges")
            if isinstance(edges, list):
                return [
                    edge.get("node", {}) if isinstance(edge, dict) else {}
                    for edge in edges
                ]
            nodes = search_obj.get("nodes")
            if isinstance(nodes, list):
                return nodes
            if isinstance(search_obj, list):
                return search_obj

        # أنماط أخرى شائعة
        for key in ("items", "results", "records", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value

        # إن كانت data نفسها قائمة (نادر)
        return []

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء GraphQL (query أو mutate).

        Args (via kwargs):
            query (str): نص الـ GraphQL query/mutation (إلزامي).
            variables (dict): متغيرات GraphQL.
            operation_name (str): اسم العملية.
            raise_on_errors (bool): رفع ConnectorError عند وجود GraphQL errors
                (افتراضيًا True).

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم أو فشل التنفيذ أو
                وجود GraphQL errors (إذا raise_on_errors=True).
        """
        handlers = {
            "query": self._query,
            "mutate": self._mutate,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"GraphQL: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _query(self, **kw: Any) -> dict[str, Any]:
        """تنفيذ GraphQL query (read-only).

        Args (via kwargs):
            query (str): نص الـ GraphQL query (إلزامي).
            variables (dict): متغيرات GraphQL.
            operation_name (str): اسم العملية.
            raise_on_errors (bool): رفع ConnectorError عند وجود GraphQL errors.

        Returns:
            قاموس GraphQL الكامل: {"data": {...}, "errors": [...]?}.
        """
        return await self._run_graphql(raise_on_errors_default=True, **kw)

    async def _mutate(self, **kw: Any) -> dict[str, Any]:
        """تنفيذ GraphQL mutation (write).

        Args (via kwargs):
            query (str): نص الـ GraphQL mutation (إلزامي).
            variables (dict): متغيرات GraphQL.
            operation_name (str): اسم العملية.
            raise_on_errors (bool): رفع ConnectorError عند وجود GraphQL errors.

        Returns:
            قاموس GraphQL الكامل: {"data": {...}, "errors": [...]?}.
        """
        return await self._run_graphql(raise_on_errors_default=True, **kw)

    async def _run_graphql(self, *, raise_on_errors_default: bool, **kw: Any) -> dict[str, Any]:
        """تنفيذ GraphQL query/mutation مع معالجة موحدة للأخطاء.

        Args:
            raise_on_errors_default: القيمة الافتراضية لـ raise_on_errors
                إن لم تُحدَّد في kwargs.

        Raises:
            ConnectorError: عند فقدان 'query' أو فشل التنفيذ أو وجود
                GraphQL errors (إذا raise_on_errors=True).
        """
        query: Optional[str] = kw.get("query")
        if not query:
            raise ConnectorError("GraphQL: 'query' إلزامي لإجراءات query/mutate")
        variables: Optional[dict[str, Any]] = kw.get("variables")
        operation_name: Optional[str] = kw.get("operation_name")
        raise_on_errors: bool = bool(kw.get("raise_on_errors", raise_on_errors_default))

        result = await self._execute_graphql(
            query, variables=variables, operation_name=operation_name,
        )

        if raise_on_errors and self._has_graphql_errors(result):
            errors = result.get("errors", [])
            first_msg = (
                errors[0].get("message", str(errors[0]))
                if errors and isinstance(errors[0], dict)
                else str(errors[:1])
            )
            raise ConnectorError(
                f"GraphQL: أخطاء في الاستجابة: {first_msg}",
            )
        return result

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
            "protocol": "GraphQL over HTTP POST",
            "graphql_path": self._graphql_path,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "read": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "customizable": True,
            "supports_introspection": True,
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل (RBAC)."""
        return self.config.required_permissions or [
            "connector:graphql:read",
            "connector:graphql:write",
            "graphql:query:execute",
            "graphql:mutation:execute",
        ]
