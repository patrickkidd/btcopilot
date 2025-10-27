# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
- **Virtual environment**: `.venv/bin/activate` (uses pyproject.toml for dependencies)
- **Start PostgreSQL**: `docker-compose up fd-server` (requires `docker volume create familydiagram_postgres` first)

### Running the Application
- **Development server**: Use VSCode debugger with Flask configuration (port 8888)
- **Manual run**: `python manage.py run -h 0.0.0.0 -p 8888`
- **Production**: `docker-compose -d production.yml up fd-server`

### Background Tasks (Celery)
- **Start Redis**: `redis-server` (required for Celery broker/backend)
- **Start Celery worker**: `celery -A btcopilot.celery:celery worker --loglevel=info`
- **Start Celery beat scheduler**: `celery -A btcopilot.celery:celery beat --loglevel=info`
- **Monitor tasks**: `celery -A btcopilot.celery:celery flower` (web UI at http://localhost:5555)
- **Debug Celery worker**: Use VSCode "Celery Worker (Debug)" configuration (single-threaded with breakpoints)
- **Debug Celery beat**: Use VSCode "Celery Beat" configuration

### Testing
- **Run all tests**: `pytest -vv tests`
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
- Always use `black` to format all source files after changes.


## Code architecture and rules
- This app is not in production yet and additional db migrations are not
  required yet, so all db changes should just go in
  @alembic/versions/b30fb43b8f92_add_therapist_tables.py
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

## Debugging and validation rules
- You may start a flask server on port 4999 with FLASK_CONFIG=development to
  debug templates and endpoints
