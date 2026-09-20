# ADR-004b: In-Memory Event Bus (Interim)

**Status:** Accepted
**Date:** 2026-07-09
**Supersedes:** [ADR-004](004-adopt-kafka-event-bus.md)

## Context

ADR-004 mandated Apache Kafka as the HSAAI event bus. In practice Kafka
was never adopted:

- `aiokafka` is not listed in **any** `requirements.txt` file in the
  repository (`packages/common/requirements.txt`,
  `services/*/requirements.txt`, `tests/requirements.txt`).
- `packages/common/event_bus/__init__.py` wraps the `aiokafka` import in
  a `try/except ImportError` and silently falls back to in-memory mode.
  Because `aiokafka` is never installed, the fallback is the *only* code
  path that ever executes.
- The default `EVENT_BUS_BACKEND` is `"memory"`, and no `.env*` file in
  the repo overrides it to `"kafka"`.
- No Kafka broker is defined in `docker-compose.yml` or in any
  Kubernetes manifest under `infrastructure/`.

The result is a documentation/code mismatch: the ADR says "we use Kafka"
while the platform runs an in-memory bus that loses every queued event
on process restart. This ADR records the *actual* current decision so
that operators are not misled.

The relevant code (`packages/common/event_bus/__init__.py`) supports two
backends:

| Backend | Persistence | Replay | Cross-process fan-out | Requires |
|---------|-------------|--------|-----------------------|----------|
| `memory` (default) | None — events live only in the publishing process's RAM | No | No — subscribers in other processes never see the event | nothing |
| `kafka` | Durable (Kafka log) | Yes (offset rewind) | Yes (consumer groups) | `aiokafka` + a Kafka cluster |

## Decision

Adopt the **in-memory event bus** (`EventBus(backend="memory")`) as the
accepted, documented, *interim* HSAAI event bus. Concretely:

1. The in-memory bus is the only backend that ships by default. The
   `EVENT_BUS_BACKEND` environment variable remains supported so that a
   future Kafka rollout does not require a code change — only a
   dependency install + env var flip.
2. All code that publishes events MUST treat the event as best-effort:
   - The publisher MUST NOT depend on the event being delivered to a
     subscriber in another process for correctness.
   - Critical side-effects (audit log writes, governance decisions,
     cost-record writes) MUST be persisted via their primary
     synchronous path (Postgres) and NOT rely on the event bus.
3. Subscribers that need durable delivery MUST register a fallback
   polling job that reads from the durable source-of-truth table
   directly. The event bus is only a low-latency hint.
4. `aiokafka` is intentionally NOT added to `requirements.txt` in this
   ADR. Adding it would imply Kafka is supported, which it currently is
   not (no broker, no ops runbook, no SLO).

## Consequences

- **Positive:**
  - Zero new infrastructure to operate. No Kafka cluster, no ZooKeeper,
    no schema registry, no consumer-group rebalancing bugs.
  - Local development works with no extra services running.
  - The `EventBus` abstraction is preserved, so a future Kafka rollout
    is a dependency + config change, not a rewrite.
- **Negative:**
  - Events are NOT durable. A process restart loses any in-flight
    events that have not yet been delivered to in-process subscribers.
  - No cross-process fan-out. A subscriber in service A cannot receive
    an event published by service B — the in-memory bus is
    per-process. Cross-service "events" must be implemented as direct
    HTTP calls or as a periodic polling job against the source-of-truth
    table.
  - No replay. Once an event is dispatched (or dropped), it is gone.
- **Mitigation:**
  - Treat the event bus as a best-effort notification mechanism, never
    as the system of record. The system of record for every event
    topic is a Postgres table (e.g. `audit_logs`, `agent_logs`,
    `knowledge_documents`). Subscribers that need at-least-once
    delivery poll the table; the event bus only wakes them up faster
    when the publisher and subscriber happen to share a process.

## When to re-evaluate (Kafka re-introduction criteria)

Kafka (or an equivalent durable log: NATS JetStream, Redpanda, Pulsar)
should be re-introduced — and ADR-004 un-superseded — when **any** of
the following becomes true:

1. A subscriber exists that needs durable, at-least-once, cross-process
   event delivery AND polling the source-of-truth table is too slow
   (p99 > 5s) or too load-intensive.
2. The platform needs event-sourced replay for disaster recovery
   (e.g. rebuild a read model from the event log).
3. More than one consumer group needs to independently process the same
   stream of events (e.g. real-time fraud detection + batch analytics
   over the same `agent.tool_called` topic).
4. Audit/compliance requires a tamper-evident append-only log that is
   separate from the OLTP `audit_logs` table. (Note: as of FIX D-07,
   `audit_logs` is the durable source of truth and is archived to
   S3/MinIO for 7-year ISO 27001 retention — so this criterion is not
   currently met.)

When re-evaluating, the rollout plan MUST include:

- Adding `aiokafka` (or chosen client) to every service's
  `requirements.txt` that publishes or consumes.
- A Kafka broker (and ZooKeeper / KRaft controller) in
  `docker-compose.yml` and in the production Helm chart.
- An ops runbook for partition rebalancing, consumer-group lag
  monitoring, and broker failure.
- An SLO for end-to-end event delivery latency.
- Setting `EVENT_BUS_BACKEND=kafka` in the production environment files.

Until ALL of the above are done, ADR-004 remains Superseded and the
in-memory bus is the documented, accepted decision.

## Alternatives considered

1. **Kafka (ADR-004):** Mandated but never implemented. Superseded by
   this ADR. Re-evaluation criteria above.
2. **NATS JetStream:** Lighter-weight than Kafka, supports durable
   streams. Rejected for now because the platform does not currently
   have a durable-streaming need that justifies ANY new infrastructure.
   Re-evaluate alongside Kafka when the criteria above are met.
3. **Redis Streams:** Already have Redis in the stack (used by the
   AuditLogger cache). Could provide durable-ish delivery with consumer
   groups. Rejected because Redis is configured for cache eviction, not
   durability — using it as an event log would conflate two failure
   modes (cache evictions would silently drop events). If we need a
   durable log we should use a real durable log (Kafka/NATS/Redpanda),
   not Redis.
4. **Postgres LISTEN/NOTIFY:** Already have Postgres. Would give us
   cross-process fan-out without new infra. Rejected because NOTIFY
   messages are not durable (lost on restart if no listener is
   attached) and the payload size is capped at 8 KB. Suitable as a
   low-latency hint on top of the polling-based fallback, but not as a
   primary bus.

## Reference

- EventBus implementation:
  [`packages/common/event_bus/__init__.py`](../../packages/common/event_bus/__init__.py)
- Superseded ADR: [ADR-004](004-adopt-kafka-event-bus.md)
- Related fix: FIX D-07 (durable audit log to Postgres + S3 archive —
  reduces the urgency of a durable event bus for audit use cases).
