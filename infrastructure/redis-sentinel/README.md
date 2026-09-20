# HSAAI Redis Sentinel HA (v3.0)

3-node Redis Sentinel cluster for HA + automatic failover.

## Architecture

```
                    ┌──────────────────┐
                    │   HSAAI Services │
                    │  (backend_core,  │
                    │   auth_service,  │
                    │   model_training)│
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Sentinel-aware  │
                    │  Redis Client    │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │ Redis 1 │◄───────►│ Redis 2 │◄───────►│ Redis 3 │
   │(master) │  repl   │(replica)│  repl   │(replica)│
   └────┬────┘         └─────────┘         └─────────┘
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │Sentinel1│◄───────►│Sentinel2│◄───────►│Sentinel3│
   │  :26379 │         │  :26379 │         │  :26379 │
   └─────────┘         └─────────┘         └─────────┘
```

## Deployment

```bash
REDIS_PASSWORD=strong-pass docker compose -f infrastructure/redis-sentinel/docker-compose.sentinel.yml up -d

# Verify master
redis-cli -h sentinel1 -p 26379 sentinel get-master-addr-by-name hsaai-redis
```

## Failover

- Sentinel quorum: 2/3 (survives 1 node loss)
- Down-after-milliseconds: 5000 (5s unresponsive = marked down)
- Failover-timeout: 30000 (30s max failover)
- Parallel-syncs: 1 (one replica at a time re-syncs to new master)

## Client Configuration

Clients must connect via Sentinel, not directly to Redis:
```python
import redis.sentinel
sentinel = redis.sentinel.Sentinel(
    [("sentinel1", 26379), ("sentinel2", 26379), ("sentinel3", 26379)],
    socket_timeout=0.5,
    password="your-redis-password",
    sentinel_kwargs={"password": "your-sentinel-password"},
)
master = sentinel.master("hsaai-redis")
replica = sentinel.slave("hsaai-redis")
```
