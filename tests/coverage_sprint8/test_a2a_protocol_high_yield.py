import asyncio
import importlib
import time

import pytest


def _m():
    return importlib.import_module("common.a2a_protocol")


def test_message_defaults_and_explicit_values():
    m = _m()

    msg = m.A2AMessage(
        from_agent="a",
        to_agent="b",
        message_type="query",
    )

    assert msg.message_id.startswith("msg-")
    assert msg.trace_id.startswith("trace-")
    assert msg.timestamp > 0

    explicit = m.A2AMessage(
        message_id="m1",
        trace_id="t1",
        timestamp=123.0,
    )

    assert explicit.message_id == "m1"
    assert explicit.trace_id == "t1"
    assert explicit.timestamp == 123.0


def test_register_unregister_and_stats():
    m = _m()
    bus = m.A2AProtocol()

    async def handler(message):
        return {"ok": True}

    bus.register_agent("agent-a", handler)
    assert "agent-a" in bus._agents

    bus.unregister_agent("agent-a")
    assert "agent-a" not in bus._agents
    assert bus.stats() == {}


@pytest.mark.asyncio
async def test_broadcast_success_skip_sender_and_handler_failure():
    m = _m()
    bus = m.A2AProtocol()

    async def sender_handler(message):
        raise AssertionError("sender must be skipped")

    async def good(message):
        return {"answer": 1}

    async def empty(message):
        return None

    async def bad(message):
        raise RuntimeError("agent failed")

    bus.register_agent("sender", sender_handler)
    bus.register_agent("good", good)
    bus.register_agent("empty", empty)
    bus.register_agent("bad", bad)

    result = await bus.send(
        m.A2AMessage(
            from_agent="sender",
            to_agent="all",
            message_type="broadcast",
        )
    )

    assert result == {
        "broadcast_responses": [
            {
                "agent": "good",
                "response": {"answer": 1},
            }
        ]
    }
    assert bus.stats()["sent_broadcast"] == 1


@pytest.mark.asyncio
async def test_direct_delivery_missing_success_timeout_and_failure():
    m = _m()
    bus = m.A2AProtocol()

    missing = await bus.send(
        m.A2AMessage(
            to_agent="missing",
            message_type="query",
        )
    )
    assert "not registered" in missing["error"]

    async def ok(message):
        return {"result": "ok"}

    async def timeout(message):
        raise asyncio.TimeoutError()

    async def bad(message):
        raise ValueError("bad delivery")

    bus.register_agent("ok", ok)
    bus.register_agent("timeout", timeout)
    bus.register_agent("bad", bad)

    result = await bus.send(
        m.A2AMessage(
            to_agent="ok",
            message_type="query",
        )
    )

    assert result == {"result": "ok"}
    assert bus.stats()["delivered_query"] == 1
    assert bus.stats()["successful_deliveries"] == 1

    result = await bus.send(
        m.A2AMessage(
            to_agent="timeout",
            message_type="task_request",
            deadline=time.time() + 1,
        )
    )
    assert result == {"error": "timeout"}
    assert bus.stats()["timeouts"] == 1

    result = await bus.send(
        m.A2AMessage(
            to_agent="bad",
            message_type="query",
        )
    )
    assert "bad delivery" in result["error"]
    assert bus.stats()["delivery_failures"] == 1


@pytest.mark.asyncio
async def test_request_and_query_build_correct_messages(monkeypatch):
    m = _m()
    bus = m.A2AProtocol()
    captured = []

    async def fake_send(message):
        captured.append(message)
        return {"ok": True}

    monkeypatch.setattr(bus, "send", fake_send)

    result1 = await bus.request(
        "agent-a",
        "agent-b",
        {"task": "work"},
        priority="high",
        timeout=5,
    )

    result2 = await bus.query(
        "agent-a",
        "agent-b",
        "question?",
        timeout=3,
    )

    assert result1 == {"ok": True}
    assert result2 == {"ok": True}

    assert captured[0].message_type == "task_request"
    assert captured[0].priority == "high"
    assert captured[0].content == {"task": "work"}

    assert captured[1].message_type == "query"
    assert captured[1].content == {"question": "question?"}


def test_message_log_filter_limit_and_trim():
    m = _m()
    bus = m.A2AProtocol()

    bus._message_log = [
        m.A2AMessage(
            from_agent="a",
            to_agent="b",
            message_type="query",
        ),
        m.A2AMessage(
            from_agent="c",
            to_agent="a",
            message_type="query",
        ),
        m.A2AMessage(
            from_agent="x",
            to_agent="y",
            message_type="query",
        ),
    ]

    filtered = bus.get_message_log(
        agent_id="a",
        limit=10,
    )

    assert len(filtered) == 2

    limited = bus.get_message_log(limit=1)
    assert len(limited) == 1


@pytest.mark.asyncio
async def test_message_log_is_bounded():
    m = _m()
    bus = m.A2AProtocol()

    bus._message_log = [
        m.A2AMessage(
            message_id=f"m{i}",
            timestamp=1,
            trace_id="t",
        )
        for i in range(10000)
    ]

    result = await bus.send(
        m.A2AMessage(
            to_agent="missing",
            message_type="query",
        )
    )

    assert "error" in result
    assert len(bus._message_log) == 5000
