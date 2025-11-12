#!/bin/bash
# Clear Python bytecode cache to prevent stale imports
# Remove __pycache__ directories completely (more reliable than just .pyc files)
rm -rf btcopilot/btcopilot/__pycache__
find btcopilot .venv -name "*.pyc" -delete 2>/dev/null

PYTHONDONTWRITEBYTECODE=1 \
FLASK_APP=btcopilot.app:create_app \
FLASK_CONFIG=development \
FLASK_DEBUG=1 \
FLASK_AUTO_AUTH_USER=patrickkiod+unittest@gmail.com \
uv run python -m flask run -p 5555 --no-reload
