# CLAUDE.md — btcopilot

Backend for the chat app (the personal app, the review and the admin commands). The Pro
backend and the training app live on branch `master-legacy`, not here.
The extraction pipeline and the pending data pool were removed 2026-09-23 (R-0414); last commit holding them: a7eeb2c.

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
- **A picture that needs that much prose does not speak (2026-09-23, Patrick: "if you have to
  include that much prose/copy then your visual concepts don't speak for themselves enough. a
  little is ok, but not this much").** What he sees: the frames, one sentence per concept, the
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

## Confidential Data Rules

Induction reports, GT exports, and coach sessions contain clinical data, and
extraction/conversational-AI experiment artifacts are proprietary IP — **NEVER store any
of it in the btcopilot repo, and NEVER in btcopilot-sources**. All of it lives in the
private **fdserver** repo (2026-07-22, Patrick's direction; supersedes the earlier
btcopilot-sources scheme).

**btcopilot-sources is ONLY for copyrighted academic literature** (Bowen theory book
chapters etc.; rarely added to). It will be retired once the Pro app's Copilot feature is
replaced by the embedded personal app. Never route generated data or experiment artifacts
there.

| Data Type | WRONG Location | Correct Location |
|-----------|----------------|-----------------|
| Induction reports | `btcopilot/doc/induction-reports/`, `btcopilot-sources/` | `fdserver/training/induction-reports/` |
| GT exports | `btcopilot/instance/gt_export.json` (runtime copy only), `btcopilot-sources/` | `fdserver/training/gt-exports/` |
| Coach feel-test sessions (`bin/coach_chat.py`) | `btcopilot/doc/log/coach-sessions/`, `btcopilot-sources/` | `fdserver/coach-sessions/` (freeform sessions contain real personal content). In-repo path is opt-in `--out shared` and only for synthetic-persona runs. |

`btcopilot/instance/gt_export.json` remains the runtime file the test harness reads; the
authoritative archived exports live in fdserver.

New clinical/IP data outputs: store in `fdserver/`, add to btcopilot `.gitignore` if a
runtime copy is needed, update this section.

---

## Documentation Index

**Integrate new domain knowledge into the authoritative doc for that domain.**

| Domain | Doc |
|--------|-----|
| Data model (schema, enums, validation) | [doc/specs/DATA_MODEL.md](doc/specs/DATA_MODEL.md) |
| Prompt engineering decisions | [doc/PROMPT_ENGINEERING_LOG.md](doc/PROMPT_ENGINEERING_LOG.md) |
| Bowen theory concepts | [CONTEXT.md](CONTEXT.md) |
| Drawability — when the timeline picture may draw vs must ask (5 rules, ruled 2026-08-31) | [doc/DRAWABILITY.md](doc/DRAWABILITY.md) |

| Diagram layout/rendering/SVG | [doc/FAMILY_DIAGRAM_VISUAL_SPEC.md](doc/FAMILY_DIAGRAM_VISUAL_SPEC.md) |
| Client-server data sync | [familydiagram DATA_SYNC_FLOW.md](../familydiagram/doc/specs/DATA_SYNC_FLOW.md) |
| Decisions (career, strategy) | [decisions/log.md](decisions/log.md) — see top-level CLAUDE.md "Documentation Routing > Decisions" for triggers and rules |
| Architecture decisions (backend) | [adrs/](adrs/) — durable patterns only, not point-in-time choices (those go in decisions/log.md) |
| IRR calibration, coding guidelines | [doc/irr/](doc/irr/) |
| Calibration system (as-built) | [doc/adrs/calibration.md](doc/adrs/calibration.md) |
| Synthetic client personas/evals | [doc/specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md](doc/specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md) |
| Synthetic client dev log | [doc/log/synthetic-clients/](doc/log/synthetic-clients/) |
| Psychological foundations | [doc/specs/PSYCHOLOGICAL_FOUNDATIONS.md](doc/specs/PSYCHOLOGICAL_FOUNDATIONS.md) |
| Feature/behavior specs | [doc/specs/](doc/specs/) |
| Bowen theory formal spec | [doc/specs/BOWEN_THEORY.md](doc/specs/BOWEN_THEORY.md) |
| Diagram layout — language-agnostic spec | [doc/FAMILY_DIAGRAM_LAYOUT_ALGORITHM.md](doc/FAMILY_DIAGRAM_LAYOUT_ALGORITHM.md) |

## Chat-first rebuild (CANONICAL)

The chat-first rebuild ("a coach who never forgets your family") is documented under
the two-clocks regime in [doc/](doc/):
- **Read [doc/STATE.md](doc/STATE.md) FIRST in every session touching this work** — it is the current system of record — **then [doc/TOPICS.md](doc/TOPICS.md)**, the register of open topics by plain name; the owner names a topic in his own words and the session continues from its block. **End every session with `/two-clocks`.**
- [doc/HISTORY.md](doc/HISTORY.md) — the event clock: decision/brainstorm history; append, never rewrite.
- [doc/DRAWABILITY.md](doc/DRAWABILITY.md) — ruled drawing/asking rules.
- [doc/PICTURE_IDEAS.md](doc/PICTURE_IDEAS.md) — round 7 (2026-09-23):
  fourteen picture-spot concepts, the passage each draws from, and the critic's verdict.
- [doc/MOBILE_VIEWS.md](doc/MOBILE_VIEWS.md) — twenty-four small-screen
  data views from shipped phone apps, each mapped onto the eight things the picture must say.
- **The human oracle (MANDATORY regime; store lives in the PRIVATE fdserver repo)**: Patrick's direction is the binding input to all agentic development on this app and is maintained as a BKM store — fdserver `doc/oracle/` (SPEC + rulings index + evidence). Public docs cite rulings by id (`[Oracle: R-0001]`) and never restate quotes. Mining ops are append/merge/split/reword ONLY; withdrawal = status SUPERSEDED naming the successor (newest statement wins); never author a ruling the human did not say; capture his new statements into the store immediately. No raw transcripts anywhere — mine and maintain, never archive (R-0064). Nothing store-shaped may live in this public repo (the SPEC's oracle-outside-the-store guard will police this once built).
These are living documents: every session refines them as part of its work (append to
HISTORY, revise STATE).
The clinical corpus itself lives OUTSIDE all repos at ~/fd-corpus (see STATE.md).

