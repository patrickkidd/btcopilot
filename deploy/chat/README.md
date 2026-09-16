# The chat app's box — what runs it, and the order things happen in

This folder is the whole deployment of the chat app: one compose file, one
Caddyfile, one encrypted secrets file. It lives in this repo because everything
the chat app needs lives here now: the prompts and the rulings are encrypted
files in this repo, and fdserver has no part in the chat app. The box is separate
from the Pro box on purpose. Nothing in it has run yet; the droplet does not exist.

## What Patrick does, once, in this order

1. **Secrets.** Copy `secrets.env.example` to `secrets.env`, fill every value
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
4. **First start.** `docker compose pull && docker compose up -d`, then
   `docker compose exec fd-app flask admin db upgrade` — the chat chain from
   empty — then `docker compose exec fd-app flask admin users invite <email>`
   for your own account and open the link.
5. **Import.** Restore a copy of the Pro dump beside it, dry-run twice, then
   `flask admin imports run` once (step 13 of PLATFORM_BUILD).
6. **DNS.** Lower the TTL on familydiagram.com a day ahead, then point the
   root A record at the box and www as a CNAME. Caddy gets its certificate on
   the first request. database.familydiagram.com stays on the Pro box.
7. **Freeze the old box** for Pro: it takes no more chat-app deploys.

## Every deploy after that

The release workflow pushes the image to GHCR on a merge to master;
`release-chat.yml` then pulls it on the box and runs `flask admin db upgrade`.
Nothing is built on the box.

## What is not here yet

- Datadog agent on this box (kept on the Pro box; add when there is something
  to watch).
- Stripe, which waits on the price.
