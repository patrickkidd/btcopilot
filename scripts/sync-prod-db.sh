#!/usr/bin/env bash
#
# sync-prod-db.sh — Pull production database to local Docker postgres
#
# Usage:
#   ./scripts/sync-prod-db.sh              # Full sync (with confirmation)
#   ./scripts/sync-prod-db.sh --dry-run    # Show what would happen
#   ./scripts/sync-prod-db.sh --dump-only  # Download dump but don't restore
#   ./scripts/sync-prod-db.sh --restore <file>  # Restore from existing dump
#
# Prerequisites:
#   - SSH access to production server (root@107.170.236.117)
#   - Local Docker postgres running (fd-postgres container)
#

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────

PROD_HOST="107.170.236.117"
PROD_USER="root"
PROD_CONTAINER="fd-postgres"
PROD_DB_USER="familydiagram"
PROD_DB_NAME="familydiagram"

LOCAL_CONTAINER="fd-postgres"
LOCAL_DB_USER="familydiagram"
LOCAL_DB_NAME="familydiagram"

BACKUP_DIR="${HOME}/.openclaw/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="${BACKUP_DIR}/prod_${TIMESTAMP}.pgdump"

# ── Helpers ─────────────────────────────────────────────────────────────────

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }

die() { red "ERROR: $*" >&2; exit 1; }

check_local_postgres() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${LOCAL_CONTAINER}$"; then
        die "Local container '${LOCAL_CONTAINER}' is not running. Start it with: docker compose up fd-postgres -d"
    fi
    green "✓ Local postgres container is running"
}

check_ssh() {
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${PROD_USER}@${PROD_HOST}" "echo ok" &>/dev/null; then
        die "Cannot SSH to ${PROD_USER}@${PROD_HOST}. Check your SSH keys."
    fi
    green "✓ SSH connection to production OK"
}

check_prod_postgres() {
    if ! ssh "${PROD_USER}@${PROD_HOST}" "docker exec ${PROD_CONTAINER} pg_isready -U ${PROD_DB_USER}" &>/dev/null; then
        die "Production postgres is not ready"
    fi
    green "✓ Production postgres is ready"
}

show_prod_stats() {
    bold "Production database stats:"
    ssh "${PROD_USER}@${PROD_HOST}" "docker exec ${PROD_CONTAINER} psql -U ${PROD_DB_USER} -d ${PROD_DB_NAME} -c \"
        SELECT schemaname, relname AS table, n_live_tup AS row_count
        FROM pg_stat_user_tables
        ORDER BY n_live_tup DESC
        LIMIT 15;
    \""
}

show_local_stats() {
    bold "Local database stats:"
    docker exec "${LOCAL_CONTAINER}" psql -U "${LOCAL_DB_USER}" -d "${LOCAL_DB_NAME}" -c "
        SELECT schemaname, relname AS table, n_live_tup AS row_count
        FROM pg_stat_user_tables
        ORDER BY n_live_tup DESC
        LIMIT 15;
    "
}

dump_prod() {
    mkdir -p "${BACKUP_DIR}"
    bold "Dumping production database..."
    yellow "  → ${DUMP_FILE}"

    ssh "${PROD_USER}@${PROD_HOST}" \
        "docker exec ${PROD_CONTAINER} pg_dump -U ${PROD_DB_USER} -Fc ${PROD_DB_NAME}" \
        > "${DUMP_FILE}"

    local size
    size=$(du -h "${DUMP_FILE}" | cut -f1)
    green "✓ Dump complete (${size})"
}

backup_local() {
    local backup="${BACKUP_DIR}/local_backup_${TIMESTAMP}.pgdump"
    bold "Backing up local database first..."
    yellow "  → ${backup}"

    docker exec "${LOCAL_CONTAINER}" \
        pg_dump -U "${LOCAL_DB_USER}" -Fc "${LOCAL_DB_NAME}" \
        > "${backup}"

    local size
    size=$(du -h "${backup}" | cut -f1)
    green "✓ Local backup saved (${size})"
}

