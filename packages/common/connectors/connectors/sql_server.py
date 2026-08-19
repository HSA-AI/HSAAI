"""
موصل Microsoft SQL Server لمنصة HSAAI
======================================
يتيح هذا الموصل الوصول إلى Microsoft SQL Server عبر مكتبة pyodbc.

الإجراءات المدعومة:
    - execute_query : تنفيذ استعلام SQL (SELECT) وإرجاع الصفوف
    - list_tables   : سرد الجداول في schema محدد
    - get_schema    : جلب schema (أعمدة + أنواع) لجدول محدد
    - insert_row    : إدراج صف في جدول (معاملات موضعية آمنة)
    - update_row    : تحديث صفوف في جدول عبر WHERE clause

كما يدعم search() للبحث في أسماء الجداول.

ملاحظات:
    - مكتبة pyodbc متزامنة، لذا يُغلّف الموصل استدعاءاتها بـ asyncio.to_thread
      لجعلها متوافقة مع البنية async للـ BaseConnector.
    - إذا لم تكن مكتبة pyodbc مثبتة، يبقى الموصل قابلاً للاستيراد لكنه
      يرفع ConnectorError عند connect().

الاستخدام:
    cfg = ConnectorConfig(
        name="sql_server",
        display_name="Corporate SQL Server",
        category="Database",
        base_url="mssql+pyodbc://sql01.corp.local:1433/CorporateDB",
        auth_strategy=AuthStrategy.BASIC,
        secrets={
            "username": "sa",
            "password": "...",
            "driver": "ODBC Driver 18 for SQL Server",
        },
        database="CorporateDB",
    )
    connector = SQLServerConnector(cfg)
    await connector.connect()
    rows = await connector.call("execute_query", query="SELECT TOP 10 * FROM Customers")
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

# محاولة استيراد pyodbc مع fallback أنيق
try:
    import pyodbc
    _PYODBC_AVAILABLE = True
except ImportError:  # pragma: no cover - defensive
    pyodbc = None  # type: ignore[assignment]
    _PYODBC_AVAILABLE = False
    logger.warning(
        "sql_server: مكتبة pyodbc غير مثبتة — الموصل قابل للاستيراد "
        "لكن لن يعمل حتى تُثبت: pip install pyodbc",
    )


@connector("sql_server", version="1.0.0", category="Database")
class SQLServerConnector(BaseConnector):
    """موصل Microsoft SQL Server عبر pyodbc مع تشغيل async عبر to_thread."""

    #: الـ driver الافتراضي لـ ODBC
    DEFAULT_DRIVER: str = "ODBC Driver 17 for SQL Server"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "execute_query",
        "list_tables",
        "get_schema",
        "insert_row",
        "update_row",
    )

    #: أسماء أعمدة INFORMATION_SCHEMA.COLUMN
    SCHEMA_COLUMNS: tuple[str, ...] = (
        "column_name", "data_type", "character_maximum_length",
        "numeric_precision", "numeric_scale", "is_nullable",
        "column_default", "ordinal_position",
    )

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        # pyodbc لا يستخدم HTTP — نُلغي العميل httpx
        self._client = None  # type: ignore[assignment]

        self._username: str = self._get_secret("username", "")
        self._password: str = self._get_secret("password", "")
        self._driver: str = self._get_secret("driver", "") or getattr(
            self.config, "driver", self.DEFAULT_DRIVER,
        )
        # اسم الخادم والمنفذ وقاعدة البيانات من config أو base_url
        self._server: str = getattr(self.config, "server", "") or self._parse_server()
        self._port: int = int(getattr(self.config, "port", 0) or 0) or 1433
        self._database: str = (
            getattr(self.config, "database", "")
            or getattr(self.config, "dbname", "")
            or "master"
        )
        self._encrypt: str = getattr(self.config, "encrypt", "yes")
        self._trust_server_certificate: str = getattr(
            self.config, "trust_server_certificate", "no",
        )
        self._connection: Any = None  # pyodbc.Connection
        # سلسلة الاتصال المُجمَّعة
        self._connection_string: str = self._build_connection_string()

    def _get_secret(self, key: str, default: str = "") -> str:
        """استرجاع سر من config.secrets بأمان."""
        secret = self.config.secrets.get(key)
        if secret is None:
            return default
        try:
            return secret.get_secret_value()
        except Exception:
            return default

    def _parse_server(self) -> str:
        """استخراج اسم الخادم من base_url بصيغة mssql+pyodbc://host:port/db."""
        url = self.config.base_url or ""
        if "://" in url:
            url = url.split("://", 1)[1]
        # إزالة بيانات الاعتماد إن وُجدت
        if "@" in url:
            url = url.split("@", 1)[1]
        # إزالة قاعدة البيانات
        if "/" in url:
            url = url.split("/", 1)[0]
        # إزالة المنفذ
        if ":" in url:
            url = url.split(":", 1)[0]
        return url

    def _build_connection_string(self) -> str:
        """بناء سلسلة اتصال ODBC آمنة."""
        parts = [
            f"DRIVER={{{self._driver}}}",
            f"SERVER={self._server},{self._port}",
            f"DATABASE={self._database}",
            f"Encrypt={self._encrypt}",
            f"TrustServerCertificate={self._trust_server_certificate}",
        ]
        if self._username:
            parts.append(f"UID={self._username}")
        if self._password:
            parts.append(f"PWD={self._password}")
        return ";".join(parts)

    # ───────────────────────────────────────────────────────────────────
    #  Connect / Disconnect (override — لا HTTP)
    # ───────────────────────────────────────────────────────────────────
    async def connect(self) -> None:
        """تهيئة الموصل: إنشاء اتصال pyodbc والمصادقة."""
        from packages.common.connectors.base import ConnectorState
        if self.state == ConnectorState.CONNECTED:
            return
        self.state = ConnectorState.INITIALIZING
        try:
            await self.authenticate()
            self.state = ConnectorState.CONNECTED
            logger.info("sql_server: تم الاتصال بقاعدة البيانات '%s'", self._database)
            self._start_health_check()
        except Exception as e:
            self.state = ConnectorState.ERROR
            logger.error("sql_server: فشل الاتصال: %s", e)
            raise

    async def disconnect(self) -> None:
        """إغلاق اتصال SQL Server."""
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
                logger.info("sql_server: تم إغلاق اتصال قاعدة البيانات")
            except Exception as exc:
                logger.warning("sql_server: خطأ أثناء الإغلاق: %s", exc)
            finally:
                self._connection = None
        self.state = ConnectorState.DISCONNECTED

    # ───────────────────────────────────────────────────────────────────
    #  Authentication
    # ───────────────────────────────────────────────────────────────────
    async def authenticate(self) -> None:
        """إنشاء اتصال pyodbc مُصادَق مع SQL Server.

        يستخدم SQL Server Authentication (username/password) بشكل افتراضي.
        يمكن استخدام Windows Authentication عبر ترك username/password فارغين
        وتفعيل Trusted_Connection=yes في سلسلة الاتصال.

        Raises:
            ConnectorAuthenticationError: عند فقدان البيانات أو فشل الاتصال.
            ConnectorError: إذا لم تكن pyodbc متوفرة.
        """
        if not _PYODBC_AVAILABLE:
            raise ConnectorError(
                "sql_server: مكتبة pyodbc غير مثبتة. ثبّتها عبر: pip install pyodbc",
            )
        if not self._server:
            raise ConnectorAuthenticationError(
                "sql_server: server (host) مطلوب لاتصال SQL Server",
            )
        # التحقق من بيانات الاعتماد فقط عند عدم استخدام Trusted_Connection
        if "Trusted_Connection=yes" not in self._connection_string:
            if not self._username or not self._password:
                raise ConnectorAuthenticationError(
                    "sql_server: username و password مطلوبان (أو فعّل Trusted_Connection)",
                )

        try:
            self._connection = await asyncio.to_thread(
                pyodbc.connect, self._connection_string,
            )
        except Exception as exc:
            raise ConnectorAuthenticationError(
                f"sql_server: فشل الاتصال بـ {self._server}:{self._port}: {exc}",
            ) from exc

        # تعطيل auto-commit لتفعيل المعاملات الصريحة عند الحاجة
        try:
            self._connection.autocommit = True
        except Exception:
            pass

    async def _ensure_connected(self) -> None:
        """التأكد من أن الاتصال ما زال حيًا."""
        if not _PYODBC_AVAILABLE:
            raise ConnectorError(
                "sql_server: pyodbc غير متوفرة. ثبّتها: pip install pyodbc",
            )
        if self._connection is None:
            raise ConnectorError(
                "sql_server: الاتصال غير مهيأ — استدعِ connect() أولاً",
            )
        # فحص سريع لإعادة الاتصال عند الفقد
        try:
            await asyncio.to_thread(self._connection.cursor)
        except Exception as exc:
            logger.warning("sql_server: الاتصال معطوب، محاولة إعادة الاتصال: %s", exc)
            await self.authenticate()

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة SQL Server عبر SELECT 1."""
        start = time.monotonic()
        try:
            if not _PYODBC_AVAILABLE:
                return HealthResult(
                    status=HealthStatus.UNHEALTHY,
                    connector=self.config.name,
                    latency_ms=0.0,
                    error="pyodbc library not installed",
                )
            await self._ensure_connected()
            await self._exec_simple("SELECT 1")
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                status=HealthStatus.HEALTHY,
                connector=self.config.name,
                latency_ms=latency_ms,
                details={
                    "server": self._server,
                    "port": self._port,
                    "database": self._database,
                    "probe": "SELECT 1",
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
    async def _exec_simple(self, sql: str) -> None:
        """تنفيذ SQL بدون إرجاع نتائج (للفحوصات)."""
        def _do() -> None:
            cursor = self._connection.cursor()
            try:
                cursor.execute(sql)
                cursor.fetchone()
            finally:
                cursor.close()
        await asyncio.to_thread(_do)

    async def _exec_fetchall(
        self, sql: str, params: tuple[Any, ...] = (),
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """تنفيذ SELECT وإرجاع (column_names, rows).

        Raises:
            ConnectorError: عند فشل التنفيذ.
        """
        def _do() -> tuple[list[str], list[tuple[Any, ...]]]:
            cursor = self._connection.cursor()
            try:
                cursor.execute(sql, params)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                return columns, [tuple(r) for r in rows]
            except Exception as exc:
                raise ConnectorError(
                    f"sql_server: فشل تنفيذ الاستعلام: {exc}",
                ) from exc
            finally:
                cursor.close()
        await self._ensure_connected()
        return await asyncio.to_thread(_do)

    async def _exec_dml(
        self, sql: str, params: tuple[Any, ...] = (),
        *, commit: bool = True,
    ) -> int:
        """تنفيذ INSERT/UPDATE/DELETE وإرجاع عدد الصفوف المتأثرة."""
        def _do() -> int:
            cursor = self._connection.cursor()
            try:
                cursor.execute(sql, params)
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
                    f"sql_server: فشل تنفيذ DML: {exc}",
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
        """البحث في أسماء الجداول في قاعدة البيانات الحالية.

        Args:
            query: نص البحث (يُطابق اسم الجدول جزئيًا، غير حساس لحالة الأحرف).
            **kwargs:
                schema (str): اسم الـ schema (افتراضيًا 'dbo').
                top (int): عدد النتائج (افتراضيًا 100).

        Returns:
            قائمة بنتائج البحث {schema, table_name, table_type}.
        """
        if not query or not query.strip():
            return []
        schema: str = kwargs.pop("schema", "dbo")
        top = int(kwargs.pop("top", 100))

        sql = (
            "SELECT TOP (?) TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
            "FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_NAME LIKE ? AND TABLE_SCHEMA = ? "
            "ORDER BY TABLE_NAME"
        )
        pattern = f"%{query}%"
        _, rows = await self._exec_fetchall(sql, (top, pattern, schema))
        return [
            {
                "type": "table",
                "schema": r[0],
                "table_name": r[1],
                "table_type": r[2],
            }
            for r in rows
        ]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على SQL Server.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "execute_query": self._execute_query,
            "list_tables": self._list_tables,
            "get_schema": self._get_schema,
            "insert_row": self._insert_row,
            "update_row": self._update_row,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"sql_server: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _execute_query(self, **kw: Any) -> dict[str, Any]:
        """تنفيذ استعلام SELECT وإرجاع الصفوف.

        Args (via kwargs):
            query (str): استعلام SQL (مطلوب).
            params (list | tuple): بارامترات موضعية للمعاملات (اختياري).
            max_rows (int): أقصى عدد صفوف (افتراضيًا 1000).

        Returns:
            {"columns": list[str], "rows": list[dict], "row_count": int}.
        """
        query: Optional[str] = kw.get("query")
        if not query:
            raise ConnectorError("sql_server: execute_query يتطلب 'query'")
        params = kw.get("params", ())
        if isinstance(params, list):
            params = tuple(params)
        max_rows = int(kw.get("max_rows", 1000))

        columns, rows = await self._exec_fetchall(query, params)
        if len(rows) > max_rows:
            rows = rows[:max_rows]
        rows_as_dicts = [dict(zip(columns, r)) for r in rows]
        return {
            "columns": columns,
            "rows": rows_as_dicts,
            "row_count": len(rows_as_dicts),
            "truncated": len(rows) == max_rows,
        }

    async def _list_tables(self, **kw: Any) -> dict[str, Any]:
        """سرد الجداول في قاعدة البيانات الحالية.

        Args (via kwargs):
            schema (str): اسم الـ schema (افتراضيًا 'dbo').
            table_type (str): 'BASE TABLE' أو 'VIEW' أو None (الكل).
        """
        schema = kw.get("schema", "dbo")
        table_type = kw.get("table_type")
        sql = (
            "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
            "FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = ?"
        )
        params: tuple[Any, ...] = (schema,)
        if table_type:
            sql += " AND TABLE_TYPE = ?"
            params = (schema, table_type)
        sql += " ORDER BY TABLE_NAME"
        _, rows = await self._exec_fetchall(sql, params)
        tables = [
            {"schema": r[0], "table_name": r[1], "table_type": r[2]}
            for r in rows
        ]
        return {"count": len(tables), "tables": tables}

    async def _get_schema(self, **kw: Any) -> dict[str, Any]:
        """جلب schema (أعمدة + أنواع) لجدول محدد.

        Args (via kwargs):
            table_name (str): اسم الجدول (مطلوب).
            schema (str): اسم الـ schema (افتراضيًا 'dbo').
        """
        table_name = kw.get("table_name")
        if not table_name:
            raise ConnectorError("sql_server: get_schema يتطلب 'table_name'")
        schema = kw.get("schema", "dbo")
        sql = (
            "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
            "NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, "
            "COLUMN_DEFAULT, ORDINAL_POSITION "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? "
            "ORDER BY ORDINAL_POSITION"
        )
        _, rows = await self._exec_fetchall(sql, (schema, table_name))
        columns = [
            {
                "name": r[0],
                "data_type": r[1],
                "max_length": r[2],
                "numeric_precision": r[3],
                "numeric_scale": r[4],
                "nullable": (r[5] == "YES"),
                "default": r[6],
                "position": r[7],
            }
            for r in rows
        ]
        return {
            "schema": schema,
            "table_name": table_name,
            "columns": columns,
            "column_count": len(columns),
        }

    async def _insert_row(self, **kw: Any) -> dict[str, Any]:
        """إدراج صف في جدول باستخدام البارامترات الموضعية الآمنة.

        Args (via kwargs):
            table_name (str): اسم الجدول (مطلوب).
            schema (str): اسم الـ schema (افتراضيًا 'dbo').
            columns (list[str]): قائمة أسماء الأعمدة (مطلوب).
            values (list[Any]): قائمة القيم بنفس ترتيب الأعمدة (مطلوب).

        Returns:
            {"table": str, "rows_affected": int}.
        """
        table_name = kw.get("table_name")
        columns: Optional[list[str]] = kw.get("columns")
        values: Optional[list[Any]] = kw.get("values")
        if not table_name or not columns or values is None:
            raise ConnectorError(
                "sql_server: insert_row يتطلب 'table_name' و 'columns' و 'values'",
            )
        if len(columns) != len(values):
            raise ConnectorError(
                "sql_server: عدد الأعمدة لا يطابق عدد القيم",
            )
        schema = kw.get("schema", "dbo")
        # بناء placeholders آمنة (?) — لا تنسيق القيم في النص مباشرةً (SQL injection prevention)
        placeholders = ", ".join(["?"] * len(columns))
        cols = ", ".join(f"[{c}]" for c in columns)
        sql = (
            f"INSERT INTO [{schema}].[{table_name}] ({cols}) "
            f"VALUES ({placeholders})"
        )
        rows_affected = await self._exec_dml(sql, tuple(values))
        return {"table": f"[{schema}].[{table_name}]", "rows_affected": rows_affected}

    async def _update_row(self, **kw: Any) -> dict[str, Any]:
        """تحديث صفوف في جدول عبر WHERE clause آمنة بالبارامترات.

        Args (via kwargs):
            table_name (str): اسم الجدول (مطلوب).
            schema (str): اسم الـ schema (افتراضيًا 'dbo').
            set_clauses (dict[str, Any]): {column: value} للتحديث (مطلوب).
            where_clauses (dict[str, Any]): {column: value} لشرط WHERE
                (يُدمج بـ AND) (مطلوب).

        Returns:
            {"table": str, "rows_affected": int}.
        """
        table_name = kw.get("table_name")
        set_clauses: Optional[dict[str, Any]] = kw.get("set_clauses")
        where_clauses: Optional[dict[str, Any]] = kw.get("where_clauses")
        if not table_name or not set_clauses or not where_clauses:
            raise ConnectorError(
                "sql_server: update_row يتطلب 'table_name' و 'set_clauses' "
                "و 'where_clauses'",
            )
        schema = kw.get("schema", "dbo")

        set_sql = ", ".join(f"[{c}] = ?" for c in set_clauses.keys())
        where_sql = " AND ".join(f"[{c}] = ?" for c in where_clauses.keys())
        sql = (
            f"UPDATE [{schema}].[{table_name}] "
            f"SET {set_sql} WHERE {where_sql}"
        )
        params = tuple(set_clauses.values()) + tuple(where_clauses.values())
        rows_affected = await self._exec_dml(sql, params)
        return {"table": f"[{schema}].[{table_name}]", "rows_affected": rows_affected}

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
            "protocol": "TDS over ODBC (pyodbc)",
            "pyodbc_available": _PYODBC_AVAILABLE,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "ddl": False,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "server": self._server,
            "port": self._port,
            "database": self._database,
            "driver": self._driver,
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:sql_server:read",
            "connector:sql_server:write",
            "database:tables:read",
            "database:tables:insert",
            "database:tables:update",
        ]
