import os.path
import sys
import logging

from flask import Flask

from btcopilot import extensions, commands, v1
from btcopilot.engine import Engine

_log = logging.getLogger(__name__)


def create_app(
    config_overrides=None,
    app_class=Flask,
    instance_path: str = None,
    vector_db_path: str = None,
):

    if not instance_path:
        instance_path = os.path.join(os.getcwd(), "instance")

    app = app_class(__name__, instance_path=instance_path)

    if vector_db_path is None:
        if os.getenv("FLASK_VECTOR_DB_PATH"):
            vector_db_path = os.getenv("FLASK_VECTOR_DB_PATH")
        else:
            vector_db_path = os.path.join(app.instance_path, "vector_db")

    engine = Engine(data_dir=vector_db_path)
    app.engine = engine

    # 1. Default config
    app.config.from_mapping(
        FD_DIR=app.instance_path,
        STRIPE_ENABLED=True,
        CONFIG="development",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )

    if config_overrides and config_overrides.get("CONFIG"):
        app.config["CONFIG"] = config_overrides.get("CONFIG")
    elif os.getenv("FLASK_CONFIG"):
        app.config["CONFIG"] = os.getenv("FLASK_CONFIG")

    # 2 - Overrides from environment vars (i.e. from Docker)
    _log.debug("Importing config overrides from environment variables.")
    app.config.from_prefixed_env()  # "FLASK_" default prefix

    # 3 - Overrides from passed kwargs
    if config_overrides:
        # load the test config if passed in
        _log.debug("Importing config overrides passed to create_app().")
        app.config.from_mapping(config_overrides)

    ## Instance

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    else:
        _log.info(f"Created instance dir {app.instance_path}")

    @app.errorhandler(Exception)
    def on_exception(e):
        app.logger.exception(e.__repr__())

    @app.errorhandler(404)
    def handler_404(request):
        return ("Not Found", 404)

    ## Initialize Modules

    extensions.init_app(app)
    commands.init_app(app)
    v1.init_app(app)

    _log.debug("Patrick says flask app is ready to go.")
    return app
