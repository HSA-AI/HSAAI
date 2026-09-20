# ADR-004: Adopt Kafka as Event Bus

**Status:** Superseded by [ADR-004b](004b-in-memory-event-bus.md)
**Date:** 2026-07-04
**Superseded:** 2026-07-09

## Context
HSAAI services communicate via synchronous HTTP. This causes:
- Cascading failures (one slow service blocks callers)
- No async processing for long-running tasks
- No event sourcing for audit trails
- Tight coupling between services

## Decision
Adopt Apache Kafka as the event bus for all inter-service async communication.

## Consequences
- **Positive:** Decoupled services, replay capability, event sourcing,
  CQRS support.
- **Negative:** Operational complexity (Kafka cluster management),
  eventual consistency model.
- **Mitigation:** Start with one event (audit logging), expand gradually.

## Alternatives
1. **NATS JetStream:** Simpler operations, less mature ecosystem.
   Considered for smaller deployments.
2. **RabbitMQ:** Good for point-to-point, weaker for event streaming.
3. **AWS Kinesis:** Vendor lock-in. Rejected.

## Supersession

<!-- FIX D-13: This ADR was superseded on 2026-07-09. -->

**Status changed from "Accepted" to "Superseded".**

This ADR mandated Kafka as the event bus, but Kafka was never actually
adopted in practice. Concretely:

1. **`aiokafka` is not in any `requirements.txt` file** in the
   repository. A repo-wide search for `aiokafka`, `kafka-python`, and
   `confluent-kafka` finds the Python symbol referenced only in
   `packages/common/event_bus/__init__.py` — and there it is wrapped in
   a `try: from aiokafka import AIOKafkaProducer` / `except ImportError:
   ... falling back to memory` block. Because `aiokafka` is never
   installed, the import always fails and the EventBus silently
   downgrades to in-memory mode at runtime.

2. **The default backend is `"memory"`** — `EventBus.__init__` reads
   `EVENT_BUS_BACKEND` with a default of `"memory"`, and no environment
   file in the repo (`.env.example`, `.env.hsa-internal.example`,
   `.env.production.example`) sets it to `"kafka"`.

3. **No Kafka cluster is defined in `docker-compose.yml`** or in any
   Kubernetes manifest under `infrastructure/`. There is no broker to
   connect to even if `aiokafka` were installed.

The net effect: ADR-004 says "we use Kafka" while the code runs an
in-memory bus that loses all queued events on any process restart.
That is a documentation/code mismatch that misleads operators into
thinking they have durable event streaming when they do not.

Kafka adoption is **deferred** — not cancelled — until the platform's
throughput and durability requirements actually justify the operational
cost of running a Kafka cluster. The actual, current decision is
documented in [ADR-004b](004b-in-memory-event-bus.md), which records
the in-memory bus as the accepted (interim) decision and the explicit
conditions under which Kafka should be re-evaluated.

## Reference
- Kafka: https://kafka.apache.org/
- Replacement ADR: [004b-in-memory-event-bus.md](004b-in-memory-event-bus.md)
