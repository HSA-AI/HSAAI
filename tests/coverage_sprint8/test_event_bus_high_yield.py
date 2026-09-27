import builtins
import importlib
import json
import sys
import types

import pytest


def _m():
    import common.event_bus as module
    return module


def test_event_serialization():
    m = _m()

    event = m.Event(
        topic="document.ingested",
        payload={"doc_id": "123"},
        tenant_id="tenant-1",
        source="rag-engine",
    )

    data = json.loads(event.to_json())

    assert data["topic"] == "document.ingested"
    assert data["payload"] == {"doc_id": "123"}
    assert data["tenant_id"] == "tenant-1"
    assert data["source"] == "rag-engine"
    assert data["event_id"]
    assert data["timestamp"]
    assert data["version"] == "1.0.0"


def test_memory_backend_and_unknown_backend():
    m = _m()

    bus = m.EventBus("memory")

    assert bus.backend == "memory"
    assert bus._subscribers == {}
    assert bus._kafka_producer is None

    with pytest.raises(
        ValueError,
        match="Unknown backend",
    ):
        m.EventBus("unsupported")


def test_backend_from_environment(monkeypatch):
    m = _m()

    monkeypatch.setenv(
        "EVENT_BUS_BACKEND",
        "memory",
    )

    bus = m.EventBus()

    assert bus.backend == "memory"


def test_kafka_initialization_success(monkeypatch):
    m = _m()

    created = {}

    class Producer:
        def __init__(self, **kwargs):
            created.update(kwargs)

    fake = types.ModuleType("aiokafka")
    fake.AIOKafkaProducer = Producer

    monkeypatch.setitem(
        sys.modules,
        "aiokafka",
        fake,
    )

    monkeypatch.setenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "broker:9092",
    )

    bus = m.EventBus("kafka")

    assert bus.backend == "kafka"
    assert isinstance(
        bus._kafka_producer,
        Producer,
    )

    assert (
        created["bootstrap_servers"]
        == "broker:9092"
    )
    assert created["acks"] == "all"
    assert created["enable_idempotence"] is True

    assert (
        created["value_serializer"](
            {"a": 1}
        )
        == b'{"a": 1}'
    )

    assert (
        created["key_serializer"]("tenant")
        == b"tenant"
    )

    assert (
        created["key_serializer"](None)
        is None
    )


def test_kafka_import_error_falls_back(
    monkeypatch,
):
    m = _m()

    real_import = builtins.__import__

    def fake_import(
        name,
        globals=None,
        locals=None,
        fromlist=(),
        level=0,
    ):
        if name == "aiokafka":
            raise ImportError(
                "aiokafka unavailable"
            )

        return real_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    monkeypatch.setattr(
        builtins,
        "__import__",
        fake_import,
    )

    bus = m.EventBus("kafka")

    assert bus.backend == "memory"
    assert bus._kafka_producer is None


@pytest.mark.asyncio
async def test_start_stop_and_cancel_tasks():
    m = _m()

    class Producer:
        def __init__(self):
            self.started = 0
            self.stopped = 0

        async def start(self):
            self.started += 1

        async def stop(self):
            self.stopped += 1

    class Task:
        def __init__(self):
            self.cancelled = 0

        def cancel(self):
            self.cancelled += 1

    producer = Producer()
    task1 = Task()
    task2 = Task()

    bus = m.EventBus("memory")
    bus.backend = "kafka"
    bus._kafka_producer = producer
    bus._kafka_consumer_tasks = [
        task1,
        task2,
    ]

    await bus.start()
    await bus.stop()

    assert producer.started == 1
    assert producer.stopped == 1
    assert task1.cancelled == 1
    assert task2.cancelled == 1


@pytest.mark.asyncio
async def test_publish_to_kafka():
    m = _m()

    sent = []

    class Producer:
        async def send_and_wait(
            self,
            topic,
            value,
            key,
        ):
            sent.append(
                (topic, value, key)
            )

    bus = m.EventBus("memory")
    bus.backend = "kafka"
    bus._kafka_producer = Producer()

    event = m.Event(
        topic="agent.completed",
        payload={"result": "ok"},
        tenant_id="tenant-1",
    )

    await bus.publish(event)

    assert len(sent) == 1

    topic, value, key = sent[0]

    assert topic == "agent.completed"
    assert value["payload"] == {
        "result": "ok"
    }
    assert key == "tenant-1"


@pytest.mark.asyncio
async def test_publish_kafka_default_key():
    m = _m()

    sent = []

    class Producer:
        async def send_and_wait(
            self,
            topic,
            value,
            key,
        ):
            sent.append(key)

    bus = m.EventBus("memory")
    bus.backend = "kafka"
    bus._kafka_producer = Producer()

    await bus.publish(
        m.Event(
            topic="audit.user_action",
            payload={},
        )
    )

    assert sent == ["default"]


@pytest.mark.asyncio
async def test_memory_publish_subscribe_and_handler_error():
    m = _m()

    bus = m.EventBus("memory")
    received = []

    @bus.subscribe("document.ingested")
    async def good(event):
        received.append(
            event.payload["doc_id"]
        )

    @bus.subscribe("document.ingested")
    async def bad(event):
        raise RuntimeError(
            "handler failed"
        )

    assert (
        len(
            bus._subscribers[
                "document.ingested"
            ]
        )
        == 2
    )

    event = m.Event(
        topic="document.ingested",
        payload={"doc_id": "doc-1"},
    )

    await bus.publish(event)

    assert received == ["doc-1"]


@pytest.mark.asyncio
async def test_dispatch_topic_without_handlers():
    m = _m()

    bus = m.EventBus("memory")

    await bus._dispatch(
        m.Event(
            topic="unknown.topic",
            payload={},
        )
    )


def test_singleton_event_bus(monkeypatch):
    m = _m()

    monkeypatch.setattr(
        m,
        "_bus",
        None,
    )

    first = m.get_event_bus()
    second = m.get_event_bus()

    assert isinstance(
        first,
        m.EventBus,
    )
    assert first is second


def test_standard_topics_exist():
    m = _m()

    assert (
        m.Topics.DOCUMENT_INGESTED
        == "document.ingested"
    )
    assert (
        m.Topics.AGENT_COMPLETED
        == "agent.completed"
    )
    assert (
        m.Topics.LLM_ERROR
        == "llm.error"
    )
    assert (
        m.Topics.SAFETY_KILL_SWITCH
        == "safety.kill_switch"
    )
    assert (
        m.Topics.AUDIT_USER_ACTION
        == "audit.user_action"
    )
