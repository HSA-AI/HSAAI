"""
HSAAI Connector Framework — Tests
==================================
اختبارات شاملة لإطار الموصلات المؤسسي HSAAI.

تغطي الاختبارات:
  - BaseConnector (دورة الحياة، call()، الصلاحيات)
  - CircuitBreaker (CLOSED → OPEN → HALF_OPEN → CLOSED)
  - RateLimiter (token bucket: burst + refuel)
  - ResponseCache (set/get/expire)
  - RetryPolicy (exponential backoff with jitter)
  - AuditLogger (HMAC signature verification)
  - ConnectorRegistry (register_class, create, health_all)
  - Connector call() مع retry/circuit-breaker/cache/rate-limit
  - GenericRESTConnector (from sdk.py)
  - scaffold_connector (from sdk.py)
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from typing import Any, Optional

import httpx
import pytest

from packages.common.connectors import (
    AuthStrategy,
    BaseConnector,
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
    ConnectorAuthenticationError,
    ConnectorConfig,
    ConnectorError,
    ConnectorRegistry,
    HealthResult,
    HealthStatus,
    RateLimitExceededError,
    RateLimiter,
    ResponseCache,
    RetryPolicy,
    AuditLogger,
    connector,
)


# ═══════════════════════════════════════════════════════════════════════════
#  Test Connectors
# ═══════════════════════════════════════════════════════════════════════════
@connector("dummy", version="1.0.0", category="test")
class DummyConnector(BaseConnector):
    """موصل اختبار بسيط — يُرجع بيانات ثابتة دون اتصال شبكي فعلي."""

    async def authenticate(self) -> None:
        pass

    async def health(self) -> HealthResult:
        return HealthResult(
            status=HealthStatus.HEALTHY,
            connector="dummy",
            latency_ms=1.0,
        )

    async def search(self, query: str, **kwargs: Any) -> list[dict]:
        return [{"id": 1, "query": query}]

    async def execute(self, action: str, **kwargs: Any) -> dict:
        return {"action": action, "received": kwargs}

    def metadata(self) -> dict:
        return {"name": "dummy"}

    def permissions(self) -> list[str]:
        return ["connector:dummy:use"]


class FailingConnector(BaseConnector):
    """موصل اختبار يحاكي الفشل لـ N محاولات ثم النجاح.

    يُستخدم لاختبار آلية retry و circuit breaker.
    """

    def __init__(self, config: ConnectorConfig, fail_until: int = 0) -> None:
        super().__init__(config)
        self._call_count: int = 0
        self._fail_until: int = fail_until

    async def authenticate(self) -> None:
        pass

    async def health(self) -> HealthResult:
        return HealthResult(
            status=HealthStatus.HEALTHY,
            connector=self.config.name,
            latency_ms=1.0,
        )

    async def search(self, query: str, **kwargs: Any) -> list[dict]:
        return []

    async def execute(self, action: str, **kwargs: Any) -> dict:
        self._call_count += 1
        if self._call_count <= self._fail_until:
            raise ConnectorError(
                f"محاكاة فشل #{self._call_count} للإجراء '{action}'",
            )
        return {"action": action, "attempt": self._call_count}

    def metadata(self) -> dict:
        return {"name": self.config.name}

    def permissions(self) -> list[str]:
        return []


class CountingConnector(BaseConnector):
    """موصل اختبار يعدّ عدد استدعاءات execute() — لاختبار الـ cache."""

    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self.execute_count: int = 0

    async def authenticate(self) -> None:
        pass

    async def health(self) -> HealthResult:
        return HealthResult(
            status=HealthStatus.HEALTHY,
            connector=self.config.name,
            latency_ms=1.0,
        )

    async def search(self, query: str, **kwargs: Any) -> list[dict]:
        return []

    async def execute(self, action: str, **kwargs: Any) -> dict:
        self.execute_count += 1
        return {"action": action, "call_number": self.execute_count}

    def metadata(self) -> dict:
        return {"name": self.config.name}

    def permissions(self) -> list[str]:
        return []


class RestrictedConnector(BaseConnector):
    """موصل اختبار يرفض المستخدمين غير المصرّح لهم — لاختبار الصلاحيات."""

    async def authenticate(self) -> None:
        pass

    async def health(self) -> HealthResult:
        return HealthResult(
            status=HealthStatus.HEALTHY,
            connector=self.config.name,
            latency_ms=1.0,
        )

    async def search(self, query: str, **kwargs: Any) -> list[dict]:
        return []

    async def execute(self, action: str, **kwargs: Any) -> dict:
        return {"action": action}

    def metadata(self) -> dict:
        return {"name": self.config.name}

    def permissions(self) -> list[str]:
        return ["connector:restricted:use"]

    def _check_permissions(self, user: str) -> bool:
        """فقط 'admin' له صلاحية استخدام هذا الموصل."""
        return user == "admin"


# ═══════════════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def clean_registry():
    """تنظيف الـ registry قبل وبعد كل اختبار لضمان العزل."""
    ConnectorRegistry.clear()
    yield
    ConnectorRegistry.clear()


def _make_config(
    name: str = "test_connector",
    **overrides: Any,
) -> ConnectorConfig:
    """إنشاء ConnectorConfig بالحدود الدنيا للاختبارات."""
    defaults: dict[str, Any] = dict(
        name=name,
        display_name=f"Test {name}",
        category="test",
        base_url="https://test.example.com",
        auth_strategy=AuthStrategy.NONE,
        cache_enabled=True,
        cache_ttl_seconds=300,
        max_retries=3,
        retry_backoff_factor=2.0,
        retry_max_delay=60.0,
        cb_failure_threshold=5,
        cb_recovery_timeout=60.0,
        cb_half_open_max_calls=3,
        rate_limit_qps=100.0,
        rate_limit_burst=100,
    )
    defaults.update(overrides)
    return ConnectorConfig(**defaults)


# ═══════════════════════════════════════════════════════════════════════════
#  1. CircuitBreaker States
# ═══════════════════════════════════════════════════════════════════════════
class TestCircuitBreaker:
    """اختبارات قاطع الدائرة (CircuitBreaker)."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_states(self):
        """اختبار CLOSED → OPEN → HALF_OPEN → CLOSED."""
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=0.15,
            half_open_max_calls=1,
        )

        # 1. الحالة الابتدائية: CLOSED
        assert cb.state == CircuitBreakerState.CLOSED

        # 2. ثلاث فشلات متتالية → OPEN
        for i in range(3):
            with pytest.raises(ValueError, match="fail"):
                await cb.call(self._failing_coro)

        assert cb.state == CircuitBreakerState.OPEN

        # 3. محاولة استدعاء أثناء OPEN → CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(self._failing_coro)

        # 4. انتظار recovery_timeout ثم استدعاء ناجح → HALF_OPEN ثم CLOSED
        await asyncio.sleep(0.2)

        # ملاحظة: HALF_OPEN حالة عابرة تُلاحَظ داخل coro قبل النجاح
        observed_states: list[CircuitBreakerState] = []

        async def observe_and_succeed():
            observed_states.append(cb.state)
            return "success"

        result = await cb.call(observe_and_succeed)

        # 5. بعد النجاح: CLOSED
        assert result == "success"
        assert CircuitBreakerState.HALF_OPEN in observed_states
        assert cb.state == CircuitBreakerState.CLOSED

    @staticmethod
    async def _failing_coro():
        raise ValueError("intentional fail")


