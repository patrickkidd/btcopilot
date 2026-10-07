# Monitoring (FD-374)

Grafana Cloud is replaced. The production box only holds raw data on its own disk; Patrick's
laptop collects it whenever it is awake and keeps it with no time limit. Grafana runs on the
laptop and shows nothing while the laptop is closed. There are no alerts. [Design approved by
Patrick 2026-10-06; every open choice below ruled yes the same day, with "I just want to make
sure that we don't lose any data and have no interruption of data" (decisions/log.md).]

Grafana Cloud leaves the stack in the same deploy that brings the box side in (Patrick: "yes,
take grafana cloud out of this PR"). No data is lost: the box holds everything from the deploy
on, and `bin/cloudbackfill.py` copies what Cloud received before it. See "Cutover".

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
| Browser errors | `POST /app/browser-errors` writes each error as one log line, `Browser error {json}` at level WARNING, below the error email (logger `btcopilot.routes.browsererrors`) | the journal, like any log line | VictoriaLogs |
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

1. `authorized_keys` line for the dedicated key, in the home of the user `fdlink`:
   `restrict,port-forwarding,permitopen="127.0.0.1:5432",permitlisten="172.17.0.1:18428",permitlisten="172.17.0.1:14318",command="/usr/local/bin/fd-logpull" ssh-ed25519 ...`
   `fd-logpull` checks that `$SSH_ORIGINAL_COMMAND` is a journal cursor and runs
   `journalctl --after-cursor=<it> -o export` (or `--since -30d` when empty).
2. sshd, for `fdlink` only: `GatewayPorts clientspecified` (so `-R` may bind `172.17.0.1`), and
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
  each of the collector's two queues holds 260,000 batches, which is 30 days of absence at the
  most one batch per 10 s allows; past that the collector refuses new metrics and traces, and
  they are lost, so the box's disk never fills. Measured with the collector itself against a
  stopped receiver (Docker Desktop, 10 containers, 2026-10-07): one metrics batch a minute of
  149 data points, 24 KB as protobuf, and the queue file at 512 KB after six batches, so at most
  87 KB a batch on disk. A full metrics queue is then at most 22.6 GB (260,000 x 87 KB), and at
  the measured one batch a minute it fills only after 180 days. The traces queue stays under
  1 MB a day at a few hundred spans a day.
- Box down: nothing is collected for that time; whatever was already on the laptop stays.
- Laptop disk lost: history is lost; no backup is planned (a later decision if wanted).

## What FD-374 changes

- Box compose: `fd-otel` added (contrib 0.162.0, `mem_limit` 150 MB, `file_storage` queue on
  the `otel-queue` volume, retry forever; `host_metrics` and `docker_stats` every 60 s;
  exporters to `172.17.0.1:18428` and `172.17.0.1:14318`). The app and the three Celery
  containers send OTLP to `fd-otel`. `fd-alloy`, `fd-pdc` and `deploy/alloy/` are removed.
- The app's and the Celery containers' trace exporter waits up to 60 s for the collector
  (`OTEL_EXPORTER_OTLP_TIMEOUT=60`, the SDK's own retry with backoff 1, 2, 4, 8, 16 s), so a
  restart of `fd-otel` loses no spans: with the default 10 s, a 12 s outage lost 23 of 116
  spans in a local test; with 60 s, none.
- Every service logs through the `journald` driver; `docker logs` keeps working (checked
  2026-10-06 on Ubuntu 24.04's docker.io 29.1.3: the Docker API's container-logs call answered
  both the backlog and a follow, and the journal held `CONTAINER_NAME` and `MESSAGE`).
- fd-postgres published on `127.0.0.1:5432` only.
- Browser: the Faro SDK is gone; `web/src/telemetry.ts` posts uncaught errors and rejected
  promises to `/app/browser-errors`. Page-load timings and session replay stop here (ruled).
- `deploy/box/setup.sh` and `deploy/box/fd-logpull`: the one-time box changes (the `fdlink`
  user and its key line, the sshd drop-in, the ufw rule), run at step 3 of the cutover.
- The release workflow no longer pushes dashboards and `bin/grafanapush.py` is gone: the
  laptop's Grafana provisions `deploy/grafana/*.json` itself. `GRAFANA_CLOUD_TOKEN` and
  `GRAFANA_PDC_TOKEN` leave `deploy/secrets.env.example`.
- The product owner's Grafana reader reads the laptop's Grafana (`http://127.0.0.1:3000`, as
  admin, the password from `deploy/laptop/.env`); LogQL and TraceQL became LogsQL on
  VictoriaLogs and the Jaeger API of VictoriaTraces.

Memory: 1054 MB available on 2026-10-06 with Alloy (360 MB) and fd-pdc (11 MB) running; the
collector measured 77 to 92 MB (cap 150 MB), so about 1300 MB should be available after the
deploy (estimate, to be measured on the box).

## Cutover

1. FD-371 finishes its deploy and migrations; Patrick moves the deploy lock to FD-374.
2. Back up the database on the box.
3. On the box, from `/var/www/btcopilot/deploy`: `sh box/setup.sh "<laptop public key>"`.
   It creates the user `fdlink` (group systemd-journal, so it reads the whole journal) and puts
   the key in its `authorized_keys` with the forced command and forward limits; the sshd
   settings apply to `fdlink` only, in a `Match User` block that is checked with `sshd -t`
   before it is put in place. Root's keys and settings are not touched. The ufw step reads the
   compose network's subnet, so the stack must be up.
4. Straight before the deploy, on the box, check that Alloy holds nothing Grafana Cloud has not
   received. Alloy keeps its buffer inside its container, so the deploy's removal of it loses
   whatever is still pending:

   ```sh
   ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' fd-alloy)
   curl -s "http://$ip:12345/metrics" | grep -E '^(prometheus_remote_storage_samples_pending|otelcol_exporter_queue_size|loki_write_(encoded|sent)_bytes_total)'
   ```

   Go ahead only when the pending samples and every exporter queue size are 0, and each host's
   encoded bytes equal its sent bytes. Otherwise wait a minute and read again.
5. Deploy FD-374 from its branch (the release workflow) at a quiet hour, straight after the
   backup, with no coach turn queued. The deploy's `up -d` recreates fd-caddy, fd-postgres and
   fd-redis once, because their log driver changes, and its `--remove-orphans` removes fd-alloy
   and fd-pdc. Each recreated service was unreachable
   0.5 to 0.8 s on the laptop (Docker Desktop, three runs, 2026-10-06); on the 2 vCPU box
   expect a few seconds of failed requests (guess: 2 to 5 s). fd-redis keeps no volume, so
   whatever was queued in it is lost, as on any restart of it. Note the time the deploy
   finished: from then on every container logs to the journal, and Grafana Cloud receives
   nothing more.
6. At least 10 minutes after the deploy finished, on the laptop:
   `uv run python bin/cloudbackfill.py --until <deploy time>`, which copies Cloud's last hours
   up to the switch. Cloud makes a line or sample queryable a few minutes after it arrives (the
   backfill's own default stops 5 minutes short of now for this reason), so the wait lets
   everything Alloy sent before its removal be read; the run skips what the laptop already holds,
   so running it again later is safe.
7. Within minutes, check the laptop receives the box's data, printed as expected vs seen: a
   memory sample in VictoriaMetrics newer than 2 minutes; fd-app lines in VictoriaLogs newer
   than the deploy; an fd-app or fd-worker trace in VictoriaTraces newer than the deploy.
8. Once the backfill run succeeded and step 7 holds, remove the FD-374 cloudbackfill crontab
   line on the laptop.
9. Patrick closes the Grafana Cloud account himself.

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
6. One dedicated ssh key for the laptop with a forced command and forwarding limits (built for a
   dedicated user `fdlink`, not root), plus
   the sshd and ufw changes listed under "The private link".
