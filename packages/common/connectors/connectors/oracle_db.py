"""
موصل Oracle Database لمنصة HSAAI
=================================
يتيح هذا الموصل الوصول إلى Oracle Database عبر مكتبة oracledb
(الإصدار الجديد من cx_Oracle — thin mode افتراضيًا).

الإجراءات المدعومة:
    - execute_query : تنفيذ استعلام SELECT وإرجاع الصفوف
    - list_tables   : سرد الجداول في schema محدد
    - get_schema    : جلب schema (أعمدة + أنواع) لجدول محدد
    - execute_plsql : تنفيذ كتلة PL/SQL مجهولة (anonymous block)

كما يدعم search() للبحث في أسماء الجداول.

ملاحظات:
    - مكتبة oracledb متزامنة، لذا يُغلّف الموصل استدعاءاتها بـ asyncio.to_thread.
    - إذا لم تكن oracledb مثبتة، يبقى الموصل قابلاً للاستيراد لكنه يرفع
      ConnectorError عند connect().

الاستخدام:
    cfg = ConnectorConfig(
        name="oracle_db",
        display_name="Corporate Oracle DB",
        category="Database",
        base_url="oracle+oracledb://oracle01.corp.local:1521/ORCLPDB1",
        auth_strategy=AuthStrategy.BASIC,
        secrets={
            "username": "system",
            "password": "...",
        },
        service_name="ORCLPDB1",
    )
    connector = OracleDBConnector(cfg)
    await connector.connect()
    rows = await connector.call("execute_query", query="SELECT * FROM ALL_USERS FETCH FIRST 10 ROWS ONLY")
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

# محاولة استيراد oracledb مع fallback أنيق
try:
    import oracledb
    _ORACLEDB_AVAILABLE = True
except ImportError:  # pragma: no cover - defensive
    oracledb = None  # type: ignore[assignment]
    _ORACLEDB_AVAILABLE = False
    logger.warning(
        "oracle_db: مكتبة oracledb غير مثبتة — الموصل قابل للاستيراد "
        "لكن لن يعمل حتى تُثبت: pip install oracledb",
    )


@connector("oracle_db", version="1.0.0", category="Database")
class OracleDBConnector(BaseConnector):
    """موصل Oracle Database عبر مكتبة oracledb مع تشغيل async عبر to_thread."""

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "execute_query",
        "list_tables",
        "get_schema",
        "execute_plsql",
    )

    #: المنفذ الافتراضي لأوراكل
    DEFAULT_PORT: int = 1521

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        # oracledb لا يستخدم HTTP — نُلغي العميل httpx
        self._client = None  # type: ignore[assignment]

        self._username: str = self._get_secret("username", "")
        self._password: str = self._get_secret("password", "")

        # اسم الخادم والمنفذ من config أو base_url
        self._host: str = (
            getattr(self.config, "host", "") or self._parse_host()
        )
        self._port: int = (
            int(getattr(self.config, "port", 0) or 0) or self.DEFAULT_PORT
        )
        # service_name أو sid — نُفضّل service_name
        self._service_name: str = (
            getattr(self.config, "service_name", "")
            or getattr(self.config, "service", "")
            or self._parse_service_name()
        )
        self._sid: Optional[str] = getattr(self.config, "sid", None)
        # thin mode (افتراضيًا True — لا يتطلب Oracle Client)
        self._thin_mode: bool = bool(getattr(self.config, "thin_mode", True))
        # وضع الاتصال: CDB أوغير ذلك
        self._connection: Any = None  # oracledb.Connection
        # اسم الـ schema الافتراضي (نفس username عند عدم التحديد)
        self._default_schema: str = (
            getattr(self.config, "schema", "") or self._username.upper()
            if self._username else ""
        )
        self._dsn: str = self._build_dsn()

    def _get_secret(self, key: str, default: str = "") -> str:
        """استرجاع سر من config.secrets بأمان."""
        secret = self.config.secrets.get(key)
        if secret is None:
            return default
        try:
            return secret.get_secret_value()
        except Exception:
            return default

    def _parse_host(self) -> str:
        """استخراج اسم الخادم من base_url بصيغة oracle+oracledb://host:port/svc."""
        url = self.config.base_url or ""
        if "://" in url:
            url = url.split("://", 1)[1]
        if "@" in url:
            url = url.split("@", 1)[1]
        if "/" in url:
            url = url.split("/", 1)[0]
        if ":" in url:
            url = url.split(":", 1)[0]
        return url

    def _parse_service_name(self) -> str:
        """استخراج اسم الخدمة من base_url (آخر جزء بعد /)."""
        url = self.config.base_url or ""
        if "/" in url:
            tail = url.rsplit("/", 1)[-1]
            # إزالة query string إن وُجد
            if "?" in tail:
                tail = tail.split("?", 1)[0]
            return tail
        return ""

    def _build_dsn(self) -> str:
        """بناء سلسلة DSN بصيغة Easy Connect أو SID."""
        if self._sid:
            # استخدام SID عبر بناء واصف TNS بسيط
            return (
                f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)"
                f"(HOST={self._host})(PORT={self._port}))"
                f"(CONNECT_DATA=(SID={self._sid})))"
            )
        # Easy Connect: host:port/service_name
        return f"{self._host}:{self._port}/{self._service_name}"

    # ───────────────────────────────────────────────────────────────────
    #  Connect / Disconnect (override — لا HTTP)
    # ───────────────────────────────────────────────────────────────────
    async def connect(self) -> None:
        """تهيئة الموصل: إنشاء اتصال oracledb والمصادقة."""
        from packages.common.connectors.base import ConnectorState
        if self.state == ConnectorState.CONNECTED:
            return
        self.state = ConnectorState.INITIALIZING
        try:
            await self.authenticate()
            self.state = ConnectorState.CONNECTED
            logger.info(
                "oracle_db: تم الاتصال بـ %s/%s كـ %s",
                self._host, self._service_name or self._sid, self._username,
            )
            self._start_health_check()
        except Exception as e:
            self.state = ConnectorState.ERROR
            logger.error("oracle_db: فشل الاتصال: %s", e)
            raise

    async def disconnect(self) -> None:
        """إغلاق اتصال Oracle."""
        from packages.common.connectors.base import ConnectorState
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except Exception:
                pass
            self._health_task = None
        if self._connection is not None:
            try:
                await asyncio.to_thread(self._connection.close)
                logger.info("oracle_db: تم إغلاق اتصال قاعدة البيانات")
            except Exception as exc:
                logger.warning("oracle_db: خطأ أثناء الإغلاق: %s", exc)
            finally:
                self._connection = None
        self.state = ConnectorState.DISCONNECTED

    # ───────────────────────────────────────────────────────────────────
    #  Authentication
    # ───────────────────────────────────────────────────────────────────
    async def authenticate(self) -> None:
        """إنشاء اتصال oracledb مُصادَق مع Oracle Database.

        يستخدم username/password مع DSN (Easy Connect أو SID descriptor).
        يعمل في thin mode افتراضيًا (لا يتطلب Oracle Client مثبتًا محليًا).

        Raises:
            ConnectorAuthenticationError: عند فقدان البيانات أو فشل الاتصال.
            ConnectorError: إذا لم تكن oracledb متوفرة.
        """
        if not _ORACLEDB_AVAILABLE:
            raise ConnectorError(
                "oracle_db: مكتبة oracledb غير مثبتة. ثبّتها عبر: pip install oracledb",
            )
        if not self._username or not self._password:
            raise ConnectorAuthenticationError(
                "oracle_db: username و password مطلوبان للمصادقة",
            )
        if not self._host and not self._sid:
            raise ConnectorAuthenticationError(
                "oracle_db: host/service_name (أو sid) مطلوبان لاتصال Oracle",
            )

        try:
            self._connection = await asyncio.to_thread(
                oracledb.connect,
                user=self._username,
                password=self._password,
                dsn=self._dsn,
                thin=self._thin_mode,
            )
        except Exception as exc:
            raise ConnectorAuthenticationError(
                f"oracle_db: فشل الاتصال بـ {self._dsn}: {exc}",
            ) from exc

        # تعيين schema افتراضي إن لزم
        if self._default_schema and self._default_schema.upper() != self._username.upper():
            try:
                cursor = self._connection.cursor()
                try:
                    cursor.execute(
                        f"ALTER SESSION SET CURRENT_SCHEMA = {self._default_schema.upper()}",
                    )
                finally:
                    cursor.close()
            except Exception as exc:
                logger.warning(
                    "oracle_db: تعذّر تعيين CURRENT_SCHEMA=%s: %s",
                    self._default_schema, exc,
                )

        # تعطيل autocommit (Oracle الافتراضي False — مناسب للمعاملات)
        try:
            self._connection.autocommit = False
        except Exception:
            pass

    async def _ensure_connected(self) -> None:
        """التأكد من أن الاتصال ما زال حيًا."""
        if not _ORACLEDB_AVAILABLE:
            raise ConnectorError(
                "oracle_db: oracledb غير متوفرة. ثبّتها: pip install oracledb",
            )
        if self._connection is None:
            raise ConnectorError(
                "oracle_db: الاتصال غير مهيأ — استدعِ connect() أولاً",
            )
        # فحص سريع للاتصال
        try:
            def _ping() -> None:
                cursor = self._connection.cursor()
                try:
                    cursor.execute("SELECT 1 FROM DUAL")
                    cursor.fetchone()
                finally:
                    cursor.close()
            await asyncio.to_thread(_ping)
        except Exception as exc:
            logger.warning("oracle_db: الاتصال معطوب، محاولة إعادة الاتصال: %s", exc)
            await self.authenticate()

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة Oracle Database عبر SELECT 1 FROM DUAL."""
        start = time.monotonic()
        try:
            if not _ORACLEDB_AVAILABLE:
                return HealthResult(
                    status=HealthStatus.UNHEALTHY,
                    connector=self.config.name,
                    latency_ms=0.0,
                    error="oracledb library not installed",
                )
            await self._ensure_connected()
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                status=HealthStatus.HEALTHY,
                connector=self.config.name,
                latency_ms=latency_ms,
                details={
                    "host": self._host,
                    "port": self._port,
                    "service_name": self._service_name,
                    "sid": self._sid,
                    "username": self._username,
                    "thin_mode": self._thin_mode,
                    "probe": "SELECT 1 FROM DUAL",
                },
            )
        except Exception as exc:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=(time.monotonic() - start) * 1000,
                error=str(exc),
            )

    # ───────────────────────────────────────────────────────────────────
    #  DB Helpers (sync wrapped with to_thread)
    # ───────────────────────────────────────────────────────────────────
    async def _exec_fetchall(
        self, sql: str, params: dict[str, Any] | tuple[Any, ...] | None = None,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """تنفيذ SELECT وإرجاع (column_names, rows_as_dicts).

        يدعم البارامترات الموضعية (:1, :2) أو المسماة (:name).

        Raises:
            ConnectorError: عند فشل التنفيذ.
        """
        def _do() -> tuple[list[str], list[dict[str, Any]]]:
            cursor = self._connection.cursor()
            try:
                cursor.execute(sql, params or {})
                columns = [
                    desc[0].lower() for desc in cursor.description
                ] if cursor.description else []
                rows = cursor.fetchall()
                rows_as_dicts = [
                    {columns[i]: r[i] for i in range(len(columns))}
                    for r in rows
                ]
                return columns, rows_as_dicts
            except Exception as exc:
                raise ConnectorError(
                    f"oracle_db: فشل تنفيذ الاستعلام: {exc}",
                ) from exc
            finally:
                cursor.close()
        await self._ensure_connected()
        return await asyncio.to_thread(_do)

    async def _exec_dml(
        self, sql: str,
        params: dict[str, Any] | tuple[Any, ...] | None = None,
        *, commit: bool = True,
    ) -> int:
        """تنفيذ INSERT/UPDATE/DELETE وإرجاع عدد الصفوف المتأثرة."""
        def _do() -> int:
            cursor = self._connection.cursor()
            try:
                cursor.execute(sql, params or {})
                rowcount = cursor.rowcount
                if commit:
                    self._connection.commit()
                return rowcount
            except Exception as exc:
                try:
                    self._connection.rollback()
                except Exception:
                    pass
                raise ConnectorError(
                    f"oracle_db: فشل تنفيذ DML: {exc}",
                ) from exc
            finally:
                cursor.close()
        await self._ensure_connected()
        return await asyncio.to_thread(_do)

    async def _exec_plsql(
        self, block: str,
        params: dict[str, Any] | None = None,
        *, commit: bool = True,
    ) -> int:
        """تنفيذ كتلة PL/SQL مجهولة (BEGIN ... END;)."""
        def _do() -> int:
            cursor = self._connection.cursor()
            try:
                # oracledb يدعم bind variables عبر dict
                cursor.execute(block, params or {})
                rowcount = cursor.rowcount
                if commit:
                    self._connection.commit()
                return rowcount
            except Exception as exc:
                try:
                    self._connection.rollback()
                except Exception:
                    pass
                raise ConnectorError(
                    f"oracle_db: فشل تنفيذ كتلة PL/SQL: {exc}",
                ) from exc
            finally:
                cursor.close()
        await self._ensure_connected()
        return await asyncio.to_thread(_do)

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في أسماء الجداول في schema محدد.

        يستعلم من ALL_TABLES (مع تقييد OWNER للـ schema الافتراضي إن لزم).

        Args:
            query: نص البحث (يُطابق اسم الجدول جزئيًا، غير حساس لحالة الأحرف).
            **kwargs:
                owner (str): اسم مالك الـ schema (افتراضيًا اسم المستخدم).
                top (int): عدد النتائج (افتراضيًا 100).

        Returns:
            قائمة بنتائج البحث {owner, table_name, tablespace_name}.
        """
        if not query or not query.strip():
            return []
        owner: str = kwargs.pop("owner", self._default_schema or self._username.upper())
        top = int(kwargs.pop("top", 100))

        sql = (
            "SELECT owner, table_name, tablespace_name "
            "FROM all_tables "
            "WHERE owner = :owner AND LOWER(table_name) LIKE :pattern "
            "ORDER BY table_name"
        )
        params = {
            "owner": owner.upper(),
            "pattern": f"%{query.lower()}%",
        }
        _, rows = await self._exec_fetchall(sql, params)
        return [
            {
                "type": "table",
                "owner": r.get("owner"),
                "table_name": r.get("table_name"),
                "tablespace_name": r.get("tablespace_name"),
            }
            for r in rows[:top]
        ]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Oracle Database.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "execute_query": self._execute_query,
            "list_tables": self._list_tables,
            "get_schema": self._get_schema,
            "execute_plsql": self._execute_plsql_action,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"oracle_db: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _execute_query(self, **kw: Any) -> dict[str, Any]:
        """تنفيذ استعلام SELECT وإرجاع الصفوف.

        Args (via kwargs):
            query (str): استعلام SQL (مطلوب).
            params (dict | tuple): بارامترات bind variables (اختياري).
            max_rows (int): أقصى عدد صفوف (افتراضيًا 1000).

        Returns:
            {"columns": list[str], "rows": list[dict], "row_count": int}.
        """
        query: Optional[str] = kw.get("query")
        if not query:
            raise ConnectorError("oracle_db: execute_query يتطلب 'query'")
        params = kw.get("params")
        max_rows = int(kw.get("max_rows", 1000))

        columns, rows = await self._exec_fetchall(query, params)
        if len(rows) > max_rows:
            rows = rows[:max_rows]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": len(rows) == max_rows,
        }

    async def _list_tables(self, **kw: Any) -> dict[str, Any]:
        """سرد الجداول في schema محدد.

        Args (via kwargs):
            owner (str): اسم مالك الـ schema (افتراضيًا اسم المستخدم).
        """
        owner = kw.get("owner", self._default_schema or self._username.upper())
        sql = (
            "SELECT owner, table_name, tablespace_name, num_rows, last_analyzed "
            "FROM all_tables "
            "WHERE owner = :owner "
            "ORDER BY table_name"
        )
        _, rows = await self._exec_fetchall(sql, {"owner": owner.upper()})
        tables = [
            {
                "owner": r.get("owner"),
                "table_name": r.get("table_name"),
                "tablespace_name": r.get("tablespace_name"),
                "num_rows": r.get("num_rows"),
                "last_analyzed": (
                    r.get("last_analyzed").isoformat()
                    if r.get("last_analyzed") else None
                ),
            }
            for r in rows
        ]
        return {"count": len(tables), "tables": tables}

    async def _get_schema(self, **kw: Any) -> dict[str, Any]:
        """جلب schema (أعمدة + أنواع) لجدول محدد.

        Args (via kwargs):
            table_name (str): اسم الجدول (مطلوب).
            owner (str): اسم مالك الـ schema (افتراضيًا اسم المستخدم).
        """
        table_name = kw.get("table_name")
        if not table_name:
            raise ConnectorError("oracle_db: get_schema يتطلب 'table_name'")
        owner = kw.get("owner", self._default_schema or self._username.upper())

        sql = (
            "SELECT column_name, data_type, data_length, data_precision, "
            "data_scale, nullable, data_default, column_id "
            "FROM all_tab_columns "
            "WHERE owner = :owner AND table_name = :table_name "
            "ORDER BY column_id"
        )
        params = {
            "owner": owner.upper(),
            "table_name": table_name.upper(),
        }
        _, rows = await self._exec_fetchall(sql, params)
        columns = [
            {
                "name": r.get("column_name"),
                "data_type": r.get("data_type"),
                "length": r.get("data_length"),
                "precision": r.get("data_precision"),
                "scale": r.get("data_scale"),
                "nullable": (r.get("nullable") == "Y"),
                "default": r.get("data_default"),
                "position": r.get("column_id"),
            }
            for r in rows
        ]
        return {
            "owner": owner,
            "table_name": table_name,
            "columns": columns,
            "column_count": len(columns),
        }

    async def _execute_plsql_action(self, **kw: Any) -> dict[str, Any]:
        """تنفيذ كتلة PL/SQL مجهولة (anonymous block).

        Args (via kwargs):
            block (str): كتلة PL/SQL (BEGIN ... END;) (مطلوب).
            params (dict): bind variables بصيغة {name: value} (اختياري).
            commit (bool): تنفيذ commit بعد الكتلة (افتراضيًا True).

        Returns:
            {"rows_affected": int, "committed": bool}.
        """
        block = kw.get("block")
        if not block:
            raise ConnectorError("oracle_db: execute_plsql يتطلب 'block'")
        params = kw.get("params")
        commit = bool(kw.get("commit", True))
        rows_affected = await self._exec_plsql(block, params, commit=commit)
        return {
            "rows_affected": rows_affected,
            "committed": commit,
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
            "protocol": "Oracle Net (TNS) via oracledb",
            "oracledb_available": _ORACLEDB_AVAILABLE,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "ddl": False,
                "plsql": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "host": self._host,
            "port": self._port,
            "service_name": self._service_name,
            "sid": self._sid,
            "default_schema": self._default_schema,
            "thin_mode": self._thin_mode,
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:oracle_db:read",
            "connector:oracle_db:write",
            "database:tables:read",
            "database:plsql:execute",
        ]
