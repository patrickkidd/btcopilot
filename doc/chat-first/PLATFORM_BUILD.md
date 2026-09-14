# Platform build order — the chat app on its own box, its own database, its own secrets

Written 2026-09-13 from the rulings in TOPICS.md (T-11) and the decision log entries of
2026-09-12 and 2026-09-13. One public repo, prompts as files, secrets encrypted in place,
fdserver out of the daily loop, the chat app on its own droplet with its own database,
old Pro users imported once, money through Stripe's hosted page, admin through a CLI.

Steps 1–8 can be built and proved on the local sandbox today. Steps 9–15 need the new box,
the DNS name, or an account only Patrick holds.

## Built and proved locally

| # | Step | Changes | Depends on | Proved by | Needs Patrick |
|---|---|---|---|---|---|
| 1 | Throwaway encryption key for development | A key pair kept in the sandbox only, plus the rules file naming which paths are encrypted | nothing | Encrypt a file, commit it, read it back through the tool, and see only ciphertext in the committed copy | no |
| 2 | Prompts become files | Each prompt leaves the Python constants and becomes one file per prompt with shared fragments; the loader reads them | 1 | Every prompt renders to the same text the constants produced today, asserted string for string | no |
| 3 | A renderer that resolves fragments | The stock file renderer holds only the prompt itself, so fragments do not resolve; a subclass with a file loader fixes it | 2 | A prompt that includes two fragments renders whole; a missing fragment raises rather than rendering empty | no |
| 4 | Prompts and rulings move into this repo, encrypted | The private prompt file and the oracle rulings arrive here as encrypted files; the runtime path override to the other repo is deleted | 1, 2, 3 | The app starts with no second repo present; the same conversation produces the same coach reply | no |
| 5 | Files naming real people leave every repo | They move to the corpus folder that sits outside all repos; a test refuses a commit that reintroduces them | 4 | The test fails on a planted file and passes on the tree | no |
| 6 | The chat app stops sharing tables with Pro | Its own database, its own migration chain starting from empty; the Pro tables it reads become an import, not a join | nothing | The whole migration chain runs against an empty database and the app serves every screen | no |
| 7 | Import of the old Pro accounts and diagrams | A one-shot importer reads a dump of the old database and writes users and converted diagrams into the new one | 6 | Run against a copy of a real dump: counts in equal counts out, every diagram opens, failures listed rather than swallowed | no |
| 8 | The admin command line, and its skill file | One command with subcommands for users, licences, diagrams, imports and token caps; the skill file is generated from the command's own declarations | 6 | Generating the skill file twice gives the same bytes; a test fails when a subcommand exists with no entry | no |

## Needs the new box or an account

| # | Step | Changes | Depends on | Proved by | Needs Patrick |
|---|---|---|---|---|---|
| 9 | Rotate every secret in the committed compose file | New values for every credential now sitting in git history | nothing | The old values no longer open anything; the running production app keeps serving Pro | **yes** — he issues the new credentials and says when the old ones die |
| 10 | A key pair per machine | One on his Mac, one on the new box; private keys never copied; both public keys listed in the rules file | 1 | Each machine reads the encrypted files; a third machine cannot | **yes** — he generates the key on his Mac and on the box |
| 11 | The new droplet | A 2 GB box with the web server in front, the backup add-on on, monitoring kept | 9 | The box answers on its address over https with a real certificate | **yes** — he creates it and points the name at it |
| 12 | The old box is frozen | It keeps serving the Pro desktop app and takes no more chat-app deploys | 11 | A Pro desktop client still signs in and saves after the freeze | **yes** — he declares the freeze |
| 13 | The import run for real | Step 7 run once against the live dump into the new database | 7, 11 | The counts from the dry run match; a named clinician signs in and sees their own diagram | **yes** — he approves the cutover moment |
| 14 | Money through Stripe | Flat monthly plan on Stripe's hosted page, the customer portal linked from every subscription email, tax on, US only | 11 | A test-mode purchase grants the licence and a cancel in the portal removes it | **yes** — account, keys, and the price, which is still unset |
| 15 | The other repo is archived | It leaves the daily loop and becomes a read-only archive holding the files with real people in them | 4, 5, 13 | Nothing in the build refers to it; the app starts with it absent | **yes** — he archives it |

Token metering with a hard cap and a paid top-up sits in our own table and rides on step 14.
Nothing in this list depends on the price, which waits for real beta usage.

## The risks worth naming before any of this starts

**One migration chain versus a fresh one.** This branch adds seven revisions to the chain the
Pro app shares. Step 6 says the chat app starts from empty on its own chain instead. That is
the right shape, but it means the branch's revisions are thrown away and rewritten as one
initial revision, and anything already written into a sandbox database on the old chain is
lost unless it is re-imported. Doing it later costs more, not less.

