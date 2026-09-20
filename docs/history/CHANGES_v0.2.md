# HSAAI v0.2.0 — Super Intelligence Layers

> **8 new packages + 4 new services + Agent Civilization upgrade**

## New Packages (8)

| Package | Purpose |
|---------|---------|
| `causal_intelligence` | Why/What will/What should/Counterfactual (Pearl's do-calculus) |
| `wisdom` | Wisdom Crystallization + Failure Memory (T7+T8) |
| `constitution` | AI Constitution — inline ethical enforcement |
| `reasoning` | 6-mode hybrid reasoning with mandatory verification |
| `consciousness` | Enterprise Consciousness Stream + Salience scoring |
| `proactive` | Anomaly detection + Opportunity discovery + Risk prediction |
| `twin` | Digital Twin — Monte Carlo + agent-based simulation |
| `intelligence_economy` | Intelligence value measurement (6 dimensions) |

## New Services (4)

| Service | Port | Purpose |
|---------|------|---------|
| `consciousness_stream` | 8070 | Real-time enterprise event ingestion |
| `proactive_intelligence` | 8071 | Proactive alerts (anomaly/opportunity/risk) |
| `digital_twin` | 8072 | "What happens if?" simulation |
| `intelligence_economy` | 8073 | Intelligence balance sheet |

## Upgrades

- `multi_agents/agent_civilization.py` — 12 enterprise agents + Chief Intelligence Supervisor
- `multi_agents/main.py` — v0.1 fixes (reflection + preferred_agent) retained

## Architecture Change

v0.1: 12 services (reactive)
v0.2: 16 services (proactive + causal + evolutionary)

The enterprise is no longer "blind" between queries — the Consciousness
Stream sees everything, the Proactive Intelligence discovers opportunities,
the Digital Twin simulates futures, and the Intelligence Economy measures
the value of it all.

## New Dependencies

```bash
pip install numpy  # for causal_intelligence statistical computations
```

## Quick Start

```bash
# Deploy all 16 services
docker compose up -d --build

# Verify new services
curl http://localhost:8070/health  # consciousness_stream
curl http://localhost:8071/health  # proactive_intelligence
curl http://localhost:8072/health  # digital_twin
curl http://localhost:8073/health  # intelligence_economy
```
