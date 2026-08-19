"""
موصل MongoDB لمنصة HSAAI
========================
يتيح هذا الموصل الوصول إلى MongoDB عبر مكتبة pymongo (مع دعم AsyncMongo
اختياريًا في المستقبل).

الإجراءات المدعومة:
    - find        : تنفيذ find على collection مع filter
    - insert_one  : إدراج مستند واحد
    - insert_many : إدراج عدة مستندات
    - update_one  : تحديث مستند واحد (مع upsert اختياري)
    - delete_one  : حذف مستند واحد
    - aggregate   : تنفيذ aggregation pipeline

كما يدعم search() عبر $text search على collection محدد.

ملاحظات:
    - مكتبة pymongo متزامنة، لذا يُغلّف الموصل استدعاءاتها بـ asyncio.to_thread.
    - إذا لم تكن pymongo مثبتة، يبقى الموصل قابلاً للاستيراد لكنه يرفع
      ConnectorError عند connect().

الاستخدام:
    cfg = ConnectorConfig(
        name="mongodb",
        display_name="Corporate MongoDB",
        category="Database",
        base_url="mongodb://mongo01.corp.local:27017",
        auth_strategy=AuthStrategy.BASIC,
        database="corporate",
        secrets={
            "username": "appuser",
            "password": "...",
            "auth_source": "admin",
        },
    )
    connector = MongoDBConnector(cfg)
    await connector.connect()
    docs = await connector.call("find", collection="users", filter={"active": True})
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

# محاولة استيراد pymongo مع fallback أنيق
try:
    import pymongo
    from pymongo import ASCENDING, DESCENDING, MongoClient
    from pymongo.errors import (
        PyMongoError,
        OperationFailure,
        ConnectionFailure as PyMongoConnectionFailure,
    )
    _PYMONGO_AVAILABLE = True
except ImportError:  # pragma: no cover - defensive
    pymongo = None  # type: ignore[assignment]
    ASCENDING = 1  # type: ignore[assignment]
    DESCENDING = -1  # type: ignore[assignment]
    MongoClient = None  # type: ignore[assignment]
    PyMongoError = Exception  # type: ignore[assignment]
    OperationFailure = Exception  # type: ignore[assignment]
    PyMongoConnectionFailure = Exception  # type: ignore[assignment]
    _PYMONGO_AVAILABLE = False
    logger.warning(
        "mongodb: مكتبة pymongo غير مثبتة — الموصل قابل للاستيراد "
        "لكن لن يعمل حتى تُثبت: pip install pymongo",
    )


@connector("mongodb", version="1.0.0", category="Database")
class MongoDBConnector(BaseConnector):
    """موصل MongoDB عبر pymongo مع تشغيل async عبر to_thread."""

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "find",
        "insert_one",
        "insert_many",
        "update_one",
        "delete_one",
        "aggregate",
    )

    #: المنفذ الافتراضي لـ MongoDB
    DEFAULT_PORT: int = 27017

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        # pymongo لا يستخدم HTTP — نُلغي العميل httpx
        self._client = None  # type: ignore[assignment]

        self._username: str = self._get_secret("username", "")
        self._password: str = self._get_secret("password", "")
        self._auth_source: str = (
            self._get_secret("auth_source", "") or "admin"
        )
        # قاعدة البيانات الافتراضية من config.database أو من base_url
        self._database_name: str = (
            getattr(self.config, "database", "")
            or getattr(self.config, "dbname", "")
            or self._parse_database_name()
        )
        # replica set اختياري
        self._replica_set: Optional[str] = getattr(self.config, "replica_set", None)
        # TLS settings
        self._tls: bool = bool(getattr(self.config, "tls", False))
        self._tls_ca_file: Optional[str] = getattr(self.config, "tls_ca_file", None)
        # MongoDB client (sync)
        self._mongo_client: Any = None  # pymongo.MongoClient
        self._db: Any = None  # pymongo.database.Database
        # connection string مُجمَّعة (بدون كلمة المرور للسجلات)
        self._connection_uri: str = self._build_connection_uri()

    def _get_secret(self, key: str, default: str = "") -> str:
        """استرجاع سر من config.secrets بأمان."""
        secret = self.config.secrets.get(key)
        if secret is None:
            return default
        try:
            return secret.get_secret_value()
        except Exception:
            return default

    def _parse_database_name(self) -> str:
        """استخراج اسم قاعدة البيانات من base_url بصيغة mongodb://host:port/db."""
        url = self.config.base_url or ""
        if "/" in url:
            tail = url.rsplit("/", 1)[-1]
            # إزالة query string
            if "?" in tail:
                tail = tail.split("?", 1)[0]
            return tail
        return "test"  # الافتراضي في MongoDB

    def _build_connection_uri(self) -> str:
        """بناء سلسلة اتصال MongoDB URI آمنة مع بيانات الاعتماد."""
        base = self.config.base_url or "mongodb://localhost:27017"
        # إذا كانت base_url تحتوي بالفعل على بيانات اعتماد، نعيد استخدامها مباشرة
        if "@" in base and self._username and self._password:
            return base
        # بناء URI من host + بيانات اعتماد
        if "://" in base:
            scheme, rest = base.split("://", 1)
        else:
            scheme, rest = "mongodb", base
        # إزالة بيانات الاعتماد القديمة إن وُجدت
        if "@" in rest:
            rest = rest.split("@", 1)[1]
        creds = ""
        if self._username and self._password:
            creds = f"{self._username}:{self._password}@"
        return f"{scheme}://{creds}{rest}"

    # ───────────────────────────────────────────────────────────────────
    #  Connect / Disconnect (override — لا HTTP)
    # ───────────────────────────────────────────────────────────────────
    async def connect(self) -> None:
        """تهيئة الموصل: إنشاء MongoClient واختبار الاتصال."""
        from packages.common.connectors.base import ConnectorState
        if self.state == ConnectorState.CONNECTED:
            return
        self.state = ConnectorState.INITIALIZING
        try:
            await self.authenticate()
            self.state = ConnectorState.CONNECTED
            logger.info(
                "mongodb: تم الاتصال بـ %s (db=%s)",
                self.config.base_url, self._database_name,
            )
            self._start_health_check()
        except Exception as e:
            self.state = ConnectorState.ERROR
            logger.error("mongodb: فشل الاتصال: %s", e)
            raise

    async def disconnect(self) -> None:
        """إغلاق اتصال MongoDB."""
        from packages.common.connectors.base import ConnectorState
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except Exception:
                pass
            self._health_task = None
        if self._mongo_client is not None:
            try:
                await asyncio.to_thread(self._mongo_client.close)
                logger.info("mongodb: تم إغلاق اتصال MongoDB")
            except Exception as exc:
                logger.warning("mongodb: خطأ أثناء الإغلاق: %s", exc)
            finally:
                self._mongo_client = None
                self._db = None
        self.state = ConnectorState.DISCONNECTED

    # ───────────────────────────────────────────────────────────────────
    #  Authentication
    # ───────────────────────────────────────────────────────────────────
    async def authenticate(self) -> None:
        """إنشاء اتصال MongoClient مع MongoDB.

        يدعم SCRAM-SHA-1/256 (افتراضيًا في MongoDB الحديث) عبر تضمين
        بيانات الاعتماد في URI. يختبر الاتصال عبر ping.

        Raises:
            ConnectorAuthenticationError: عند فشل الاتصال أو المصادقة.
            ConnectorError: إذا لم تكن pymongo متوفرة.
        """
        if not _PYMONGO_AVAILABLE:
            raise ConnectorError(
                "mongodb: مكتبة pymongo غير مثبتة. ثبّتها: pip install pymongo",
            )

        # بناء خيارات الاتصال
        kwargs: dict[str, Any] = {
            "serverSelectionTimeoutMS": int(self.config.connect_timeout * 1000),
            "socketTimeoutMS": int(self.config.read_timeout * 1000),
            "connectTimeoutMS": int(self.config.connect_timeout * 1000),
        }
        if self._replica_set:
            kwargs["replicaSet"] = self._replica_set
        if self._tls:
            kwargs["tls"] = True
            if self._tls_ca_file:
                kwargs["tlsCAFile"] = self._tls_ca_file
        # authSource إذا كانت بيانات الاعتماد موجودة
        if self._username and self._password and "authSource" not in self._connection_uri:
            kwargs["authSource"] = self._auth_source

        try:
            self._mongo_client = await asyncio.to_thread(
                MongoClient, self._connection_uri, **kwargs,
            )
        except Exception as exc:
            raise ConnectorAuthenticationError(
                f"mongodb: فشل إنشاء MongoClient: {exc}",
            ) from exc

        # تحديد قاعدة البيانات الافتراضية
        if self._database_name:
            self._db = self._mongo_client[self._database_name]

        # اختبار الاتصال عبر ping
        try:
            def _ping() -> dict[str, Any]:
                return self._mongo_client.admin.command("ping")
            ping_result = await asyncio.to_thread(_ping)
        except PyMongoConnectionFailure as exc:
            raise ConnectorAuthenticationError(
                f"mongodb: تعذّر الاتصال بالخادم: {exc}",
            ) from exc
        except OperationFailure as exc:
            # فشل المصادقة (عادة code=18)
            raise ConnectorAuthenticationError(
                f"mongodb: فشل المصادقة: {exc}",
            ) from exc
        except Exception as exc:
            raise ConnectorAuthenticationError(
                f"mongodb: فشل اختبار الاتصال (ping): {exc}",
            ) from exc

        if not ping_result or ping_result.get("ok") != 1.0:
            raise ConnectorAuthenticationError(
                f"mongodb: ping لم يُرجع ok=1: {ping_result}",
            )

        logger.info(
            "mongodb: اتصال ناجح (ping ok) — db=%s", self._database_name,
        )

    async def _ensure_connected(self) -> None:
        """التأكد من أن الاتصال ما زال حيًا."""
        if not _PYMONGO_AVAILABLE:
            raise ConnectorError(
                "mongodb: pymongo غير متوفرة. ثبّتها: pip install pymongo",
            )
        if self._mongo_client is None or self._db is None:
            raise ConnectorError(
                "mongodb: الاتصال غير مهيأ — استدعِ connect() أولاً",
            )

    def _collection(self, name: str) -> Any:
        """الحصول على collection من قاعدة البيانات الافتراضية."""
        if name is None or not str(name).strip():
            raise ConnectorError("mongodb: اسم collection مطلوب")
        return self._db[name]

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة MongoDB عبر أمر ping."""
        start = time.monotonic()
        try:
            if not _PYMONGO_AVAILABLE:
                return HealthResult(
                    status=HealthStatus.UNHEALTHY,
                    connector=self.config.name,
                    latency_ms=0.0,
                    error="pymongo library not installed",
                )
            await self._ensure_connected()

            def _ping() -> dict[str, Any]:
                return self._mongo_client.admin.command("ping")
            ping_result = await asyncio.to_thread(_ping)
            latency_ms = (time.monotonic() - start) * 1000
            if ping_result and ping_result.get("ok") == 1.0:
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    connector=self.config.name,
                    latency_ms=latency_ms,
                    details={
                        "database": self._database_name,
                        "replica_set": self._replica_set,
                        "probe": "ping",
                    },
                )
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=latency_ms,
                error=f"ping returned unexpected: {ping_result}",
            )
        except Exception as exc:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=(time.monotonic() - start) * 1000,
                error=str(exc),
            )

    # ───────────────────────────────────────────────────────────────────
    #  Serialization Helpers
    # ───────────────────────────────────────────────────────────────────
    @staticmethod
    def _serialize_doc(doc: Any) -> dict[str, Any]:
        """تحويل مستند MongoDB إلى dict JSON-serializable.

        يحوّل ObjectId إلى سلسلة نصية والتواريخ إلى ISO 8601.
        """
        if doc is None:
            return {}
        if not isinstance(doc, dict):
            return {"value": str(doc)}
        out: dict[str, Any] = {}
        for k, v in doc.items():
            if k == "_id":
                # تحويل ObjectId إلى سلسلة
                out[k] = str(v)
            elif hasattr(v, "isoformat"):
                # datetime, date
                out[k] = v.isoformat()
            elif isinstance(v, (list, tuple)):
                out[k] = [
                    MongoDBConnector._serialize_doc(x) if isinstance(x, dict)
                    else (str(x) if hasattr(x, "binary") or hasattr(x, "isoformat") else x)
                    for x in v
                ]
            elif isinstance(v, dict):
                out[k] = MongoDBConnector._serialize_doc(v)
            elif hasattr(v, "binary"):
                # Binary data
                out[k] = f"<binary {len(v)} bytes>"
            else:
                out[k] = v
        return out

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في collection عبر $text search.

        يتطلب وجود فهرس نصي (text index) على الـ collection.

        Args:
            query: نص البحث.
            **kwargs:
                collection (str): اسم الـ collection (مطلوب).
                limit (int): عدد النتائج (افتراضيًا 50).
                project (dict): حقول الإسقاط (اختياري).

        Returns:
            قائمة بالمستندات المطابقة (متسلسلة JSON-safe).

        Raises:
            ConnectorError: عند عدم تمرير collection أو فشل البحث.
        """
        if not query or not query.strip():
            return []
        collection_name: Optional[str] = kwargs.pop("collection", None)
        if not collection_name:
            raise ConnectorError("mongodb: search يتطلب 'collection'")
        limit = int(kwargs.pop("limit", 50))
        project = kwargs.pop("project", None)

        filter_doc = {"$text": {"$search": query.strip()}}
        await self._ensure_connected()
        collection = self._collection(collection_name)

        def _do() -> list[dict[str, Any]]:
            cursor = collection.find(
                filter_doc,
                projection=project,
            ).limit(max(1, min(limit, 1000)))
            return [MongoDBConnector._serialize_doc(d) for d in cursor]
        try:
            return await asyncio.to_thread(_do)
        except PyMongoError as exc:
            raise ConnectorError(
                f"mongodb: فشل $text search في '{collection_name}': {exc}",
            ) from exc

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على MongoDB.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "find": self._find,
            "insert_one": self._insert_one,
            "insert_many": self._insert_many,
            "update_one": self._update_one,
            "delete_one": self._delete_one,
            "aggregate": self._aggregate,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"mongodb: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _find(self, **kw: Any) -> dict[str, Any]:
        """تنفيذ find على collection مع filter.

        Args (via kwargs):
            collection (str): اسم الـ collection (مطلوب).
            filter (dict): فلتر الاستعلام (افتراضيًا {} — الكل).
            projection (dict): حقول الإسقاط (اختياري).
            sort (list[tuple[str, int]]): ترتيب (اختياري).
            limit (int): أقصى عدد نتائج (افتراضيًا 100).
            skip (int): عدد المستندات للتخطّي (للتصفّح).

        Returns:
            {"collection": str, "count": int, "documents": list[dict]}.
        """
        collection_name = kw.get("collection")
        if not collection_name:
            raise ConnectorError("mongodb: find يتطلب 'collection'")
        filter_doc: dict[str, Any] = kw.get("filter", {}) or {}
        projection = kw.get("projection")
        sort = kw.get("sort")
        limit = int(kw.get("limit", 100))
        skip = int(kw.get("skip", 0))

        await self._ensure_connected()
        collection = self._collection(collection_name)

        def _do() -> list[dict[str, Any]]:
            cursor = collection.find(filter_doc, projection=projection)
            if sort:
                cursor = cursor.sort(sort)
            if skip > 0:
                cursor = cursor.skip(skip)
            cursor = cursor.limit(max(1, min(limit, 10000)))
            return [MongoDBConnector._serialize_doc(d) for d in cursor]
        try:
            docs = await asyncio.to_thread(_do)
        except PyMongoError as exc:
            raise ConnectorError(
                f"mongodb: فشل find في '{collection_name}': {exc}",
            ) from exc
        return {
            "collection": collection_name,
            "count": len(docs),
            "documents": docs,
        }

    async def _insert_one(self, **kw: Any) -> dict[str, Any]:
        """إدراج مستند واحد في collection.

        Args (via kwargs):
            collection (str): اسم الـ collection (مطلوب).
            document (dict): المستند المراد إدراجه (مطلوب).
        """
        collection_name = kw.get("collection")
        document = kw.get("document")
        if not collection_name or not isinstance(document, dict):
            raise ConnectorError(
                "mongodb: insert_one يتطلب 'collection' و 'document' (dict)",
            )
        await self._ensure_connected()
        collection = self._collection(collection_name)

        def _do() -> str:
            result = collection.insert_one(document)
            return str(result.inserted_id)
        try:
            inserted_id = await asyncio.to_thread(_do)
        except PyMongoError as exc:
            raise ConnectorError(
                f"mongodb: فشل insert_one في '{collection_name}': {exc}",
            ) from exc
        return {
            "collection": collection_name,
            "inserted_id": inserted_id,
            "inserted_count": 1,
        }

    async def _insert_many(self, **kw: Any) -> dict[str, Any]:
        """إدراج عدة مستندات في collection.

        Args (via kwargs):
            collection (str): اسم الـ collection (مطلوب).
            documents (list[dict]): قائمة المستندات (مطلوب).
            ordered (bool): تنفيذ مُرتَّب (افتراضيًا True).
        """
        collection_name = kw.get("collection")
        documents = kw.get("documents")
        if not collection_name or not isinstance(documents, list):
            raise ConnectorError(
                "mongodb: insert_many يتطلب 'collection' و 'documents' (list)",
            )
        if not documents:
            return {
                "collection": collection_name,
                "inserted_ids": [],
                "inserted_count": 0,
            }
        ordered = bool(kw.get("ordered", True))
        await self._ensure_connected()
        collection = self._collection(collection_name)

        def _do() -> list[str]:
            result = collection.insert_many(documents, ordered=ordered)
            return [str(_id) for _id in result.inserted_ids]
        try:
            inserted_ids = await asyncio.to_thread(_do)
        except PyMongoError as exc:
            raise ConnectorError(
                f"mongodb: فشل insert_many في '{collection_name}': {exc}",
            ) from exc
        return {
            "collection": collection_name,
            "inserted_ids": inserted_ids,
            "inserted_count": len(inserted_ids),
        }

    async def _update_one(self, **kw: Any) -> dict[str, Any]:
        """تحديث مستند واحد في collection.

        Args (via kwargs):
            collection (str): اسم الـ collection (مطلوب).
            filter (dict): فلتر اختيار المستند (مطلوب).
            update (dict): تعليمات التحديث ($set, $inc, ...) (مطلوب).
            upsert (bool): إنشاء مستند جديد إن لم يوجد (افتراضيًا False).
        """
        collection_name = kw.get("collection")
        filter_doc = kw.get("filter")
        update_doc = kw.get("update")
        if not collection_name or not isinstance(filter_doc, dict) or not isinstance(update_doc, dict):
            raise ConnectorError(
                "mongodb: update_one يتطلب 'collection' و 'filter' (dict) "
                "و 'update' (dict)",
            )
        upsert = bool(kw.get("upsert", False))
        await self._ensure_connected()
        collection = self._collection(collection_name)

        def _do() -> dict[str, Any]:
            result = collection.update_one(filter_doc, update_doc, upsert=upsert)
            return {
                "matched_count": result.matched_count,
                "modified_count": result.modified_count,
                "upserted_id": str(result.upserted_id) if result.upserted_id else None,
            }
        try:
            stats = await asyncio.to_thread(_do)
        except PyMongoError as exc:
            raise ConnectorError(
                f"mongodb: فشل update_one في '{collection_name}': {exc}",
            ) from exc
        return {
            "collection": collection_name,
            **stats,
        }

    async def _delete_one(self, **kw: Any) -> dict[str, Any]:
        """حذف مستند واحد من collection.

        Args (via kwargs):
            collection (str): اسم الـ collection (مطلوب).
            filter (dict): فلتر اختيار المستند (مطلوب).
        """
        collection_name = kw.get("collection")
        filter_doc = kw.get("filter")
        if not collection_name or not isinstance(filter_doc, dict):
            raise ConnectorError(
                "mongodb: delete_one يتطلب 'collection' و 'filter' (dict)",
            )
        await self._ensure_connected()
        collection = self._collection(collection_name)

        def _do() -> int:
            result = collection.delete_one(filter_doc)
            return result.deleted_count
        try:
            deleted_count = await asyncio.to_thread(_do)
        except PyMongoError as exc:
            raise ConnectorError(
                f"mongodb: فشل delete_one في '{collection_name}': {exc}",
            ) from exc
        return {
            "collection": collection_name,
            "deleted_count": deleted_count,
        }

    async def _aggregate(self, **kw: Any) -> dict[str, Any]:
        """تنفيذ aggregation pipeline على collection.

        Args (via kwargs):
            collection (str): اسم الـ collection (مطلوب).
            pipeline (list[dict]): خطوات الـ aggregation pipeline (مطلوب).
            batch_size (int): حجم الدفعة (اختياري).
        """
        collection_name = kw.get("collection")
        pipeline = kw.get("pipeline")
        if not collection_name or not isinstance(pipeline, list):
            raise ConnectorError(
                "mongodb: aggregate يتطلب 'collection' و 'pipeline' (list)",
            )
        batch_size = kw.get("batch_size")
        await self._ensure_connected()
        collection = self._collection(collection_name)

        def _do() -> list[dict[str, Any]]:
            kwargs: dict[str, Any] = {}
            if batch_size:
                kwargs["batchSize"] = int(batch_size)
            cursor = collection.aggregate(pipeline, **kwargs)
            return [MongoDBConnector._serialize_doc(d) for d in cursor]
        try:
            docs = await asyncio.to_thread(_do)
        except PyMongoError as exc:
            raise ConnectorError(
                f"mongodb: فشل aggregate في '{collection_name}': {exc}",
            ) from exc
        return {
            "collection": collection_name,
            "count": len(docs),
            "documents": docs,
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
            "protocol": "MongoDB Wire Protocol (pymongo)",
            "pymongo_available": _PYMONGO_AVAILABLE,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "aggregation": True,
                "text_search": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "database": self._database_name,
            "replica_set": self._replica_set,
            "tls": self._tls,
            "auth_source": self._auth_source if self._username else None,
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:mongodb:read",
            "connector:mongodb:write",
            "database:documents:read",
            "database:documents:insert",
            "database:documents:update",
            "database:documents:delete",
            "database:aggregate:execute",
        ]
