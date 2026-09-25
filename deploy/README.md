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
   commit `secrets.env.enc`.
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

On a merge to master `release.yml` builds the image, tags it with the release
version `3.YYYY.M.D.N+g<sha7>` (UTC commit date, N counts that day's releases; the
image tag has `-` for `+`; R-0419), pushes it to GHCR, then pulls it on the box, rolls the app and the worker with
`docker rollout` (the new container comes up beside the old one and the old one
stops once the new one is healthy, so no request is dropped), and runs
`flask admin db upgrade`. Nothing is built on the box. The plugin is installed
once at /root/.docker/cli-plugins/docker-rollout (github.com/wowu/docker-rollout).

**One-time stamp (R-0417).** The seven old migrations became one revision, `1b00000000aa`.
Before its upgrade the deploy moves a database at the old head `1a00000000af` to it (from
`1a00000000ae` it adds the one missing column first); any other old revision stops the deploy.

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

The desktop app's update feeds live on the legacy box and are forwarded because shipped apps have this address built in.

## What is not here yet

- Stripe, which waits on the price.

## The bot's admin key

Patrick's local assistant runs the admin CLI over SSH with its own key. The key's
line in `/root/.ssh/authorized_keys` is pinned to `bin/fd-admin-gate` (installed at
`/usr/local/bin/fd-admin-gate`), which hands the words it was given to
`flask admin run -- <words>` inside fd-app and nothing else. Reads run at once; a
command that changes data prints a preview and stops until the words carry `--yes`.
