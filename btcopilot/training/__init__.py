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
    app.register_blueprint(routes.bp)
    app.jinja_env.filters["format_date_us"] = format_date_us
    app.jinja_env.filters["sort_by_modified"] = sort_by_modified


def init_celery(celery):
    from . import tasks

    celery.task(tasks.extract_next_statement, name="extract_next_statement")
    celery.task(tasks.extract_discussion_statements, name="extract_discussion_statements")
    celery.task(
        tasks.generate_synthetic_discussion,
        name="generate_synthetic_discussion",
        bind=True,
    )
