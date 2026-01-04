# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## ⚠️ CONFIDENTIAL DATA STORAGE RULES ⚠️

**CRITICAL**: Induction reports and GT exports contain confidential clinical data and MUST NEVER be stored in the btcopilot repository.

| Data Type | WRONG Location | CORRECT Location |
|-----------|----------------|------------------|
| Induction reports | `btcopilot/btcopilot/induction-reports/` | `btcopilot-sources/training/induction-reports/` |
| GT exports | `btcopilot/instance/gt_export.json` | `btcopilot-sources/training/gt-exports/` |

**Symlinks exist** to allow workflow compatibility:
- `btcopilot/btcopilot/induction-reports` → `btcopilot-sources/training/induction-reports/`
- `theapp/instance/gt_export.json` → `btcopilot-sources/training/gt-exports/gt_export.json`

**If you create new clinical data outputs**:
1. Store in `btcopilot-sources/` (private repo)
2. Create symlink for workflow compatibility
3. Add path to `.gitignore` in both repos
4. Update this section

---

## Authoritative Documentation Index

**When learning new facts about a domain, integrate them into the authoritative doc for that domain.**

| Knowledge Domain | Authoritative Doc |
|------------------|-------------------|
| PDP behavior, deltas, cumulative logic | [doc/DATA_MODEL_FLOW.md](doc/DATA_MODEL_FLOW.md) |
| SARF coding, GT workflow, approval | [doc/SARF_GROUND_TRUTH_TECHNICAL.md](doc/SARF_GROUND_TRUTH_TECHNICAL.md) |
| Prompt engineering decisions | [doc/PROMPT_ENGINEERING_LOG.md](doc/PROMPT_ENGINEERING_LOG.md) |
| Prompt induction workflow | [doc/PROMPT_INDUCTION_CLI.md](doc/PROMPT_INDUCTION_CLI.md) |
| Bowen theory domain concepts | [CONTEXT.md](CONTEXT.md) |
| Diagram layout, rendering, SVG | [doc/FAMILY_DIAGRAM_VISUAL_SPEC.md](doc/FAMILY_DIAGRAM_VISUAL_SPEC.md) |
| F1 metrics, evaluation | [doc/F1_METRICS.md](doc/F1_METRICS.md) |
| Chat flow, personal app AI | [doc/CHAT_FLOW.md](doc/CHAT_FLOW.md) |
| Major decisions (career, strategy) | [decisions/log.md](decisions/log.md) |
| Architecture decisions | [adrs/](adrs/) |

**Other references:**
- [README.md](README.md) - Project overview

## Architecture Overview

btcopilot has these primary functions:
- Backend for person/pro apps.
- AI machine learning system interface for SARF research design
- AI model that outputs a "Pending Data Pool" of deltas for a given diagram file
  (i.e. single family case), to be accepted/committed later by the pro/personal
  apps.

### Core Application Structure
- **Flask Application Factory**: `btcopilot/app.py:create_app()` - main app initialization with extensions, error handlers, and module registration
- **Main Package**: `btcopilot/__init__.py` - imports and exposes core components
  - `btcopilot/pro` - Pro / desktop app backend server functionality
  - `btcopilot/personal` - Personal / mobile app backend server functionality
  - `btcopilot/training` - AI Training app backend server functionality
- **API Endpoints**:
  - `btcopilot/pro/routes.py` - REST API using pickle protocol over HTTPS
  - `btcopilot/personal/routes.py` - REST API for personal mobile app using JSON
- **Management CLI**:
  `manage.py` - Flask CLI commands and utilities
  `btcopilot/commands.py` - click commands management interface.

### Key Modules
- **Schema** (`btcopilot/pro/schema.py`): Core data model, shared with Pro / Personal app repos
- **Pro** (`btcopilot/pro/models/`): Pro desktop app, including SQLAlchemy models User, Diagram, License, Session, Statement/Discussion
- **Personal** (`btcopilot/personal/`): Personal mobile app API with AI-powered data extraction from discussions for four variables; symptom, anxiety, relationship, functioning.
  - *JSON-BASED data schema*: `btcopilot/personal/database.py`
