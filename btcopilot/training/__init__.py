from . import routes


def init_app(app):
    app.register_blueprint(routes.bp)


def init_celery(celery):
    from . import tasks

    celery.task(tasks.extract_next_statement, name="extract_next_statement")
    celery.task(
        tasks.extract_discussion_statements, name="extract_discussion_statements"
    )
