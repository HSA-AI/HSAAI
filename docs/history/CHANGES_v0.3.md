# HSAAI v0.3.0 — Agent Civilization + CDC + Wisdom Marketplace + Evolution + Federation

> **3 new packages + 3 new services + Agent Civilization activation + multi_agents upgrade**

## New Packages (3)

| Package | Purpose |
|---------|---------|
| `cdc_adapters` | SAP/Salesforce/IoT Change Data Capture → Consciousness Stream |
| `a2a_protocol` | Agent-to-Agent communication bus (task delegation + queries) |
| `federation` | Cross-organization intelligence sharing mesh (subsidiary/partner/external) |

## New Services (3)

| Service | Port | Purpose |
|---------|------|---------|
| `wisdom_marketplace` | 8074 | Trade Wisdom Crystals between organizations |
| `evolution_engine` | 8075 | Autonomous self-improvement (detect→hypothesize→test→deploy) |
| `federation_hub` | 8076 | Cross-org intelligence mesh + trust management |

## Upgrades

### multi_agents/main.py — Full Agent Civilization
- **Agent Civilization mode** (default): Supervisor decomposes task → selects agents → parallel execution → conflict resolution → synthesis
- **A2A Protocol**: agents communicate via A2A messages during execution
- **Constitutional enforcement**: every agent action checked against AI Constitution
- **Wisdom lookup**: checks applicable Wisdom Crystals BEFORE deciding
- **Failure Memory**: checks past failures BEFORE deciding ("Have we failed at something similar?")
- **Legacy fallback**: v0.1 mode still available (`use_civilization: false`)
- New endpoints: `/v1/civilization/agents`, `/v1/a2a/messages`, `/v1/failure/record`, `/v1/wisdom/list`

## Architecture Summary

v0.1: 12 services (reactive, fixed bugs)
v0.2: 16 services (proactive, added consciousness + causal + twin + economy)
v0.3: 19 services (civilized, evolved, federated)

Total packages: 38
Total services: 19
Total LoC new: ~2,500

## Quick Start

```bash
docker compose up -d --build

# Verify new services
curl http://localhost:8074/health  # wisdom_marketplace
curl http://localhost:8075/health  # evolution_engine
curl http://localhost:8076/health  # federation_hub

# Test Agent Civilization
curl -X POST http://localhost:8040/v1/run \
  -H "Content-Type: application/json" \
  -d '{"message": "Should we diversify tuna suppliers?", "use_civilization": true}'

# List civilization agents
curl http://localhost:8040/v1/civilization/agents

# Browse Wisdom Marketplace
curl http://localhost:8074/v1/browse
```
