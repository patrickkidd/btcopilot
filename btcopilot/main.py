def main_server():
    from btcopilot.app import create_app

    app = create_app()
    app.engine.llm()
    app.engine.vector_db()
    app.run("0.0.0.0", port=8888)


def main_celery():
    """
    Celery application module for the btcopilot package.

    This module creates a Celery instance that can be accessed when btcopilot
    is installed as a wheel package. The Celery instance is available at:
    btcopilot.celery:celery

    Usage:
        celery -A btcopilot.celery:celery worker --loglevel=info
        celery -A btcopilot.celery:celery beat --loglevel=info
        celery -A btcopilot.celery:celery flower
    """

    import os, sys

    os.environ["FD_IS_CELERY"] = "true"

    if "ddtrace" in sys.modules:
        from ddtrace import patch, config

        print("setting up datadog tracing for celery...")
        patch(celery=True)

        # Configure Datadog
        config.celery["distributed_tracing_enabled"] = True
        config.celery["producer_span_enabled"] = True
        config.celery["worker_span_enabled"] = True

    from btcopilot.app import create_app

    # Create Flask app instance - this initializes all extensions including celery
    app = create_app()

    # Import celery after app creation to ensure it's initialized
    from btcopilot.extensions import celery
