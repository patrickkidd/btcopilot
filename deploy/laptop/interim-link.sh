#!/bin/sh
# Until the box has the fdlink user: forwards laptop 127.0.0.1:15432 to fd-postgres
# over Patrick's own root ssh, so the Postgres dashboards work. Stop it before
# starting fd-link, which takes the same port; the data source does not change.
#   nohup deploy/laptop/interim-link.sh > ~/fd-monitoring/interim-link.log 2>&1 &
set -u
BOX="${FD_BOX_ADMIN:-familydiagram}"
SSH="ssh -o User=root -o BatchMode=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3"

while true; do
  ip=$($SSH "$BOX" "docker inspect fd-postgres --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'")
  if [ -n "$ip" ]; then
    $SSH -N -o ExitOnForwardFailure=yes -L "127.0.0.1:15432:$ip:5432" "$BOX"
  fi
  echo "$(date -u +%FT%TZ) interim link down, reconnecting in 10s"
  sleep 10
done
