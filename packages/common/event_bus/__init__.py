"""
HSAAI Event Bus — Kafka/NATS Abstraction (Phase 1 — Critical)
================================================================
Provides async event publishing and consuming for all services.
Enables event-driven architecture, async task processing, and
audit log streaming.

Usage:
    from packages.common.event_bus import EventBus, Event

    bus = EventBus()

    # Publish
    await bus.publish(Event(
        topic="document.ingested",
        payload={"doc_id": "123", "tenant_id": "hsa-foods"},
    ))

    # Subscribe
    @bus.subscribe("document.ingested")
    async def handle_doc(event):
        logger.info(f"Got document: {event.payload}")
"""
import os
import json
import asyncio
import logging
from typing import Callable, Awaitable, Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hsaai.event_bus")


@dataclass
class Event:
    """Standard event structure for all HSAAI events."""
    topic: str
    payload: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tenant_id: Optional[str] = None
    source: Optional[str] = None  # service that published
    version: str = "1.0.0"

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


class EventBus:
    """
    Async event bus abstraction. Uses Kafka in production,
    falls back to in-memory for development.
    """

    def __init__(self, backend: str = None):
        backend = backend or os.getenv("EVENT_BUS_BACKEND", "memory")
        self.backend = backend
        self._subscribers: Dict[str, List[Callable]] = {}
        self._kafka_producer = None
        self._kafka_consumer_tasks: List[asyncio.Task] = []

        if backend == "kafka":
            self._init_kafka()
        elif backend == "memory":
            logger.info("EventBus: in-memory mode (dev only)")
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def _init_kafka(self):
        """Initialize Kafka producer."""
        try:
            from aiokafka import AIOKafkaProducer
            self._kafka_producer = AIOKafkaProducer(
                bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",  # Wait for all replicas
                enable_idempotence=True,  # Exactly-once semantics
            )
            logger.info("EventBus: Kafka mode initialized")
        except ImportError:
            logger.warning("aiokafka not installed — falling back to memory")
            self.backend = "memory"

    async def start(self):
        """Start the event bus (Kafka producer connection)."""
        if self.backend == "kafka" and self._kafka_producer:
            await self._kafka_producer.start()
            logger.info("Kafka producer started")

    async def stop(self):
        """Stop the event bus."""
        if self.backend == "kafka" and self._kafka_producer:
            await self._kafka_producer.stop()
            logger.info("Kafka producer stopped")
        for task in self._kafka_consumer_tasks:
            task.cancel()

    async def publish(self, event: Event):
        """Publish an event to the bus."""
        if self.backend == "kafka" and self._kafka_producer:
            key = event.tenant_id or "default"
            await self._kafka_producer.send_and_wait(
                event.topic, value=asdict(event), key=key
            )
            logger.debug(f"Published to Kafka: {event.topic} (id={event.event_id})")
        else:
            # In-memory: call subscribers directly
            await self._dispatch(event)

    async def _dispatch(self, event: Event):
        """Dispatch event to all subscribers (in-memory mode)."""
        handlers = self._subscribers.get(event.topic, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.topic}: {e}")

    def subscribe(self, topic: str) -> Callable:
        """Decorator to subscribe a handler to a topic."""
        def decorator(func: Callable[[Event], Awaitable[None]]):
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(func)
            logger.info(f"Subscribed handler to topic: {topic}")
            return func
        return decorator


# ─── Standard Event Topics ──────────────────────────────────────────
class Topics:
    """Standard event topic names. Use these constants to avoid typos."""
    # Document events
    DOCUMENT_INGESTED = "document.ingested"
    DOCUMENT_INDEXED = "document.indexed"
    DOCUMENT_DELETED = "document.deleted"

    # Agent events
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    AGENT_TOOL_CALLED = "agent.tool_called"

    # LLM events
    LLM_REQUEST = "llm.request"
    LLM_RESPONSE = "llm.response"
    LLM_ERROR = "llm.error"

    # Memory events
    MEMORY_EPISODIC_STORED = "memory.episodic.stored"
    MEMORY_CONSOLIDATED = "memory.consolidated"

    # Safety events
    SAFETY_APPROVAL_REQUESTED = "safety.approval.requested"
    SAFETY_APPROVAL_GRANTED = "safety.approval.granted"
    SAFETY_KILL_SWITCH = "safety.kill_switch"

    # Audit events
    AUDIT_TOOL_CALL = "audit.tool_call"
    AUDIT_USER_ACTION = "audit.user_action"


# Singleton
_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the singleton EventBus instance."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
