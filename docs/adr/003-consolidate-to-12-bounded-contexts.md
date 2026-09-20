# ADR-003: Consolidate 29 Services to 12 Bounded Contexts

**Status:** Accepted
**Date:** 2026-07-04
**Decider:** Architecture Team

## Context
HSAAI currently has 29 microservices averaging 760 lines of Python.
This decomposition does not align with bounded contexts:
- Service boundaries follow capability (rag, agents, memory)
  rather than domain (procurement, compliance, knowledge)
- Cross-cutting changes require coordination across many services
- Duplication exists: rag_engine + rag_v2, multi_agents + agent_runtime_v2

## Decision
Consolidate to 12 bounded contexts aligned with HSA business domains:
1. Identity (auth, users, tenants)
2. Knowledge (documents, RAG, knowledge graph)
3. Agents (agent runtime, agent studio, memory)
4. Workflow (workflow engine, automation)
5. Governance (policies, compliance, audit)
6. Integration (connectors, MCP tools)
7. Observability (metrics, logs, traces, SLOs)
8. ML Ops (training, evaluation, registry)
9. Cost (attribution, budgeting, optimization)
10. Search (enterprise search, semantic search)
11. Conversation (chat, sessions, history)
12. Admin (administration, configuration)

## Consequences
- **Positive:** Clearer ownership, fewer cross-service calls, less
  duplication, easier onboarding.
- **Negative:** Larger services are harder to deploy independently.
  Risk of "distributed monolith" if not disciplined.
- **Mitigation:** Each context has internal modules with clear
  boundaries. Module-level deployment via feature flags.

## Migration Strategy
Use the Strangler Fig pattern:
1. Deploy new aggregated service alongside old services
2. Route 5% of traffic to new service
3. Monitor for 1 week
4. If clean, increase to 25%, 50%, 100% over 2 weeks
5. Decommission old services

## Alternatives Considered
1. **Keep 29 services:** Operational overhead exceeds benefits. Rejected.
2. **Single monolith:** Loses independent scaling. Rejected.
3. **Service-per-feature:** Too granular. Rejected.

## References
- Domain-Driven Design (Evans, 2003)
- Strangler Fig pattern: https://martinfowler.com/bliki/StranglerFigApplication.html
