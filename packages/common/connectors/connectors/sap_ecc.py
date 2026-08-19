"""
موصل SAP ECC لمنصة HSAAI
==========================
يتيح هذا الموصل الوصول إلى SAP ECC (ERP Central Component) عبر بروتوكول
RFC باستخدام مكتبة pyrfc (التي تعتمد على SAP NWRFC SDK). يتضمن الموصل
آلية fallback أنيقة: إذا لم تكن مكتبة pyrfc أو SAP NWRFC SDK متوفرة،
يُسجَّل الموصل ويبقى قابلاً للاستيراد، لكنه يرفع ConnectorError عند
connect() مع توضيح سبب الفشل.

آلية العمل:
    - pyrfc متزامنة بالكامل، لذا تُغلَّف استدعاءاتها بـ asyncio.to_thread
      لتظل متوافقة مع البنية async للـ BaseConnector.
    - يُدعم SAP connection parameters عبر config.secrets: ASHOST, SYSNR,
      CLIENT, USER, PASSWD, LANG، أو عبر config.sap_params (dict كامل).
    - يدعم أيضًا connection parameters المخصصة (MSSERV, GROUP, ...).

الإجراءات المدعومة:
    - call_rfc             : استدعاء RFC function module عام
    - call_bapi            : استدعاء BAPI (Business API) مع التزام/التراجع
    - get_table            : قراءة جدول SAP عبر RFC_READ_TABLE
    - create_sales_order   : إنشاء أمر مبيعات عبر BAPI_SALESORDER_CREATEFROMDAT2

search() يبحث في أسماء جداول SAP (DD02L) أو في أي جدول محدد.

الاستخدام:
    cfg = ConnectorConfig(
        name="sap_ecc",
        display_name="SAP ECC Production",
        category="ERP",
        base_url="sap://eccprd.corp.local",
        auth_strategy=AuthStrategy.BASIC,
        secrets={
            "ashost": "eccprd.corp.local",
            "sysnr": "00",
            "client": "100",
            "user": "RFCUSER",
            "passwd": "...",
            "lang": "EN",
        },
    )
    connector = SAPECCConnector(cfg)
    await connector.connect()
    result = await connector.call("call_rfc", function="STFC_CONNECTION", REQUTEXT="hello")
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

# محاولة استيراد pyrfc مع fallback أنيق. pyrfc تتطلب SAP NWRFC SDK
# مُثبَّتًا على مستوى النظام، لذا قد لا تكون متوفرة في كل بيئة.
try:
    import pyrfc  # type: ignore[import-not-found]
    from pyrfc import Connection as SAPConnection  # type: ignore[import-not-found]
    _PYRFC_AVAILABLE = True
except ImportError:  # pragma: no cover - defensive
    pyrfc = None  # type: ignore[assignment]
    SAPConnection = None  # type: ignore[assignment]
    _PYRFC_AVAILABLE = False
    logger.warning(
        "sap_ecc: مكتبة pyrfc غير مثبتة (أو SAP NWRFC SDK غير متوفر). "
        "الموصل قابل للاستيراد لكن لن يعمل حتى تُثبَّت: "
        "pip install pyrfc وتثبيت SAP NWRFC SDK.",
    )


@connector("sap_ecc", version="1.0.0", category="ERP")
class SAPECCConnector(BaseConnector):
    """موصل SAP ECC عبر بروتوكول RFC باستخدام pyrfc مع fallback آمن."""

    #: الحد الأقصى لعدد الصفوف المُسترجَعة من get_table
    DEFAULT_TABLE_ROW_LIMIT: int = 1000

    #: اللغة الافتراضية لجلسة SAP
    DEFAULT_LANG: str = "EN"

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "call_rfc",
        "call_bapi",
        "get_table",
        "create_sales_order",
    )

    #: أسماء معاملات الاتصال القياسية بـ SAP RFC
    _CONN_PARAMS_KEYS: tuple[str, ...] = (
        "ashost", "sysnr", "client", "user", "passwd", "lang",
        "mshost", "msserv", "group", "sysid", "saprouter",
    )

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        # SAP RFC لا يستخدم HTTP، لذا نُلغي عميل httpx الافتراضي
        self._client = None  # type: ignore[assignment]

        self._conn_params: dict[str, str] = self._build_conn_params()
        self._sap_connection: Any = None  # SAPConnection instance
        self._connected_at: float = 0.0

    def _build_conn_params(self) -> dict[str, str]:
        """بناء قاموس معاملات اتصال SAP RFC من config.secrets و config.sap_params.

        يُعطى الأولوية لـ config.sap_params (إن وُجد كقاموس كامل)، ثم تُدمَج
        المفاتيح الفردية من secrets (ashost, sysnr, client, user, passwd, lang).
        """
        # إن أُعطي قاموس sap_params كامل، نستخدمه كأساس
        sap_params = getattr(self.config, "sap_params", None)
        params: dict[str, str] = {}
        if isinstance(sap_params, dict):
            params.update({k: str(v) for k, v in sap_params.items() if v is not None})

        # دمج المفاتيح الفردية من secrets (لها الأولوية عند التعارض)
        for key in self._CONN_PARAMS_KEYS:
            value = self._get_secret(key, "")
            if value:
                params[key] = value

        # ضمان وجود اللغة
        params.setdefault("lang", self.DEFAULT_LANG)
        return params

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
        """إنشاء اتصال RFC مُصادَق مع خادم SAP ECC.

        يبني SAPConnection من معاملات الاتصال (ashost/sysnr/client/user/passwd)
        وينفذ الـ connection في thread منفصل لأن pyrfc متزامنة.

        Raises:
            ConnectorError: إذا لم تكن pyrfc/SAP NWRFC SDK متوفرة.
            ConnectorAuthenticationError: عند فقدان معاملات الاتصال الإلزامية
                أو فشل إنشاء الاتصال.
        """
        if not _PYRFC_AVAILABLE:
            raise ConnectorError(
                "sap_ecc: مكتبة pyrfc غير مثبتة أو SAP NWRFC SDK غير متوفر. "
                "ثبّتها عبر: pip install pyrfc وتثبيت SAP NWRFC SDK من SAP Support Portal.",
            )

        # التحقق من المعاملات الإلزامية
        required = ("ashost", "sysnr", "client", "user", "passwd")
        missing = [k for k in required if not self._conn_params.get(k)]
        # في حالة Logon Group (mshost + group) قد لا يكون ashost/sysnr مطلوبًا
        if missing and not (self._conn_params.get("mshost") and self._conn_params.get("group")):
            raise ConnectorAuthenticationError(
                f"sap_ecc: معاملات الاتصال الإلزامية مفقودة: {missing} "
                "(أو وفّر mshost+group لاستخدام Logon Group)",
            )

        try:
            # إنشاء الاتصال في thread منفصل (pyrfc متزامن)
            self._sap_connection = await asyncio.to_thread(
                SAPConnection, **self._conn_params,  # type: ignore[misc]
            )
        except Exception as exc:
            raise ConnectorAuthenticationError(
                f"sap_ecc: فشل إنشاء اتصال RFC مع {self._conn_params.get('ashost', 'N/A')}: {exc}",
            ) from exc

        self._connected_at = time.time()
        logger.info(
            "sap_ecc: اتصال RFC ناجح مع %s (client=%s, user=%s)",
            self._conn_params.get("ashost", "N/A"),
            self._conn_params.get("client", "N/A"),
            self._conn_params.get("user", "N/A"),
        )

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة اتصال SAP ECC عبر استدعاء RFC ping بسيط (STFC_PING).

        Returns:
            HealthResult: HEALTHY إذا نجح ping، UNHEALTHY خلاف ذلك.
        """
        start = time.monotonic()
        if self._sap_connection is None:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=0.0,
                error="sap_ecc: لا يوجد اتصال RFC — استدعِ connect() أولاً",
            )
        try:
            await asyncio.to_thread(
                self._sap_connection.call, "STFC_PING", {"REQUTEXT": "hsaai-health-check"},
            )
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                status=HealthStatus.HEALTHY,
                connector=self.config.name,
                latency_ms=latency_ms,
                details={"function": "STFC_PING", "ashost": self._conn_params.get("ashost", "")},
            )
        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=latency_ms,
                error=f"sap_ecc: فشل ping RFC: {exc}",
            )

    # ───────────────────────────────────────────────────────────────────
    #  RFC Call Helpers
    # ───────────────────────────────────────────────────────────────────
    async def _rfc_call(
        self, function: str, parameters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """تنفيذ استدعاء RFC عام في thread منفصل.

        Args:
            function: اسم الـ function module (مثل 'STFC_CONNECTION').
            parameters: قاموس معاملات الإدخال.

        Returns:
            قاموس نتائج الـ RFC كما أرجعها الخادم.

        Raises:
            ConnectorError: عند فقدان الاتصال أو فشل الاستدعاء.
        """
        if self._sap_connection is None:
            raise ConnectorError("sap_ecc: العميل غير مهيأ — استدعِ connect() أولاً")
        params = parameters or {}
        try:
            result = await asyncio.to_thread(
                self._sap_connection.call, function, params,
            )
        except Exception as exc:
            raise ConnectorError(
                f"sap_ecc: فشل استدعاء RFC '{function}': {exc}",
            ) from exc
        # pyrfc يُرجع عادةً ABAP structure أو dict-like؛ نُحوِّل إلى dict عادي
        if isinstance(result, dict):
            return dict(result)
        return {"result": result}

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في أسماء جداول SAP عبر RFC_READ_TABLE على DD02L (جدول الجداول).

        Args:
            query: نص البحث (يُطابَق ضد TABNAME).
            **kwargs:
                table (str): اسم الجدول البديل (افتراضيًا 'DD02L').
                fields (list[str]): الحقول المُسترجَعة (افتراضيًا
                    ['TABNAME', 'TABCLASS', 'DDTEXT']).
                limit (int): عدد النتائج (افتراضيًا 50).

        Returns:
            قائمة بقواميس صفوف الجدول المطابقة.
        """
        table: str = kwargs.pop("table", "DD02L")
        fields: list[str] = kwargs.pop(
            "fields", ["TABNAME", "TABCLASS", "DDTEXT"],
        )
        limit: int = int(kwargs.pop("limit", 50))
        # تنظيف النص لمنع حقن ABAP (إزالة علامات الاقتباس)
        safe_query = query.replace("'", "").replace('"', "").strip()
        if not safe_query:
            return []

        # بناء WHERE clause لـ RFC_READ_TABLE
        options = [{"TEXT": f"TABNAME LIKE '%{safe_query}%'"}]
        fields_def = [{"FIELDNAME": f, "OFFSET": str(i * 255)} for i, f in enumerate(fields)]

        try:
            result = await self._rfc_call("RFC_READ_TABLE", {
                "QUERY_TABLE": table,
                "DELIMITER": "|",
                "ROWCOUNT": str(min(limit, self.DEFAULT_TABLE_ROW_LIMIT)),
                "OPTIONS": options,
                "FIELDS": fields_def,
            })
        except ConnectorError:
            return []

        # تحويل النتائج: DATA هو قائمة من {"WA": "VAL1|VAL2|..."}
        rows: list[dict[str, Any]] = []
        data = result.get("DATA", []) or []
        for row in data:
            wa = row.get("WA", "") if isinstance(row, dict) else str(row)
            values = wa.split("|")
            entry = {fields[i]: values[i].strip() if i < len(values) else "" for i in range(len(fields))}
            rows.append(entry)
        return rows

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على SAP ECC.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم أو فشل التنفيذ.
        """
        handlers = {
            "call_rfc": self._call_rfc,
            "call_bapi": self._call_bapi,
            "get_table": self._get_table,
            "create_sales_order": self._create_sales_order,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"sap_ecc: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _call_rfc(self, **kw: Any) -> dict[str, Any]:
        """استدعاء RFC function module عام.

        Args (via kwargs):
            function (str): اسم الـ function module (إلزامي).
            parameters (dict): معاملات الإدخال (اختياري).

        Raises:
            ConnectorError: عند فقدان 'function' أو فشل الاستدعاء.
        """
        function: Optional[str] = kw.get("function")
        if not function:
            raise ConnectorError("sap_ecc: 'function' إلزامي لإجراء call_rfc")
        parameters: dict[str, Any] = kw.get("parameters", {}) or {}
        return await self._rfc_call(function, parameters)

    async def _call_bapi(self, **kw: Any) -> dict[str, Any]:
        """استدعاء BAPI مع إدارة المعاملة (commit/rollback).

        Args (via kwargs):
            function (str): اسم الـ BAPI (مثل 'BAPI_USER_GET_DETAIL').
            parameters (dict): معاملات الإدخال.
            commit (bool): إن كان True (افتراضيًا)، يُنفَّذ BAPI_TRANSACTION_COMMIT
                بعد نجاح الاستدعاء. إن كان False، يُتراجَع via
                BAPI_TRANSACTION_ROLLBACK عند الفشل فقط.

        Returns:
            قاموس يحتوي على 'result' و 'commit_status'.
        """
        function: Optional[str] = kw.get("function")
        if not function:
            raise ConnectorError("sap_ecc: 'function' إلزامي لإجراء call_bapi")
        parameters: dict[str, Any] = kw.get("parameters", {}) or {}
        commit: bool = bool(kw.get("commit", True))

        result = await self._rfc_call(function, parameters)

        # التحقق من RETURN structure (معة BAPIs) لتحديد النجاح/الفشل
        return_struct = result.get("RETURN") or {}
        if isinstance(return_struct, dict):
            return_type = return_struct.get("TYPE", "")
            return_msg = return_struct.get("MESSAGE", "")
        else:
            return_type = ""
            return_msg = str(return_struct)

        if return_type in ("E", "A"):  # Error / Abort
            # تراجع تلقائي عند الفشل
            try:
                await self._rfc_call("BAPI_TRANSACTION_ROLLBACK", {})
            except ConnectorError:
                pass
            raise ConnectorError(
                f"sap_ecc: BAPI '{function}' فشل: {return_msg}",
            )

        commit_status = "skipped"
        if commit:
            try:
                await self._rfc_call("BAPI_TRANSACTION_COMMIT", {"WAIT": "X"})
                commit_status = "committed"
            except ConnectorError as exc:
                raise ConnectorError(
                    f"sap_ecc: فشل BAPI_TRANSACTION_COMMIT بعد '{function}': {exc}",
                ) from exc

        return {"result": result, "commit_status": commit_status, "return_message": return_msg}

    async def _get_table(self, **kw: Any) -> dict[str, Any]:
        """قراءة جدول SAP عبر RFC_READ_TABLE.

        Args (via kwargs):
            table (str): اسم الجدول (إلزامي).
            fields (list[str]): الحقول المُسترجَعة (افتراضيًا '*' = جميع الحقول).
            where (list[str]): شروط WHERE (قائمة نصوص ABAP).
            limit (int): عدد الصفوف (افتراضيًا 100).
            delimiter (str): الفاصل (افتراضيًا '|').

        Returns:
            قاموس يحتوي على 'table', 'fields', 'count', 'rows'.
        """
        table: Optional[str] = kw.get("table")
        if not table:
            raise ConnectorError("sap_ecc: 'table' إلزامي لإجراء get_table")
        fields: list[str] = kw.get("fields") or ["*"]
        where: list[str] = kw.get("where") or []
        limit: int = int(kw.get("limit", 100))
        delimiter: str = kw.get("delimiter", "|")

        options = [{"TEXT": clause} for clause in where]
        fields_def = [
            {"FIELDNAME": f, "OFFSET": str(i * 512)}
            for i, f in enumerate(fields)
        ]
        result = await self._rfc_call("RFC_READ_TABLE", {
            "QUERY_TABLE": table,
            "DELIMITER": delimiter,
            "ROWCOUNT": str(min(limit, self.DEFAULT_TABLE_ROW_LIMIT)),
            "OPTIONS": options,
            "FIELDS": fields_def,
        })

        rows: list[dict[str, Any]] = []
        data = result.get("DATA", []) or []
        for row in data:
            wa = row.get("WA", "") if isinstance(row, dict) else str(row)
            values = wa.split(delimiter)
            if fields == ["*"]:
                rows.append({"raw": wa, "values": values})
            else:
                entry = {fields[i]: values[i].strip() if i < len(values) else "" for i in range(len(fields))}
                rows.append(entry)

        return {
            "table": table,
            "fields": fields,
            "count": len(rows),
            "rows": rows,
        }

    async def _create_sales_order(self, **kw: Any) -> dict[str, Any]:
        """إنشاء أمر مبيعات عبر BAPI_SALESORDER_CREATEFROMDAT2.

        Args (via kwargs):
            order_header_in (dict): ترويسة أمر المبيعات (إلزامي، يتضمن
                DOC_TYPE, SALES_ORG, DISTR_CHAN, DIVISION, ...).
            order_items_in (list[dict]): بنود الأمر (إلزامي، كل بند:
                MATERIAL, REQ_QTY, ...).
            order_partners (list[dict]): الشركاء (إلزامي، كل شريك:
                PARTN_ROLE, PARTN_NUMB).
            order_schedules_in (list[dict]): جداول التسليم (اختياري).
            commit (bool): تنفيذ commit بعد الإنشاء (افتراضيًا True).

        Returns:
            قاموس يحتوي على 'sales_order_number' و 'commit_status'.

        Raises:
            ConnectorError: عند فقدان الحقول الإلزامية أو فشل الإنشاء.
        """
        order_header_in: dict[str, Any] = kw.get("order_header_in") or {}
        order_items_in: list[dict[str, Any]] = kw.get("order_items_in") or []
        order_partners: list[dict[str, Any]] = kw.get("order_partners") or []
        order_schedules_in: list[dict[str, Any]] = kw.get("order_schedules_in") or []
        commit: bool = bool(kw.get("commit", True))

        # التحقق من الحقول الإلزامية
        if not order_header_in:
            raise ConnectorError("sap_ecc: 'order_header_in' إلزامي لإنشاء أمر مبيعات")
        if not order_items_in:
            raise ConnectorError("sap_ecc: 'order_items_in' لا يمكن أن يكون فارغًا")
        if not order_partners:
            raise ConnectorError("sap_ecc: 'order_partners' لا يمكن أن يكون فارغًا (مطلوب شريك Sold-To على الأقل)")

        required_header = ("DOC_TYPE", "SALES_ORG", "DISTR_CHAN", "DIVISION")
        missing = [f for f in required_header if not order_header_in.get(f)]
        if missing:
            raise ConnectorError(
                f"sap_ecc: حقول ترويسة إلزامية مفقودة: {missing}",
            )

        parameters = {
            "ORDER_HEADER_IN": order_header_in,
            "ORDER_ITEMS_IN": order_items_in,
            "ORDER_PARTNERS": order_partners,
            "ORDER_SCHEDULES_IN": order_schedules_in,
        }
        result = await self._rfc_call(
            "BAPI_SALESORDER_CREATEFROMDAT2", parameters,
        )

        sales_doc = result.get("SALESDOCUMENT", "") or ""
        return_struct = result.get("RETURN") or {}
        if isinstance(return_struct, dict):
            return_type = return_struct.get("TYPE", "")
            return_msg = return_struct.get("MESSAGE", "")
        else:
            return_type = ""
            return_msg = str(return_struct)

        if return_type in ("E", "A") or not sales_doc:
            try:
                await self._rfc_call("BAPI_TRANSACTION_ROLLBACK", {})
            except ConnectorError:
                pass
            raise ConnectorError(
                f"sap_ecc: فشل إنشاء أمر المبيعات: {return_msg}",
            )

        commit_status = "skipped"
        if commit:
            try:
                await self._rfc_call("BAPI_TRANSACTION_COMMIT", {"WAIT": "X"})
                commit_status = "committed"
            except ConnectorError as exc:
                raise ConnectorError(
                    f"sap_ecc: فشل commit بعد إنشاء أمر المبيعات {sales_doc}: {exc}",
                ) from exc

        return {
            "sales_order_number": sales_doc,
            "commit_status": commit_status,
            "return_message": return_msg,
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
            "protocol": "SAP RFC (pyrfc + NWRFC SDK)",
            "pyrfc_available": _PYRFC_AVAILABLE,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "read": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "connection_params_known": sorted(self._conn_params.keys()),
            "customizable": True,
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل (RBAC)."""
        return self.config.required_permissions or [
            "connector:sap_ecc:read",
            "connector:sap_ecc:write",
            "sap:rfc:call",
            "sap:bapi:execute",
        ]
