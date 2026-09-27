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


@pytest.mark.asyncio
async def test_producer_start_success_and_stop(monkeypatch):
    m = _module()

    state = {
        "started": False,
        "stopped": False,
        "task_cancelled": False,
    }

    class FakeAIOKafkaProducer:
        def __init__(self, **kwargs):
            state["kwargs"] = kwargs

        async def start(self):
            state["started"] = True

        async def stop(self):
            state["stopped"] = True

    fake_aiokafka = types.ModuleType("aiokafka")
    fake_aiokafka.AIOKafkaProducer = FakeAIOKafkaProducer

    monkeypatch.setitem(
        sys.modules,
        "aiokafka",
        fake_aiokafka,
    )

    class FakeTask:
        def cancel(self):
            state["task_cancelled"] = True

        def __await__(self):
            async def cancelled():
                raise m.asyncio.CancelledError()

            return cancelled().__await__()

    def fake_create_task(coro):
        coro.close()
        return FakeTask()

    monkeypatch.setattr(
        m.asyncio,
        "create_task",
        fake_create_task,
    )

    producer = m.KafkaProducer(
        bootstrap_servers="kafka-test:9092"
    )

    await producer.start()

    assert state["started"] is True
    assert producer._producer is not None
    assert producer._running is True

    kwargs = state["kwargs"]

    assert (
        kwargs["bootstrap_servers"]
        == "kafka-test:9092"
    )
    assert kwargs["acks"] == "all"
    assert kwargs["enable_idempotence"] is True
    assert kwargs["retries"] == 3

    await producer.stop()

    assert producer._running is False
    assert state["task_cancelled"] is True
    assert state["stopped"] is True


@pytest.mark.asyncio
async def test_producer_start_import_error_enters_outbox_mode(
    monkeypatch,
):
    m = _module()

    # Existing module but missing AIOKafkaProducer causes
    # "from aiokafka import AIOKafkaProducer" to raise ImportError.
    fake_aiokafka = types.ModuleType("aiokafka")

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

    producer = m.KafkaProducer()

    await producer.start()

    assert producer._producer is None
    assert producer._running is True
    assert len(tasks) == 1

    # Avoid stop() awaiting the SimpleNamespace fake.
    producer._relay_task = None

    await producer.stop()

    assert producer._running is False


@pytest.mark.asyncio
async def test_producer_start_connection_failure_enters_outbox_mode(
    monkeypatch,
):
    m = _module()

    class BrokenAIOKafkaProducer:
        def __init__(self, **kwargs):
            raise RuntimeError("Kafka unavailable")

    fake_aiokafka = types.ModuleType("aiokafka")
    fake_aiokafka.AIOKafkaProducer = BrokenAIOKafkaProducer

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

    producer = m.KafkaProducer()

    await producer.start()

    assert producer._producer is None
    assert producer._running is True
    assert len(tasks) == 1

    producer._relay_task = None

    await producer.stop()


@pytest.mark.asyncio
async def test_publish_queues_event_and_updates_stats():
    m = _module()

    producer = m.KafkaProducer()

    event_id = await producer.publish(
        "document.ingested",
        {
            "document_id": "doc-1",
        },
        tenant_id="tenant-a",
        source="rag-engine",
    )

    assert event_id
    assert len(producer._outbox) == 1

    event = producer._outbox[0]

    assert event.event_id == event_id
    assert event.event_type == "document.ingested"
    assert event.tenant_id == "tenant-a"
    assert event.source == "rag-engine"

    stats = producer.get_stats()

    assert stats["queued"] == 1
    assert stats["published"] == 0
    assert stats["failed"] == 0
    assert stats["outbox_size"] == 1


@pytest.mark.asyncio
async def test_drain_outbox_success_clears_queue(monkeypatch):
    m = _module()

    producer = m.KafkaProducer()

    await producer.publish(
        m.EventTypes.DOCUMENT_INGESTED,
        {"document_id": "doc-success"},
        tenant_id="tenant-a",
    )

    captured = []

    async def publish_ok(topic, event):
        captured.append(
            (topic, event.event_id)
        )
        return True

    monkeypatch.setattr(
        producer,
        "_publish_to_kafka",
        publish_ok,
    )

    await producer._drain_outbox()

    assert len(captured) == 1
    assert (
        captured[0][0]
        == m.Topics.DOCUMENT_EVENTS
    )

    stats = producer.get_stats()

    assert stats["published"] == 1
    assert stats["failed"] == 0
    assert stats["outbox_size"] == 0


@pytest.mark.asyncio
async def test_drain_outbox_failure_requeues_event(monkeypatch):
    m = _module()

    producer = m.KafkaProducer()

    event_id = await producer.publish(
        "custom.unknown.event",
        {"value": 1},
    )

    captured = []

    async def publish_fail(topic, event):
        captured.append(
            (topic, event.event_id)
        )
        return False

    monkeypatch.setattr(
        producer,
        "_publish_to_kafka",
        publish_fail,
    )

    await producer._drain_outbox()

    assert captured == [
        (
            "hsaai.unknown",
            event_id,
        )
    ]

    stats = producer.get_stats()

    assert stats["published"] == 0
    assert stats["failed"] == 1
    assert stats["outbox_size"] == 1

    assert producer._outbox[0].event_id == event_id


@pytest.mark.asyncio
async def test_drain_outbox_empty_is_noop():
    m = _module()

    producer = m.KafkaProducer()

    await producer._drain_outbox()

    stats = producer.get_stats()

    assert stats["published"] == 0
    assert stats["failed"] == 0
    assert stats["outbox_size"] == 0


@pytest.mark.asyncio
async def test_publish_to_kafka_without_connection_returns_false():
    m = _module()

    producer = m.KafkaProducer()
    producer._producer = None

    event = m.Event(
        event_type="test.event",
        tenant_id="tenant-a",
    )

    result = await producer._publish_to_kafka(
        "topic-a",
        event,
    )

    assert result is False


@pytest.mark.asyncio
async def test_publish_to_kafka_success():
    m = _module()

    producer = m.KafkaProducer()

    captured = {}

    class Backend:
        async def send_and_wait(
            self,
            topic,
            **kwargs,
        ):
            captured["topic"] = topic
            captured["kwargs"] = kwargs

    producer._producer = Backend()

    event = m.Event(
        event_type="test.event",
        tenant_id="tenant-a",
        payload={"value": 7},
    )

    result = await producer._publish_to_kafka(
        "topic-a",
        event,
    )

    assert result is True
    assert captured["topic"] == "topic-a"
    assert captured["kwargs"]["key"] == "tenant-a"
    assert (
        captured["kwargs"]["value"]["event_id"]
        == event.event_id
    )


@pytest.mark.asyncio
async def test_publish_to_kafka_failure_returns_false():
    m = _module()

    producer = m.KafkaProducer()

    class Backend:
        async def send_and_wait(
            self,
            *args,
            **kwargs,
        ):
            raise RuntimeError(
                "broker write failed"
            )

    producer._producer = Backend()

    event = m.Event(
        event_type="test.event",
        tenant_id="tenant-a",
    )

    result = await producer._publish_to_kafka(
        "topic-a",
        event,
    )

    assert result is False
