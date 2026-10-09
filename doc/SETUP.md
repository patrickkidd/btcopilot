# Setting up a checkout

How to go from nothing to a working server and green tests, on a Mac or in a Claude Code
cloud session. Follow it top to bottom. Every path below is relative to the clone root.

## 1. Clone

```bash
git clone https://github.com/patrickkidd/btcopilot.git
cd btcopilot
```

The repo is standalone; nothing needs to sit beside it. Work happens in worktrees under
`.claude/worktrees/<ticket>`; a worktree reads the main clone's `.env` and private corpus, so
neither is copied into it.

**Optional: the private corpus.** Clinical sources, approved mockups, production dumps and the
plain copies of the rulings live in the private repo `patrickkidd/btcopilot-sources`. Clone it
inside the main clone (it is gitignored there):

```bash
git clone https://github.com/patrickkidd/btcopilot-sources.git btcopilot-sources
```

To keep it elsewhere, set `BTCOPILOT_SOURCES` to its path. Nothing in the app, the tests or the
sandbox needs it. The flush scripts in `.claude/skills/two-clocks/bin/` write into it and stop
with a message naming `BTCOPILOT_SOURCES` when it is absent. Agents read the approved designs
from `btcopilot-sources/fd-corpus/design/`.

## 2. Tools

| Tool | Why | Mac |
|---|---|---|
| uv | Python 3.11 and every Python dependency | `brew install uv` |
| Node 22 and npm | the chat page (`web/`) | nvm or `brew install node` |
| Docker | the sandbox's Postgres | Docker Desktop |
| Redis | the sandbox's broker (the `redis-server` binary) | `brew install redis` |
| Ollama with `qwen3:8b` | the sandbox's coach, free | `brew install ollama`, `ollama pull qwen3:8b` |
| sops and age | the encrypted prompts and rulings under `private/` | `brew install sops age` |
| gh | PRs and the release workflow | `brew install gh`, `gh auth login` |
| jq | the git guard `bin/git-guard`, run before every Bash command by `.claude/settings.json` | `brew install jq` |

## 3. Install

```bash
uv sync --extra app --extra test         # fetches Python 3.11 (pinned in .python-version) into .venv
npm --prefix web ci
npm --prefix web run build               # writes btcopilot/static/web/; the Python and page tests read it
```

`uv.lock` is gitignored, so each machine resolves the newest versions `pyproject.toml` allows;
a failure that only one machine sees may be a version difference.

## 4. The encryption key

`private/prompts/` (the coach's prompts) and `private/oracle/` (Patrick's rulings) are encrypted
with sops to age keys. The app, the tests and the sandbox look for the key in
`~/.config/sops/age/keys.txt` (or the file `SOPS_AGE_KEY_FILE` names), or take its text from the
`SOPS_AGE_KEY` environment variable.