restore_to_local() {
    local dump_path="$1"

    if [ ! -f "${dump_path}" ]; then
        die "Dump file not found: ${dump_path}"
    fi

    bold "Restoring to local database..."
    yellow "  ← ${dump_path}"

    # Drop and recreate database
    docker exec "${LOCAL_CONTAINER}" psql -U "${LOCAL_DB_USER}" -d postgres -c "
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '${LOCAL_DB_NAME}' AND pid <> pg_backend_pid();
    " &>/dev/null || true

    docker exec "${LOCAL_CONTAINER}" dropdb -U "${LOCAL_DB_USER}" --if-exists "${LOCAL_DB_NAME}"
    docker exec "${LOCAL_CONTAINER}" createdb -U "${LOCAL_DB_USER}" "${LOCAL_DB_NAME}"

    # Restore
    docker exec -i "${LOCAL_CONTAINER}" \
        pg_restore -U "${LOCAL_DB_USER}" -d "${LOCAL_DB_NAME}" --no-owner --no-privileges \
        < "${dump_path}" || true
    # pg_restore returns non-zero on warnings (e.g., missing extensions), which is OK

    green "✓ Restore complete"
}

# ── Main ────────────────────────────────────────────────────────────────────

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Pull production database to local Docker postgres for testing.

Options:
  --dry-run         Show what would happen without doing it
  --dump-only       Download dump file but don't restore locally
  --restore <file>  Restore from an existing dump file (skip SSH)
  -h, --help        Show this help

Backups are stored in: ${BACKUP_DIR}/
EOF
}

main() {
    local dry_run=false
    local dump_only=false
    local restore_file=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)    dry_run=true; shift ;;
            --dump-only)  dump_only=true; shift ;;
            --restore)    restore_file="$2"; shift 2 ;;
            -h|--help)    usage; exit 0 ;;
            *)            die "Unknown option: $1" ;;
        esac
    done

    bold "═══════════════════════════════════════"
    bold "  Production → Local Database Sync"
    bold "═══════════════════════════════════════"
    echo

    # ── Restore-only mode ──
    if [[ -n "${restore_file}" ]]; then
        check_local_postgres
        echo
        yellow "Restoring from: ${restore_file}"
        yellow "This will DESTROY the local '${LOCAL_DB_NAME}' database and replace it."
        echo
        read -rp "Continue? [y/N] " confirm
        [[ "${confirm}" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }
        echo
        backup_local
        restore_to_local "${restore_file}"
        echo
        show_local_stats
        echo
        green "Done. Restart the Flask server to pick up the new data."
        exit 0
    fi

    # ── Preflight checks ──
    bold "Preflight checks..."
    if [[ "${dry_run}" == true ]]; then
        yellow "(DRY RUN — no changes will be made)"
        echo
    fi

    check_ssh
    check_prod_postgres

    if [[ "${dump_only}" == false ]]; then
        check_local_postgres
    fi
    echo

    # ── Show prod stats ──
    show_prod_stats
    echo

    if [[ "${dry_run}" == true ]]; then
        yellow "DRY RUN complete. Would do:"
        echo "  1. pg_dump from ${PROD_HOST}:${PROD_CONTAINER} → ${DUMP_FILE}"
        if [[ "${dump_only}" == false ]]; then
            echo "  2. Backup local DB → ${BACKUP_DIR}/local_backup_${TIMESTAMP}.pgdump"
            echo "  3. Drop & recreate local '${LOCAL_DB_NAME}'"
            echo "  4. pg_restore dump into local"
        fi
        exit 0
    fi

    # ── Confirmation ──
    if [[ "${dump_only}" == false ]]; then
        echo
        yellow "This will:"
        echo "  1. Download production database dump"
        echo "  2. DESTROY the local '${LOCAL_DB_NAME}' database"
        echo "  3. Replace it with production data"
        echo
        read -rp "Continue? [y/N] " confirm
        [[ "${confirm}" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }
        echo
    fi

    # ── Execute ──
    dump_prod

    if [[ "${dump_only}" == true ]]; then
        echo
        green "Dump saved to: ${DUMP_FILE}"
        echo "To restore later: $(basename "$0") --restore ${DUMP_FILE}"
        exit 0
    fi

    echo
    backup_local
    echo
    restore_to_local "${DUMP_FILE}"
    echo
    show_local_stats
    echo
    green "Done. Restart the Flask server to pick up the new data."
}

main "$@"
