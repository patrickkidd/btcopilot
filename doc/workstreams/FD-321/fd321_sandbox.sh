#!/bin/bash
# FD-321 sandbox controller for the human walkthrough.
# Subcommands: up | state | relaunch-personal | down
# Independent SQLite server on 62090 (no Docker; no postgres/redis) that survives
# app restarts, plus the Personal and Pro apps against it. State lives in $DBDIR.
set -uo pipefail

PORT=62090
DBDIR=/tmp/fd321_walkdb
EMAIL="patrick+fd321walk@example.com"
PY=/Users/patrick/theapp/.venv/bin/python
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WT=/Users/patrick/worktrees/FD-321
SRV="http://127.0.0.1:$PORT"

start_server() {
  rm -rf "$DBDIR"; mkdir -p "$DBDIR"
  ( cd "$WT" && FLASK_CONFIG=development FLASK_AUTO_AUTH_USER="$EMAIL" PYTHONUNBUFFERED=1 \
      uv run python familydiagram/mcpserver/ephemeral_server.py --port "$PORT" --db-dir "$DBDIR" \
      >/tmp/fd321_server.log 2>&1 & )
  for _ in $(seq 1 60); do curl -s "$SRV/test/health" >/dev/null 2>&1 && break; sleep 1; done
  "$PY" - <<EOF
import requests
from pkdiagram import util
requests.post("$SRV/test/seed", json={"users":[{"username":"$EMAIL","password":"test","status":"confirmed"}],"hardware_uuid":util.HARDWARE_UUID}, timeout=10)
print("server up + seeded on $PORT")
EOF
}

launch() { ( cd "$WT/familydiagram" && nohup "$PY" -u "$HERE/fd321_app.py" "$1" "$SRV" >/tmp/fd321_$1.log 2>&1 & ); }

case "${1:-}" in
  up)   start_server; launch personal; launch pro; sleep 12; echo "sandbox up: Personal + Pro windows against $SRV" ;;
  relaunch-personal) launch personal; sleep 10; echo "Personal app relaunched against $SRV (state preserved)" ;;
  state)
    "$PY" - <<EOF
import sys, sqlite3, pickle
try:
    from PyQt5 import sip as _s; sys.modules['sip']=_s
except Exception: pass
c=sqlite3.connect("$DBDIR/test.db")
u=c.execute("SELECT first_name,last_name FROM users WHERE id=1").fetchone()
print("ACCOUNT NAME:", (u or ('',''))[0], (u or ('',''))[1])
d=c.execute("SELECT data FROM diagrams WHERE id=1").fetchone()
ppl=[]
if d and d[0]:
    data=pickle.loads(d[0]); ppl=[(p.get('name'),'primary' if p.get('primary') else '') for p in (data.get('people') or [])]
print("DIAGRAM NODE(S):", ppl or "(none)")
EOF
    ;;
  down) pkill -f "m pkdiagram" 2>/dev/null; pkill -f "ephemeral_server.py" 2>/dev/null; rm -rf "$DBDIR"; echo "sandbox down + scratch removed" ;;
  *) echo "usage: fd321_sandbox.sh up|state|relaunch-personal|down"; exit 2 ;;
esac
