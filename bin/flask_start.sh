#!/bin/bash
# Clear Python bytecode cache to prevent stale imports
find btcopilot -name "*.pyc" -delete 2>/dev/null

FLASK_APP="btcopilot.app:create_app" \
FLASK_CONFIG=development \
FLASK_DEBUG=1 \
FLASK_AUTO_AUTH_USER=patrickkiod+unittest@gmail.com \
uv run flask run -p 5555 --no-reload