# ═══════════════════════════════════════════════════════════════════════════
#  2. RateLimiter Token Bucket
# ═══════════════════════════════════════════════════════════════════════════
class TestRateLimiter:
    """اختبارات محدد المعدل (RateLimiter)."""

    @pytest.mark.asyncio
    async def test_rate_limiter_token_bucket(self):
        """اختبار burst ثم refuel: استهلاك الرشقة ثم انتظار التعبئة."""
        limiter = RateLimiter(qps=10.0, burst=3)

        # استهلاك الرشقة الكاملة (3 tokens)
        results_burst: list[bool] = []
        for _ in range(3):
            results_burst.append(await limiter.acquire())

        assert results_burst == [True, True, True]

        # الاستدعاء الرابع يجب أن يُرفض (لا توجد tokens)
        rejected = await limiter.acquire()
        assert rejected is False

        # انتظار التعبئة: 0.2s × 10 qps = 2 tokens
        await asyncio.sleep(0.25)

        # بعد التعبئة: يجب أن ينجح الاستدعاء
        refueled = await limiter.acquire()
        assert refueled is True


# ═══════════════════════════════════════════════════════════════════════════
#  3. ResponseCache TTL
# ═══════════════════════════════════════════════════════════════════════════
class TestResponseCache:
    """اختبارات ذاكرة التخزين المؤقت (ResponseCache)."""

    def test_response_cache_ttl(self):
        """اختبار set/get/expire مع TTL قصير."""
        # استخدام default_ttl كسري عشري (ثواني) لاختبار سريع لانتهاء الصلاحية
        cache = ResponseCache(max_entries=100, default_ttl=0.05)

        # set + get فوري
        cache.set("key1", {"value": 42})
        assert cache.get("key1") == {"value": 42}

        # cache miss لمفتاح غير موجود
        assert cache.get("nonexistent") is None
        assert cache.misses >= 1

        # انتهاء الصلاحية بعد TTL
        time.sleep(0.1)
        assert cache.get("key1") is None  # منتهي الصلاحية

        # التحقق من عدّاد hits
        cache.set("key3", "data")
        cache.get("key3")
        assert cache.hits >= 2  # key1 + key3

    def test_response_cache_invalidate(self):
        """اختبار إبطال ذاكرة التخزين المؤقت."""
        cache = ResponseCache(max_entries=100, default_ttl=300)
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.get("a") == 1

        cache.invalidate("a")
        assert cache.get("a") is None
        assert cache.get("b") == 2

        cache.clear()
        assert cache.get("b") is None