- **Training** (`btcopilot/training`): Domain-expert human feedback system for fine-tuning AI model for the personal app.
- **Extensions** (`btcopilot/extensions/`): Flask extensions setup (database, LLM, chroma vector store)
- **Authentication**: `btcopilot/auth.py` - user authentication with current_user

### External Services Integration
- **AI/ML Stack**: OpenAI API (GPT-4o-mini), Hugging Face embeddings, ChromaDB vector store, LangChain
- **Payment Processing**: Stripe integration for licensing
- **Database**: PostgreSQL with SQLAlchemy ORM
  - Connection: `postgresql://familydiagram:pks@localhost:5432/familydiagram`
  - Access via Flask app context: `uv run python -c "from btcopilot.app import create_app; from btcopilot.extensions import db; app=create_app(); app.app_context().push(); ..."`

### Data Architecture
- **Vector Database**: ChromaDB for embeddings stored in instance/vector_db/
- **Session Management**: Custom session handling via models/session.py
- **Licensing System**: Professional/annual licenses via Stripe integration
- **Chat System**: Message threading with Statement/Discussion models

### Development Notes
- **Configuration**: Environment-based config (FLASK_CONFIG=development/production)
- **Instance Directory**: App data stored in instance/ (logs, vector DB, etc.)
- **Docker Setup**: Multi-service with Flask app + PostgreSQL
- **Error Handling**: Centralized exception handling with logging
- **Testing Framework**: pytest with snapshot testing and async support

## Terminology & Component Reference

### SARF Editor
The interactive, re-usable component for reviewing and editing extracted clinical data (SARF = Symptom, Anxiety, Relationship, Functioning variables). Located in:
- **File**: `btcopilot/training/templates/components/sarf_editor.html`
- **Purpose**: Displays and allows editing of extracted people, events, and clinical variable coding
- **Features**: Collapsed/expanded views, in-place editing, feedback controls, cumulative data display
- **Used in**: Training module for domain-expert review and fine-tuning of AI extraction model

### Family Diagram Renderer
SVG-based family diagram visualization for displaying cumulative PDP (Pending Data Pool) data.
- **Component**: `btcopilot/training/templates/components/family_diagram_svg.html`
- **Route**: `btcopilot/training/routes/diagrams.py` - `/diagrams/render/<statement_id>` endpoint
- **Standalone Page**: `/training/diagrams/render/<statement_id>/<auditor_id>` - Full page view for development and testing diagram layout
- **Embed Mode**: Add `?embed=true` to get just the SVG component (used in modals)
- **Modal Access**: Discussion page has "Diagram" buttons that open embedded view in a modal
- **Purpose**: Visualize cumulative family data (people, pair bonds, parent-child relationships) at any statement

### Personal App Chat Flow
The AI-powered conversation system that extracts family relationship data from user messages. For detailed architecture and prompt engineering guidance:
- **File**: [doc/CHAT_FLOW.md](doc/CHAT_FLOW.md)
- **Purpose**: Documents chat flow architecture starting from `btcopilot.personal.ask`
- **Includes**: System prompts, test fixtures, data extraction flow, LLM integration
- **Use When**: Improving system prompts for better LLM alignment based on developer requests for certain behaviors

### Synthetic Conversation Testing
Automated testing framework for evaluating conversational quality in the Personal app chat flow:
- **File**: [btcopilot/tests/personal/README.md](btcopilot/tests/personal/README.md)
- **Module**: `btcopilot.tests.personal.synthetic`
- **Purpose**: Simulates conversations with synthetic user personas and detects robotic patterns
- **Includes**: Persona generator, conversation simulator, quality evaluator with pattern detection
- **Use When**: Testing prompt changes for conversational quality, regression testing for robotic behaviors
- **Run**: `uv run pytest btcopilot/btcopilot/tests/personal/test_synthetic.py -v -m e2e`

### F1 Metrics for AI Extraction Evaluation
Documentation for the F1 metrics system that evaluates AI extraction quality against human ground truth:
- **File**: [doc/F1_METRICS.md](doc/F1_METRICS.md)
- **Purpose**: Comprehensive reference for F1 score calculation, entity matching logic, and ground truth workflow
- **Includes**: Matching criteria (people, events, SARF variables), F1 types (aggregate, per-type, macro-F1), cache strategy, configuration constants
- **Use When**: Understanding or modifying F1 calculation logic, tuning matching thresholds, analyzing AI extraction quality, or implementing prompt improvements based on F1 scores

