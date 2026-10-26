"""Celery worker entry point - creates Flask app and returns configured Celery instance"""

from celery.signals import worker_ready

from btcopilot import turns
from btcopilot.app import create_app
from btcopilot.extensions import celery as celery_instance

# Create Flask app to initialize Celery and register tasks
app = create_app()

# Return the configured Celery instance for the worker
celery = celery_instance


@worker_ready.connect
def swept(**_) -> None:
    with app.app_context():
        turns.sweep()
