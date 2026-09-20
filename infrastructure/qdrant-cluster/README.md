# HSAAI Qdrant Clustering (v3.0)

3-node Qdrant cluster with sharding (4 shards) and replication (factor 2).

## Architecture

```
                    ┌──────────────────┐
                    │   HSAAI Services │
                    │  (rag_engine,    │
                    │   backend_core)  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Nginx LB        │
                    │   :6333          │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         └────▼────┐
   │Qdrant 1 │◄───────►│Qdrant 2 │◄───────►│Qdrant 3 │
   │(seed)   │  gossip │         │  gossip │         │
   └─────────┘         └─────────┘         └─────────┘
```

## Deployment

```bash
docker compose -f infrastructure/qdrant-cluster/docker-compose.cluster.yml up -d
curl http://localhost:6333/cluster  # verify
```

## Sharding Strategy

- `shard_number: 4` — vectors distributed across 4 shards
- `replication_factor: 2` — each shard has 2 copies on different nodes
- `write_consistency_factor: 2` — strong consistency (survives 1 node loss)