# ═══════════════════════════════════════════════════════════════════════════
#  4. RetryPolicy Delay
# ═══════════════════════════════════════════════════════════════════════════
class TestRetryPolicy:
    """اختبارات سياسة إعادة المحاولة (RetryPolicy)."""

    def test_retry_policy_delay(self):
        """اختبار exponential backoff: التأخير ينمو مع كل محاولة."""
        policy = RetryPolicy(
            max_retries=5,
            backoff_factor=2.0,
            max_delay=60.0,
        )

        delays = [policy.delay(attempt) for attempt in range(5)]

        # base = min(max_delay, backoff_factor ** attempt)
        # delay = base * (0.5 + random * 0.5)  → بين 0.5*base و base
        # attempt 0: base=1.0, delay في [0.5, 1.0]
        # attempt 1: base=2.0, delay في [1.0, 2.0]
        # attempt 2: base=4.0, delay في [2.0, 4.0]
        # attempt 3: base=8.0, delay في [4.0, 8.0]
        # attempt 4: base=16.0, delay في [8.0, 16.0]

        # التحقق من النمو الأسي (مع jitter، نتحقق من الحدود الدنيا)
        for i in range(4):
            # الحد الأدنى للمحاولة i+1 يجب أن يكون ≥ الحد الأدنى للمحاولة i
            # (مع jitter قد يتقاطعان قليلاً، لكن النزعة العامة نمو)
            assert delays[i + 1] >= delays[i] * 0.4  # سماح للـ jitter

        # التحقق من أن التأخير لا يتجاوز max_delay
        big_policy = RetryPolicy(
            max_retries=10,
            backoff_factor=10.0,
            max_delay=5.0,
        )
        for attempt in range(10):
            assert big_policy.delay(attempt) <= 5.0

    def test_retry_policy_retry_on_status(self):
        """اختبار أن سياسة الإعادة تتعرف على أكواد الحالة الصحيحة."""
        policy = RetryPolicy(retry_on_status=[429, 500, 503])
        assert 429 in policy.retry_on_status
        assert 200 not in policy.retry_on_status
        assert 404 not in policy.retry_on_status


