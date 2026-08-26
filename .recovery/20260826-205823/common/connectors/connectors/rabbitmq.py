"""
موصل RabbitMQ لمنصة HSAAI
============================
يتيح هذا الموصل الوصول إلى RabbitMQ لإنتاج واستهلاك الرسائل
وإدارة الطوابير (queues) والتبادلات (exchanges). يستخدم الموصل
مكتبة pika (BlockingConnection) داخل asyncio.to_thread لتفادي
حظر event loop.

الإجراءات المدعومة:
    - publish_message   : نشر رسالة إلى exchange/queue
    - consume_messages  : استهلاك رسائل من queue
    - declare_queue     : تعريف queue
    - declare_exchange  : تعريف exchange

search() للبحث في أسماء queues بنمط نصي (يستخدم RabbitMQ Management HTTP API
إن توفّر، وإلا فالبحث في queues المُعلَنة محليًا).

الاستخدام:
    cfg = ConnectorConfig(
        name="rabbitmq",
        display_name="Corporate RabbitMQ",
        category="Messaging",
        base_url="amqp://rabbitmq-host:5672",
        auth_strategy=AuthStrategy.NONE,  # أو BASIC
        secrets={
            "username": "guest",
            "password": "guest",
            "vhost": "/",  # اختياري
        },
    )
    connector = RabbitMQConnector(cfg)
    await connector.connect()
    await connector.call("publish_message", routing_key="tasks", body="hello")
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional
from urllib.parse import urlparse, quote

import httpx  # لاستخدامها في BaseConnector.connect وفي استدعاء Management HTTP API

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
#  استيراد مكتبة pika مع fallback
# ─────────────────────────────────────────────────────────────────────
try:
    import pika  # type: ignore
    _HAS_PIKA = True
except ImportError:  # pragma: no cover
    pika = None  # type: ignore[assignment]
    _HAS_PIKA = False


@connector("rabbitmq", version="1.0.0", category="Messaging")
class RabbitMQConnector(BaseConnector):
    """موصل RabbitMQ (نشر + استهلاك + إدارة queues/exchanges) عبر pika."""

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "publish_message",
        "consume_messages",
        "declare_queue",
        "declare_exchange",
    )

    #: منفذ إدارة RabbitMQ الافتراضي (HTTP API)
    DEFAULT_MANAGEMENT_PORT: int = 15672

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        # base_url قد يكون amqp://... أو host:port
        self._amqp_url: str = self.config.base_url
        self._username: str = self._get_secret("username", "guest")
        self._password: str = self._get_secret("password", "guest")
        self._vhost: str = self._get_secret("vhost", "/")
        # إدارة HTTP API اختياري (لاستعلام queues عبر REST)
        self._management_url: str = getattr(
            self.config, "management_url", self._derive_management_url(),
        )
        # اتصال pika (يُنشأ كسولًا)
        self._connection: Any = None
        self._channel: Any = None
        # قائمة بالـ queues المُعلَنة محليًا (fallback للبحث)
        self._declared_queues: set[str] = set()
        self._declared_exchanges: set[str] = set()

    def _get_secret(self, key: str, default: str = "") -> str:
        """استرجاع سر من config.secrets بأمان."""
        secret = self.config.secrets.get(key)
        if secret is None:
            return default
        try:
            return secret.get_secret_value()
        except Exception:
            return default

    def _derive_management_url(self) -> str:
        """اشتقاق عنوان Management HTTP API من AMQP URL."""
        try:
            parsed = urlparse(self._amqp_url)
            host = parsed.hostname or "localhost"
            port = self.DEFAULT_MANAGEMENT_PORT
            return f"http://{host}:{port}"
        except Exception:
            return f"http://localhost:{self.DEFAULT_MANAGEMENT_PORT}"

    def _build_connection_params(self) -> Any:
        """بناء pika.ConnectionParameters من إعدادات الموصل."""
        if not _HAS_PIKA:
            raise ConnectorError(
                "RabbitMQ: مطلوب تثبيت 'pika' لاستخدام هذا الموصل",
            )
        # إذا كان base_url عبارة عن URL amqp://، نستخدم URLParameters
        if self._amqp_url.startswith("amqp://") or self._amqp_url.startswith("amqps://"):
            # دمج credentials في URL إن لم تكن موجودة
            try:
                parsed = urlparse(self._amqp_url)
                if not parsed.username:
                    auth = f"{quote(self._username, safe='')}:{quote(self._password, safe='')}@"
                    host = parsed.hostname or "localhost"
                    port = f":{parsed.port}" if parsed.port else ""
                    path = parsed.path or f"/{quote(self._vhost, safe='')}"
                    scheme = parsed.scheme
                    full_url = f"{scheme}://{auth}{host}{port}{path}"
                    return pika.URLParameters(full_url)
                return pika.URLParameters(self._amqp_url)
            except Exception as exc:
                raise ConnectorError(
                    f"RabbitMQ: فشل تحليل AMQP URL '{self._amqp_url}': {exc}",
                ) from exc
        # خلاف ذلك: نعتبر base_url مجرد host[:port]
        host = self._amqp_url.split(":")[0]
        port_str = self._amqp_url.split(":", 1)[1] if ":" in self._amqp_url else "5672"
        try:
            port = int(port_str)
        except ValueError:
            port = 5672
        creds = pika.PlainCredentials(self._username, self._password)
        return pika.ConnectionParameters(
            host=host, port=port, virtual_host=self._vhost,
            credentials=creds,
            heartbeat=60, blocked_connection_timeout=300,
        )

    # ───────────────────────────────────────────────────────────────────
    #  Authentication
    # ───────────────────────────────────────────────────────────────────
    async def authenticate(self) -> None:
        """الاتصال بـ RabbitMQ والتحقق من بيانات الاعتماد.

        ينشئ اتصال AMQP ويفتح قناة. تعتمد المصادقة على PLAIN SASL
        (username/password) عبر بروتوكول AMQP.

        Raises:
            ConnectorAuthenticationError: عند عدم توفّر pika أو فشل الاتصال.
        """
        if not _HAS_PIKA:
            raise ConnectorAuthenticationError(
                "RabbitMQ: مطلوب تثبيت 'pika' لاستخدام هذا الموصل",
            )
        try:
            await asyncio.to_thread(self._ensure_connection)
            logger.info(
                "RabbitMQ: تم الاتصال بالخادم (vhost='%s')", self._vhost,
            )
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorAuthenticationError(
                f"RabbitMQ: فشل الاتصال: {exc}",
            ) from exc

    def _ensure_connection(self) -> Any:
        """إنشاء اتصال pika وقناة كسريًا (مزامن)."""
        if self._connection is not None and self._channel is not None:
            if self._connection.is_open and self._channel.is_open:
                return self._channel
            # إعادة الاتصال
            self._close_quietly()
        params = self._build_connection_params()
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        return self._channel

    def _close_quietly(self) -> None:
        """إغلاق الاتصال والقناة بهدوء."""
        try:
            if self._channel is not None and self._channel.is_open:
                self._channel.close()
        except Exception:
            pass
        try:
            if self._connection is not None and self._connection.is_open:
                self._connection.close()
        except Exception:
            pass
        self._channel = None
        self._connection = None

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة RabbitMQ عبر التحقق من حالة الاتصال."""
        start = time.monotonic()
        try:
            # محاولة فتح قناة جديدة للتأكد من الخدمة
            await asyncio.to_thread(self._ensure_connection)
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                status=HealthStatus.HEALTHY,
                connector=self.config.name,
                latency_ms=latency_ms,
                details={
                    "vhost": self._vhost,
                    "is_open": self._connection.is_open if self._connection else False,
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
    def _publish_sync(
        self, exchange: Optional[str], routing_key: str,
        body: bytes, properties: Optional[dict[str, Any]],
        mandatory: bool,
    ) -> dict[str, Any]:
        """نشر رسالة بشكل متزامن عبر pika."""
        channel = self._ensure_connection()
        props: Any = None
        if properties:
            props = pika.BasicProperties(**properties)
        channel.basic_publish(
            exchange=exchange or "",
            routing_key=routing_key,
            body=body,
            properties=props,
            mandatory=mandatory,
        )
        return {
            "exchange": exchange or "(default)",
            "routing_key": routing_key,
            "body_size": len(body),
        }

    def _consume_sync(
        self, queue: str, limit: int, timeout: float,
        auto_ack: bool, requeue: bool,
    ) -> list[dict[str, Any]]:
        """استهلاك رسائل بشكل متزامن من queue.

        يستخدم basic_get في حلقة لتفادي حظر consumer callback (أنسب لـ asyncio).
        """
        channel = self._ensure_connection()
        results: list[dict[str, Any]] = []
        deadline = time.monotonic() + timeout
        count = 0
        while count < limit and time.monotonic() < deadline:
            method, props, body = channel.basic_get(queue=queue, auto_ack=auto_ack)
            if method is None:
                # لا توجد رسالة جاهزة — نُريح قليلاً
                time.sleep(0.05)
                continue
            results.append({
                "delivery_tag": method.delivery_tag,
                "exchange": method.exchange,
                "routing_key": method.routing_key,
                "redelivered": method.redelivered,
                "body": body.decode("utf-8", errors="replace") if isinstance(body, (bytes, bytearray)) else str(body),
                "headers": (props.headers or {}) if props else {},
                "content_type": props.content_type if props else None,
                "message_id": props.message_id if props else None,
                "timestamp": props.timestamp if props else None,
            })
            count += 1
            if not auto_ack:
                channel.basic_ack(delivery_tag=method.delivery_tag)
        return results

    def _declare_queue_sync(
        self, queue: str, durable: bool, exclusive: bool,
        auto_delete: bool, arguments: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """تعريف queue بشكل متزامن."""
        channel = self._ensure_connection()
        result = channel.queue_declare(
            queue=queue, durable=durable, exclusive=exclusive,
            auto_delete=auto_delete, arguments=arguments or {},
        )
        self._declared_queues.add(queue)
        return {
            "queue": result.method.queue,
            "message_count": result.method.message_count,
            "consumer_count": result.method.consumer_count,
        }

    def _declare_exchange_sync(
        self, exchange: str, exchange_type: str, durable: bool,
        auto_delete: bool, arguments: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """تعريف exchange بشكل متزامن."""
        channel = self._ensure_connection()
        channel.exchange_declare(
            exchange=exchange, exchange_type=exchange_type,
            durable=durable, auto_delete=auto_delete,
            arguments=arguments or {},
        )
        self._declared_exchanges.add(exchange)
        return {
            "exchange": exchange,
            "type": exchange_type,
            "durable": durable,
            "auto_delete": auto_delete,
        }

    # ───────────────────────────────────────────────────────────────────
    #  Search (Management HTTP API)
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في أسماء queues في RabbitMQ.

        يحاول أولاً استخدام RabbitMQ Management HTTP API (/api/queues)
        إذا كان متاحًا؛ وإلا يرجع إلى قائمة الـ queues المُعلَنة محليًا
        عبر هذا الموصل.

        Args:
            query: نص البحث (substring).
            **kwargs:
                limit (int): عدد النتائج (افتراضيًا 100).
                vhost (str): تقييد البحث على vhost محدد.

        Returns:
            قائمة بالـ queues المطابقة.
        """
        limit: int = int(kwargs.pop("limit", 100))
        vhost: str = kwargs.pop("vhost", self._vhost)

        queues: list[dict[str, Any]] = []
        # محاولة استخدام Management HTTP API
        try:
            queues = await self._list_queues_via_http(vhost)
        except Exception as exc:
            logger.debug(
                "RabbitMQ: Management API غير متاح (%s) — استخدام الـ queues المحلية",
                exc,
            )
            queues = [
                {"name": q, "vhost": self._vhost, "source": "local"}
                for q in sorted(self._declared_queues)
            ]

        matched = [q for q in queues if query.lower() in str(q.get("name", "")).lower()]
        return matched[:limit]

    async def _list_queues_via_http(self, vhost: str) -> list[dict[str, Any]]:
        """جلب قائمة queues عبر RabbitMQ Management HTTP API."""
        auth = httpx.BasicAuth(self._username, self._password)
        vhost_quoted = quote(vhost, safe="")
        url = f"{self._management_url.rstrip('/')}/api/queues/{vhost_quoted}"
        async with httpx.AsyncClient(
            timeout=self.config.health_check_timeout, auth=auth,
        ) as client:
            response = await client.get(
                url, headers={"Accept": "application/json"},
            )
        if response.status_code == 401:
            raise ConnectorError("RabbitMQ Management: بيانات اعتماد غير صالحة")
        if response.status_code == 404:
            raise ConnectorError(
                f"RabbitMQ Management: vhost '{vhost}' غير موجود",
            )
        if response.status_code >= 400:
            raise ConnectorError(
                f"RabbitMQ Management: خطأ HTTP {response.status_code}: "
                f"{response.text[:200]}",
            )
        data = response.json()
        return [
            {
                "name": q.get("name"),
                "vhost": q.get("vhost"),
                "durable": q.get("durable"),
                "messages": q.get("messages", 0),
                "consumers": q.get("consumers", 0),
                "state": q.get("state"),
                "source": "management_api",
            }
            for q in data
        ]

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على RabbitMQ.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم أو فشل التنفيذ.
        """
        handlers = {
            "publish_message": self._publish_message,
            "consume_messages": self._consume_messages,
            "declare_queue": self._declare_queue,
            "declare_exchange": self._declare_exchange,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"RabbitMQ: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _publish_message(self, **kw: Any) -> dict[str, Any]:
        """نشر رسالة إلى exchange أو queue مباشرة.

        Args (via kwargs):
            routing_key (str): مفتاح التوجيه (مطلوب).
            body (str|bytes): محتوى الرسالة (مطلوب).
            exchange (str): اسم الـ exchange (افتراضيًا '' للـ default exchange).
            properties (dict): خصائص الرسالة (content_type, headers, delivery_mode, ...).
            mandatory (bool): توجيه إلزامي (افتراضيًا False).
        """
        if not _HAS_PIKA:
            raise ConnectorError("RabbitMQ: pika غير مثبت")
        routing_key = kw.get("routing_key")
        body = kw.get("body")
        if not routing_key or body is None:
            raise ConnectorError(
                "RabbitMQ: publish_message يتطلب 'routing_key' و 'body'",
            )
        if isinstance(body, str):
            body_bytes = body.encode("utf-8")
        elif isinstance(body, (bytes, bytearray)):
            body_bytes = bytes(body)
        else:
            body_bytes = str(body).encode("utf-8")
        exchange = kw.get("exchange")
        properties = kw.get("properties")
        mandatory = bool(kw.get("mandatory", False))
        try:
            result = await asyncio.to_thread(
                self._publish_sync, exchange, routing_key,
                body_bytes, properties, mandatory,
            )
        except ConnectorError:
            raise
        except Exception as exc:
            # محاولة إعادة الاتصال مرة واحدة
            logger.warning("RabbitMQ: محاولة إعادة الاتصال بعد فشل النشر: %s", exc)
            self._close_quietly()
            try:
                result = await asyncio.to_thread(
                    self._publish_sync, exchange, routing_key,
                    body_bytes, properties, mandatory,
                )
            except Exception as exc2:
                raise ConnectorError(
                    f"RabbitMQ: فشل publish_message بعد إعادة المحاولة: {exc2}",
                ) from exc2
        return {"status": "published", **result}

    async def _consume_messages(self, **kw: Any) -> dict[str, Any]:
        """استهلاك رسائل من queue.

        Args (via kwargs):
            queue (str): اسم الـ queue (مطلوب).
            limit (int): أقصى عدد رسائل للاستهلاك (افتراضيًا 100).
            timeout (float): مهلة الاستهلاك الإجمالية بالثواني (افتراضيًا 30s).
            auto_ack (bool): تأكيد تلقائي (افتراضيًا False).
        """
        if not _HAS_PIKA:
            raise ConnectorError("RabbitMQ: pika غير مثبت")
        queue = kw.get("queue")
        if not queue:
            raise ConnectorError("RabbitMQ: consume_messages يتطلب 'queue'")
        limit = int(kw.get("limit", 100))
        timeout = float(kw.get("timeout", 30.0))
        auto_ack = bool(kw.get("auto_ack", False))
        try:
            messages = await asyncio.to_thread(
                self._consume_sync, queue, limit, timeout, auto_ack, False,
            )
        except Exception as exc:
            logger.warning("RabbitMQ: محاولة إعادة الاتصال: %s", exc)
            self._close_quietly()
            try:
                messages = await asyncio.to_thread(
                    self._consume_sync, queue, limit, timeout, auto_ack, False,
                )
            except Exception as exc2:
                raise ConnectorError(
                    f"RabbitMQ: فشل consume_messages: {exc2}",
                ) from exc2
        return {
            "queue": queue,
            "count": len(messages),
            "messages": messages,
        }

    async def _declare_queue(self, **kw: Any) -> dict[str, Any]:
        """تعريف queue.

        Args (via kwargs):
            queue (str): اسم الـ queue (مطلوب؛ '' لـ queue عشوائي).
            durable (bool): قائمة على إعادة التشغيل (افتراضيًا True).
            exclusive (bool): حصري للاتصال الحالي (افتراضيًا False).
            auto_delete (bool): حذف تلقائي عند انقطاع آخر مستهلك (افتراضيًا False).
            arguments (dict): خصائص إضافية (مثل x-message-ttl).
        """
        if not _HAS_PIKA:
            raise ConnectorError("RabbitMQ: pika غير مثبت")
        queue = kw.get("queue", "")
        durable = bool(kw.get("durable", True))
        exclusive = bool(kw.get("exclusive", False))
        auto_delete = bool(kw.get("auto_delete", False))
        arguments = kw.get("arguments")
        try:
            result = await asyncio.to_thread(
                self._declare_queue_sync, queue, durable,
                exclusive, auto_delete, arguments,
            )
        except Exception as exc:
            raise ConnectorError(
                f"RabbitMQ: فشل declare_queue: {exc}",
            ) from exc
        return {"status": "declared", **result}

    async def _declare_exchange(self, **kw: Any) -> dict[str, Any]:
        """تعريف exchange.

        Args (via kwargs):
            exchange (str): اسم الـ exchange (مطلوب).
            exchange_type (str): direct/topic/fanout/headers (افتراضيًا 'direct').
            durable (bool): قائم على إعادة التشغيل (افتراضيًا True).
            auto_delete (bool): حذف تلقائي (افتراضيًا False).
            arguments (dict): خصائص إضافية.
        """
        if not _HAS_PIKA:
            raise ConnectorError("RabbitMQ: pika غير مثبت")
        exchange = kw.get("exchange")
        if not exchange:
            raise ConnectorError("RabbitMQ: declare_exchange يتطلب 'exchange'")
        exchange_type = kw.get("exchange_type", "direct")
        durable = bool(kw.get("durable", True))
        auto_delete = bool(kw.get("auto_delete", False))
        arguments = kw.get("arguments")
        try:
            result = await asyncio.to_thread(
                self._declare_exchange_sync, exchange, exchange_type,
                durable, auto_delete, arguments,
            )
        except Exception as exc:
            raise ConnectorError(
                f"RabbitMQ: فشل declare_exchange: {exc}",
            ) from exc
        return {"status": "declared", **result}

    # ───────────────────────────────────────────────────────────────────
    #  Cleanup
    # ───────────────────────────────────────────────────────────────────
    async def disconnect(self) -> None:
        """تنظيف موارد RabbitMQ."""
        if _HAS_PIKA and (self._connection is not None or self._channel is not None):
            try:
                await asyncio.to_thread(self._close_quietly)
            except Exception as exc:
                logger.warning("RabbitMQ: خطأ أثناء الإغلاق: %s", exc)
            self._channel = None
            self._connection = None
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
            "protocol": "AMQP 0-9-1 (RabbitMQ)",
            "pika_available": _HAS_PIKA,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "read": True,
                "streaming": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "vhost": self._vhost,
            "management_url": self._management_url,
            "declared_queues": sorted(self._declared_queues),
            "declared_exchanges": sorted(self._declared_exchanges),
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:rabbitmq:read",
            "connector:rabbitmq:write",
            "messaging:queue:declare",
            "messaging:queue:publish",
            "messaging:queue:consume",
            "messaging:exchange:declare",
        ]
