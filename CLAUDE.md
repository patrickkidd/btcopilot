# CLAUDE.md — btcopilot

Backend for Pro/Personal apps, training app, AI extraction system.

---

## Confidential Data Rules

Induction reports and GT exports contain clinical data — **NEVER store in btcopilot repo**.

| Data Type | WRONG Location | Correct Location |
|-----------|----------------|-----------------|
| Induction reports | `btcopilot/doc/induction-reports/` | `btcopilot-sources/training/induction-reports/` |
| GT exports | `btcopilot/instance/gt_export.json` | `btcopilot-sources/training/gt-exports/` |

Symlinks exist for workflow compatibility:
- `btcopilot/doc/induction-reports` → `btcopilot-sources/training/induction-reports/`
- `theapp/instance/gt_export.json` → `btcopilot-sources/training/gt-exports/gt_export.json`

New clinical data outputs: store in `btcopilot-sources/`, create symlink, add to `.gitignore`, update this section.

---

## Documentation Index

**Integrate new domain knowledge into the authoritative doc for that domain.**

| Domain | Doc |
|--------|-----|
| Data model (schema, enums, validation) | [doc/specs/DATA_MODEL.md](doc/specs/DATA_MODEL.md) |
| PDP extraction, deltas, cumulative logic | [doc/specs/PDP_DATA_FLOW.md](doc/specs/PDP_DATA_FLOW.md) |
| SARF coding, GT workflow, approval | [doc/SARF_GROUND_TRUTH_TECHNICAL.md](doc/SARF_GROUND_TRUTH_TECHNICAL.md) |
| Prompt engineering decisions | [doc/PROMPT_ENGINEERING_LOG.md](doc/PROMPT_ENGINEERING_LOG.md) |
| Prompt induction workflow | [doc/PROMPT_INDUCTION_CLI.md](doc/PROMPT_INDUCTION_CLI.md) |
| Bowen theory concepts | [CONTEXT.md](CONTEXT.md) |
| Diagram layout/rendering/SVG | [doc/FAMILY_DIAGRAM_VISUAL_SPEC.md](doc/FAMILY_DIAGRAM_VISUAL_SPEC.md) |
| F1 metrics, evaluation | [doc/F1_METRICS.md](doc/F1_METRICS.md) |
| Chat flow, personal app AI | [doc/CHAT_FLOW.md](doc/CHAT_FLOW.md) |
| Client-server data sync | [familydiagram DATA_SYNC_FLOW.md](../familydiagram/doc/specs/DATA_SYNC_FLOW.md) |
| Decisions (career, strategy) | [decisions/log.md](decisions/log.md) |
| Architecture decisions | [adrs/](adrs/) |
| IRR calibration, coding guidelines | [doc/irr/](doc/irr/) |
| Synthetic client personas/evals | [doc/specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md](doc/specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md) |
| Synthetic client dev log | [doc/log/synthetic-clients/](doc/log/synthetic-clients/) |
| Psychological foundations | [doc/specs/PSYCHOLOGICAL_FOUNDATIONS.md](doc/specs/PSYCHOLOGICAL_FOUNDATIONS.md) |
| Feature/behavior specs | [doc/specs/](doc/specs/) |
| Prompt extraction strategy | [doc/PROMPT_ENG_EXTRACTION_STRATEGY.md](doc/PROMPT_ENG_EXTRACTION_STRATEGY.md) (self-updating after each induction run) |
| Deferred Gemini optimizations | [doc/TODO_GEMINI_SCHEMA.md](doc/TODO_GEMINI_SCHEMA.md) |

Other: [README.md](README.md), [doc/plans/](doc/plans/)

**Key prompt engineering lessons** (details in PROMPT_ENGINEERING_LOG.md): model is Gemini 2.0 Flash; verbose definitions killed F1 scores; see log for what NOT to include in prompts.

### MVP Dashboard Maintenance (MANDATORY)

[MVP_DASHBOARD.md](MVP_DASHBOARD.md) is the primary dev punchlist. Each task links to a detailed analysis in [doc/analyses/](doc/analyses/) — read the linked analysis before re-investigating whether a bug still exists. The dashboard must be a reliable cold-start reference for new sessions.