Other: [README.md](README.md), [doc/plans/](doc/plans/)


### MVP State Tracking

Jira is the single source of truth (MVP epic **FD-264**). Site, id format, API auth, and the approval rule live in the top-level [CLAUDE.md "Jira (CANONICAL)"](../CLAUDE.md#jira-canonical) — not redefined here.

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
| Personal backend | `btcopilot/personal/` | The chat app's API (JSON): the coach's turns and the tools it edits the record with |
| Review | `btcopilot/review/` | The coders' app |
| Admin | `btcopilot/admin/` | Flask CLI commands for the box |
| Schema | `btcopilot/schema.py` | Core data model shared with the desktop app (PUBLIC — see boundary rule below) |
| Extensions | `btcopilot/extensions/` | Flask extensions (DB, mail, Celery, tracing) |
| Auth | `btcopilot/auth/` | Passwordless sign-in, `current_user` |
| Models | `btcopilot/models/` | SQLAlchemy: User, Diagram, License, Policy, AccessRight |
| Matching | `btcopilot/matching.py` | Content matching of two PDPs (people, events, pair bonds) and the F1 built on it |

### Public API Boundary (MANDATORY)

`btcopilot.schema` is the ONLY public submodule — it is imported by the desktop app builds where Flask, SQLAlchemy, and all other server dependencies are unavailable. **schema.py must NEVER import from any other btcopilot module** (pdp, extensions, personal, app, auth, llmutil, celery, modelmixin). This includes deferred/lazy imports inside methods.

If schema.py needs a utility function that currently lives in a private module, move that function INTO schema.py. Do not import it.

The isolation test at `btcopilot/tests/schema/test_isolation.py` enforces this boundary — run it after any schema.py changes.

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
| Synthetic Testing | `btcopilot.tests.chat.personal.synthetic`, [tests README](btcopilot/tests/chat/personal/README.md) | Persona generator, conversation simulator, quality evaluator. Run: `uv run pytest btcopilot/btcopilot/tests/chat/personal/test_synthetic.py -v -m e2e` |
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
- **Raw transcripts are always committed** — they are irreplaceable ground truth. Never delete them.
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

### Data Serialization (Pro App Compatibility)

`Diagram.data` MUST use pickle format. Only these types allowed in pickle data:
- Built-in: `str`, `int`, `float`, `bool`, `list`, `dict`, `None`
- QtCore types from PyQt5 (e.g., `QDate`, `QDateTime`)

**NEVER pickle**: classes from `btcopilot.*`, `fdserver.*`, dataclasses, Pydantic models, third-party classes (except QtCore). User will manually delete broken discussions with `ModuleNotFoundError`.

---

## Flask Server

**The dev server on port 8888 is managed by the user. NEVER start one yourself.**

| Action | Command |
|--------|---------|
| Verify running | `curl -s http://127.0.0.1:8888/ > /dev/null && echo "OK" \|\| echo "ERROR"` |
| Not running | **STOP and ask user** |
| Not responding | Ask user to restart |
| Bytecode issues | Ask user: `find . -name "*.pyc" -delete` |

Auto-authenticates as `patrick@alaskafamilysystems.com`. Live reloading enabled.

**Uses Flask 3.x native CLI** — the obsolete `flask-cli` package is incompatible and has been removed. If you see `create_app() takes 0 to 1 positional arguments but 2 were given`, check `uv pip show flask-cli` and remove if present.

**Troubleshooting**: Import errors → check user is in project root. Server fails on first request → bytecode cache issue, clear and restart.

### Web UI Testing (chrome-devtools MCP)

**Mandatory for all HTML/CSS/JS/Flask route changes:**
1. Verify Flask server running (port 8888)
2. Navigate to page via `navigate_page` or `new_page`
3. Take snapshot + screenshot to verify UI state
4. Test interactions (click, fill, etc.)
5. Verify before declaring completion

### Dashboard Server
Ask user to start/restart before using chrome-devtools MCP: `cd dashboard && uv run python app.py` (port 8765).

---

## Development Commands

### Environment
- **Venv**: uv workspace (`pyproject.toml`)
- **Install**: `uv sync --extra app --extra test`
- **PyTorch**: Pinned to `torch>=2.0.0,<2.1.0` (newer versions lack macOS x86_64 wheels). If wheel errors occur, remove `uv.lock` and re-sync.
- **PostgreSQL**: `docker-compose up fd-server` (requires `docker volume create familydiagram_postgres` first)
- **Production**: `docker-compose -d production.yml up fd-server`

### Testing
- **All tests**: `uv run pytest -vv tests`
- **Oracle guards** (`btcopilot/tests/conventions/`, marker `conventions`) read the sops-encrypted rulings store and run on CI only, where the key is; locally run `uv run pytest -m "not conventions" ...`. Without a key they fail, never skip.
- **E2e tests** (real LLM calls): `uv run pytest --e2e -m e2e` — requires `GOOGLE_GEMINI_API_KEY` from `theapp/.env`
- **Async**: `--asyncio-mode=auto` (configured in `btcopilot/tests/pytest.ini`)
- **Directories**: `btcopilot/tests/chat/` (the chat app's suite), `btcopilot/tests/schema/`, `btcopilot/tests/test_*.py`
- **Every test cites the ruling it proves (R-0421)**: `# R-0NNN` as the first line under a Python test's def, `// R-0NNN` on the line above a TypeScript/Playwright test; several ids comma-separated; never a process ruling for product behaviour.
- **A test that proves no ruling** says `# no ruling` / `// no ruling` and gets one line in `doc/TESTS_WITHOUT_RULING.md` saying what it proves; never guess an id.
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