### Prompt Engineering Context
**CRITICAL FOR PROMPT INDUCTION**: Authoritative record of prompt engineering decisions, experiments, and lessons learned.
- **File**: [doc/PROMPT_ENGINEERING_CONTEXT.md](doc/PROMPT_ENGINEERING_CONTEXT.md)
- **Purpose**: Prevents regressions by documenting what works, what doesn't, and why
- **Includes**: Model selection (Gemini 2.0 Flash), known issues, critical lessons (verbose definitions killed F1), prompt architecture, what NOT to include
- **Use When**: Modifying extraction prompts, running prompt induction, or diagnosing F1 score issues
- **Related**: [doc/TODO_GEMINI_SCHEMA.md](doc/TODO_GEMINI_SCHEMA.md) (deferred Gemini optimizations)

### Prompt Engineering Extraction Strategy
**SYSTEMATIC IMPROVEMENT PROCESS**: Strategy and process for improving SARF extraction F1 scores when automated induction plateaus.
- **File**: [doc/PROMPT_ENG_EXTRACTION_STRATEGY.md](doc/PROMPT_ENG_EXTRACTION_STRATEGY.md)
- **Purpose**: Documents known blockers, manual troubleshooting process, metrics-driven priorities, and recommended actions
- **Includes**: Current F1 baseline, root cause analysis (event matching brittleness, model stochasticity, sparse GT), established best practices, manual investigation workflow
- **Use When**: F1 scores are low, prompt induction stops improving, or planning next optimization steps
- **Self-updating**: Document should be updated after each induction run or manual investigation

### Prompt Induction Workflow

## ⚠️ MANDATORY FOR ALL PROMPT CHANGES ⚠️

**Trigger Files** (changes to ANY of these REQUIRE the induction workflow):
- `btcopilot/personal/prompts.py` - Extraction prompts
- `btcopilot/extensions/llm.py` - `PDP_FIELD_DESCRIPTIONS` dict

**BEFORE making prompt changes**:
1. Read [doc/PROMPT_ENGINEERING_LOG.md](doc/PROMPT_ENGINEERING_LOG.md) - critical lessons and known issues
2. Check `PDP_FIELD_DESCRIPTIONS` in `btcopilot/extensions/llm.py` for field documentation
3. Both locations must stay in sync

| Doc | Purpose |
|-----|---------|
| [doc/PROMPT_INDUCTION_CLI.md](doc/PROMPT_INDUCTION_CLI.md) | **PRIMARY** - CLI-driven automated iteration ($0 cost, RECOMMENDED) |
| [doc/PROMPT_OPTIMIZATION_MANUAL.md](doc/PROMPT_OPTIMIZATION_MANUAL.md) | Manual copy-paste approach (current MVP) |
| [doc/PROMPT_INDUCTION_AUTOMATED.md](doc/PROMPT_INDUCTION_AUTOMATED.md) | Future roadmap - NOT IMPLEMENTED |

**Required Process**:
1. Export GT: `uv run python -m btcopilot.training.export_gt`
2. Edit prompts in `btcopilot/personal/prompts.py` AND/OR `PDP_FIELD_DESCRIPTIONS` in `llm.py`
3. **TEST IMMEDIATELY**: `uv run python -m btcopilot.training.test_prompts`
4. Only commit if F1 improves (or document why regression is acceptable)
5. Save induction report to `btcopilot-sources/training/induction-reports/`

**⚠️ CRITICAL: NEVER skip step 3.** Even for "obvious" fixes like adding validation rules or clarifying instructions, you MUST run `test_prompts` before declaring completion. Prompt changes can have unexpected effects on F1 scores.

**Key Rules**:
- ADD nuance to prompts, don't replace entire sections
- Never remove working examples without F1 validation
- Track all iterations in induction reports
- Large refactors need explicit approval
- **Test after EVERY prompt edit** - no exceptions