After completing or reviewing any MVP task:
1. Update the task's row in the tier table (strikethrough if done, add DONE date/notes)
2. Update [REVIEW.md](doc/log/mvp_dashboard/REVIEW.md) with approval/rejection decision
3. Update the "Current State Summary" table if the subsystem status changed
4. Update the sprint plan status if sprint-level progress changed

After new bugs are discovered during testing:
1. Create a T*.md in `doc/log/mvp_dashboard/`
2. Add a row to the appropriate tier table in MVP_DASHBOARD.md
3. Update "Current State Summary" if it affects subsystem status

Additional rules:
- **Anti-staleness**: Never trust dashboard task statuses at face value. Verify against actual code before working on a task. Add findings to the Spot-Check Log.
- **No hardcoded F1 values**: F1 numbers are computed on-demand by admin/audit routes. Dashboard should reference measurement date and conditions, not bare numbers.
- **Task status must match code reality**: If implementation already exists, mark it done regardless of when it was implemented.

### Synthetic Client Dev Log (MANDATORY)

After ANY change to synthetic conversation generation, create a timestamped entry in `doc/log/synthetic-clients/`. See [README.md](doc/log/synthetic-clients/README.md) for triggers and format.

Triggers: prompt edits, response mode/weight changes, structural token mechanisms, evaluator tuning, persona generation, AND qualitative observations from evaluating discussions.

Process: make change → create `doc/log/synthetic-clients/YYYY-MM-DD_HH-MM--description.md` → update README index → notify.

---

## Architecture

btcopilot provides:
- Backend for Pro/Personal apps
- AI/ML interface for SARF research
- PDP (Pending Data Pool) extraction — two modes:
  - **Single-prompt** (Personal app): `pdp.extract_full()` via
    `POST /personal/discussions/<id>/extract`. Full conversation → one LLM call
    → complete PDP. Chat is chat-only.
  - **Per-statement** (Training app): `pdp.update()` per statement for GT
    coding workflows.

### Core Structure

| Component | Location | Purpose |
|-----------|----------|---------|
| App factory | `btcopilot/app.py:create_app()` | Flask init, extensions, error handlers |
| Pro backend | `btcopilot/pro/` | Desktop app API (pickle over HTTPS) |
| Personal backend | `btcopilot/personal/` | Mobile app API (JSON), chat-only conversation + endpoint-driven extraction |
| Training app | `btcopilot/training/` | Domain-expert feedback for AI fine-tuning |
| Schema | `btcopilot/pro/schema.py` | Core data model shared with Pro/Personal apps |
| Personal DB | `btcopilot/personal/database.py` | JSON-based data schema |
| Extensions | `btcopilot/extensions/` | Flask extensions (DB, LLM, ChromaDB) |
| Auth | `btcopilot/auth.py` | User authentication with `current_user` |
| CLI | `manage.py`, `btcopilot/commands.py` | Flask CLI commands |
| Pro models | `btcopilot/pro/models/` | SQLAlchemy: User, Diagram, License, Session, Statement/Discussion |

### External Services

- **AI/ML**: OpenAI (GPT-4o-mini), HuggingFace embeddings, ChromaDB, LangChain
- **Payments**: Stripe licensing
- **Database**: PostgreSQL + SQLAlchemy (`postgresql://familydiagram:pks@localhost:5432/familydiagram`)
- **Vector DB**: ChromaDB in `instance/vector_db/`
- **Config**: Environment-based (`FLASK_CONFIG=development/production`)
- **Docker**: Multi-service with Flask + PostgreSQL

---

## Components & Terminology

| Component | Key Files | Purpose |
|-----------|-----------|---------|
| SARF Editor | `training/templates/components/sarf_editor.html` | Review/edit extracted clinical data (collapsed/expanded views, in-place editing, feedback, cumulative display) |
| Diagram Renderer | `training/templates/components/family_diagram_svg.html`, `training/routes/diagrams.py` | SVG family diagram visualization. Standalone: `/training/diagrams/render/<statement_id>/<auditor_id>`, embed: `?embed=true`, modal via Discussion page "Diagram" buttons |
| Chat Flow | [doc/CHAT_FLOW.md](doc/CHAT_FLOW.md) | Chat-only AI conversation (no extraction). Extraction is endpoint-driven via `pdp.extract_full()` — see [PDP_DATA_FLOW.md](doc/specs/PDP_DATA_FLOW.md) |
| Synthetic Testing | `btcopilot.tests.personal.synthetic`, [tests README](btcopilot/tests/personal/README.md) | Persona generator, conversation simulator, quality evaluator. Run: `uv run pytest btcopilot/btcopilot/tests/personal/test_synthetic.py -v -m e2e` |
| F1 Metrics | [doc/F1_METRICS.md](doc/F1_METRICS.md) | F1 score calculation, entity matching, GT workflow, matching criteria, cache strategy |
| Visual Spec | [doc/FAMILY_DIAGRAM_VISUAL_SPEC.md](doc/FAMILY_DIAGRAM_VISUAL_SPEC.md) | Platform-independent layout spec: person symbols, PairBond geometry, ChildOf connections, MultipleBirth, generational layout, label positioning |

