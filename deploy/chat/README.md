# The chat app's box — what runs it, and the order things happen in

This folder is the whole deployment of the chat app: one compose file, one
Caddyfile, one encrypted secrets file. It lives in this repo because everything
the chat app needs lives here now: the prompts and the rulings are encrypted
files in this repo, and fdserver has no part in the chat app. The box is separate
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
   to `/var/www/btcopilot`, `cd deploy/chat`, decrypt the secrets into
   `/etc/fd/secrets.env` (root, 600).
4. **First start.** `docker compose --env-file /etc/fd/secrets.env pull && docker compose --env-file /etc/fd/secrets.env up -d`,
   then `docker compose --env-file /etc/fd/secrets.env exec fd-app flask admin db upgrade` — the chat chain from
   empty — then `docker compose --env-file /etc/fd/secrets.env exec fd-app flask admin users invite <email>`
   for your own account and open the link. The `--env-file` flag makes compose
   read `/etc/fd/secrets.env` for `${...}` interpolation in the compose file
   itself, in addition to the `env_file:` that feeds it into the containers.
5. **Import.** Restore a copy of the Pro dump beside it, dry-run twice, then
   `flask admin imports run` once (step 13 of PLATFORM_BUILD).
6. **DNS.** Lower the TTL on familydiagram.com a day ahead, then point the
   root A record at the box and www as a CNAME. Caddy gets its certificate on
   the first request. database.familydiagram.com stays on the Pro box.
7. **Freeze the old box** for Pro: it takes no more chat-app deploys.

## Every deploy after that

The release workflow pushes the image to GHCR on a merge to master;
`release-chat.yml` then pulls it on the box, rolls the app and the worker with
`docker rollout` (the new container comes up beside the old one and the old one
stops once the new one is healthy, so no request is dropped), and runs
`flask admin db upgrade`. Nothing is built on the box. The plugin is installed
once at /root/.docker/cli-plugins/docker-rollout (github.com/wowu/docker-rollout).

## Grafana Cloud

`fd-alloy` (Grafana Alloy) ships host and container metrics, every container's log
lines and the app's and worker's traces to Grafana Cloud; nothing is stored on the box.
It reads `GRAFANA_CLOUD_TOKEN` from the secrets file like everything else, and its config
is `alloy/config.alloy`. Its UI on port 12345 has no host port, so it is not exposed.
`fd-pdc` (Grafana's Private Data source Connect agent) holds an outbound tunnel to Grafana Cloud with `GRAFANA_PDC_TOKEN`; no port is opened.
Grafana's Postgres data source reaches `fd-postgres:5432` through it as the read-only role `grafana`, password `GRAFANA_PG_PASSWORD`.

## What is not here yet

- Stripe, which waits on the price.

## The bot's admin key

Patrick's local assistant runs the admin CLI over SSH with its own key. The key's
line in `/root/.ssh/authorized_keys` is pinned to `bin/fd-admin-gate` (installed at
`/usr/local/bin/fd-admin-gate`), which hands the words it was given to
`flask admin run -- <words>` inside fd-app and nothing else. Reads run at once; a
command that changes data prints a preview and stops until the words carry `--yes`.
