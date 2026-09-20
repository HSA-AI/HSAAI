# Rollback Plan

- Keep previous Docker image tag.
- Keep last known working `.env` backup.
- Restore PostgreSQL/Qdrant from protected snapshots.
- Re-run smoke tests before re-opening user access.
