from . import chat
from .chat import ask, Response
from . import routes


def init_app(app):
    routes.init_app(app)


def init_celery(celery):
    from . import tasks
    from google.genai.errors import ClientError
    from openai import PermissionDeniedError, RateLimitError

    celery.task(
        tasks.deep_reextract_task,
        name="deep_reextract",
        bind=True,
        autoretry_for=(ClientError, PermissionDeniedError, RateLimitError),
        retry_backoff=60,
        retry_backoff_max=600,
        retry_jitter=True,
        max_retries=5,
    )