---

## Domain Knowledge

### GT / F1 Data Model

- Birth/Adopted events: `child` is the primary link (who was born/adopted), `person`/`spouse` are optional parent links. `person=None` on birth events is legitimate.
- Other events: `person` is the primary link.
- Structural events (Birth, Death, Married, etc.) skip description matching in F1 — only Shift events use descriptions.

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

## Prompt Induction Workflow

**MANDATORY for changes to**: `btcopilot/personal/prompts.py`, `btcopilot/extensions/llm.py` (`PDP_FIELD_DESCRIPTIONS`)

**Before editing**: read [doc/PROMPT_ENGINEERING_LOG.md](doc/PROMPT_ENGINEERING_LOG.md) and check `PDP_FIELD_DESCRIPTIONS` in `llm.py`. Both must stay in sync.

| Doc | Purpose |
|-----|---------|
| [doc/PROMPT_INDUCTION_CLI.md](doc/PROMPT_INDUCTION_CLI.md) | **PRIMARY** — CLI-driven automated iteration ($0, RECOMMENDED) |
| [doc/PROMPT_OPTIMIZATION_MANUAL.md](doc/PROMPT_OPTIMIZATION_MANUAL.md) | Manual copy-paste approach (current MVP) |
| [doc/PROMPT_INDUCTION_AUTOMATED.md](doc/PROMPT_INDUCTION_AUTOMATED.md) | Future roadmap — NOT IMPLEMENTED |

**Process**:
1. Export GT: `uv run python -m btcopilot.training.export_gt`
2. Edit prompts in `prompts.py` and/or `PDP_FIELD_DESCRIPTIONS` in `llm.py`
3. **TEST IMMEDIATELY**: `uv run python -m btcopilot.training.test_prompts` — **NEVER skip this step**
4. Only commit if F1 improves (or document why regression is acceptable)
5. Save induction report to `btcopilot-sources/training/induction-reports/`

**Rules**: ADD nuance, don't replace sections. Never remove working examples without F1 validation. Track iterations in reports. Large refactors need approval. Test after EVERY edit.

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
- **Async**: `--asyncio-mode=auto` (configured in `btcopilot/tests/pytest.ini`)
- **Directories**: `tests/` (main), `tests/training/` (training module)

### Database
- **Migrations**: Alembic (`alembic.ini`, `alembic/versions/`)
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

## Documentation Maintenance Triggers

### SARF Ground Truth Technical Reference

When changing SARF-related code, check and update [doc/SARF_GROUND_TRUTH_TECHNICAL.md](doc/SARF_GROUND_TRUTH_TECHNICAL.md).

**Trigger files**: `training/routes/*.py`, `training/models.py`, `training/templates/discussion.html`, `training/templates/components/sarf_editor.html`, `training/export_tests.py`, `schema.py` (Event, PDPDeltas, SARF enums), `pdp.py` (cumulative/apply_deltas), `personal/models/statement.py`

**Update**: code examples, function signatures, file paths, business logic, API routes/payloads, data schemas, Alpine.js state changes, line number references, testing scenarios. Use TodoWrite to add "Verify SARF_GROUND_TRUTH_TECHNICAL.md accuracy" task. Commit doc updates with code changes.

**Skip**: typo fixes, non-SARF changes in same files, purely cosmetic UI changes.

### Family Diagram Visual Spec

When changing diagram rendering, update [doc/FAMILY_DIAGRAM_VISUAL_SPEC.md](doc/FAMILY_DIAGRAM_VISUAL_SPEC.md).

**Trigger files**: `training/templates/components/family_diagram_svg.html`, `training/routes/diagram_render.py`, any diagram layout code.

**Process**: update spec FIRST with new rule → implement in code → test → confirm sync.
