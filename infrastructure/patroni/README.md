# HSAAI PostgreSQL HA via Patroni (v3.0)

This directory contains Patroni configuration for PostgreSQL High Availability.

## Architecture

```
                    ┌──────────────────┐
                    │   PgBouncer      │
                    │ (connection pool)│
                    │   :5432          │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   HAProxy        │
                    │ (read/write split)│
                    │   :5430 (write)  │
                    │   :5431 (read)   │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │Patroni 1│◄───────►│Patroni 2│◄───────►│Patroni 3│
   │(leader) │  etcd   │(replica)│  etcd   │(replica)│
   │ PG 16   │         │ PG 16   │         │ PG 16   │
   └─────────┘         └─────────┘         └─────────┘
        │                    │                    │
        └────────────────────┴────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │      etcd        │
                    │  (cluster state) │
                    └──────────────────┘
```

## Components

- **3 Patroni nodes**: 1 leader (read/write) + 2 replicas (read-only)
- **etcd**: Distributed configuration store for cluster state
- **HAProxy**: Load balancer with read/write split
- **PgBouncer**: Connection pooling (transaction mode)

## Deployment

```bash
# Start the HA cluster
docker compose -f infrastructure/patroni/docker-compose.ha.yml up -d

# Verify cluster health
docker exec hsaai-patroni1 patronictl list
# Expected output:
# + Cluster: hsaai (1234567890) --+---------+----+-----------+
# | Member       | Host           | Role    | State    | TL | Lag in MB |
# +--------------+----------------+---------+----------+----+-----------+
# | hsaai-pg-1   | 10.0.0.1       | Leader  | running  |  1 |           |
# | hsaai-pg-2   | 10.0.0.2       | Replica | streaming|  1 |         0 |
# | hsaai-pg-3   | 10.0.0.3       | Replica | streaming|  1 |         0 |
# +--------------+----------------+---------+----------+----+-----------+

# Test failover
docker exec hsaai-patroni1 patronictl switchover
```

## Configuration

See:
- `patroni.yml` — Patroni node configuration
- `pgbouncer.ini` — PgBouncer pool configuration
- `haproxy.cfg` — HAProxy load balancer config
- `docker-compose.ha.yml` — Full HA stack

## Backup

Automated backups via `pg_dump` on the leader every 6 hours:
```bash
./backup.sh
```

## Monitoring

Patroni exposes metrics at `:8008/metrics` per node. Prometheus scrapes all 3 nodes.
Alerts:
- `patroni_cluster_unhealthy` — cluster has no leader
- `patroni_replication_lag_high` — replica lag > 60s
- `patroni_node_down` — a node is offline

## Failover Behavior

1. Leader becomes unavailable (crash, network partition)
2. etcd detects leader failure (within 10s)
3. Patroni promotes the most up-to-date replica
4. HAProxy routes writes to the new leader (within 5s)
5. Total RTO: ~15-20 seconds

## Recovery

If all nodes are down:
```bash
# 1. Start etcd first
docker compose -f infrastructure/patroni/docker-compose.ha.yml up -d etcd

# 2. Start Patroni nodes (they'll elect a leader from latest WAL)
docker compose -f infrastructure/patroni/docker-compose.ha.yml up -d patroni1 patroni2 patroni3

# 3. If data corruption, restore from backup
./restore.sh /backups/postgres/latest.dump
```