**Sharing the user table or not.** The chat app needs to know who a person is and what they
have bought; the Pro app owns that today. Copying users at import time gives two records of
the same person that drift the moment someone changes an email. Keeping one shared table
across two databases means a live link between the boxes, which defeats the separation. The
third choice — the new box owns identity and the old box is told about changes until Pro is
sunset — is the only one that ends cleanly. Unruled; it decides steps 6 and 7 and should be
settled before either starts.

**The coach's model settings.** The ruling is Claude Opus 4.6 with thinking. Where that
choice lives is not ruled: a setting per deployment, or a value the prompt file carries. If it
lives in the prompt file it is encrypted, which makes changing a model a decrypt-and-commit.
Recommend the deployment setting, with the prompt file naming nothing about the model.

**The prompt renderer.** The stock renderer does not resolve fragments, so step 3 writes a
subclass. That subclass is ours to maintain against a library we do not control, and a silent
fallback that renders a prompt with an empty fragment would cost a coach turn with no error.
Build it to raise on a missing fragment, never to render an empty one.

**The encrypted-file diff.** Whether the tool shows a readable difference on a prose file it
holds as one block is unverified. If it does not, every ruling edit reads as a wall of
ciphertext in review. Verify it in step 1 before the rulings move in step 4; if it fails,
split the rulings into one file per ruling so a change shows as a new file.

**The import is one-way.** Step 13 has no way back once clinicians are writing on the new
box. The dry run in step 7 against a real dump is what makes it safe, and it is worth running
twice.

## Deploy checkpoint (flushed 2026-09-14; nothing below runs until Patrick says deploy may start)

Ruled: the droplet is created only after Patrick has tested the new build (R-0330).

**What is already in hand**
- DigitalOcean API token in ~/theapp/.env as DIGITALOCEAN_ADMIN; every admin action is confirmed with Patrick here first, production boxes.
- Patrick's age public key on this Mac: age105g6wq3zc6xszu75ejeqryqjq69xrfm4hp8hktq89u3jpyafvq7sf23nqu (saved in the sandbox keys folder as patrick-mac.pub; not yet added to the encryption rules).
- Read-only listing done: old boxes in sfo1 (database.familydiagram.com = Pro API, 107.170.236.117; alaskafamilysystems.com = 107.170.200.120), one sfo3 droplet discussions.familydiagram.com (137.184.42.58, purpose unconfirmed), one SSH key on the account (turin).
- familydiagram.com records: root and database → Pro box; www → 198.199.116.86 (stale, nothing of ours); pypi → alaskafamilysystems box; discussions → sfo3 box. No mail on familydiagram.com. alaskafamilysystems.com carries mail (Google MX, Brevo SPF/DKIM/DMARC) and is never touched.
- The old box's nginx serves on familydiagram.com: the desktop app's Sparkle appcast files, and a 301 of everything else to alaskafamilysystems.com/family-diagram (fdserver nginx/conf.d/default.conf:34-58).

**The create, when he says go**
droplet familydiagram-app · sfo3 · s-2vcpu-2gb ($18/mo) · Ubuntu 24.04 · backups on · monitoring on · ssh key turin · tag familydiagram-app. sfo3 chosen because sfo1 lacks block-storage volumes and services must never be limited by region (R-0328).

**DNS, after the app answers on the new IP**
1. Lower TTL on familydiagram.com root and www to 300 a day before.
2. familydiagram.com A → new IP; www CNAME → familydiagram.com. database.familydiagram.com untouched.
3. Caddy on the new box: /app → the chat app; the appcast paths copied from the old nginx so desktop updates keep working; everything else → 301 to alaskafamilysystems.com/family-diagram until the new site exists.

**Observability (R-0328, R-0329)**: Datadog free host tier for now (paid host waits); logs ingest-only with exclusion filters, errors indexed, Error Tracking on logs on; RUM with Session Replay from day one; LLM Observability within its free tier with a span-count monitor; one uptime check; browser logs and error tracking. APM and product analytics later. See DATADOG.md.

**Box shape**: one compose file — caddy, app, postgres (config in repo), datadog agent (container logs by label), nightly pg_dump; secrets as one sops-encrypted env decrypted at deploy with the box's own age key; deploy = tag → one image from GitHub Actions → compose pull and up over SSH, also drivable from the admin CLI.

**Still needs Patrick at that time**: the droplet's own age key; rotated credentials; Stripe account and keys; the Pro freeze; import cutover approval; fdserver archive; what discussions.familydiagram.com is.
