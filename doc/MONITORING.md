# Monitoring (FD-374)

Grafana Cloud is replaced. The production box only holds raw data on its own disk; Patrick's
laptop collects it whenever it is awake and keeps it with no time limit. Grafana runs on the
laptop and shows nothing while the laptop is closed. There are no alerts. [Design approved by
Patrick 2026-10-06; every open choice below ruled yes the same day, with "I just want to make
sure that we don't lose any data and have no interruption of data" (decisions/log.md).]

The work ships in two phases so no data is lost and none stops arriving: phase 1 adds the
laptop's path beside Grafana Cloud's, and phase 2 removes Grafana Cloud's only after the laptop
has held 7 complete days. See "Phases and cutover".

## What was measured (2026-10-06)

Box (2 vCPU, 1967 MB RAM, 2 GB swap of which 651 MB in use, 48 GB disk free, Ubuntu 24.04,
Docker 29.8.1, OpenSSH 9.6, ufw active with only OpenSSH allowed, no Tailscale):

| Container | RAM |
|---|---|
| fd-alloy | 360 MB |
| fd-app | 169 MB |
| fd-postgres | 41 MB |
| fd-worker | 30 MB |
| fd-caddy | 16 MB |
| fd-shadow, fd-beat, fd-pdc, fd-redis | 13, 10, 11, 5 MB |

- Logs today: every container uses Docker's default json-file driver with no rotation. A
  container's file is deleted when the release replaces the container, so logs survive on the
  box only until the next deploy. Volume is small: fd-app wrote 120 KB in 37 hours.
- The host's systemd journal is already persistent: 255 MB, 20 days, default cap 4 GB.
- Traces leave the app and the three Celery containers as OTLP over HTTP to `fd-alloy:4318`
  (`OTEL_EXPORTER_OTLP_ENDPOINT` in the compose file; `btcopilot/tracing.py`).
- Browser errors, page performance and session replay go from `web/src/telemetry.ts` (Faro SDK
  with the replay instrumentation) straight to Grafana Cloud's collector.
- The box health dashboard exists only in Grafana Cloud (uid `fd-box`). Its queries are listed
  under "Dashboards". Its container panels filter `name=~"fd.*|chat.*"`, which misses
  `familydiagram-fd-app-60` and the other compose-named containers: they show only the four
  containers that have a fixed name.

## Buffer test (laptop, Docker Desktop, 2026-10-06)

The stores were stopped for 605 seconds while the box-side agents kept collecting, then started.

- vmagent (scraping node_exporter and cAdvisor every 15 s, `-remoteWrite.tmpDataPath`): every
  minute across the outage holds 4 of 4 samples; 1.1 MB buffered on disk.
- OpenTelemetry Collector (host and container metrics every 15 s, plus 2 traces a second from a
  generator, `file_storage` queue, retry forever): every minute holds 4 of 4 metric samples and
  180 of 180 spans; 1.5 MB queued on disk.
- Both agents restarted while the stores were down: nothing lost after the restart.
- Logs: 1041 entries of the box's own journal pulled over ssh into VictoriaLogs, then 156 more
  from the saved cursor 15 minutes later; VictoriaLogs holds 1197, and the journal sequence
  numbers run on with no gap.

Memory during the test (arm64, so only a guide for the box): vmagent 40 to 57 MB, node_exporter
13 to 18 MB, cAdvisor 35 to 42 MB, OpenTelemetry Collector with metrics and traces 77 to 92 MB.

## Data flow per signal

| Signal | On the box | Held on the box while the laptop is closed | On the laptop |
|---|---|---|---|
| Metrics (host, containers) | the same OpenTelemetry Collector: `hostmetrics` (cpu, memory, load, filesystem) and `docker_stats` receivers, every 60 s | the collector's on-disk queue, retry forever | VictoriaMetrics |
| Logs (every container) | Docker's `journald` log driver | the systemd journal, cap 4 GB (years at today's volume) | VictoriaLogs, filled by a pull: `ssh box journalctl --after-cursor=<c> -o export` every minute, posted to `/insert/journald/upload`; the cursor is saved only after a 200 |
| Traces | OpenTelemetry Collector (contrib build) receives OTLP from the app | the collector's on-disk queue (`file_storage`), retry forever | VictoriaTraces |
| Browser errors | `POST /app/browser-errors` writes each error as one log line, `Browser error {json}` at level ERROR (logger `btcopilot.routes.browsererrors`) | the journal, like any log line | VictoriaLogs |
| Postgres tables (the four existing dashboards) | fd-postgres, read-only role `grafana` | nothing to hold: read live | Grafana's Postgres data source through the private link |

