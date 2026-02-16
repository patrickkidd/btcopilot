from . import routes


def format_date_us(value):
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%m/%d/%Y")
    return value


def sort_by_modified(diagrams):
    from datetime import datetime

    def get_sort_key(d):
        return d.updated_at or d.created_at or datetime.min

    return sorted(diagrams, key=get_sort_key, reverse=True)


def init_app(app):
    routes.init_app(app)
    app.jinja_env.filters["format_date_us"] = format_date_us
    app.jinja_env.filters["sort_by_modified"] = sort_by_modified


def init_celery(celery):
    from . import tasks
    from google.genai.errors import ClientError
    from openai import PermissionDeniedError, RateLimitError

    celery.task(
        tasks.extract_next_statement,
        name="extract_next_statement",
        autoretry_for=(ClientError, PermissionDeniedError, RateLimitError),
        retry_backoff=60,
        retry_backoff_max=600,
        retry_jitter=True,
        max_retries=5,
    )
    celery.task(
        tasks.extract_discussion_statements,
        name="extract_discussion_statements",
        autoretry_for=(ClientError, PermissionDeniedError, RateLimitError),
        retry_backoff=60,
        retry_backoff_max=600,
        retry_jitter=True,
        max_retries=5,
    )
    celery.task(
        tasks.generate_synthetic_discussion,
        name="generate_synthetic_discussion",
        bind=True,
        autoretry_for=(ClientError, PermissionDeniedError, RateLimitError),
        retry_backoff=60,
        retry_backoff_max=600,
        retry_jitter=True,
        max_retries=5,
    )
