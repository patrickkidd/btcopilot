"""Tests to ensure Celery tasks are properly registered and accessible"""

import pytest


def test_celery_tasks_are_registered(app):
    """Ensure all training Celery tasks are registered and discoverable"""
    from btcopilot.extensions import celery

    registered_tasks = list(celery.tasks.keys())

    assert "extract_next_statement" in registered_tasks
    assert "extract_discussion_statements" in registered_tasks


def test_celery_broker_connection(app):
    """Ensure Celery can connect to the broker"""
    from btcopilot.extensions import celery

    # This will fail if redis package is missing or broker is unreachable
    try:
        celery.connection().ensure_connection(max_retries=1)
    except Exception as e:
        pytest.fail(f"Celery cannot connect to broker: {e}")