Log lines from removed containers are kept, because the journal belongs to the host, not the
container. `docker logs` keeps working with the journald driver.

A retry after a failed log post can store some lines twice (VictoriaLogs stores what arrived
before the failure); accepted, since the cursor is advanced only after a complete post.

## Components

On the box (replaces fd-alloy 360 MB and fd-pdc 11 MB):

- `fd-otel`: OpenTelemetry Collector, contrib image, about 80 to 90 MB (measured above); one
  process for metrics and traces, with a `mem_limit` of 150 MB. Config in
  `deploy/otel/config.yaml`.
- `/usr/local/bin/fd-logpull`: a shell script run only by the laptop's ssh key; no process
  between pulls.
- Docker's `journald` log driver on every service; no process.

Net: about 370 MB freed, about 90 MB added. Box memory ends near 280 MB lower than today.

Not chosen: vmagent with node_exporter and cAdvisor for metrics. It works (test above) but is
three containers and about 110 MB beside the collector that traces need anyway. The collector
alone does both. The box dashboard is rebuilt in either case, so the change of metric names
(`system.memory.usage` instead of `node_memory_MemAvailable_bytes`) costs nothing extra.

On the laptop (`deploy/laptop/compose.yml`, Docker Desktop, data under `~/fd-monitoring/`,
which is outside iCloud):

- VictoriaMetrics, `-retentionPeriod=100y`
- VictoriaLogs, `-retentionPeriod=100y`
- VictoriaTraces, `-retentionPeriod=100y`
- Grafana, with data sources and dashboards provisioned from files
- `fd-link`: a small container (alpine with openssh-client) that holds the ssh link and runs
  the log pull loop; restart always

## The private link

Chosen: one ssh connection opened from the laptop, with a dedicated key. No new account, no
login step, no memory on the box. Tailscale works too but adds tailscaled on the box (about
30 MB, not measured) and a one-time `tailscale up` login there and on the laptop.

The connection carries:

- `-L 127.0.0.1:15432:127.0.0.1:5432`: Grafana on the laptop to fd-postgres. fd-postgres gets a
  host port bound to `127.0.0.1` only.
- `-R 172.17.0.1:14318:<laptop VictoriaTraces>` and `-R 172.17.0.1:18428:<laptop VictoriaMetrics>`: containers on the box reach the
  laptop's stores through the address of the box's `docker0` interface. When the laptop is
  closed the port is closed and the box side queues.
- the log pull, as a forced command on the same key.

One-time box changes, in `deploy/box/setup.sh` (run at step 3 of the cutover):

1. `authorized_keys` line for the dedicated key:
   `restrict,port-forwarding,permitopen="127.0.0.1:5432",permitlisten="172.17.0.1:18428",permitlisten="172.17.0.1:14318",command="/usr/local/bin/fd-logpull" ssh-ed25519 ...`
   `fd-logpull` checks that `$SSH_ORIGINAL_COMMAND` is a journal cursor and runs
   `journalctl --after-cursor=<it> -o export` (or `--since -30d` when empty).
2. sshd: `GatewayPorts clientspecified` (so `-R` may bind `172.17.0.1`), and
   `ClientAliveInterval 30`, `ClientAliveCountMax 3` so a link dropped by a sleeping laptop
   frees its port within 90 seconds instead of about two hours.
3. ufw: allow TCP from the compose network `172.18.0.0/16` to `172.17.0.1` on the forwarded
   ports (the INPUT policy is DROP).

Human steps: none on the box beyond saying yes to the three changes above. On the laptop,
`docker compose -f deploy/laptop/compose.yml up -d` once; Docker Desktop must be set to start
at login.

## Dashboards

Grafana on the laptop provisions from files at start:

