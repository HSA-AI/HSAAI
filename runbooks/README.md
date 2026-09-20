# Operational Runbooks

This directory contains operational runbooks for common HSAAI operational scenarios.

## Runbook Index

| # | Title | Trigger |
|---|-------|---------|
| [01](RUNBOOK-01-postgres-down.md) | PostgreSQL is Down | `/health` returns `database: error` |
| [02](RUNBOOK-02-qdrant-down.md) | Qdrant is Down | RAG search returns 503 |
| [03](RUNBOOK-03-keycloak-down.md) | Keycloak is Down | Login returns 503 |
| [04](RUNBOOK-04-ollama-down.md) | Ollama (LLM) is Down | LLM generation returns 502 |
| [05](RUNBOOK-05-redis-down.md) | Redis is Down | Rate limiting fails open |
| [06](RUNBOOK-06-high-error-rate.md) | High Error Rate (>5%) | Alertmanager fires |
| [07](RUNBOOK-07-disk-full.md) | Disk Full Alert | Prometheus alert |
| [08](RUNBOOK-08-backup-restore.md) | Database Restore Procedure | Disaster recovery |
| [09](RUNBOOK-09-pkce-flow-broken.md) | PKCE Flow Broken | Login returns 400 |
| [10](RUNBOOK-10-tenant-isolation-breach.md) | Tenant Isolation Breach Suspected | Security incident |

## How to Use a Runbook

1. Identify the alert trigger
2. Find the matching runbook
3. Follow the steps in order
4. Document any deviations in the incident ticket
5. After resolution, do a post-mortem if the runbook was insufficient

## Runbook Format

Each runbook follows this template:

```
# RUNBOOK-NN: Title

## Trigger
What alert or symptom indicates this issue

## Impact
What's affected and how severely

## Diagnosis
How to confirm the issue (commands to run, logs to check)

## Immediate Actions
Step-by-step actions to stabilize

## Root Cause Analysis
How to find the underlying cause

## Long-term Fixes
What to do to prevent recurrence

## Escalation
Who to contact if runbook is insufficient
```
