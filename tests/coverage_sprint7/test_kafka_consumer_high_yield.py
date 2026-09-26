import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


def _module():
    repo_root = Path(__file__).resolve().parents[2]
    common_dir = repo_root / "packages" / "common"

    if str(common_dir) not in sys.path:
        sys.path.insert(0, str(common_dir))

    return importlib.import_module(
        "event_bus.kafka_producer"
    )


def _message(m, *, event_type="test.event", event_id="event-1"):
    event = m.Event(
        event_type=event_type,
        event_id=event_id,
        tenant_id="tenant-a",
        source="unit-test",
        payload={"value": 1},
    )

    return SimpleNamespace(
        value=event.to_dict()
    )


@pytest.mark.asyncio
async def test_process_message_duplicate_is_skipped():
    m = _module()

    consumer = m.KafkaConsumer()

    consumer._processed_ids.add(
        "duplicate-1"
    )

    await consumer._process_message(
        _message(
            m,
            event_id="duplicate-1",
        )
    )

    stats = consumer.get_stats()

    assert stats["consumed"] == 1
    assert stats["skipped_duplicate"] == 1
    assert stats["succeeded"] == 0
    assert stats["failed"] == 0


@pytest.mark.asyncio
async def test_process_message_without_handler_returns_cleanly():
    m = _module()

    consumer = m.KafkaConsumer()

    await consumer._process_message(
        _message(
            m,
            event_type="unknown.event",
            event_id="event-no-handler",
        )
    )

    stats = consumer.get_stats()

    assert stats["consumed"] == 1
    assert stats["succeeded"] == 0
    assert stats["failed"] == 0
    assert stats["dlq_sent"] == 0


@pytest.mark.asyncio
async def test_process_message_success_marks_processed():
    m = _module()

    consumer = m.KafkaConsumer()

    calls = []

    async def handler(event):
        calls.append(event.event_id)

        return m.ProcessResult(
            success=True,
        )

    consumer.subscribe(
        "test.event",
        handler,
    )

    await consumer._process_message(
        _message(
            m,
            event_id="success-1",
        )
    )

    stats = consumer.get_stats()

    assert calls == ["success-1"]
    assert stats["consumed"] == 1
    assert stats["succeeded"] == 1
    assert stats["failed"] == 0
    assert "success-1" in consumer._processed_ids


@pytest.mark.asyncio
async def test_process_message_retry_then_success(monkeypatch):
    m = _module()

    consumer = m.KafkaConsumer()

    consumer.MAX_RETRIES = 3
    consumer.RETRY_DELAY_BASE = 0

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(
        m.asyncio,
        "sleep",
        fake_sleep,
    )

    attempts = 0

    async def handler(event):
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            return m.ProcessResult(
                success=False,
                error="temporary failure",
                should_retry=True,
            )

        return m.ProcessResult(
            success=True,
        )

    consumer.subscribe(
        "test.event",
        handler,
    )

    await consumer._process_message(
        _message(
            m,
            event_id="retry-success",
        )
    )

    stats = consumer.get_stats()

    assert attempts == 2
    assert stats["retried"] == 1
    assert stats["succeeded"] == 1
    assert stats["failed"] == 0
    assert "retry-success" in consumer._processed_ids
    assert len(sleep_calls) == 1


@pytest.mark.asyncio
async def test_process_message_nonretryable_goes_to_dlq():
    m = _module()

    consumer = m.KafkaConsumer()

    consumer.MAX_RETRIES = 3

    async def handler(event):
        return m.ProcessResult(
            success=False,
            error="validation failed",
            should_retry=False,
        )

    consumer.subscribe(
        "test.event",
        handler,
    )

    # Use the real _send_to_dlq implementation.
    await consumer._process_message(
        _message(
            m,
            event_id="nonretry-1",
        )
    )

    stats = consumer.get_stats()

    assert stats["consumed"] == 1
    assert stats["failed"] == 1
    assert stats["dlq_sent"] == 1
    assert stats["retried"] == 0
    assert "nonretry-1" not in consumer._processed_ids