- data sources (`deploy/laptop/grafana/datasources.yml`): Postgres with the same uid the four
  dashboards already use, `ffz1wy7unkdfke`, pointing at `host.docker.internal:15432` as role
  `grafana` (password in the laptop's own env file, from `GRAFANA_PG_PASSWORD`); VictoriaMetrics
  as a Prometheus data source; VictoriaLogs with its Grafana plugin; VictoriaTraces as a Jaeger
  data source at `/select/jaeger`.
- dashboards: `deploy/grafana/*.json`, mounted read-only. Saving in the UI does not change the
  files; editing is done in the files, as today.
- the box health dashboard is rebuilt as `deploy/grafana/fd-box.json` from the export below,
  against VictoriaMetrics and VictoriaLogs; the container panels select by the container's name
  label so the compose-named containers appear.

New Grafana plugins needed: VictoriaLogs data source (`victoriametrics-logs-datasource`).
VictoriaMetrics works with the built-in Prometheus data source and VictoriaTraces with the
built-in Jaeger data source.

Box health dashboard as exported from Grafana Cloud (8 panels):

| Panel | Query today |
|---|---|
| Memory available | `node_memory_MemAvailable_bytes` |
| Disk free on / | `node_filesystem_avail_bytes{mountpoint="/"}` |
| CPU busy | `1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))` |
| Load (1m) | `node_load1` |
| Memory used by container | `container_memory_working_set_bytes{name=~"fd.*\|chat.*"}` |
| CPU by container | `rate(container_cpu_usage_seconds_total{name=~"fd.*\|chat.*"}[5m])` |
| Errors and exceptions (last 6h) | `{container=~".+"} \|~ "(?i)error\|traceback\|exception"` (Loki) |
| Log lines a minute by container | `sum by (container) (count_over_time({container=~".+"}[1m]))` (Loki) |

The two log panels become LogsQL against the journal fields `CONTAINER_NAME` and `MESSAGE`,
for example `CONTAINER_NAME:~".+" MESSAGE:~"(?i)error|traceback|exception"`.

## When something fails

- Laptop closed: the box keeps metrics and traces in the on-disk queues and logs in the journal;
  the laptop catches up when it wakes. Grafana shows nothing meanwhile.
- Laptop closed longer than the box can hold: the journal drops its oldest entries at 4 GB; the
  queues are bounded only by disk (48 GB free).
- Box down: nothing is collected for that time; whatever was already on the laptop stays.
- Laptop disk lost: history is lost; no backup is planned (a later decision if wanted).

## Phases and cutover

Phase 1 (built on FD-374): the laptop's path is added and Grafana Cloud's is kept.

- Box compose: `fd-otel` added (contrib 0.162.0, `mem_limit` 150 MB, `file_storage` queue on
  the `otel-queue` volume, retry forever; `host_metrics` and `docker_stats` every 60 s;
  exporters to `172.17.0.1:18428` and `172.17.0.1:14318`). The app and the three Celery
  containers send OTLP to `fd-otel`, which also passes traces on to `fd-alloy`, so Grafana
  Cloud's traces keep arriving. `fd-alloy` and `fd-pdc` stay as they are.
- Every service logs through the `journald` driver. Alloy keeps reading logs through the
  Docker socket: checked 2026-10-06 on Ubuntu 24.04's docker.io 29.1.3 with the journald
  driver, where the Docker API's container-logs call (what Alloy's `loki.source.docker` uses)
  answered both the backlog and a follow, and the journal held `CONTAINER_NAME` and `MESSAGE`.
- fd-postgres published on `127.0.0.1:5432` only.
- Browser: the Faro SDK is gone; `web/src/telemetry.ts` posts uncaught errors and rejected
  promises to `/app/browser-errors`. Page-load timings and session replay stop here (ruled).
- `deploy/box/setup.sh` and `deploy/box/fd-logpull`: the one-time box changes (key line,
  sshd drop-in, ufw rule), written, run at the cutover below.
- The product owner's Grafana reader takes `FD_GRAFANA_URL` and `FD_GRAFANA_TOKEN` to read
  the laptop's Grafana (`http://localhost:3000`); Grafana Cloud stays its default.

Memory in phase 1: 1054 MB available on 2026-10-06 with Alloy running; the collector measured
77 to 92 MB (cap 150 MB), so about 900 to 980 MB stays available.

Cutover order:

1. FD-371 finishes its deploy and migrations; Patrick moves the deploy lock to FD-374.
2. Back up the database on the box.
3. On the box, from `/var/www/btcopilot/deploy`: `sh box/setup.sh "<laptop public key>"`.
   The ufw step reads the compose network's subnet, so the stack must be up.
