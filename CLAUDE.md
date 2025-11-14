# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
- **Virtual environment**: Managed by uv workspace (run from repository root)
- **Install dependencies**: `uv sync --extra app --extra test` (run after cloning or in new worktrees)
- **Platform compatibility**: PyTorch is pinned to `torch>=2.0.0,<2.1.0` with platform markers to support macOS x86_64. Newer torch versions don't have wheels for Intel Macs.
- **Start PostgreSQL**: `docker-compose up fd-server` (requires `docker volume create familydiagram_postgres` first)

### Running the Application
- **Manual run**: `uv run python manage.py run -h 0.0.0.0 -p 5555`
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

**IMPORTANT**: This project uses Flask 3.x's native CLI. The obsolete `flask-cli` package is incompatible with Flask 3.x application factory pattern and has been removed from dependencies in `btcopilot/pyproject.toml`.

**CRITICAL FOR TESTING**: When testing UI changes with chrome-devtools-mcp, you MUST use these scripts (not manual flask run or checking with lsof). The start script enables auto-authentication which is required for MCP server testing. Always use these scripts even if a server is already running.

**Start server:**
```bash
bash bin/flask_start.sh
```
- Auto-selects first available port from 5555-5565 (supports parallel Claude Code sessions)
- Prints selected port to console
- Runs in foreground (use `run_in_background: true` in Bash tool)
- Auto-authenticates as test user (patrickkidd+unittest@gmail.com) for MCP server testing
- Test user must exist first (run any test to create it)

**Stop server:**
```bash
bash bin/flask_stop.sh        # Stops all Flask servers in range 5555-5565
bash bin/flask_stop.sh 5556   # Stops server on specific port
```

**Check status:**
```bash
for port in {5555..5565}; do lsof -ti:$port >/dev/null 2>&1 && echo "Server running on port $port"; done
```

**Troubleshooting:**

If Flask server fails to start or shows errors about function signatures:
1. **Stop Flask**: `bash bin/flask_stop.sh`
2. **Remove __pycache__ directories**: `rm -rf btcopilot/btcopilot/__pycache__`
3. **Clear remaining bytecode**: `find btcopilot .venv -name "*.pyc" -delete 2>/dev/null`
4. **Restart Flask**: `bash bin/flask_start.sh`

**One-line fix** (use this if you encounter bytecode cache errors):
```bash
bash bin/flask_stop.sh && rm -rf btcopilot/btcopilot/__pycache__ && find btcopilot .venv -name "*.pyc" -delete 2>/dev/null && bash bin/flask_start.sh
```

Common issues:
- **"create_app() takes from 0 to 1 positional arguments but 2 were given"** - Either stale bytecode OR `flask-cli` package is installed. First check `uv pip show flask-cli`. If installed, remove it from `btcopilot/pyproject.toml` dependencies and run `uv sync`. Then use the one-line fix above to clear bytecode. This error occurs when the obsolete `flask-cli` package overrides Flask 3's native CLI, which doesn't support application factory functions with `**kwargs`.
- **Port already in use** - Another Flask instance is running. Use `bash bin/flask_stop.sh` to kill it.
- **Import errors** - Check that you're in the project root directory.
- **Server starts but immediately fails on first request** - Bytecode cache issue. The Flask dev server caches imported modules and __pycache__ directories must be removed, not just individual .pyc files.
- **Torch dependency errors on macOS x86_64** - The project pins torch to 2.0.x because newer versions don't have wheels for Intel Macs. If you see "can't be installed because it doesn't have a source distribution or wheel", remove `uv.lock` and run `uv sync --extra app --extra test` to re-resolve dependencies.

## Testing Flask Changes with chrome-devtools-mcp

When making changes to the training app (btcopilot/training), **always test using chrome-devtools-mcp**:

1. Start Flask server: `bash bin/flask_start.sh` (use `run_in_background: true`)
2. Navigate to relevant page using `mcp__chrome-devtools-mcp__navigate_page` or `new_page`
3. Take snapshot with `mcp__chrome-devtools-mcp__take_snapshot` to verify UI state
4. Test interactions using `click`, `fill`, `fill_form`, etc.
5. Verify functionality before declaring completion
6. Stop server when done: `bash bin/flask_stop.sh`

**This is mandatory for all HTML, CSS, JavaScript, and Flask route changes.**

### Background Tasks (Celery)
- **Start Redis**: `redis-server` (required for Celery broker/backend)
- **Start Celery worker**: `uv run celery -A btcopilot.celery:celery worker --loglevel=info`
- **Start Celery beat scheduler**: `uv run celery -A btcopilot.celery:celery beat --loglevel=info`
- **Monitor tasks**: `uv run celery -A btcopilot.celery:celery flower` (web UI at http://localhost:5555)
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
- **Pro** (`btcopilot/pro/schema.py`): Core data model, shared with Pro / Personal app repos
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
- **File**: `btcopilot/training/templates/components/extracted_data_display.html`
- **Purpose**: Displays and allows editing of extracted people, events, and clinical variable coding
- **Features**: Collapsed/expanded views, in-place editing, feedback controls, cumulative data display
- **Used in**: Training module for domain-expert review and fine-tuning of AI extraction model

## Development rules

- At this stage we are not concerned with legacy data, we woudl rather delete
  and re-create broken data than add complicated code for backward compatiblity.  

## Code Style & Conventions

- Keep all names, e.g. variables, functions, classes, methods, modules, etc, as
  short, accurate, and precise as possible.
- Use consistent naming and code organization conventions.
- Use the minimum amount of code as possible.
- Never use "process" in a callable name.
- Keep code self-documenting.
- Strictly adhere to D.R.Y.
- Don't put code in inline strings, especially in HTML. Put them in their native
  language in an appropriate place like a javascript file or a python file.
- Never simply catch `Exception` unless explicitly adding an exception router or filter.
- Don't return errors back to the frontend via jsonify() unless there is a
  specific place that the frontend reads and displays the error in a usable
  manner. Otherwise just let the backend blow up with an exception so that it is
  obvious during testing.- Assume that exceptions are already handled in the blueprint and jsonfiy() is
  called with an error string and 5xx code.
- Only add comments for complex business logic, non-obvious algorithms, or when
  explaining WHY something is done (not WHAT is being done)
- Never add docstrings for simple functions where the name and parameters make
  the purpose clear
- Avoid comments that simply restate what the code obviously does
- Don't use the class-based pytest pattern and instead use only module-level functions.
- Keep flask endpoints oriented around updating entries in database tables, not
  just adding a new endpoint for every application verb.
- For python enum items, keep only the first letter of each word capitalized. Do
  not capitalize all letters.
- Create a re-usable component or template whenever markup or logic is
  duplicated.
- Always use `black` to format Python source files (`.py` files only) after changes. Never run black on HTML, JavaScript, CSS, shell scripts, or other non-Python files.


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

## Documentation Maintenance

### SARF Ground Truth Technical Reference

**CRITICAL**: When making changes to SARF-related code in btcopilot, you MUST automatically check and update [doc/SARF_GROUND_TRUTH_TECHNICAL.md](doc/SARF_GROUND_TRUTH_TECHNICAL.md).

**Trigger Files** (changes to any of these require doc review):
- `training/routes/*.py` - API endpoints, approval logic
- `training/models.py` - Feedback model
- `training/templates/discussion_audit.html` - Discussion audit page layout, cumulative refresh logic
- `training/templates/components/extracted_data_display.html` - SARF editor component
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

---

## Debugging and validation rules
- You may start a flask server on port 4999 with FLASK_CONFIG=development to
  debug templates and endpoints
