"""Celery worker entry point - creates Flask app and returns configured Celery instance"""

from btcopilot.app import create_app
from btcopilot.extensions import celery as celery_instance

# Create Flask app to initialize Celery and register tasks
app = create_app()

# Return the configured Celery instance for the worker
celery = celery_instance