**From a machine that already has it** (Patrick's Mac): copy `~/.config/sops/age/keys.txt`, a
two-line file (a comment carrying the public key, then the `AGE-SECRET-KEY-` line), to the same
path on the new machine, then:

```bash
chmod 600 ~/.config/sops/age/keys.txt
bin/sops-setup.sh ~/.config/sops/age/keys.txt
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt   # in your shell profile, for sops itself
```

**A new key of your own:** `age-keygen -o ~/.config/sops/age/keys.txt`, send Patrick the public
key it prints, and wait for him to add it as a recipient.

**Claude Code cloud:** put the key file's text in the environment's settings as `SOPS_AGE_KEY`.
Anyone using that environment can read it. No key file is needed there: the app, the tests and
the oracle guards hand the key to sops from that variable.

`SOPS_AGE_KEY_FILE` is only needed for the `sops` command itself (git diffs of the encrypted
files, editing a ruling), whose own default on macOS is under `~/Library`.

Without the key, every place that notices says one line naming the file and the variable:

```
no sops key in ~/.config/sops/age/keys.txt or SOPS_AGE_KEY: the open-source prompts are in use, not the private ones
```

- **The unit suites** print it once per run and run on the open-source prompts.
- **The sandbox** prints it and refuses to start; `sandbox up <name> <port> --open-prompts`
  starts it on the open-source prompts on purpose.
- **Does not work at all:** the app itself (it stops on the first private prompt), the oracle
  guards (`-m conventions`), the live prompt evals, and the flush.

## 5. `.env` at the clone root

Gitignored, never printed, never committed. Only the rows marked "needed" matter for day-to-day
work; the file on Patrick's Mac also carries keys for his other projects.

| Name | Needed for | Where it comes from |
|---|---|---|
| `ANTHROPIC_TESTING_KEY` | needed for `sandbox up --real` and the live evals, except on a Bedrock machine (section 6); spends real money, ask Patrick first | Anthropic console, the testing workspace |
| `GOOGLE_GEMINI_API_KEY` | needed for `pytest --e2e` and `--real`, except on a Bedrock machine | Google AI Studio |
| `ATLASSIAN_TOKEN` | needed for Jira reads and writes | Atlassian account, API tokens |
| `GRAFANA_SA_TOKEN`, `GRAFANA_URL` | only `bin/cloudbackfill.py`, once, at the FD-374 cutover (doc/MONITORING.md) | the old Grafana Cloud service account |
| `DIGITALOCEAN_ADMIN` | box administration, confirmed with Patrick each time | DigitalOcean API tokens |
| `GITHUB_FD_THEORY_TOKEN` | the concept pages locally; the app reads it as `FLASK_THEORY_GITHUB_TOKEN` | GitHub fine-grained token, read-only on btcopilot-sources |
| `ASSEMBLYAI_API_KEY` | transcription | AssemblyAI dashboard |
| `ANTHROPIC_PRODUCTION_KEY`, `GRAFANA_PG_PASSWORD` | the box's own secrets, kept for reference; production reads `/etc/fd/secrets.env` | the same consoles |
| `FLASK_APP`, `FLASK_CONFIG` | local flask commands outside the sandbox | fixed values: `btcopilot.app:create_app` and `development` |
| `FLASK_VAPID_PUBLIC_KEY`, `FLASK_VAPID_PRIVATE_KEY`, `FLASK_VAPID_SUBJECT` | needed by every local flask command outside the sandbox: the app refuses to start without them | `python -m btcopilot.push` prints the pair; the subject is `mailto:` and your own address |
| `GROK_API_KEY`, `OPENAI_API_KEY`, `MINIMAX_API_KEY`, `TWINE_*`, `GITHUB_TOKEN`, `FD_BUILD_*` | not read by this repo; the desktop app's build and older experiments | — |

The file holds multi-line values, so it cannot be `source`d; read one key with
`grep '^NAME=' .env | cut -d= -f2-`.

**Which clone.** Work on this project happens in the standalone clone and its ticket worktrees
(`.claude/worktrees/<ticket>` under it). The older clone under `theapp` is retired for this project:
it serves the legacy app's upkeep and nothing else, so never create a ticket worktree there.

## 6. A working server: the sandbox kit

One command brings up Postgres, Redis, the Celery worker, the fixture records and the built
page on Flask, with the coach on the local Ollama model:

```bash
bin/sandbox/sandbox up <name> <port>     # e.g. bin/sandbox/sandbox up mine 8912
bin/sandbox/sandbox down <name> --purge
```

It needs Docker, `redis-server`, Ollama with the model (or `--real`), and the age key
(section 4). Its data
lives in `~/btcopilot-sandbox/<name>/` (override with `SANDBOX_HOME`); `.env` is read from the
main clone's root (override with `SANDBOX_DOTENV`). `bin/sandbox/sandbox` with no arguments
prints every command. Port 8888 is Patrick's own server: never use it.

**Bedrock.** The app calls Anthropic's API with the key by default. `BTCOPILOT_MODEL_PROVIDER=bedrock`
is the only switch to Amazon Bedrock: every model call then goes through Bedrock with the shell's
AWS sign-in, no Anthropic or Google key is read, and a Gemini-named title, summary or cluster call is answered by Haiku
(Gemini is not on Bedrock); a Gemini coach model fails plainly and a Gemini side-by-side model is skipped. Bedrock needs `AWS_REGION`; the SDK reads `ANTHROPIC_BEDROCK_BASE_URL`
and `AWS_CA_BUNDLE` itself. Without a usable sign-in the app stops at startup and says so. Bedrock needs the optional `bedrock` extra (`uv sync --extra bedrock`; the test extra includes it); the production image never installs it.

```bash
export AWS_PROFILE=default
aws sso login
export AWS_REGION=us-west-2
export BTCOPILOT_MODEL_PROVIDER=bedrock
bin/sandbox/sandbox up mine 8912 --real
```

The sandbox kit copies the flag into the instance's settings and passes `AWS_PROFILE`,
`AWS_REGION`, `AWS_CA_BUNDLE` and `ANTHROPIC_BEDROCK_BASE_URL` to the server and workers. Without
`--real` the coach stays on the local Ollama model. A Claude model with no Bedrock inference
profile in `BEDROCK_MODELS` (`btcopilot/provider.py`) is named at startup.

## 7. Tests

```bash
uv run pytest -n auto -m "not conventions" btcopilot/tests -q   # the Python suite in parallel, no key needed; -n 0 only to locate a hang or a collision
npm --prefix web test                                    # the page's unit tests
. $(bin/sandbox/sandbox env <name>); npm --prefix web run test:visual   # Playwright, against a sandbox
uv run pytest -m conventions btcopilot/tests             # the oracle guards, key needed (CI runs them)
```

Every new test cites the ruling it proves (CLAUDE.md, "Testing").

## 8. Production

Production is reached only from Patrick's Mac and GitHub:

- `ssh familydiagram` is an alias in his `~/.ssh/config` with his key; the box has no other.
- Deploys run the release workflow: `gh workflow run release.yml --ref <branch>`, which needs
  `gh` signed in with write access to the repo.
- `sandbox up --dev` serves the page to his phone at `https://turin:<port>/app/`; `turin` is his
  Mac's name and the certificate lives in `~/btcopilot-sandbox/certs/`.
- Grafana and DigitalOcean tokens are in his `.env` only.

## 9. Claude Code cloud sessions

From the Claude Code documentation (code.claude.com/docs/en/cloud-environments), a cloud session
is Ubuntu 24.04 on x86_64 with 4 CPUs, 16 GB and 30 GB of disk, uv, Node 22, Docker, Postgres
16 and Redis 7 installed, `gh` signed in through `GH_TOKEN`, and GitHub reachable through a
proxy. Not yet tried in a cloud session:

| Step | In the cloud |
|---|---|
| Clone, `uv sync`, `npm ci`, build, both unit suites | expected to work |
| The private corpus | only if btcopilot-sources is added to the session when it starts |
| The age key | put its text in the environment's settings as `SOPS_AGE_KEY` (section 4); anyone using that environment can read it |
| sops | not installed; the setup script downloads it, as `.github/workflows/ci.yml` does |
| The sandbox | Docker and Redis are there; the kit also needs `lsof`. Ollama is not documented: with no GPU the local coach would be minutes per turn at best, so plan on `--real` with Patrick's yes |
| `ssh familydiagram`, the phone at `turin` | no: there is no ssh egress documented and no key |
| Deploys | `gh workflow run` works if the session's GitHub access allows workflow dispatch |

## 10. Claude Code user-level files

Patrick's user-level Claude Code rules and the efficiency and theory skills live in the private corpus,
under `btcopilot-sources/claude-user/`, as the only copy. On a new machine, after cloning the
corpus, link them into `~/.claude`:

```bash
ln -s ~/btcopilot/btcopilot-sources/claude-user/CLAUDE.md ~/.claude/CLAUDE.md
mkdir -p ~/.claude/skills
ln -s ~/btcopilot/btcopilot-sources/claude-user/skills/efficiency ~/.claude/skills/efficiency
ln -s ~/btcopilot/btcopilot-sources/claude-user/skills/theory ~/.claude/skills/theory
```
