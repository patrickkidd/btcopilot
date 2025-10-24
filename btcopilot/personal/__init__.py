from . import chat
from .chat import ask, Response, ResponseDirection
from . import routes


def init_app(app):
    routes.init_app(app)


def init_celery(celery):
    pass
