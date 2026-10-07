#!/bin/sh
# The laptop's one ssh connection to the box (doc/MONITORING.md): Postgres
# forwarded here, the laptop stores forwarded to the box's docker0 address,
# and every minute the journal after the saved cursor posted to VictoriaLogs.
# The cursor moves only after VictoriaLogs answers 200.
set -u
KEY=/link/id_ed25519
CURSOR=/link/cursor
CTL=/tmp/box.ctl
BATCH=/tmp/batch
SSH="ssh -T -i $KEY -o BatchMode=yes -o UserKnownHostsFile=/link/known_hosts -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes"

tunnel() {
  while true; do
    $SSH -M -S "$CTL" -N -o GatewayPorts=yes \
      -L 0.0.0.0:15432:127.0.0.1:5432 \
      -R 172.17.0.1:18428:vm:8428 \
      -R 172.17.0.1:14318:vt:10428 \
      "$FD_BOX"
    echo "link down, reconnecting in 10s"
    sleep 10
  done
}

pull() {
  while true; do
    sleep 60
    [ -S "$CTL" ] || continue
    $SSH -S "$CTL" "$FD_BOX" "$(cat "$CURSOR" 2>/dev/null)" > "$BATCH" || continue
    next=$(grep -a '^__CURSOR=' "$BATCH" | tail -n 1 | cut -d= -f2-)
    [ -n "$next" ] || continue
    curl -sf -H 'Content-Type: application/vnd.fdo.journal' --data-binary @"$BATCH" \
      http://vl:9428/insert/journald/upload || continue
    printf '%s' "$next" > "$CURSOR.new" && mv "$CURSOR.new" "$CURSOR"
    echo "pulled $(grep -ac '^__CURSOR=' "$BATCH") journal entries"
  done
}

tunnel &
pull
