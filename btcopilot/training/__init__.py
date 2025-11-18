from . import routes


def format_date_us(value):
    """Format date as mm/dd/yyyy instead of yyyy-mm-dd"""
    if value is None:
        return ''
    if hasattr(value, 'strftime'):
        # It's a datetime/date object
        return value.strftime('%m/%d/%Y')
    # It's a string in ISO format
    return value


def init_app(app):
    app.register_blueprint(routes.bp)
    app.jinja_env.filters['format_date_us'] = format_date_us


def init_celery(celery):
    from . import tasks

    celery.task(tasks.extract_next_statement, name="extract_next_statement")
    celery.task(
        tasks.extract_discussion_statements, name="extract_discussion_statements"
    )
