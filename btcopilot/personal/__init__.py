from . import database
from . import chat
from .chat import ask, Response, ResponseDirection
from . import routes


def init_app(app):
    routes.init_app(app)
