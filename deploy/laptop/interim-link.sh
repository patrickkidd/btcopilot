#!/bin/sh
# Until the box has the fdlink user: forwards port 15432 to fd-postgres over
# Patrick's own root ssh, so the Postgres dashboards work. Run by the fd-pg-interim
# service; fd-link replaces it on the same port and the data source does not change.
set -u
BOX="${FD_BOX_ADMIN:-familydiagram}"
LISTEN="${LISTEN:-127.0.0.1}"
SSH="ssh -o User=root -o BatchMode=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3"

while true; do
  ip=$($SSH "$BOX" "docker inspect fd-postgres --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'")
  if [ -n "$ip" ]; then
    $SSH -N -o ExitOnForwardFailure=yes -L "$LISTEN:15432:$ip:5432" "$BOX"
  fi
  echo "$(date -u +%FT%TZ) interim link down, reconnecting in 10s"
  sleep 10
done