# ═══════════════════════════════════════════════════════════════════════════
#  5. AuditLogger HMAC
# ═══════════════════════════════════════════════════════════════════════════
class TestAuditLogger:
    """اختبارات مسجل التدقيق (AuditLogger) مع التحقق من HMAC."""

    def test_audit_logger_hmac(self):
        """اختبار أن الـ HMAC signature صحيحة وقابلة للتحقق."""
        hmac_key = "test-hmac-secret-key-for-testing"
        entries: list[dict] = []

        audit = AuditLogger(hmac_key=hmac_key, sink=entries.append)

        audit.log_call(
            connector="test_connector",
            action="get_data",
            user="test_user",
            params={"filter": "active", "limit": 10},
            result={"items": [1, 2, 3]},
            error=None,
            duration_ms=42.5,
        )

        assert len(entries) == 1
        entry = entries[0]

        # التحقق من وجود الحقول الإلزامية
        required_fields = {
            "timestamp", "connector", "action", "user", "params_hash",
            "success", "error", "duration_ms", "correlation_id", "signature",
        }
        assert required_fields.issubset(entry.keys())

        # التحقق من صحة HMAC
        stored_signature = entry["signature"]
        entry_without_sig = {k: v for k, v in entry.items() if k != "signature"}

        payload = json.dumps(entry_without_sig, sort_keys=True).encode("utf-8")
        expected_signature = hmac.new(
            hmac_key.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

        assert stored_signature == expected_signature

        # التحقق من أن التلاعب بالإدخال يكسر التوقيع
        tampered = dict(entry_without_sig)
        tampered["action"] = "delete_data"
        tampered_payload = json.dumps(tampered, sort_keys=True).encode("utf-8")
        tampered_sig = hmac.new(
            hmac_key.encode("utf-8"),
            tampered_payload,
            hashlib.sha256,
        ).hexdigest()
        assert tampered_sig != stored_signature

    def test_audit_logger_error_entry(self):
        """اختبار تسجيل الإدخالات الفاشلة."""
        entries: list[dict] = []
        audit = AuditLogger(hmac_key="key", sink=entries.append)

        audit.log_call(
            connector="conn",
            action="fail_action",
            error="Connection timeout",
            duration_ms=5000.0,
        )

        entry = entries[0]
        assert entry["success"] is False
        assert entry["error"] == "Connection timeout"
        assert "signature" in entry


# ═══════════════════════════════════════════════════════════════════════════
#  6-8. ConnectorRegistry
# ═══════════════════════════════════════════════════════════════════════════
class TestConnectorRegistry:
    """اختبارات سجل الموصلات (ConnectorRegistry)."""

    def test_registry_register_class(self):
        """اختبار تسجيل class في الـ registry."""
        ConnectorRegistry.clear()

        ConnectorRegistry.register_class(
            "my_test_conn",
            DummyConnector,
            version="2.0.0",
            category="TestCategory",
        )

        classes = ConnectorRegistry.list_classes()
        names = [c["name"] for c in classes]
        assert "my_test_conn" in names

        cls_info = ConnectorRegistry.get_class("my_test_conn")
        assert cls_info is not None
        registered_cls, version, category = cls_info
        assert registered_cls is DummyConnector
        assert version == "2.0.0"
        assert category == "TestCategory"

    @pytest.mark.asyncio
    async def test_registry_create_instance(self):
        """اختبار إنشاء instance من class مسجّل."""
        ConnectorRegistry.clear()
        ConnectorRegistry.register_class(
            "dummy_create_test",
            DummyConnector,
            version="1.0.0",
            category="test",
        )

        config = _make_config(name="dummy_create_test")
        instance = ConnectorRegistry.create("dummy_create_test", config)

        assert isinstance(instance, DummyConnector)
        assert instance.config.name == "dummy_create_test"
        assert instance.get_state().value == "uninitialized"

        # التحقق من أن execute يعمل
        result = await instance.execute("ping", value=42)
        assert result == {"action": "ping", "received": {"value": 42}}

    def test_registry_health_all(self):
        """اختبار aggregate health لجميع الموصلات."""
        ConnectorRegistry.clear()

        # إنشاء موصلين بحالات صحية مختلفة
        config1 = _make_config(name="healthy_conn")
        conn1 = DummyConnector(config1)
        conn1._last_health = HealthResult(
            status=HealthStatus.HEALTHY,
            connector="healthy_conn",
            latency_ms=5.0,
        )

        config2 = _make_config(name="unhealthy_conn")
        conn2 = DummyConnector(config2)
        conn2._last_health = HealthResult(
            status=HealthStatus.UNHEALTHY,
            connector="unhealthy_conn",
            latency_ms=0.0,
            error="Connection refused",
        )

        report = ConnectorRegistry.health_all()

        assert report["total"] == 2
        assert report["healthy"] == 1
        assert report["unhealthy"] == 1
        assert "healthy_conn" in report["connectors"]
        assert "unhealthy_conn" in report["connectors"]
        assert report["connectors"]["healthy_conn"]["health"]["status"] == "healthy"
        assert report["connectors"]["unhealthy_conn"]["health"]["status"] == "unhealthy"

    def test_registry_unregister(self):
        """اختبار إلغاء تسجيل موصل."""
        ConnectorRegistry.clear()
        ConnectorRegistry.register_class("temp_conn", DummyConnector, "1.0.0", "test")

        config = _make_config(name="temp_conn")
        ConnectorRegistry.create("temp_conn", config)

        assert ConnectorRegistry.get_instance("temp_conn") is not None

        ConnectorRegistry.unregister("temp_conn")
        assert ConnectorRegistry.get_instance("temp_conn") is None
        assert ConnectorRegistry.get_class("temp_conn") is None


# ═══════════════════════════════════════════════════════════════════════════
#  9-13. Connector call() with middleware
# ═══════════════════════════════════════════════════════════════════════════
class TestConnectorCall:
    """اختبارات BaseConnector.call() مع الـ middleware stack."""

    @pytest.mark.asyncio
    async def test_connector_call_with_retry(self):
        """اختبار أن call() يعيد المحاولة عند الفشل ثم ينجح."""
        config = _make_config(name="retry_test")
        connector_inst = FailingConnector(config, fail_until=2)

        # تجاوز سياسة الإعادة لتأخيرات سريعة
        connector_inst._retry_policy = RetryPolicy(
            max_retries=3, backoff_factor=1.0, max_delay=0.001,
        )
        # عتبة CB عالية لمنع فتحه أثناء الإعادة
        connector_inst._circuit_breaker = CircuitBreaker(
            failure_threshold=10, recovery_timeout=60.0,
        )

        result = await connector_inst.call("test_action", param="value")

        assert result["action"] == "test_action"
        assert result["attempt"] == 3  # فشل في 1,2 ثم نجح في 3

        metrics = connector_inst.get_metrics()
        assert metrics.total_calls == 1
        assert metrics.successful_calls == 1

    @pytest.mark.asyncio
    async def test_connector_call_circuit_breaker_opens(self):
        """اختبار أن CB يفتح بعد N فشل متتالي."""
        config = _make_config(name="cb_test")
        connector_inst = FailingConnector(config, fail_until=999)  # يفشل دائمًا

        # إعادة محاولة محدودة + عتبة CB منخفضة
        connector_inst._retry_policy = RetryPolicy(
            max_retries=2, backoff_factor=1.0, max_delay=0.001,
        )
        connector_inst._circuit_breaker = CircuitBreaker(
            failure_threshold=3, recovery_timeout=0.5,
        )

        # الاستدعاء الأول: يفشل بعد 3 محاولات، CB يفتح
        with pytest.raises(ConnectorError, match="محاكاة فشل"):
            await connector_inst.call("test_action")

        # التحقق من أن CB مفتوح
        assert connector_inst._circuit_breaker.state == CircuitBreakerState.OPEN

        # الاستدعاء الثاني: مرفوض فورًا من CB
        with pytest.raises(CircuitBreakerOpenError):
            await connector_inst.call("test_action")

    @pytest.mark.asyncio
    async def test_connector_call_cache_hit(self):
        """اختبار أن الـ cache يعمل: الاستدعاء الثاني يُرجع النتيجة المخزّنة."""
        config = _make_config(name="cache_test", cache_enabled=True, cache_ttl_seconds=300)
        connector_inst = CountingConnector(config)

        # الاستدعاء الأول: cache miss → تنفيذ execute
        result1 = await connector_inst.call("get_data", filter="active")
        assert result1["call_number"] == 1
        assert connector_inst.execute_count == 1

        # الاستدعاء الثاني بنفس المعاملات: cache hit → لا تنفيذ
        result2 = await connector_inst.call("get_data", filter="active")
        assert result2["call_number"] == 1  # نفس النتيجة المخزّنة
        assert connector_inst.execute_count == 1  # لم يُستدعَ execute مرة أخرى

        # التحقق من مقاييس الـ cache
        metrics = connector_inst.get_metrics()
        assert metrics.cache_hits >= 1
        assert metrics.cache_misses >= 1

    @pytest.mark.asyncio
    async def test_connector_call_cache_miss_different_params(self):
        """اختبار أن معاملات مختلفة تُنتج cache miss."""
        config = _make_config(name="cache_miss_test", cache_enabled=True)
        connector_inst = CountingConnector(config)

        await connector_inst.call("get_data", filter="active")
        await connector_inst.call("get_data", filter="inactive")

        assert connector_inst.execute_count == 2  # معاملات مختلفة → تنفيذان

    @pytest.mark.asyncio
    async def test_connector_call_rate_limit(self):
        """اختبار أن rate limit يحجب بعد استهلاك الرشقة."""
        config = _make_config(
            name="rate_limit_test",
            cache_enabled=False,  # تعطيل الـ cache لإجبار المرور عبر rate limiter
        )
        connector_inst = DummyConnector(config)

        # تجاوز محدد المعدل: رشقة صغيرة + معدل منخفض
        connector_inst._rate_limiter = RateLimiter(qps=0.5, burst=2)

        # استدعاءان ناجحان (يستهلكان الرشقة)
        result1 = await connector_inst.call("ping", use_cache=False)
        result2 = await connector_inst.call("ping", use_cache=False)
        assert result1["action"] == "ping"
        assert result2["action"] == "ping"

        # الاستدعاء الثالث: مرفوض من rate limiter
        with pytest.raises(RateLimitExceededError):
            await connector_inst.call("ping", use_cache=False)

        metrics = connector_inst.get_metrics()
        assert metrics.rate_limit_rejections >= 1

    @pytest.mark.asyncio
    async def test_connector_permissions_check(self):
        """اختبار فحص الصلاحيات: المستخدم غير المصرّح يُرفض."""
        config = _make_config(name="restricted_conn")
        connector_inst = RestrictedConnector(config)

        # admin: مسموح
        result = await connector_inst.call("action", user="admin")
        assert result["action"] == "action"

        # guest: مرفوض
        with pytest.raises(PermissionError, match="lacks permissions"):
            await connector_inst.call("action", user="guest")

    @pytest.mark.asyncio
    async def test_connector_permissions_no_user_allowed(self):
        """اختبار أن الاستدعاء بدون user يُسمح به (لا فحص صلاحيات)."""
        config = _make_config(name="restricted_no_user")
        connector_inst = RestrictedConnector(config)

        # بدون user: لا فحص صلاحيات
        result = await connector_inst.call("action")
        assert result["action"] == "action"


# ═══════════════════════════════════════════════════════════════════════════
#  14. GenericRESTConnector
# ═══════════════════════════════════════════════════════════════════════════
class TestGenericRESTConnector:
    """اختبارات GenericRESTConnector من sdk.py."""

    @pytest.mark.asyncio
    async def test_generic_rest_connector(self):
        """اختبار GenericRESTConnector مع mocked HTTP transport."""
        from packages.common.connectors.sdk import (
            GenericRESTConnector,
            ConnectorManifest,
        )

        config = _make_config(
            name="generic_rest_test",
            display_name="Test REST API",
            category="Generic",
            base_url="https://api.example.com",
            auth_strategy=AuthStrategy.NONE,
        )
        # إرفاق manifest عبر __dict__ (كما يفعل register_from_manifest)
        manifest = ConnectorManifest(
            name="test_api",
            display_name="Test API",
            base_url="https://api.example.com",
            auth_strategy=AuthStrategy.NONE,
            actions={
                "get_users": {"method": "GET", "path": "/users"},
                "create_user": {"method": "POST", "path": "/users"},
            },
        )
        config.__dict__["manifest"] = manifest.model_dump()

        connector_inst = GenericRESTConnector(config)

        # بناء mock HTTP transport
        def mock_handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            method = request.method

            if path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            if path == "/users" and method == "GET":
                return httpx.Response(200, json=[{"id": 1, "name": "Alice"}])
            if path == "/users" and method == "POST":
                return httpx.Response(201, json={"id": 2, "name": "Bob"})
            if path == "/search":
                return httpx.Response(200, json={"results": [{"id": 1}]})
            return httpx.Response(404, json={"error": "not found"})

        connector_inst._client = httpx.AsyncClient(
            base_url="https://api.example.com",
            transport=httpx.MockTransport(mock_handler),
        )

        try:
            # 1. فحص الصحة
            health = await connector_inst.health()
            assert health.status == HealthStatus.HEALTHY
            assert health.connector == "generic_rest_test"

            # 2. تنفيذ إجراء GET من الـ manifest
            result = await connector_inst.execute("get_users")
            assert isinstance(result, list)
            assert result[0]["name"] == "Alice"

            # 3. تنفيذ إجراء POST من الـ manifest
            result = await connector_inst.execute(
                "create_user", body={"name": "Bob"},
            )
            assert result["id"] == 2
            assert result["name"] == "Bob"

            # 4. البحث عبر search()
            results = await connector_inst.search("test")
            assert len(results) >= 1

            # 5. البيانات الوصفية
            meta = connector_inst.metadata()
            assert meta["name"] == "generic_rest_test"
            assert meta["display_name"] == "Test REST API"
            assert "get_users" in meta["actions"]
            assert "create_user" in meta["actions"]

            # 6. الصلاحيات
            perms = connector_inst.permissions()
            assert any("connector:" in p for p in perms)

        finally:
            await connector_inst._client.aclose()

    @pytest.mark.asyncio
    async def test_generic_rest_connector_error_handling(self):
        """اختبار معالجة الأخطاء في GenericRESTConnector."""
        from packages.common.connectors.sdk import GenericRESTConnector

        config = _make_config(
            name="generic_rest_err",
            base_url="https://api.example.com",
            auth_strategy=AuthStrategy.NONE,
        )
        connector_inst = GenericRESTConnector(config)

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "internal server error"})

        connector_inst._client = httpx.AsyncClient(
            base_url="https://api.example.com",
            transport=httpx.MockTransport(mock_handler),
        )

        try:
            # فحص الصحة يجب أن يُرجع UNHEALTHY
            health = await connector_inst.health()
            assert health.status == HealthStatus.UNHEALTHY
            assert health.error is not None
        finally:
            await connector_inst._client.aclose()


