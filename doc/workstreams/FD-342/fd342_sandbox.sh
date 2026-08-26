#!/bin/bash
# FD-342 sandbox: prod copy of diagram 1924 on an independent SQLite server (8889), Personal app against it.
# Subcommands: up | reseed | relaunch [personal|pro] | license | down
set -uo pipefail
PORT=8889
TMP=/Users/patrick/.claude/jobs/ab4beafd/tmp
DBDIR=$TMP/fd342_db
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BT=/Users/patrick/theapp/btcopilot/.claude/worktrees/FD-342
FDS=/Users/patrick/theapp/fdserver/.claude/worktrees/FD-342
FDG=/Users/patrick/theapp/familydiagram/.claude/worktrees/FD-342
ENV=/Users/patrick/theapp/.env
SRV="http://127.0.0.1:$PORT"
LOG=$TMP/fd342_server.log
REDIS_PORT=6390
BROKER="redis://127.0.0.1:$REDIS_PORT/0"

seed() {
  rm -rf "$DBDIR"; mkdir -p "$DBDIR"
  ( cd "$BT" && PYTHONPATH="$BT" uv run --directory /Users/patrick/theapp --env-file "$ENV" python "$HERE/fd342_seed.py" "$DBDIR" "$HERE/prod_diagram_1924.json" )
}
start_server() {
  ( redis-server --port $REDIS_PORT --save "" --appendonly no --dir "$TMP" >"$TMP/fd342_redis.log" 2>&1 </dev/null & )
  ( cd "$BT" && PYTHONPATH="$BT:$HERE" FLASK_CONFIG=development FLASK_AUTO_AUTH_USER=patrick@alaskafamilysystems.com \
      FDSERVER_PROMPTS_PATH="$FDS/prompts/private_prompts.py" PYTHONUNBUFFERED=1 \
      uv run --directory /Users/patrick/theapp --env-file "$ENV" python "$HERE/fd342_stack.py" server --port "$PORT" --db-dir "$DBDIR" --broker "$BROKER" >"$LOG" 2>&1 </dev/null & )
  ( cd "$BT" && PYTHONPATH="$BT:$HERE" FLASK_CONFIG=development FD342_DB_DIR="$DBDIR" FD342_BROKER="$BROKER" \
      FDSERVER_PROMPTS_PATH="$FDS/prompts/private_prompts.py" PYTHONUNBUFFERED=1 \
      uv run --directory /Users/patrick/theapp --env-file "$ENV" python -m celery -A fd342_stack:celery worker --pool=solo --loglevel=info >"$TMP/fd342_worker.log" 2>&1 </dev/null & )
  for _ in $(seq 1 60); do curl -s "$SRV/test/health" >/dev/null 2>&1 && break; sleep 1; done
  curl -s "$SRV/test/health" >/dev/null && echo "server up on $PORT (log: $LOG)" || { echo "server FAILED"; tail -20 "$LOG"; exit 1; }
}
license() { ( cd "$BT" && PYTHONPATH="$BT:$FDG" uv run --directory /Users/patrick/theapp --env-file "$ENV" python "$HERE/fd342_license.py" "$DBDIR" ); }
launch() {
  ( cd "$FDG" && PYTHONPATH="$FDG" nohup uv run --directory /Users/patrick/theapp --env-file "$ENV" python -u "$HERE/fd342_app.py" "$1" "$SRV" >"$TMP/fd342_$1.log" 2>&1 </dev/null & )
}
stop() {
  pkill -f "m pkdiagram" 2>/dev/null
  pkill -f "fd342_stack.py server --port $PORT" 2>/dev/null
  pkill -f "celery -A fd342_stack" 2>/dev/null
  pkill -f "redis-server --port $REDIS_PORT" 2>/dev/null
  sleep 1
}

case "${1:-}" in
  up)       stop; seed; license; start_server; launch personal; launch pro; sleep 12; echo "Personal + Pro launched against $SRV" ;;
  reseed)   stop; seed; license; start_server; echo "reseeded from prod export; server up" ;;
  license)  stop; license; start_server ;;
  relaunch) launch "${2:-personal}"; sleep 10; echo "${2:-personal} app relaunched (server state preserved)" ;;
  down)     stop; echo "sandbox down (db kept at $DBDIR)" ;;
  *) echo "usage: fd342_sandbox.sh up|reseed|relaunch [personal|pro]|license|down"; exit 2 ;;
esac
