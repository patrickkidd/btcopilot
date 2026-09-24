# CLAUDE.md — btcopilot

Backend for the chat app (the personal app, the review and the admin commands). The Pro
backend and the training app live on branch `master-legacy`, not here.
The extraction pipeline and the pending data pool were removed 2026-09-23 (R-0414); last commit holding them: a7eeb2c.

## PRIME DIRECTIVE — re-read before composing every reply

Patrick's #1 cost is wasted reading time. Every reply is judged against these:

1. **Architect register.** Say only what changes his decision. No preamble, no restating his context, no narrating your process.
2. **Final message stands alone.** He reads ONLY your last message — never todos, logs, or prior turns. State current state, the decision, the next action.
3. **Plain words.** No jargon, acronyms, symbol names, file paths, or metric labels in prose. Write "no dupes in 10 runs", not "raw-dup 1.0→0.0".
4. **Concise ≠ lossy.** Compress the wording, never drop substance he needs.
5. **Facts, not opinions** — unless he explicitly asked for a recommendation.
6. **Don't break a rule you already know.** Worktrees, never the main clone. Don't remind him of git mechanics — 25 years a developer.

This block is a deliberate distillation of recurring corrections, not duplicate prose — do not "DRY it away".

## Where the work starts

Work on `master` through ticket worktrees (below). Every session reads
[doc/STATE.md](doc/STATE.md) first, then [doc/TOPICS.md](doc/TOPICS.md), then
[doc/HOW_THIS_PROJECT_WORKS.md](doc/HOW_THIS_PROJECT_WORKS.md) (binding process rules). The
Jira epic is **FD-362**.

## Worktrees, branches, PRs

The main clone stays on `master` and is read-only to Claude: never edit, branch-switch or run
anything in it. All work happens in a worktree at `.claude/worktrees/<ticket>` on a branch of
the same name (`FD-NNN`; if taken, `FD-NNN-<slug>`; no ticket, a short slug), created with
`git worktree add .claude/worktrees/FD-NNN -b FD-NNN` and entered with `EnterWorktree(path=...)`.

- Commit and push the worktree's own branch without asking; one git mutation per command,
  never chained. Open a **draft PR at the first push**, title starting with the Jira id, and
  keep it current. Reports link the PR, not diffs.
- Never merge, never push `master`, never rebase or force-push a pushed branch without a yes.
  `master` is server-protected: PR required.
- Remove a worktree only after its PR merges or Patrick says "discard".
- **A change to the rulings store needs its fingerprints re-pinned**: CI prints the lines to
  paste.

## Production

