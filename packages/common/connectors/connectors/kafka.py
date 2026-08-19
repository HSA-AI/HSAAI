"""
موصل Apache Kafka لمنصة HSAAI
================================
يتيح هذا الموصل الوصول إلى Apache Kafka لإنتاج واستهلاك الرسائل
وإدارة المواضيع (topics). يستخدم الموصل مكتبة kafka-python كأولوية
ثم يتراجع إلى confluent-kafka عند عدم توفرها.

يستخدم الموصل asyncio.to_thread لتغليف الاستدعاءات المتزامنة
(لأن مكتبات Kafka Python متزامنة بطبيعتها) دون حظر event loop.

الإجراءات المدعومة:
    - produce_message  : إرسال رسالة إلى topic
    - consume_messages : استهلاك رسائل من topic
    - list_topics      : سرد المواضيع في الكلاستر
    - create_topic     : إنشاء topic جديد

search() للبحث في أسماء topics بنمط نصي.

الاستخدام:
    cfg = ConnectorConfig(
        name="kafka",
        display_name="Corporate Kafka Cluster",
        category="Messaging",
        base_url="kafka-broker1:9092,kafka-broker2:9092",
        auth_strategy=AuthStrategy.NONE,  # أو BASIC/SASL
        secrets={
            "sasl_username": "...",  # اختياري
            "sasl_password": "...",  # اختياري
        },
    )
    connector = KafkaConnector(cfg)
    await connector.connect()
    await connector.call("produce_message", topic="events", value=b"hello")
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import httpx  # لاستخدامها في BaseConnector.connect (حتى لو لم تُستخدم فعليًا)

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
#  استيراد مكتبة Kafka مع التراجع بين kafka-python و confluent-kafka
# ─────────────────────────────────────────────────────────────────────
_BACKEND: str = "none"
try:
    from kafka import KafkaProducer, KafkaConsumer, KafkaAdminClient  # type: ignore
    from kafka.admin import NewTopic as _KPNewTopic  # type: ignore
    from kafka.errors import KafkaError as _KPKafkaError  # type: ignore
    _BACKEND = "kafka-python"
except ImportError:  # pragma: no cover
    try:
        from confluent_kafka import (  # type: ignore
            Producer as _CFProducer,
            Consumer as _CFConsumer,
            KafkaException as _CFKafkaException,
        )
        from confluent_kafka.admin import (  # type: ignore
            AdminClient as _CFAdminClient,
            NewTopic as _CFNewTopic,
        )
        _BACKEND = "confluent-kafka"
    except ImportError:
        _BACKEND = "none"


@connector("kafka", version="1.0.0", category="Messaging")
class KafkaConnector(BaseConnector):
    """موصل Apache Kafka (إنتاج + استهلاك + إدارة topics)."""

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "produce_message",
        "consume_messages",
        "list_topics",
        "create_topic",
    )

    #: مهلة افتراضية لعمليات Kafka (بالثواني)
    DEFAULT_KAFKA_TIMEOUT: float = 10.0

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        # base_url يُستخدم لـ bootstrap_servers (يمكن أن يكون قائمة مفصولة بفواصل)
        self._bootstrap_servers: str = self.config.base_url
        self._sasl_username: str = self._get_secret("sasl_username", "")
        self._sasl_password: str = self._get_secret("sasl_password", "")
        self._sasl_mechanism: str = getattr(self.config, "sasl_mechanism", "PLAIN")
        self._security_protocol: str = getattr(
            self.config, "security_protocol", "PLAINTEXT",
        )
        # عملاء يتم إنشاؤهم كسولًا
        self._producer: Any = None
        self._admin: Any = None

    def _get_secret(self, key: str, default: str = "") -> str:
        """استرجاع سر من config.secrets بأمان."""
        secret = self.config.secrets.get(key)
        if secret is None:
            return default
        try:
            return secret.get_secret_value()
        except Exception:
            return default

    def _build_config(self) -> dict[str, Any]:
        """بناء قاموس إعداد Kafka الموحَّد للاستخدام مع المكتبتين."""
        cfg: dict[str, Any] = {
            "bootstrap_servers": self._bootstrap_servers,
            "client_id": f"hsaai-{self.config.name}",
        }
        if self._sasl_username and self._sasl_password:
            cfg["security_protocol"] = self._security_protocol
            cfg["sasl_mechanism"] = self._sasl_mechanism
            cfg["sasl_plain_username"] = self._sasl_username
            cfg["sasl_plain_password"] = self._sasl_password
        # SSL اختياري
        if getattr(self.config, "ssl_ca_location", None):
            cfg["ssl_ca_location"] = self.config.ssl_ca_location
        return cfg

    def _build_kp_config(self) -> dict[str, Any]:
        """تحويل الإعداد لصيغة kafka-python."""
        cfg = self._build_config()
        # kafka-python يستخدم api_version_auto_timeout_ms بدلاً من timeout بسيط
        cfg["api_version_auto_timeout_ms"] = int(self.DEFAULT_KAFKA_TIMEOUT * 1000)
        return cfg

    def _build_cf_config(self) -> dict[str, Any]:
        """تحويل الإعداد لصيغة confluent-kafka (قاموس مسطح)."""
        cfg = self._build_config()
        # confluent-kafka يستخدم bootstrap.servers (بنقطة) و key/value مسطحة
        cfg["bootstrap.servers"] = cfg.pop("bootstrap_servers")
        cfg["client.id"] = cfg.pop("client_id")
        if "sasl_plain_username" in cfg:
            cfg["sasl.username"] = cfg.pop("sasl_plain_username")
            cfg["sasl.password"] = cfg.pop("sasl_plain_password")
            cfg["sasl.mechanism"] = cfg.pop("sasl_mechanism")
            cfg["security.protocol"] = cfg.pop("security_protocol")
        return cfg

    # ───────────────────────────────────────────────────────────────────
    #  Authentication
    # ───────────────────────────────────────────────────────────────────
    async def authenticate(self) -> None:
        """التحقق من الاتصال بـ Kafka والمصادقة (SASL اختياري).

        ينشئ AdminClient وينفّذ list_topics للتحقق من الوصول. لا يوجد
        تبادل توكنات في Kafka — المصادقة تتم عبر SASL/SSL على مستوى الاتصال.

        Raises:
            ConnectorAuthenticationError: عند عدم توفّر مكتبة Kafka أو فشل الاتصال.
        """
        if _BACKEND == "none":
            raise ConnectorAuthenticationError(
                "Kafka: مطلوب تثبيت 'kafka-python' أو 'confluent-kafka' لاستخدام هذا الموصل",
            )
        try:
            # إنشاء AdminClient في thread منفصل (قد يحجب event loop)
            await asyncio.to_thread(self._ensure_admin)
            # التحقق من الاتصال عبر list_topics
            topics = await asyncio.to_thread(self._list_topics_sync, self.DEFAULT_KAFKA_TIMEOUT)
            logger.info(
                "Kafka: تم الاتصال بالكلاستر عبر %s (topics متاحة: %d)",
                _BACKEND, len(topics),
            )
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorAuthenticationError(
                f"Kafka: فشل الاتصال بالكلاستر: {exc}",
            ) from exc

    def _ensure_admin(self) -> Any:
        """إنشاء AdminClient كسولًا (مزامن)."""
        if self._admin is not None:
            return self._admin
        if _BACKEND == "kafka-python":
            self._admin = KafkaAdminClient(**self._build_kp_config())
        elif _BACKEND == "confluent-kafka":
            self._admin = _CFAdminClient(self._build_cf_config())  # type: ignore[call-arg]
        else:
            raise ConnectorError("Kafka: لا توجد مكتبة Kafka متاحة")
        return self._admin

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة كلاستر Kafka عبر list_topics بمهلة قصيرة."""
        start = time.monotonic()
        try:
            topics = await asyncio.to_thread(
                self._list_topics_sync, self.config.health_check_timeout,
            )
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                status=HealthStatus.HEALTHY,
                connector=self.config.name,
                latency_ms=latency_ms,
                details={
                    "backend": _BACKEND,
                    "topics_count": len(topics),
                    "bootstrap": self._bootstrap_servers,
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
    #  Sync Helpers (تُغلَّف بـ asyncio.to_thread)
    # ───────────────────────────────────────────────────────────────────
    def _list_topics_sync(self, timeout: float) -> list[str]:
        """سرد أسماء topics بشكل متزامن."""
        admin = self._ensure_admin()
        if _BACKEND == "kafka-python":
            # KafkaAdminClient لا يكشف list_topics مباشرة؛ نستخدم consumer داخلي
            consumer = KafkaConsumer(bootstrap_servers=self._bootstrap_servers,
                                     request_timeout_ms=int(timeout * 1000),
                                     api_version_auto_timeout_ms=int(timeout * 1000))
            try:
                topics = list(consumer.topics())
            finally:
                consumer.close()
            return sorted(topics)
        # confluent-kafka
        cluster_meta = admin.list_topics(timeout=timeout)
        return sorted(cluster_meta.topics.keys())

    def _produce_sync(
        self, topic: str, value: bytes, key: Optional[bytes],
        headers: Optional[list[tuple[str, bytes]]], timeout: float,
    ) -> dict[str, Any]:
        """إنتاج رسالة بشكل متزامن عبر المكتبتين."""
        if _BACKEND == "kafka-python":
            if self._producer is None:
                self._producer = KafkaProducer(**self._build_kp_config())
            future = self._producer.send(topic, value=value, key=key, headers=headers)
            meta = future.get(timeout=timeout)
            return {
                "topic": meta.topic,
                "partition": meta.partition,
                "offset": meta.offset,
            }

        # confluent-kafka
        if self._producer is None:
            self._producer = _CFProducer(self._build_cf_config())  # type: ignore[call-arg]
        result: dict[str, Any] = {"topic": topic, "partition": -1, "offset": -1}
        error_holder: list[Any] = []

        def _on_delivery(err: Any, msg: Any) -> None:
            if err is not None:
                error_holder.append(err)
            else:
                result["topic"] = msg.topic()
                result["partition"] = msg.partition()
                result["offset"] = msg.offset()

        cf_headers = [(k, v) for k, v in (headers or [])]
        self._producer.produce(
            topic, value=value, key=key, headers=cf_headers or None,
            callback=_on_delivery,
        )
        self._producer.flush(timeout=timeout)
        if error_holder:
            raise ConnectorError(f"Kafka: فشل إنتاج الرسالة: {error_holder[0]}")
        return result

    def _consume_sync(
        self, topic: str, group_id: str, limit: int,
        timeout: float, auto_offset_reset: str,
    ) -> list[dict[str, Any]]:
        """استهلاك رسائل بشكل متزامن عبر المكتبتين."""
        results: list[dict[str, Any]] = []
        if _BACKEND == "kafka-python":
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=self._bootstrap_servers,
                group_id=group_id,
                auto_offset_reset=auto_offset_reset,
                enable_auto_commit=False,
                consumer_timeout_ms=int(timeout * 1000),
                **{k: v for k, v in self._build_kp_config().items()
                   if k not in ("bootstrap_servers",)},
            )
            try:
                count = 0
                for msg in consumer:
                    results.append({
                        "topic": msg.topic,
                        "partition": msg.partition,
                        "offset": msg.offset,
                        "key": msg.key.decode("utf-8", errors="replace") if msg.key else None,
                        "value": msg.value.decode("utf-8", errors="replace") if isinstance(msg.value, (bytes, bytearray)) else msg.value,
                        "headers": [(k, v.decode("utf-8", errors="replace")) for k, v in (msg.headers or [])],
                        "timestamp": msg.timestamp,
                    })
                    count += 1
                    if count >= limit:
                        break
            finally:
                consumer.close()
            return results

        # confluent-kafka
        cfg = self._build_cf_config()
        cfg["group.id"] = group_id
        cfg["auto.offset.reset"] = auto_offset_reset
        cfg["enable.auto.commit"] = False
        consumer = _CFConsumer(cfg)  # type: ignore[call-arg]
        try:
            consumer.subscribe([topic])
            deadline = time.monotonic() + timeout
            count = 0
            while count < limit and time.monotonic() < deadline:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    # أخطاء مثل EOF للـ partition تتجاهلها بأمان
                    continue
                results.append({
                    "topic": msg.topic(),
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                    "key": msg.key().decode("utf-8", errors="replace") if msg.key() else None,
                    "value": msg.value().decode("utf-8", errors="replace") if isinstance(msg.value(), (bytes, bytearray)) else msg.value(),
                    "timestamp": msg.timestamp()[1] if msg.timestamp() else None,
                })
                count += 1
        finally:
            consumer.close()
        return results

    def _create_topic_sync(
        self, topic: str, num_partitions: int, replication_factor: int,
        timeout: float, config: Optional[dict[str, str]],
    ) -> dict[str, Any]:
        """إنشاء topic بشكل متزامن عبر المكتبتين."""
        admin = self._ensure_admin()
        if _BACKEND == "kafka-python":
            new_topic = _KPNewTopic(  # type: ignore[call-arg]
                name=topic,
                num_partitions=num_partitions,
                replication_factor=replication_factor,
                topic_configs=config or {},
            )
            admin.create_topics([new_topic], timeout_ms=int(timeout * 1000), validate_only=False)
            return {"topic": topic, "partitions": num_partitions, "replication_factor": replication_factor}

        # confluent-kafka
        new_topic = _CFNewTopic(  # type: ignore[call-arg]
            topic=topic,
            num_partitions=num_partitions,
            replication_factor=replication_factor,
            config=config or {},
        )
        fs = admin.create_topics([new_topic])
        for topic_name, future in fs.items():
            future.result(timeout=timeout)  # يطرح KafkaException عند الفشل
        return {"topic": topic, "partitions": num_partitions, "replication_factor": replication_factor}

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في أسماء topics بنمط نصي (substring match).

        Args:
            query: نص البحث (substring).
            **kwargs:
                limit (int): عدد النتائج (افتراضيًا 100).
                timeout (float): مهلة list_topics (افتراضيًا health_check_timeout).

        Returns:
            قائمة بأسماء topics المطابقة.
        """
        limit: int = int(kwargs.pop("limit", 100))
        timeout: float = float(kwargs.pop("timeout", self.config.health_check_timeout))
        try:
            topics = await asyncio.to_thread(self._list_topics_sync, timeout)
        except Exception as exc:
            raise ConnectorError(f"Kafka: فشل list_topics: {exc}") from exc
        matched = [t for t in topics if query.lower() in t.lower()]
        return [
            {"topic": t, "matches": query}
            for t in matched[:limit]
        ]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على Kafka.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم أو فشل التنفيذ.
        """
        handlers = {
            "produce_message": self._produce_message,
            "consume_messages": self._consume_messages,
            "list_topics": self._list_topics_action,
            "create_topic": self._create_topic,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"Kafka: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _produce_message(self, **kw: Any) -> dict[str, Any]:
        """إرسال رسالة إلى topic.

        Args (via kwargs):
            topic (str): اسم الـ topic (مطلوب).
            value (str|bytes): محتوى الرسالة (مطلوب).
            key (str|bytes): مفتاح الرسالة (اختياري).
            headers (list[tuple[str,str]]): ترويسات الرسالة.
            timeout (float): مهلة الإنتاج (افتراضيًا 10s).
        """
        if _BACKEND == "none":
            raise ConnectorError("Kafka: لا توجد مكتبة Kafka متاحة")
        topic = kw.get("topic")
        value = kw.get("value")
        if not topic or value is None:
            raise ConnectorError(
                "Kafka: produce_message يتطلب 'topic' و 'value'",
            )
        # تطبيع القيمة إلى bytes
        if isinstance(value, str):
            value_bytes = value.encode("utf-8")
        elif isinstance(value, (bytes, bytearray)):
            value_bytes = bytes(value)
        else:
            value_bytes = str(value).encode("utf-8")
        key = kw.get("key")
        key_bytes: Optional[bytes] = None
        if key is not None:
            key_bytes = key.encode("utf-8") if isinstance(key, str) else bytes(key)
        headers_raw = kw.get("headers")
        headers: Optional[list[tuple[str, bytes]]] = None
        if headers_raw:
            headers = [
                (k, v.encode("utf-8") if isinstance(v, str) else bytes(v))
                for k, v in headers_raw
            ]
        timeout = float(kw.get("timeout", self.DEFAULT_KAFKA_TIMEOUT))
        try:
            result = await asyncio.to_thread(
                self._produce_sync, topic, value_bytes, key_bytes, headers, timeout,
            )
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(f"Kafka: فشل produce_message: {exc}") from exc
        return {"status": "produced", **result}

    async def _consume_messages(self, **kw: Any) -> dict[str, Any]:
        """استهلاك رسائل من topic.

        Args (via kwargs):
            topic (str): اسم الـ topic (مطلوب).
            group_id (str): معرف مجموعة المستهلكين (مطلوب).
            limit (int): أقصى عدد رسائل للاستهلاك (افتراضيًا 100).
            timeout (float): مهلة الاستهلاك الإجمالية (افتراضيًا 30s).
            auto_offset_reset (str): 'earliest' أو 'latest' (افتراضيًا 'earliest').
        """
        if _BACKEND == "none":
            raise ConnectorError("Kafka: لا توجد مكتبة Kafka متاحة")
        topic = kw.get("topic")
        group_id = kw.get("group_id")
        if not topic or not group_id:
            raise ConnectorError(
                "Kafka: consume_messages يتطلب 'topic' و 'group_id'",
            )
        limit = int(kw.get("limit", 100))
        timeout = float(kw.get("timeout", 30.0))
        auto_offset_reset = kw.get("auto_offset_reset", "earliest")
        try:
            messages = await asyncio.to_thread(
                self._consume_sync, topic, group_id, limit,
                timeout, auto_offset_reset,
            )
        except Exception as exc:
            raise ConnectorError(f"Kafka: فشل consume_messages: {exc}") from exc
        return {
            "topic": topic,
            "group_id": group_id,
            "count": len(messages),
            "messages": messages,
        }

    async def _list_topics_action(self, **kw: Any) -> dict[str, Any]:
        """سرد المواضيع في الكلاستر.

        Args (via kwargs):
            timeout (float): مهلة list_topics (افتراضيًا health_check_timeout).
        """
        if _BACKEND == "none":
            raise ConnectorError("Kafka: لا توجد مكتبة Kafka متاحة")
        timeout = float(kw.get("timeout", self.config.health_check_timeout))
        try:
            topics = await asyncio.to_thread(self._list_topics_sync, timeout)
        except Exception as exc:
            raise ConnectorError(f"Kafka: فشل list_topics: {exc}") from exc
        return {"count": len(topics), "topics": topics}

    async def _create_topic(self, **kw: Any) -> dict[str, Any]:
        """إنشاء topic جديد.

        Args (via kwargs):
            topic (str): اسم الـ topic (مطلوب).
            partitions (int): عدد الأقسام (افتراضيًا 1).
            replication_factor (int): عامل النسخ (افتراضيًا 1).
            config (dict): إعدادات topic إضافية (مثل retention.ms).
            timeout (float): مهلة الإنشاء (افتراضيًا 10s).
        """
        if _BACKEND == "none":
            raise ConnectorError("Kafka: لا توجد مكتبة Kafka متاحة")
        topic = kw.get("topic")
        if not topic:
            raise ConnectorError("Kafka: create_topic يتطلب 'topic'")
        partitions = int(kw.get("partitions", 1))
        replication_factor = int(kw.get("replication_factor", 1))
        config = kw.get("config")
        timeout = float(kw.get("timeout", self.DEFAULT_KAFKA_TIMEOUT))
        try:
            result = await asyncio.to_thread(
                self._create_topic_sync, topic, partitions,
                replication_factor, timeout, config,
            )
        except ConnectorError:
            raise
        except Exception as exc:
            # أخطاء "topic already exists" تُعامل كنجاح جزئي
            err_str = str(exc)
            if "already" in err_str.lower() or "exists" in err_str.lower():
                return {
                    "status": "already_exists",
                    "topic": topic,
                    "partitions": partitions,
                }
            raise ConnectorError(f"Kafka: فشل create_topic: {exc}") from exc
        return {"status": "created", **result}

    # ───────────────────────────────────────────────────────────────────
    #  Cleanup
    # ───────────────────────────────────────────────────────────────────
    async def disconnect(self) -> None:
        """تنظيف موارد Kafka (producer + admin)."""
        # إغلاق عملاء Kafka في thread منفصل لأنه قد يحجب
        if self._producer is not None:
            try:
                if _BACKEND == "kafka-python":
                    await asyncio.to_thread(self._producer.close, 5)
                elif _BACKEND == "confluent-kafka":
                    await asyncio.to_thread(self._producer.flush, 5)
            except Exception as exc:
                logger.warning("Kafka: خطأ أثناء إغلاق المنتج: %s", exc)
            self._producer = None
        if self._admin is not None:
            try:
                if _BACKEND == "kafka-python":
                    await asyncio.to_thread(self._admin.close)
            except Exception as exc:
                logger.warning("Kafka: خطأ أثناء إغلاق admin: %s", exc)
            self._admin = None
        await super().disconnect()

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
            "protocol": "Apache Kafka Wire Protocol",
            "backend": _BACKEND,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "read": True,
                "streaming": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "bootstrap_servers": self._bootstrap_servers,
            "sasl_enabled": bool(self._sasl_username),
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:kafka:read",
            "connector:kafka:write",
            "messaging:topic:read",
            "messaging:topic:write",
            "messaging:topic:create",
        ]
