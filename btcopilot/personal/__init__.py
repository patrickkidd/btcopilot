from . import chat
from . import database
from .chat import ask, Response, ResponseDirection


def init_app(app):
    chat.init_app(app)
    database.init_app(app)