### Family Diagram Visual Specification
**PLATFORM-INDEPENDENT LAYOUT SPEC**: Comprehensive specification for arranging and rendering family diagrams (Bowen theory family diagrams).
- **File**: [doc/FAMILY_DIAGRAM_VISUAL_SPEC.md](doc/FAMILY_DIAGRAM_VISUAL_SPEC.md)
- **Purpose**: Human-readable and machine-readable specification for implementing family diagram layout algorithms in any language/platform
- **Includes**: Person symbols (shapes, sizes, primary/deceased), PairBond geometry (U-shape, married/bonded/divorced), ChildOf connections (vertical/diagonal), MultipleBirth jig, generational layout rules, horizontal arrangement (birth order, multiple partners), label positioning
- **Use When**: Implementing HTML5 diagram preview, improving auto-arrangement in Pro app, or building diagram renderers in other platforms
- **Audience**: Software engineers and family systems practitioners/academics

## Development rules

- At this stage we are not concerned with legacy data, we woudl rather delete
  and re-create broken data than add complicated code for backward compatiblity.  

## Code architecture and rules
- Use the mcp server `chrome-devtools-mcp` to show me the effects of your
  frontend changes for btcopilot/training and ask/check with me to make sure I
  like them before considering the task done.
- This app is in production, so new db changes ned to go in new db migrations.
- Always make `.card` markup elements with a `.card-header` containing a dynamic
  list always collapsable by clicking its `.card-header`.
- Never pop a confirm message or dialog just to show something that will be
  reflected in the UI very soon
- Never use exclamation points, users are not as excited as the developers are
  about mundane application events.
- Prefer importing packages at the module level instead of inside functions
  unless required for the feature. This does not apply to tests.
- For DOM/css changes always validate the changes worked against the validated
  html and css, pulling down the page URL if necessary


## Development Commands

### Environment Setup
- **Virtual environment**: Managed by uv workspace (run from repository root)
- **Install dependencies**: `uv sync --extra app --extra test` (run after cloning or in new worktrees)
- **Platform compatibility**: PyTorch is pinned to `torch>=2.0.0,<2.1.0` with platform markers to support macOS x86_64. Newer torch versions don't have wheels for Intel Macs.
- **Start PostgreSQL**: `docker-compose up fd-server` (requires `docker volume create familydiagram_postgres` first)

### Running the Application
- **Development server**: Managed by user on port 8888 (NEVER start one yourself)
- **Production**: `docker-compose -d production.yml up fd-server`

## Critical Data Serialization Rules

**NEVER violate these rules - they are critical for Pro app backward compatibility:**

1. **Diagram.data MUST use pickle format** - The Pro desktop app requires pickle format for `diagrams.data` column
2. **NEVER pickle btcopilot or fdserver class instances** - Only store built-in Python types (str, int, float, bool, list, dict, None) and QtCore types in pickled diagram data
3. **ALWAYS maintain backward compatibility with Pro app** - Any changes to diagram data serialization must work with existing Pro app installations
4. **User will manually delete broken discussions** - If discussions throw `ModuleNotFoundError` for fdserver/btcopilot modules, the user will manually delete those discussions. Do not add complex error handling code.

**Allowed in pickle data:**
- Built-in types: str, int, float, bool, list, dict, None
- QtCore types from PyQt5 (e.g., QDate, QDateTime)

**NEVER allowed in pickle data:**
- Classes from `btcopilot.*` modules
- Classes from `fdserver.*` modules
- Custom dataclasses or Pydantic models
- Any third-party library classes (except QtCore)

## Flask Server Management

**CRITICAL: The Flask dev server must already be running on port 8888. NEVER start a Flask server yourself.**

**IMPORTANT**: This project uses Flask 3.x's native CLI. The obsolete `flask-cli` package is incompatible with Flask 3.x application factory pattern and has been removed from dependencies in `btcopilot/pyproject.toml`.

The Flask development server is managed externally by the user on port 8888.

| Action | What to do |
|--------|------------|
| Verify server running | `curl -s http://127.0.0.1:8888/ > /dev/null && echo "OK" || echo "ERROR"` |
| Server not running | **STOP and ask user to start it** - NEVER start one yourself |
| Server not responding | Ask user to restart it |
| Bytecode issues | Ask user to clear cache: `find . -name "*.pyc" -delete` |

