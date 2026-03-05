# TOOLS.md — btcopilot Development Tools

## Production Database Sync

Pull the production database to your local Docker postgres for testing.

### Prerequisites

- SSH key configured for `root@107.170.236.117` (production VPS)
- Local Docker postgres running: `docker compose -f ~/.openclaw/workspace-hurin/theapp/fdserver/docker-compose.yml up fd-postgres -d`

### Quick Start

```bash
# From btcopilot repo root:

# See what would happen (no changes):
./scripts/sync-prod-db.sh --dry-run

# Full sync (dumps prod, backs up local, restores):
./scripts/sync-prod-db.sh

# Download dump only (no local restore):
./scripts/sync-prod-db.sh --dump-only

# Restore from a previous dump:
./scripts/sync-prod-db.sh --restore ~/.openclaw/backups/prod_20260304_120000.pgdump
```

### What It Does

1. **Preflight**: Verifies SSH access and both postgres instances are reachable
2. **Dump**: Runs `pg_dump -Fc` inside the production Docker container, streams to `~/.openclaw/backups/`
3. **Backup**: Saves current local database before overwriting
4. **Restore**: Drops and recreates local `familydiagram` database, runs `pg_restore`
5. **Verify**: Shows row counts for top tables

### After Syncing

Restart the Flask dev server so it picks up the new data. The connection string (`postgresql://familydiagram:pks@localhost:5432/familydiagram`) stays the same.

### Backups

All dumps are stored in `~/.openclaw/backups/` with timestamps:
- `prod_YYYYMMDD_HHMMSS.pgdump` — production dumps
- `local_backup_YYYYMMDD_HHMMSS.pgdump` — local backups taken before restore

Clean up old dumps periodically:
```bash
ls -lh ~/.openclaw/backups/
```

### Troubleshooting

| Problem | Fix |
|---------|-----|
| SSH timeout | Verify key: `ssh root@107.170.236.117 echo ok` |
| Local container not running | `docker compose -f ~/.openclaw/workspace-hurin/theapp/fdserver/docker-compose.yml up fd-postgres -d` |
| pg_restore warnings | Normal — warns about missing extensions/roles but data restores correctly |
| Flask errors after restore | Check if Alembic migrations are ahead of prod: `alembic current` |
