#!/bin/sh
# The laptop's one ssh connection to the box (doc/MONITORING.md): Postgres
# forwarded here, the laptop stores forwarded to the box's docker0 address,
# and every minute the journal after the saved cursor posted to VictoriaLogs.
# The cursor moves only after VictoriaLogs answers 200. With no usable cursor
# nothing is pulled until approve-repull exists, since the box would send 30 days.
set -u
DIR=${LINK_DIR:-/link}
TMP=${LINK_TMP:-/tmp}
KEY=$DIR/id_ed25519
CURSOR=$DIR/cursor
APPROVE=$DIR/approve-repull
HOST='~/fd-monitoring/link'
CTL=$TMP/box.ctl
BATCH=$TMP/batch
ERR=$TMP/err
SSH="ssh -T -i $KEY -o BatchMode=yes -o UserKnownHostsFile=$DIR/known_hosts -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes"

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

valid() {
  case "$1" in *"
"*) return 1 ;; esac
  printf '%s\n' "$1" | grep -Eqx '[a-z]=[0-9a-f]+(;[a-z]=[0-9a-f]+)*'
}

step() {
  cursor=$(cat "$CURSOR" 2>/dev/null)
  if valid "$cursor"; then
    [ -e "$APPROVE" ] && rm -f "$APPROVE" && echo "approve-repull removed unused: the cursor is valid"
  elif [ -e "$APPROVE" ]; then
    echo "re-pull approved: pulling the box's last 30 days once"
    cursor=
  else
    state=missing
    [ -e "$CURSOR" ] && state=corrupt
    echo "JOURNAL PULL STOPPED: the cursor $HOST/cursor is $state, and pulling without it brings the box's last 30 days (about 2 GB). To approve that once: touch $HOST/approve-repull"
    return
  fi
  $SSH -S "$CTL" "$FD_BOX" "$cursor" > "$BATCH" 2> "$ERR"
  rc=$?
  [ $rc -eq 255 ] && return
  if [ $rc -ne 0 ]; then
    mv "$CURSOR" "$CURSOR.refused"
    echo "JOURNAL PULL STOPPED: the box refused the cursor (exit $rc): $(cat "$ERR"); moved it to $HOST/cursor.refused"
    return
  fi
  [ -z "$cursor" ] && rm -f "$APPROVE"
  next=$(grep -a '^__CURSOR=' "$BATCH" | tail -n 1 | cut -d= -f2-)
  [ -n "$next" ] || return
  curl -sf -H 'Content-Type: application/vnd.fdo.journal' --data-binary @"$BATCH" \
    http://vl:9428/insert/journald/upload || return
  printf '%s' "$next" > "$CURSOR.new" && sync "$CURSOR.new" && mv "$CURSOR.new" "$CURSOR" && sync "$DIR"
  echo "pulled $(grep -ac '^__CURSOR=' "$BATCH") journal entries"
}

pull() {
  while true; do
    sleep 60
    [ -S "$CTL" ] || continue
    step
  done
}

if [ "${1:-}" = once ]; then
  step
  exit
fi
tunnel &
pull