Features (when running):
- **Access URL**: http://127.0.0.1:8888
- Auto-authenticates as test user (patrick@alaskafamilysystems.com)
- Live reloading enabled for development

**Troubleshooting:**

Common issues:
- **"create_app() takes from 0 to 1 positional arguments but 2 were given"** - Either stale bytecode OR `flask-cli` package is installed. Ask user to check `uv pip show flask-cli`. If installed, remove it from `btcopilot/pyproject.toml` dependencies and run `uv sync`. Then ask user to restart server after clearing bytecode.
- **Port 8888 not responding** - Ask user to restart the Flask server.
- **Import errors** - Check that user is in the project root directory.
- **Server starts but immediately fails on first request** - Bytecode cache issue. Ask user to clear cache and restart.
- **Torch dependency errors on macOS x86_64** - The project pins torch to 2.0.x because newer versions don't have wheels for Intel Macs. If you see "can't be installed because it doesn't have a source distribution or wheel", remove `uv.lock` and run `uv sync --extra app --extra test` to re-resolve dependencies.

## Testing Flask Changes with chrome-devtools-mcp

When making changes to the training app (btcopilot/training), **always test using chrome-devtools-mcp**:

**CRITICAL: Flask dev server must already be running on port 8888. NEVER start one yourself.**