4. Deploy FD-374 from its branch (the release workflow). Every container is recreated with the
   journald driver; lines a container wrote before this stay only in its old json file until
   that container is removed, as today.
5. On the laptop: `docker compose -f deploy/laptop/compose.yml up -d`; the link connects, the
   log pull starts with the last 30 days of the journal, the box's queues drain.
6. Compare the laptop with Grafana Cloud for 7 days, across at least one laptop sleep:
   metrics every minute, log line counts per container, trace counts per service.

Phase 2 (after the 7 days compare complete; not built yet):

- [ ] Remove `fd-alloy`, `fd-pdc` and `deploy/alloy/`; drop the `otlp_http/alloy` exporter;
  `btcopilot/tests/test_alloy.py` goes with them.
- [ ] Remove `GRAFANA_CLOUD_TOKEN` and `GRAFANA_PDC_TOKEN` from `deploy/secrets.env.example`
  and the box's secrets.
- [ ] Remove the release workflow's dashboard push step, `bin/grafanapush.py` and
  `btcopilot/tests/test_grafanapush.py` (the dashboard list `test_feedbackloops.py` imports
  moves with it).
- [ ] Product owner skill: the laptop's Grafana becomes the default; the LogQL and Tempo
  readers become LogsQL and Jaeger; `SKILL.md` updated.
- [ ] Comments that name Grafana Cloud, Faro or Alloy: `web/src/main.ts`, `report.ts`,
  `track.ts`, `vite.config.ts`, `btcopilot/reports.py`, `productevents.py`,
  `models/report.py`, `web/tests/visual/gate.ts`; docs listed below.
- [ ] Box memory checked against the table at the top: about 280 MB lower than today.
- [ ] Patrick closes the Grafana Cloud stack (his account; not done by Claude).

## Files that reference Grafana Cloud today

Code and config: `deploy/docker-compose.yml`, `deploy/alloy/config.alloy`,
`deploy/secrets.env.example`, `deploy/grafana/*.json` (data source uids),
`.github/workflows/release.yml` (dashboard push step), `bin/grafanapush.py`,
`web/src/telemetry.ts`, `web/package.json`, `web/package-lock.json`, `web/vite.config.ts`
(comment), `web/src/main.ts`, `web/src/report.ts`, `web/src/track.ts`,
`btcopilot/reports.py`, `btcopilot/productevents.py`, `btcopilot/models/report.py` (comments),
`.claude/skills/product-owner/bin/grafana.py`, `.claude/skills/product-owner/SKILL.md`.
Tests: `btcopilot/tests/test_alloy.py`, `test_grafanapush.py`, `test_dashboards.py`,
`test_feedbackloops.py`, `test_agent.py`, `web/test/telemetry.test.ts`,
`web/tests/visual/{gate.ts,failure.spec.ts,reports.spec.ts}`.
Docs: `CLAUDE.md`, `deploy/README.md`, `doc/PLATFORM_BUILD.md`, `doc/SETUP.md`,
`doc/FEEDBACK_LOOPS.md`, `doc/STATE.md`, `doc/TOPICS.md`, `doc/API.md`, `doc/SCREENS.md`,
`doc/specs/DATA_MODEL.md`; history files (`doc/HISTORY.md`, `doc/REVIEW_LOG.md`,
`decisions/log.md`, `doc/archive/`) are left as they are.

## Ruled by Patrick (2026-10-06): yes to all six

1. OpenTelemetry Collector (contrib build) on the box, a new tool: it is the only one tested
   that holds traces on disk while the laptop is closed, and it also does the host and
   container metrics, so vmagent is not used. The design he approved named vmagent.
2. node_exporter and cAdvisor would be two more new tools if vmagent were kept instead; the
   recommendation above avoids them.
3. VictoriaTraces as the traces store (the alternative, Grafana Tempo, is heavier and needs
   object storage settings); Grafana reads it through its built-in Jaeger data source.
4. The VictoriaLogs data source plugin for Grafana.
5. Lost with the browser SDK: session replay and page-load timings. Only uncaught errors and
   rejected promises reach the new endpoint.
6. One dedicated ssh key for the laptop with root's forced command and forwarding limits, plus
   the sshd and ufw changes listed under "The private link".
