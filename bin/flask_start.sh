#!/bin/bash
# Clear Python bytecode cache to prevent stale imports
# Remove __pycache__ directories completely (more reliable than just .pyc files)
rm -rf btcopilot/btcopilot/__pycache__
find btcopilot .venv -name "*.pyc" -delete 2>/dev/null

# Find an available port starting from 5555
PORT=5555
while lsof -ti:$PORT >/dev/null 2>&1; do
    echo "Port $PORT is already in use, trying next port..."
    PORT=$((PORT + 1))
    if [ $PORT -gt 5565 ]; then
        echo "Error: No available ports found between 5555-5565"
        exit 1
    fi
done

echo "Starting Flask server on port $PORT with auto-auth enabled..."
echo $PORT > /tmp/flask_port_$$.txt

# Default to patrick@alaskafamilysystems.com if FLASK_AUTO_AUTH_USER not set
if [ -z "$FLASK_AUTO_AUTH_USER" ]; then
    FLASK_AUTO_AUTH_USER=patrick@alaskafamilysystems.com
fi

PYTHONDONTWRITEBYTECODE=1 \
FLASK_APP=btcopilot.app:create_app \
FLASK_CONFIG=development \
FLASK_DEBUG=1 \
FLASK_AUTO_AUTH_USER=$FLASK_AUTO_AUTH_USER \
uv run python -m flask run -p $PORT --no-reload