@pytest.mark.asyncio
async def test_process_message_exception_retries_then_dlq(
    monkeypatch,
):
    m = _module()

    consumer = m.KafkaConsumer()

    consumer.MAX_RETRIES = 1
    consumer.RETRY_DELAY_BASE = 0

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(
        m.asyncio,
        "sleep",
        fake_sleep,
    )

    attempts = 0

    async def handler(event):
        nonlocal attempts
        attempts += 1
        raise RuntimeError(
            "handler crashed"
        )

    consumer.subscribe(
        "test.event",
        handler,
    )

    await consumer._process_message(
        _message(
            m,
            event_id="exception-1",
        )
    )

    stats = consumer.get_stats()

    assert attempts == 2
    assert stats["failed"] == 1
    assert stats["dlq_sent"] == 1
    assert stats["succeeded"] == 0

    # One sleep occurs between attempt 0 and attempt 1.
    assert len(sleep_calls) == 1


@pytest.mark.asyncio
async def test_consumer_start_success_with_fake_aiokafka(
    monkeypatch,
):
    m = _module()

    created = {}

    class FakeAIOKafkaConsumer:
        def __init__(
            self,
            *topics,
            **kwargs,
        ):
            created["topics"] = topics
            created["kwargs"] = kwargs
            created["started"] = False

        async def start(self):
            created["started"] = True

        async def stop(self):
            created["stopped"] = True

    fake_aiokafka = types.ModuleType(
        "aiokafka"
    )

    fake_aiokafka.AIOKafkaConsumer = (
        FakeAIOKafkaConsumer
    )

    monkeypatch.setitem(
        sys.modules,
        "aiokafka",
        fake_aiokafka,
    )

    tasks = []

    def fake_create_task(coro):
        tasks.append(coro)
        coro.close()

        return SimpleNamespace()

    monkeypatch.setattr(
        m.asyncio,
        "create_task",
        fake_create_task,
    )

    consumer = m.KafkaConsumer(
        group_id="sprint7-group"
    )

    await consumer.start(
        [
            "topic-a",
            "topic-b",
        ]
    )

    assert created["started"] is True
    assert created["topics"] == (
        "topic-a",
        "topic-b",
    )

    assert (
        created["kwargs"]["group_id"]
        == "sprint7-group"
    )

    assert consumer._consumer is not None
    assert consumer._running is True
    assert len(tasks) == 1

    await consumer.stop()

    assert created["stopped"] is True
    assert consumer._running is False


@pytest.mark.asyncio
async def test_consumer_start_connection_failure_enters_stub_mode(
    monkeypatch,
):
    m = _module()

    class BrokenAIOKafkaConsumer:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            raise RuntimeError(
                "Kafka unavailable"
            )

    fake_aiokafka = types.ModuleType(
        "aiokafka"
    )

    fake_aiokafka.AIOKafkaConsumer = (
        BrokenAIOKafkaConsumer
    )

    monkeypatch.setitem(
        sys.modules,
        "aiokafka",
        fake_aiokafka,
    )

    tasks = []

    def fake_create_task(coro):
        tasks.append(coro)
        coro.close()

        return SimpleNamespace()

    monkeypatch.setattr(
        m.asyncio,
        "create_task",
        fake_create_task,
    )

    consumer = m.KafkaConsumer()

    await consumer.start(
        ["topic-a"]
    )

    assert consumer._consumer is None
    assert consumer._running is True
    assert len(tasks) == 1

    await consumer.stop()

    assert consumer._running is False


@pytest.mark.asyncio
async def test_publish_event_uses_singleton_producer(
    monkeypatch,
):
    m = _module()

    captured = {}

    class Producer:
        async def publish(
            self,
            event_type,
            payload,
            tenant_id,
            source,
        ):
            captured.update(
                {
                    "event_type": event_type,
                    "payload": payload,
                    "tenant_id": tenant_id,
                    "source": source,
                }
            )

            return "published-event-id"

    monkeypatch.setattr(
        m,
        "get_producer",
        lambda: Producer(),
    )

    result = await m.publish_event(
        "document.ingested",
        {
            "document_id": "doc-77",
        },
        tenant_id="tenant-a",
        source="rag-engine",
    )

    assert result == "published-event-id"

    assert captured == {
        "event_type": "document.ingested",
        "payload": {
            "document_id": "doc-77",
        },
        "tenant_id": "tenant-a",
        "source": "rag-engine",
    }
