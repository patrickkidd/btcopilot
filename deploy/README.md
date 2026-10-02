# Family Diagram's box — what runs it, and the order things happen in

This folder is the whole deployment of Family Diagram version three: one compose file, one
Caddyfile, one encrypted secrets file. It lives in this repo because everything
the app needs lives here now: the prompts and the rulings are encrypted
files in this repo, and fdserver has no part in it. The box is separate
from the Pro box on purpose. Nothing in it has run yet; the droplet does not exist.

## What Patrick does, once, in this order

1. **Secrets.** Copy `secrets.env.example` to `secrets.env`, fill every value
   (Gemini is the model that groups events into clusters on the picture)
   with a new credential (none of the old compose file's values are reused),
   encrypt it: `sops -e secrets.env > secrets.env.enc`, delete the plain file,
   commit `secrets.env.enc`. The Gemini values are listed under "Gemini settings" below.
2. **Keys.** On the new box: `age-keygen -o /etc/fd/age.key`, `chmod 600`. Its
   public key goes into `.sops.yaml` here beside the Mac's; the prompts, the
   rulings and the secrets file are re-encrypted with `sops updatekeys`. Claude
   does this as part of creating the box (R-0353).
3. **The droplet.** sfo3, s-2vcpu-2gb, Ubuntu 24.04, backups on, monitoring on,
   ssh key turin, tag familydiagram-app. Install docker and sops. Clone this repo
   to `/var/www/btcopilot`, `cd deploy`, decrypt the secrets into
   `/etc/fd/secrets.env` (root, 600).
4. **First start.** `docker compose --env-file /etc/fd/secrets.env pull && docker compose --env-file /etc/fd/secrets.env up -d`,
   then `docker compose --env-file /etc/fd/secrets.env exec fd-app flask admin db upgrade` — the single revision from
   empty — then `docker compose --env-file /etc/fd/secrets.env exec fd-app flask admin users invite <email>`
   for your own account and open the link. Nobody's old Pro records are imported at
   cutover: every beta user starts on an empty record (R-0355). The `--env-file` flag makes compose
   read `/etc/fd/secrets.env` for `${...}` interpolation in the compose file
   itself, in addition to the `env_file:` that feeds it into the containers.
5. **DNS.** Lower the TTL on familydiagram.com a day ahead, then point the
   root A record at the box and www as a CNAME. Caddy gets its certificate on
   the first request. database.familydiagram.com stays on the Pro box.
6. **Freeze the old box** for Pro: it takes no more deploys of this app.

## Every deploy after that

**The deploy lock (R-0530).** Only one branch may deploy: the production environment's
single allowed deployment branch. A session holds the lock only when Patrick tells it so, then
runs `uv run bin/deploy-lock set <its branch>`. Every deploy runs `uv run bin/deploy-lock show`
first and does not dispatch unless the lock names its own branch. A merge to master never
deploys; the lock never names master or a second branch.

A dispatch of `release.yml` from the lock's branch makes no git tag. The image is tagged
`<branch>-g<sha7>` (for example `fd-368-g2acce7b`), and the version string the app and Grafana
show is `3.YYYY.M.D.N+g<sha7>` (UTC commit date, N the workflow run number). A release from
master, after the PR merges, also creates the git tag `3.YYYY.M.D.N+g<sha7>` (N counts that
day's tags) and tags the image the same with `-` for `+` (R-0419). The dispatch builds the
image, pushes it to GHCR, then pulls it on the box, rolls the app and the worker with
`docker rollout` (the new container comes up beside the old one and the old one
stops once the new one is healthy, so no request is dropped), and runs
`flask admin db upgrade`. Nothing is built on the box. The plugin is installed
once at /root/.docker/cli-plugins/docker-rollout (github.com/wowu/docker-rollout).

**One-time stamp (R-0417).** The seven old migrations became one revision, `1b00000000aa`.
Before its upgrade the deploy moves a database at the old head `1a00000000af` to it (from
`1a00000000ae` it adds the one missing column first); any other old revision stops the deploy.

**The landing page's keys (R-0601).** The page at `/` needs `FLASK_TURNSTILE_SITE_KEY` and
`FLASK_TURNSTILE_SECRET_KEY` in `/etc/fd/secrets.env`, the two keys of a Turnstile widget created
in the Cloudflare dashboard for familydiagram.com. Without them the page shows but its two forms
refuse every post. Beta requests go to `FLASK_ADMIN_EMAIL`.

**A changed Caddyfile needs the Caddy container restarted**, not reloaded: the file is a
single-file bind mount, which keeps the old file after a pull replaces it. The release
workflow's deploy does this itself whenever the Caddyfile changed; by hand it is
`docker compose --env-file /etc/fd/secrets.env restart fd-caddy`.

## Rolling back

`release.yml` cannot do it: the production environment only takes a dispatch from the
branch, and a dispatch deploys the branch head. Dispatching from an older release's tag is
refused ("not allowed to deploy to production due to environment protection rules",
2026-09-28). Roll back by hand on the box instead, to the last good release: its commit is
the `<sha7>` in its image tag (`<branch>-g<sha7>`, or `3.YYYY.M.D.N-g<sha7>` for a release from
master; `docker images ghcr.io/patrickkidd/btcopilot` on the box lists them). As root:

    cd /var/www/btcopilot && git fetch origin <sha> && git checkout --detach <sha> && cd deploy
    export BTCOPILOT_TAG=<image tag, e.g. fd-368-g2acce7b>
    docker compose --env-file /etc/fd/secrets.env pull fd-app fd-worker fd-shadow fd-beat
    docker rollout --env-file /etc/fd/secrets.env fd-app
    docker rollout --env-file /etc/fd/secrets.env fd-worker
    docker compose --env-file /etc/fd/secrets.env up -d fd-shadow fd-beat
    docker compose --env-file /etc/fd/secrets.env ps

This holds only when the release being left added no migration: the database stays where it
is, and an older app on a newer schema is not safe. When it did, restore the backup taken
before that deploy instead (`/root/backups/prod-<date>-pre-<sha>.dump`, `pg_restore --clean`
into fd-postgres) and say so, since it loses every write since. The next dispatch from the
branch puts the branch head back.

A restart or recreate of any app container on the box always goes through the rollout script with the current tag. A bare `docker compose up -d` without `BTCOPILOT_TAG` falls back to an older image while the database already carries the newer migration. That happened on 2026-09-30 for about 15 minutes: release 3.2026.9.30.6 was rolled back to 3.2026.9.26.1 by an env-file change followed by a bare `up`.

After the rollout and health checks, the deploy removes every btcopilot image tag except the new one and the one that was running before it, then prunes dangling layers; a prune error is logged and does not fail the deploy.

## One time: the names move from "chat" to "familydiagram" (R-0472)

The compose project, the Postgres role and the Postgres database were all named
`chat`. The compose file and `release.yml` now use `familydiagram`, and the deploy
reads the host from the repository variable `FD_HOST` instead of `CHAT_HOST`. The
merge that brings this in does not deploy, because `FD_HOST` does not exist yet. Run
these on the box after that merge, as root, in this order:

```bash
cd /var/www/btcopilot && git pull origin master && cd deploy
# 1. stop everything that holds a connection, under the old project name
docker compose -p chat --env-file /etc/fd/secrets.env stop fd-app fd-worker fd-pdc
# 2. rename the database and the role through a temporary superuser (a role cannot rename itself)
docker exec fd-postgres psql -U chat -d postgres -c "CREATE ROLE fdtmp SUPERUSER LOGIN"
docker exec fd-postgres psql -U fdtmp -d postgres -c "ALTER DATABASE chat RENAME TO familydiagram"
docker exec fd-postgres psql -U fdtmp -d postgres -c "ALTER ROLE chat RENAME TO familydiagram"
docker exec fd-postgres psql -U fdtmp -d postgres -c "ALTER ROLE familydiagram PASSWORD '$(grep ^POSTGRES_PASSWORD= /etc/fd/secrets.env | cut -d= -f2-)'"
docker exec fd-postgres psql -U familydiagram -d postgres -c "DROP ROLE fdtmp"
# 3. take the old project down; the database is a bind mount in instance/ and is untouched
docker compose -p chat --env-file /etc/fd/secrets.env down
# 4. carry Caddy's certificates over to the new project's volumes
for v in caddy-data caddy-config; do
  docker volume create familydiagram_$v
  docker run --rm -v chat_$v:/from -v familydiagram_$v:/to alpine cp -a /from/. /to/
done
# 5. start under the new name and check
docker compose --env-file /etc/fd/secrets.env up -d
docker compose --env-file /etc/fd/secrets.env exec -T fd-app flask admin db upgrade
docker compose --env-file /etc/fd/secrets.env ps
```

Then, off the box: rename the repository variable `CHAT_HOST` to `FD_HOST` on GitHub
(`gh variable set FD_HOST --repo patrickkidd/btcopilot --body <host>`, then
`gh variable delete CHAT_HOST --repo patrickkidd/btcopilot`), and change the database
name in Grafana Cloud's Postgres data source from `chat` to `familydiagram`. Once the
site answers, `docker volume rm chat_caddy-data chat_caddy-config`.
The app is down from step 1 to step 5, about a minute.

## Grafana Cloud

`fd-alloy` (Grafana Alloy) ships host and container metrics, every container's log
lines and the app's and worker's traces to Grafana Cloud; nothing is stored on the box.
It reads `GRAFANA_CLOUD_TOKEN` from the secrets file like everything else, and its config
is `alloy/config.alloy`. Its UI on port 12345 has no host port, so it is not exposed.
`fd-pdc` (Grafana's Private Data source Connect agent) holds an outbound tunnel to Grafana Cloud with `GRAFANA_PDC_TOKEN`; no port is opened.
Grafana's Postgres data source reaches `fd-postgres:5432` through it as the read-only role `grafana`, password `GRAFANA_PG_PASSWORD`.
The quality dashboard, `fd-quality`, is kept in `grafana/fd-quality.json` and put to Grafana
with `POST /api/dashboards/db` (`{"dashboard": ..., "overwrite": true}`) on the service account
token `GRAFANA_SA_TOKEN`. Its recorded-run panels read `quality_runs`, which every release fills
with `flask admin quality load` (see `quality/evals/README.md`).
The features dashboard, `fd-features` (what people use, and what the coach and the app sent and what came back), is kept in `grafana/fd-features.json` and put the same way: the release's "Push the dashboards" step (`bin/grafanapush.py`) puts every file in `grafana/`.

The desktop app's update feeds live on the legacy box and are forwarded because shipped apps have this address built in.

## Gemini settings

Two kinds of call go to Gemini, and they do not read the same settings. All of them live in
`/etc/fd/secrets.env`; `secrets.env.example` names each one.

| Setting | Read by | What it does |
|---------|---------|--------------|
| `GOOGLE_GEMINI_API_KEY` | cluster sorting, session titles and summaries, always; a coach model on Gemini when the endpoint is `developer` | the Developer API key |
| `BTCOPILOT_GEMINI_ENDPOINT` | a coach model on Gemini (shadows and replays) | `vertex` or `developer`; unset means `vertex` |
| `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` | a coach model on Gemini, `vertex` only | the Google Cloud project and region; a call fails with a missing-key error when either is unset |
| `GCP_SA_FILE` | compose, not the app | the path on the box of the Vertex service account file (default `/etc/fd/gcp-sa.json`, root, 600), mounted read-only at `/run/secrets/gcp-sa.json` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Google's library, `vertex` only | set by the compose file to the mounted copy; never set in the secrets file |

The file at `GCP_SA_FILE` must exist whichever endpoint is set, because compose mounts it
either way; on `developer` nothing reads it and an empty file is enough. A box with no
service account therefore needs exactly these two lines for every Gemini call to work:

    GOOGLE_GEMINI_API_KEY=<the Developer API key>
    BTCOPILOT_GEMINI_ENDPOINT=developer

Vertex runs under the Google Cloud project, whose agreement covers health data; the Developer
API runs on the key alone [Oracle: R-0598].

## What is not here yet

- Stripe, which waits on the price.

## The bot's admin key

Patrick's local assistant runs the admin CLI over SSH with its own key. The key's
line in `/root/.ssh/authorized_keys` is pinned to `bin/fd-admin-gate` (installed at
`/usr/local/bin/fd-admin-gate` by every release), which hands the words it was given to
`flask admin run -- <words>` inside fd-app and nothing else. Reads run at once; a
command that changes data prints a preview and stops until the words carry `--yes`.
