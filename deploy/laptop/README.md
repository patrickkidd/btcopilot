# Monitoring on the laptop (FD-374)

The stores and Grafana for the box's metrics, logs and traces, kept with no time
limit under `~/fd-monitoring/` (outside iCloud). Design: `doc/MONITORING.md`.

## Start

```bash
mkdir -p ~/fd-monitoring/{vm,vl,vt,grafana,link}
cp deploy/laptop/.env.example deploy/laptop/.env   # then fill it in
docker compose -f deploy/laptop/compose.yml up -d --build
```

Docker Desktop must be set to start at login; every container restarts by itself.
Grafana is at http://127.0.0.1:3000 (anonymous viewing; `admin` with
`GF_SECURITY_ADMIN_PASSWORD` to edit). Dashboards come from `deploy/grafana/*.json`;
saving in the UI does not change them.

| Service | Port on 127.0.0.1 | Holds |
|---|---|---|
| vm (VictoriaMetrics) | 8428 | host and container metrics |
| vl (VictoriaLogs) | 9428 | the box's journal, every container's log lines |
| vt (VictoriaTraces) | 10428 | the app's traces |
| grafana | 3000 | dashboards |
| fd-pg-interim, later fd-link | 15432 | the box's Postgres, for the four Postgres dashboards |

## The link key

`fd-link` holds one ssh connection to the box with its own key and reconnects when
it drops. Make the key once on the laptop:

```bash
ssh-keygen -t ed25519 -N '' -C fd-link -f ~/fd-monitoring/link/id_ed25519
```

Then put the public key on the box in fdlink's `authorized_keys` with the forced
command and forwarding limits given in `deploy/README.md`. The first connection
records the box's host key in `~/fd-monitoring/link/known_hosts`.

The link carries:
- `-L 15432` to the box's `127.0.0.1:5432` (Postgres);
- `-R 172.17.0.1:18428` to VictoriaMetrics and `-R 172.17.0.1:14318` to
  VictoriaTraces, which the box's collector sends to;
- every minute, the journal after the saved cursor (`~/fd-monitoring/link/cursor`),
  posted to VictoriaLogs. The cursor is saved only after VictoriaLogs answers 200;
  a failed post is pulled again the next minute. A missing, malformed or refused
  cursor stops the pull and logs `JOURNAL PULL STOPPED:` every minute, since with no
  cursor the box sends its last 30 days (about 2 GB). To allow that once:
  `touch ~/fd-monitoring/link/approve-repull` (doc/MONITORING.md, "Reconnects and
  the cursor").

`docker compose -f deploy/laptop/compose.yml logs fd-link` shows each pull.

## Until the box has the fdlink user

The service `fd-pg-interim` (profile `interim`, set by `COMPOSE_PROFILES=interim` in
`deploy/laptop/.env`) forwards `127.0.0.1:15432` to fd-postgres over Patrick's own
root ssh, with `~/.ssh/id_rsa` and `~/.ssh/known_hosts` mounted read-only, and
restarts by itself like the stores. `GRAFANA_PG_PASSWORD` in `deploy/laptop/.env` is
the box's value of the same name in `/etc/fd/secrets.env`.

After the deploy, when fdlink's key is on the box, switch to fd-link on the same
port with no change to the data source:

```bash
sed -i '' 's/^COMPOSE_PROFILES=interim$/COMPOSE_PROFILES=link/' deploy/laptop/.env && docker compose -f deploy/laptop/compose.yml rm -sf fd-pg-interim && docker compose -f deploy/laptop/compose.yml up -d --build
```

## What Grafana Cloud held

`bin/cloudbackfill.py` copies what Grafana Cloud still holds (its last 14 days)
into these stores. It is safe to run again up to the cutover; it prints, for each
signal, Grafana Cloud's count beside the laptop's.

```bash
export $(grep -E '^GRAFANA_(URL|SA_TOKEN)=' .env | xargs)
uv run python bin/cloudbackfill.py --since 2026-09-21T00:00:00
```

Run it a last time with `--until` set to the moment the box's containers switched
to the journald log driver: after that the journal pull brings the same log lines
and a later window would hold them twice.