The box is reached as `ssh familydiagram` (Patrick's ssh config; never the raw IP). Deploys: the release workflow builds and tags the image; the rollout runs on the box from `/var/www/btcopilot/deploy` with `--env-file /etc/fd/secrets.env`. Grafana Cloud is administered through its API with `GRAFANA_SA_TOKEN` and `GRAFANA_URL` from the parent `.env`.

## Jira

Site `https://alaskafamilysystems.atlassian.net`, project **FD**, REST v3, HTTP basic as
`patrick@alaskafamilysystems.com` with `ATLASSIAN_TOKEN` from `.env` at the clone root
(gitignored; never echo it). Search is `POST /rest/api/3/search/jql`. Reads need no approval;
every create, update, transition, comment or delete needs a one-line yes from Patrick for the
operation (draft the content yourself).

```bash
TOKEN=$(grep '^ATLASSIAN_TOKEN=' .env | cut -d= -f2-)
curl -s --user "patrick@alaskafamilysystems.com:${TOKEN}" \
  "https://alaskafamilysystems.atlassian.net/rest/api/3/issue/FD-NNN?fields=summary,status,description"
```

## Sandbox and manual testing (MANDATORY)

- **Port 8888 is Patrick's server** on `master`: never start, stop, restart or test worktree
  changes against it. **Port 8889 is Claude's sandbox**, started from the worktree; Claude
  owns its lifecycle. Never the production database.
- Every web change is verified in a real browser against the sandbox before it is called
  done: check it answers (`curl -s http://127.0.0.1:8889/ >/dev/null && echo OK`), open the
  page, take a snapshot and a screenshot, exercise the interactions, report what was seen.
  Say "appears correct in testing, please verify", never "done".

## Owner corrections that bind every reply (2026-09-09)

- **His terms, verified 2026-09-22 on the round-6 mockups: "cluster" (never "stretch"), "event"
  (never "moment").** Captions, rulings and code comments use those two words.
- **Never coin a term.** Say the thing in common words every time ("signing in with an email
  code also creates the account", never "login-is-signup"). A phrase from a doc is not his term
  unless he used it. That includes the corpus's own vocabulary: "topic block", "two clocks",
  "state clock", "flush", "T-11" (verified failure 2026-09-13: "topic block?? again, with the
  clever language!"). Say "the notes on the branch", "the list of open items", "the file".
- **One test account, reused (2026-09-22, Patrick).** the claude-test account is the only
  test account on production; never create another, and delete any scratch account the moment
  it is no longer needed.
- **Never verify on production (2026-09-22, Patrick objected to nine scratch accounts on the
  dashboard).** A deploy is checked with a probe of public pages only; every walk that signs
  in, chats or writes runs on a sandbox stack, never the box.
- **Mockup method, corrected 2026-09-23 (Patrick: "nifty tech should only be used when it gives
  flexibility that actually helps communicate"; "you click somewhere and a circle appears that
  doesn't line up with anything"; "should it just be title and citation?").** (1) 3-D or motion only
  when it communicates what flat cannot, and the frame must say what that is by itself. (2) A
  mockup's tap does what the app's tap does — the ruled tap language (pick, words on the picture,
  chip lights, second tap speaks) — built on the app's own picture code, never reinvented. (3)
  Title and citation only under a concept. (4) If a stranger cannot read the frame unaided, the
  concept fails; users never see prose.
- **A picture that needs that much prose does not speak (2026-09-23, Patrick, R-0398: a
  concept that needs a lot of text to explain it is not visual enough; a little text is fine).** What he sees: the frames, one sentence per concept, the
  decisions. Gates, passages, costs and checks live in the verdict file, never on his page.
- **Every gallery passes a visual critique before Patrick sees it (2026-09-22, his words: "there
  are so many obvious, visual and aesthetic errors in these").** A separate agent, not the
  designer, reviews every frame: what is the message, is every mark explained in the caption, is
  it busier than the app today, did anything vanish without the caption saying why, any invented
  word; it argues keep or kill per frame and only survivors are published. The message the picture
  must carry is derived first, from the sources, and the drawing walks back from it.
- **A gallery gives direction, not a menu (2026-09-22, Patrick: "keep the prose in these
  artifacts more to the point and actually give clear and simple direction").** Say at the top
  whether options exclude each other or combine, recommend one, and keep every caption to what
  the reader must decide.
- **Mockups are always published as artifacts (2026-09-22, Patrick: "mockups should always be in
  artifacts. remember that").** A gallery on disk is not a deliverable; publish it (private by
  default) and give the link. The source stays in ~/theapp/btcopilot-sources/fd-corpus/design/.
- **He is Patrick (2026-09-11).** Never "the owner" in a document or a reply; it is ambiguous.
- **Sandbox addresses use `turin`, never `turin.local` (2026-09-11).** The review app is
  https://turin:8891/personal/.
- **Every question mark is a question (2026-09-11).** Each "?" he types is covered somewhere,
  explicitly or implicitly, never recited one by one and never repeated between the reply and
  the drawing.
- **Artifacts are UI drawings in the app's own style, never text documents (2026-09-11).** The
  open decisions go on the drawing, one numbered list in one place, each self-contained with its
  example, and are never repeated in the reply. The reply is a link and a few lines.
- **No topic page, no dashboard, no audit page (2026-09-11).** Never generate or link a page
  built from the register or the ledger; he will not read it.
- **UI options with one-line descriptions, never a research project (2026-09-11).** Every turn
  on a design topic shows him drawn options and says what each is. Captions are not forced
  short: not verbose, but enough that every non-self-evident control is explained.
- **Never repeat in the reply what an artifact already says (2026-09-16).** When a page is
  published, the reply is the link and only what is not on the page: the decision he must
  make, or what changed since. Duplicated content makes him read both.
- **Sub-agents do the work; this context stays small (2026-09-16, repeated).** Mechanics run in
  Sonnet or Haiku sub-agents under an auditor; the coordinator holds one-line summaries only,
  relays nothing mid-run, and posts one final message when everything is done or when there is
  something for Patrick to do.
- **Verified failure 2026-09-22 (Patrick: "don't forget your instructions about sub-agents").**
  The coordinator ran deploys, probes, log reads and file edits itself for hours, with an interim
  reply after each. Every mechanical step — a deploy, a probe, a log read, a golden regeneration, a
  box fix — goes to a Sonnet or Haiku sub-agent with a one-page brief; a build goes to Opus; an
  Opus auditor is spawned before the workers on every multi-agent run. The coordinator's own tool
  calls are limited to reading briefs and reports, spawning, and the final message.
- **Cost estimates are for the work, not for validation.** Squashing seven migrations is a few
  tool calls, not an hour. Verify only what changed, once, at the cheapest level that proves it;
  never re-verify before a merge is even in sight.

---

## Private corpus

Clinical data, experiment output and anything store-shaped never enter this repo. They live
outside every repo at `~/theapp/btcopilot-sources/fd-corpus/`: `design/` holds the approved
mockups and galleries (read, never copy in); `private/` holds the prompt mirror, the prompt
fidelity audit, the ledger of unclear points, the test method, and plain copies of the
rulings and the oracle SPEC. The encrypted rulings store and prompts in this repo
(`private/oracle/`, `private/prompts/`, sops with age) are the only private material here.

---

## Documentation Index

**Integrate new domain knowledge into the authoritative doc for that domain.**

| Domain | Doc |
|--------|-----|
| Where the build stands, what is unresolved | [doc/STATE.md](doc/STATE.md) |
| Process rules (binding) | [doc/HOW_THIS_PROJECT_WORKS.md](doc/HOW_THIS_PROJECT_WORKS.md) |
| Append-only history | [doc/HISTORY.md](doc/HISTORY.md) |
| Topic map: where each subject lives | [doc/TOPICS.md](doc/TOPICS.md) |
| Screens and approved UI | [doc/UI_SPEC.md](doc/UI_SPEC.md), [doc/SCREENS.md](doc/SCREENS.md), [doc/UI_STANDARDS.md](doc/UI_STANDARDS.md) |
| The app's JSON API | [doc/API.md](doc/API.md) |
| Data model (schema, enums, validation) | [doc/specs/DATA_MODEL.md](doc/specs/DATA_MODEL.md), [doc/specs/PDP_DATA_FLOW.md](doc/specs/PDP_DATA_FLOW.md), [doc/EVENT_MODEL.md](doc/EVENT_MODEL.md) |
| Clusters | [doc/CLUSTERS.md](doc/CLUSTERS.md) |
| Drawability — when the timeline picture may draw vs must ask | [doc/DRAWABILITY.md](doc/DRAWABILITY.md) |
| Diagram rendering | [doc/FAMILY_DIAGRAM_VISUAL_SPEC.md](doc/FAMILY_DIAGRAM_VISUAL_SPEC.md), [doc/FRAGMENT_CONVENTIONS.md](doc/FRAGMENT_CONVENTIONS.md) |
| Tests and known defects | [doc/TEST_STRATEGY.md](doc/TEST_STRATEGY.md), [doc/KNOWN_DEFECTS.md](doc/KNOWN_DEFECTS.md) |
| Box and release | [doc/PLATFORM_BUILD.md](doc/PLATFORM_BUILD.md), [deploy/README.md](deploy/README.md) |
| Prompt engineering decisions | [doc/PROMPT_ENGINEERING_LOG.md](doc/PROMPT_ENGINEERING_LOG.md) |
| Bowen theory | [CONTEXT.md](CONTEXT.md), [doc/specs/BOWEN_THEORY.md](doc/specs/BOWEN_THEORY.md) |
| SARF definitions, IRR calibration | [doc/sarf-definitions/](doc/sarf-definitions/), [doc/irr/](doc/irr/) |
| Synthetic clients | [doc/specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md](doc/specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md), [doc/specs/PSYCHOLOGICAL_FOUNDATIONS.md](doc/specs/PSYCHOLOGICAL_FOUNDATIONS.md), [doc/log/synthetic-clients/](doc/log/synthetic-clients/) |
| Decisions | [decisions/log.md](decisions/log.md) — log every significant decision immediately |
| Architecture decisions | [doc/adrs/](doc/adrs/) — durable patterns only |
| Subsystem analyses | [doc/analyses/](doc/analyses/) |

Old-app material lives in [doc/archive/](doc/archive/) and is not current knowledge.
Jira is the single source of truth for task status. Domain knowledge goes into the one
authoritative doc above; if none exists, create it in `doc/` and add it here.

**The human oracle**: Patrick's direction is the binding input, kept in the encrypted
rulings store `private/oracle/`. Public docs cite rulings by id (`[Oracle: R-0001]`) and
never restate quotes; capture his new statements into the store immediately; never author a
ruling he did not say. `HOW_THIS_PROJECT_WORKS.md` carries the rest.

### Synthetic Client Dev Log (MANDATORY)

After ANY change to synthetic conversation generation, create a timestamped entry in `doc/log/synthetic-clients/`. See [README.md](doc/log/synthetic-clients/README.md) for triggers and format.

Triggers: prompt edits, response mode/weight changes, structural token mechanisms, evaluator tuning, persona generation, AND qualitative observations from evaluating discussions.

Process: make change → create `doc/log/synthetic-clients/YYYY-MM-DD_HH-MM--description.md` → update README index → notify.

---

## Architecture

btcopilot provides:
- Backend for the chat app

### Core Structure

| Component | Location | Purpose |
|-----------|----------|---------|
| App factory | `btcopilot/app.py:create_app()` | Flask init, extensions, error handlers |
| Personal backend | `btcopilot/` | The chat app's API (JSON): the coach's turns and the tools it edits the record with |
| Review | `btcopilot/review/` | The coders' app |
| Admin | `btcopilot/admin/` | Flask CLI commands for the box |
| Schema | `btcopilot/schema.py` | Core data model |
| Extensions | `btcopilot/extensions/` | Flask extensions (DB, mail, Celery, tracing) |
| Auth | `btcopilot/auth/` | Passwordless sign-in, `current_user` |
| Models | `btcopilot/models/` | SQLAlchemy: User, Diagram, License, Policy, AccessRight |
| Matching | `btcopilot/matching.py` | Content matching of two PDPs (people, events, pair bonds) and the F1 built on it |

### External Services

- **AI/ML**: Anthropic and Gemini (see `llmutil.py`)
- **Payments**: Stripe licensing
- **Database**: PostgreSQL + SQLAlchemy (`postgresql://familydiagram:pks@localhost:5432/familydiagram`)
- **Config**: Environment-based (`FLASK_CONFIG=development/production`)
- **Docker**: Multi-service with Flask + PostgreSQL

---

## Components & Terminology

| Component | Key Files | Purpose |
|-----------|-----------|---------|
| Synthetic Testing | `btcopilot.tests.synthetic`, [tests README](btcopilot/tests/README.md) | Persona generator, conversation simulator, quality evaluator. Run: `uv run pytest btcopilot/btcopilot/tests/test_synthetic.py -v -m e2e` |
| Visual Spec | [doc/FAMILY_DIAGRAM_VISUAL_SPEC.md](doc/FAMILY_DIAGRAM_VISUAL_SPEC.md) | Platform-independent layout spec: person symbols, PairBond geometry, ChildOf connections, MultipleBirth, generational layout, label positioning |

---

## Domain Knowledge

### Event Field Semantics (MANDATORY — apply everywhere events are displayed or matched)

**Person resolution** — which person an event is "about":
- Birth/Adopted: `child` is the primary link (who was born/adopted). `person`/`spouse` are optional parent links. `person=None` is legitimate.
- All other events: `person` is the primary link.
- When displaying person name for an event, always check `event.kind` first.

**Description** — `EventKind.isSelfDescribing()` (Birth, Adopted, Married, Separated, Divorced, Bonded, Death):
- The kind name IS the description; `Event.description` is optional supplementary detail.
- Display: use `kind.value.capitalize()` as the primary label. Append description only if it adds information beyond the kind name.
- Placeholder descriptions ("New Event", "Unknown", "") should be treated as empty.
- Only Shift and Noted events require and rely on `Event.description` as their primary label. A move is a Noted event [Oracle: R-0364].

**F1 matching**: Structural events skip description matching — only Shift events use descriptions. Events match on kind + date + person links.

**Duplicate people**: `match_people` produces a 1:1 `id_map`. Same-named people are disambiguated by parent name similarity (resolves `Person.parents` PairBond → parent names → fuzzy match, weight `PARENTS_BOOST=0.1`).

### IRR Deliberation Records

- **Purpose:** Capture full diversity of opinions and their evolution per CI theory — both agreement AND unresolved ambiguity — for later retroactive rule extraction with confidence scores.
- **Exhaustiveness rule:** Every substantive point must be captured. Common failure: summarizing away tangential points (heuristics, anecdotes, personal examples, side conversations, process observations, historical references). These MUST be included. Audit transcript line-by-line before declaring completion.
- **Raw transcripts never enter this repo** (they name real people); they live in the private corpus. Their de-identified findings are published in `doc/irr/` [Oracle: R-0413].
- **Always keep `btcopilot/doc/irr/README.md` in sync** when adding/modifying meetings or artifacts.

---

## Development Rules

- Not concerned with legacy data — prefer delete/re-create over backward-compatibility code
- Prefer module-level imports (except in tests)
- `.card` elements with `.card-header` + dynamic lists: always collapsible via header click
- Never pop confirm dialogs for events that will be reflected in UI shortly
- Never use exclamation points in user-facing text
- For DOM/CSS changes, validate against rendered HTML/CSS (pull down page URL if needed)
- Always proactively run the `code-style-enforcer` sub-agent for all source code changes (not markdown)
- When a stack trace is pasted, add a test to reproduce the error if one doesn't exist
- DB is in production — new schema changes need Alembic migrations
- Keep Flask endpoints oriented around updating entries in database tables, not
  just adding a new endpoint for every application verb
- Assume that exceptions are already handled in the blueprint and jsonify() is
  called with an error string and 5xx code

### UI/CSS Styling

All web UI must work in **both light and dark modes**:
- NEVER hardcode background/text colors (no `#f9fafb`, `#ffffff`, etc.)
- Use Bulma semantic classes: `has-text-grey-light`, `.box`, `.notification`, `.message`, `has-text-primary`
- Tables: use `.table` without custom backgrounds
- Test dark mode via chrome-devtools before completing UI work

---

## Flask Server

See "Sandbox and manual testing" above. Flask 3.x native CLI; the obsolete `flask-cli`
package is incompatible (symptom: `create_app() takes 0 to 1 positional arguments but 2 were given`).

---

## Development Commands

### Environment
- **Venv**: the clone's own uv environment (`pyproject.toml`)
- **Install**: `uv sync --extra app --extra test` (Python 3.11, pinned in `.python-version`); web: `npm ci`, then `npm run build` before any test run (Python and web tests read the built page)
- **PyTorch**: Pinned to `torch>=2.0.0,<2.1.0` (newer versions lack macOS x86_64 wheels). If wheel errors occur, remove `uv.lock` and re-sync.
- **PostgreSQL**: `docker-compose up fd-server` (requires `docker volume create familydiagram_postgres` first)
- **Production**: `docker-compose -d production.yml up fd-server`

### Testing
- **Local run**: `uv run pytest -m "not conventions" btcopilot/tests -q`
- **Oracle guards** (`btcopilot/tests/conventions/`, marker `conventions`) read the sops-encrypted rulings store and run on CI only, where the key is; locally run `uv run pytest -m "not conventions" ...`. Without a key they fail, never skip.
- **E2e tests** (real LLM calls): `uv run pytest --e2e -m e2e` — requires `GOOGLE_GEMINI_API_KEY` from `.env` at the clone root
- **Async**: `--asyncio-mode=auto` (configured in `btcopilot/tests/pytest.ini`)
- **Directories**: `btcopilot/tests/` (the chat app's suite), `btcopilot/tests/schema/`, `btcopilot/tests/test_*.py`
- **Every test cites the ruling it proves (R-0421)**: `# R-0NNN` as the first line under a Python test's def, `// R-0NNN` on the line above a TypeScript/Playwright test; several ids comma-separated; never a process ruling for product behaviour.
- **A new test without a citation fails** the trace guard in `btcopilot/tests/conventions/test_oracle.py`; `# no ruling` fails it too (oracle SPEC section 1).

### Database
- **Migrations**: Alembic (`alembic.ini`, `btcopilot/migrations/versions/`)
- **Query**: `docker exec fd-postgres psql -U familydiagram -d familydiagram -c "SQL"`
- **Interactive**: `docker exec -it fd-postgres psql -U familydiagram -d familydiagram`
- **Table structure**: append `-c "\d table_name"`
- **App context**: `uv run python -c "from btcopilot.app import create_app; from btcopilot.extensions import db; app=create_app(); app.app_context().push(); ..."`
- **Common queries**: access rights (`SELECT ar.*, u.username FROM access_rights ar JOIN users u ON ar.user_id = u.id WHERE ar.diagram_id = ?`), user lookup (`SELECT id, username, roles FROM users WHERE id = ?`), diagram ownership (`SELECT id, name, user_id FROM diagrams WHERE id = ?`)

### Background Tasks (Celery)
- **Redis**: `redis-server` (required broker/backend)
- **Worker**: `uv run celery -A btcopilot.celery:celery worker --loglevel=info`
- **Beat**: `uv run celery -A btcopilot.celery:celery beat --loglevel=info`
- **Monitor**: `uv run celery -A btcopilot.celery:celery flower` (http://localhost:5556)
- **Debug**: VSCode configs "Celery Worker (Debug)" and "Celery Beat"

---