1. Verify Flask server is running: `curl -s http://127.0.0.1:8888/ > /dev/null && echo "OK" || echo "ERROR"`
2. If server not running, **STOP and ask user to start it**
3. Navigate to relevant page using `mcp__chrome-devtools__navigate_page` or `new_page` (http://127.0.0.1:8888/...)
4. Take snapshot with `mcp__chrome-devtools__take_snapshot` to verify UI state
5. Test interactions using `click`, `fill`, `fill_form`, etc.
6. Verify functionality before declaring completion

**This is mandatory for all HTML, CSS, JavaScript, and Flask route changes.**

### Background Tasks (Celery)
- **Start Redis**: `redis-server` (required for Celery broker/backend)
- **Start Celery worker**: `uv run celery -A btcopilot.celery:celery worker --loglevel=info`
- **Start Celery beat scheduler**: `uv run celery -A btcopilot.celery:celery beat --loglevel=info`
- **Monitor tasks**: `uv run celery -A btcopilot.celery:celery flower` (web UI at http://localhost:5556)
- **Debug Celery worker**: Use VSCode "Celery Worker (Debug)" configuration (single-threaded with breakpoints)
- **Debug Celery beat**: Use VSCode "Celery Beat" configuration

### Testing
- **Run all tests**: `uv run pytest -vv tests`
- **Test with async support**: Tests use `--asyncio-mode=auto` (configured in btcopilot/tests/pytest.ini)
- **Specific test directories**: `tests/` (main), `tests/training/` (training module)
- Whenever I paste a stack trace that means a test did not catch it, so add a test to reproduce that error if one did not already exist.

### Database Management
- **Migrations**: Uses Alembic (configured in alembic.ini, migrations in alembic/versions/)
- **Database URI**: `postgresql://familydiagram:pks@localhost:5432/familydiagram` (development)

#### Accessing PostgreSQL Database

**Prerequisites**: PostgreSQL must be running via Docker:
```bash
docker-compose up fd-server  # Start PostgreSQL (requires `docker volume create familydiagram_postgres` first)
docker ps | grep postgres     # Verify container is running
```

**Query Database**:
```bash
# Execute SQL query
docker exec fd-postgres psql -U familydiagram -d familydiagram -c "SELECT * FROM users LIMIT 5;"

# Interactive psql shell
docker exec -it fd-postgres psql -U familydiagram -d familydiagram

# Show table structure
docker exec fd-postgres psql -U familydiagram -d familydiagram -c "\d table_name"
```

**Common Queries**:
```bash
# Check access rights for a diagram
docker exec fd-postgres psql -U familydiagram -d familydiagram -c "SELECT ar.id, ar.diagram_id, ar.user_id, ar.right, u.username FROM access_rights ar JOIN users u ON ar.user_id = u.id WHERE ar.diagram_id = <diagram_id>;"

# Check user by ID or username
docker exec fd-postgres psql -U familydiagram -d familydiagram -c "SELECT id, username, roles FROM users WHERE id = <user_id>;"

# Check diagram ownership
docker exec fd-postgres psql -U familydiagram -d familydiagram -c "SELECT id, name, user_id FROM diagrams WHERE id = <diagram_id>;"
```


## Documentation Maintenance

### SARF Ground Truth Technical Reference

**CRITICAL**: When making changes to SARF-related code in btcopilot, you MUST automatically check and update [doc/SARF_GROUND_TRUTH_TECHNICAL.md](doc/SARF_GROUND_TRUTH_TECHNICAL.md).

**Trigger Files** (changes to any of these require doc review):
- `training/routes/*.py` - API endpoints, approval logic
- `training/models.py` - Feedback model
- `training/templates/discussion.html` - Discussion audit page layout, cumulative refresh logic
- `training/templates/components/sarf_editor.html` - SARF editor component
- `training/export_tests.py` - Test case export logic
- `schema.py` - Event, PDPDeltas, or SARF enums (VariableShift, RelationshipKind)
- `pdp.py` - cumulative() or apply_deltas() functions
- `personal/models/statement.py` - Statement model with pdp_deltas

**Automated Process** (follow these steps IMMEDIATELY after code changes):

1. **Detect Impact**: After completing code changes, scan which sections of SARF_GROUND_TRUTH_TECHNICAL.md are affected
2. **Compare**: Read the relevant sections and compare to your code changes
3. **Identify Discrepancies**:
   - New/removed/renamed fields in dataclasses
   - Changed function signatures or behavior
   - New/removed/modified API endpoints
   - Updated business logic or validation rules
   - New UI patterns or Alpine.js state changes
   - Moved code (update line number references)
4. **Update Documentation**: Make precise edits to keep doc in sync with code
5. **Add Todo Reminder**: Use TodoWrite to add "Verify SARF_GROUND_TRUTH_TECHNICAL.md accuracy" task
6. **Commit Together**: Include doc updates in the same commit as code changes

**Example Commit Message**:
```
Add SARF confidence threshold validation

- Added min/max validation in pdp.py:validate_pdp_deltas()
- Updated SARF_GROUND_TRUTH_TECHNICAL.md section 2.4 (Confidence Scoring)
- Updated section 9 (Testing Considerations) with new validation test
```

**What to Update**:
- Code examples and snippets
- Function signatures and parameters
- File path references and line numbers
- Business logic descriptions
- API endpoint routes and payloads
- Data structure schemas
- Design patterns and gotchas
- Testing scenarios

**When NOT to Update**:
- Trivial changes (typo fixes, comment updates)
- Changes to non-SARF code in same files
- Purely cosmetic UI changes that don't affect technical architecture

**Verification**: After updating, use the `/update-sarf-docs` slash command (if available) or manually review the entire doc for consistency.

### Family Diagram Visual Spec Maintenance

**CRITICAL**: When working on family diagram rendering (HTML5 renderer, layout algorithms, SVG generation), you MUST automatically update [doc/FAMILY_DIAGRAM_VISUAL_SPEC.md](doc/FAMILY_DIAGRAM_VISUAL_SPEC.md) with any new rules or layout behaviors.

**Trigger Files** (changes to any of these require spec review):
- `training/templates/components/family_diagram_svg.html` - SVG renderer and layout algorithm
- `training/routes/diagram_render.py` - Diagram rendering endpoint
- Any file implementing diagram layout logic

**What to Update**:
- New layout rules (positioning, spacing, generation assignment)
- Changes to visual conventions (shapes, lines, symbols)
- New relationship types or indicators
- Layout algorithm behaviors
- Any user-reported layout issues and their solutions

**Process**:
1. When user reports a layout issue or requests a change, FIRST update the visual spec with the new rule
2. Then implement the rule in code
3. Test the implementation
4. Confirm the spec and code are in sync

This ensures the visual spec remains the authoritative source of truth for all family diagram layout implementations.

---

## Debugging and validation rules
- The Flask dev server runs on port 8888 (managed by user) - NEVER start one yourself
- If you need the server, verify it's running first and ask user to start it if not