# ═══════════════════════════════════════════════════════════════════════════
#  15. SDK scaffold_connector
# ═══════════════════════════════════════════════════════════════════════════
class TestSDKScaffold:
    """اختبارات scaffold_connector من sdk.py."""

    def test_sdk_scaffold_connector(self, tmp_path):
        """اختبار أن scaffold ينشئ ملف Python صحيح."""
        import py_compile

        from packages.common.connectors.sdk import scaffold_connector

        file_path = scaffold_connector(
            name="my_custom_service",
            category="Custom",
            base_url="https://api.example.com",
            output_dir=tmp_path,
        )

        # 1. الملف موجود بالاسم الصحيح
        assert file_path.exists()
        assert file_path.name == "my_custom_service.py"

        # 2. الملف يُترجم بنجاح (syntax صحيح)
        py_compile.compile(str(file_path), doraise=True)

        # 3. المحتوى يحتوي على العناصر المتوقعة
        content = file_path.read_text(encoding="utf-8")

        assert 'class MyCustomServiceConnector(BaseConnector)' in content
        assert '@connector("my_custom_service"' in content
        assert 'category="Custom"' in content
        assert 'version="1.0.0"' in content
        # base_url يُمرَّر كمعامل لكنه يُستخدم في config فقط، لا كنص في الملف
        assert 'self.config.base_url' in content

        # 4. يحتوي على الطرق الإلزامية
        assert "async def authenticate" in content
        assert "async def health" in content
        assert "async def search" in content
        assert "async def execute" in content
        assert "def metadata" in content
        assert "def permissions" in content

    def test_sdk_scaffold_connector_importable(self, tmp_path):
        """اختبار أن الملف المُنشأ قابل للاستيراد."""
        import importlib.util

        from packages.common.connectors.sdk import scaffold_connector

        file_path = scaffold_connector(
            name="importable_service",
            category="Test",
            base_url="https://test.example.com",
            output_dir=tmp_path,
        )

        # تحميل الوحدة ديناميكيًا
        spec = importlib.util.spec_from_file_location(
            "importable_service", str(file_path),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # التحقق من وجود الـ class
        assert hasattr(module, "ImportableServiceConnector")
        cls = getattr(module, "ImportableServiceConnector")
        assert cls._connector_name == "importable_service"
        assert cls._connector_category == "Test"


# ═══════════════════════════════════════════════════════════════════════════
#  Bonus: New connectors import verification
# ═══════════════════════════════════════════════════════════════════════════
class TestNewConnectorsImport:
    """التحقق من أن الموصلات الستة الجديدة قابلة للاستيراد والتسجيل."""

    def test_sap_ecc_imports(self):
        """اختبار استيراد موصل SAP ECC."""
        from packages.common.connectors.connectors.sap_ecc import SAPECCConnector
        assert SAPECCConnector._connector_name == "sap_ecc"
        assert SAPECCConnector._connector_category == "ERP"

    def test_oracle_hcm_imports(self):
        """اختبار استيراد موصل Oracle HCM."""
        from packages.common.connectors.connectors.oracle_hcm import OracleHCMConnector
        assert OracleHCMConnector._connector_name == "oracle_hcm"
        assert OracleHCMConnector._connector_category == "HR"

    def test_dynamics_hr_imports(self):
        """اختبار استيراد موصل Dynamics 365 HR."""
        from packages.common.connectors.connectors.dynamics_hr import DynamicsHRConnector
        assert DynamicsHRConnector._connector_name == "dynamics_hr"
        assert DynamicsHRConnector._connector_category == "HR"

    def test_azure_ad_imports(self):
        """اختبار استيراد موصل Azure AD."""
        from packages.common.connectors.connectors.azure_ad import AzureADConnector
        assert AzureADConnector._connector_name == "azure_ad"
        assert AzureADConnector._connector_category == "Identity"

    def test_opentext_imports(self):
        """اختبار استيراد موصل OpenText."""
        from packages.common.connectors.connectors.opentext import OpenTextConnector
        assert OpenTextConnector._connector_name == "opentext"
        assert OpenTextConnector._connector_category == "Documents"

    def test_graphql_imports(self):
        """اختبار استيراد موصل GraphQL."""
        from packages.common.connectors.connectors.graphql import GraphQLConnector
        assert GraphQLConnector._connector_name == "graphql"
        assert GraphQLConnector._connector_category == "Integration"


# ═══════════════════════════════════════════════════════════════════════════
#  Bonus: Router endpoints
# ═══════════════════════════════════════════════════════════════════════════
class TestRouterEndpoints:
    """اختبارات سريعة لنقاط نهاية الـ router."""

    def test_router_has_endpoints(self):
        """اختبار أن الـ router يحتوي على المسارات المتوقعة."""
        from packages.common.connectors.router import router

        paths = {route.path for route in router.routes}
        assert "/v1/connectors/" in paths
        assert "/v1/connectors/catalog" in paths
        assert "/v1/connectors/health/all" in paths
        assert "/v1/connectors/metrics/all" in paths
        assert "/v1/connectors/metrics/prometheus" in paths
        assert "/v1/connectors/admin/create" in paths
        assert "/v1/connectors/admin/discover" in paths

    def test_router_metadata_endpoints(self):
        """اختبار وجود نقاط نهاية metadata و execute و search."""
        from packages.common.connectors.router import router

        # تجميع المسارات التي تحتوي على placeholder
        path_patterns = {route.path for route in router.routes}
        assert any("/{connector_name}/metadata" in p for p in path_patterns)
        assert any("/{connector_name}/execute" in p for p in path_patterns)
        assert any("/{connector_name}/search" in p for p in path_patterns)
        assert any("/{connector_name}/health" in p for p in path_patterns)
