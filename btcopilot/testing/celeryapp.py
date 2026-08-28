"""Celery entry point for a sandbox worker:

    celery -A btcopilot.testing.celeryapp:celery worker --pool=solo

Reads BTCOPILOT_SANDBOX_DB_URI, BTCOPILOT_SANDBOX_FD_DIR and
BTCOPILOT_SANDBOX_BROKER. `celery` is None unless the broker is a real one, so
a worker pointed at an in-memory sandbox fails at startup instead of idling.
"""

from btcopilot import extensions
from btcopilot.testing.sandbox import create_sandbox_app_from_env

app = create_sandbox_app_from_env()
celery = extensions.celery
