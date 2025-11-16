import os, os.path, sys, logging
from flask import Flask, render_template, redirect, request, url_for
from werkzeug.exceptions import Unauthorized, HTTPException

import btcopilot


_log = logging.getLogger(__name__)


def create_app(config: dict = None, **kwargs):
    from btcopilot.pro.copilot.engine import Engine
    from btcopilot import auth, extensions, pro, personal, training

    # Flask CLI may pass script_info as a kwarg, we ignore it
    kwargs.pop("script_info", None)

    instancePath = os.getenv("BTCOPILOT_INSTANCE_PATH")
    if instancePath:
        app = Flask("btcopilot", instance_path=instancePath)
    else:
        app = Flask("btcopilot", instance_relative_config=True)

    # 1. Default config
    app.config.from_mapping(
        FD_DIR=app.instance_path,
        STRIPE_ENABLED=False,
        CONFIG="development",
        SQLALCHEMY_DATABASE_URI="postgresql://familydiagram:pks@localhost:5432/familydiagram",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        COPILOT_BASE_URL="http://localhost:4999",
        CELERY_BROKER_URL="redis://localhost:6379/0",
        CELERY_RESULT_BACKEND="redis://localhost:6379/0",
        WTF_CSRF_CHECK_DEFAULT=False,
    )

    if config and config.get("CONFIG"):
        app.config["CONFIG"] = config.get("CONFIG")
    elif os.getenv("FLASK_CONFIG"):
        app.config["CONFIG"] = os.getenv("FLASK_CONFIG")

    # 2. Overrides from environment vars (i.e. from Docker)
    _log.debug("Importing config overrides from environment variables.")
    app.config.from_prefixed_env()  # "FLASK_" default prefix

    if app.config["CONFIG"] == "development":
        app.config["SECRET_KEY"] = "dev-secret-key-for-sessions-change-in-production"
    else:
        if not "SECRET_KEY" in app.config:
            raise ValueError("SECRET_KEY must be set in production! ")

    # 3. - Overrides from passed kwargs
    if config:
        # load the test config if passed in
        _log.debug("Importing config overrides passed to create_app().")
        app.config.from_mapping(config)

    ## Instance

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    else:
        _log.info(f"Created instance dir {app.instance_path}")

    engine = Engine(
        data_dir=app.config.get(
            "VECTOR_DB_PATH", os.path.join(app.instance_path, "vector_db")
        ),
        k=20,
    )
    app.engine = engine

    ## Exception Notifs

    @app.errorhandler(405)
    def _(e):
        """
        Added to prevent 405's from attacks being reported as 500's. Specific
        handlers override the generic one below.
        """
        return e

    @app.errorhandler(Exception)
    def _(e):
        if isinstance(e, HTTPException):
            return e

        app.logger.exception(f"Unhandled exception: {type(e).__name__}")
        return "Internal Server Error", 500

    @app.errorhandler(Unauthorized)
    def _(e):
        return "Unauthorized", 401

    @app.errorhandler(403)
    def _(e):
        from flask import redirect, url_for, request
        from btcopilot.auth import is_pro_app_request, is_personal_app_request

        if is_pro_app_request() or is_personal_app_request():
            return "Forbidden", 403
        else:
            return redirect(url_for("training.auth.login", next=request.url))

    @app.errorhandler(404)
    def _(e):
        try:
            user = auth.current_user()
        except HTTPException as e:
            user = None
        # if not user or user.IS_ANONYMOUS:
        #     return redirect(url_for("training.auth.login", next=request.url))
        # else:
        return (
            render_template("errors/404.html", current_user=user, btcopilot=btcopilot),
            404,
        )

    @app.before_request
    def _():
        if request.path == "/v1/health":
            return

        _log.info(
            f"{request.method} {request.path}",
            extra={
                "http": {
                    "method": request.method,
                    "url": request.url,
                    "path": request.path,
                    "referrer": request.referrer,
                    "user_agent": (
                        request.user_agent.string if request.user_agent else None
                    ),
                }
            },
        )
        if "ddtrace" in sys.modules:
            from ddtrace import tracer
            from btcopilot import version

            span = tracer.current_span()
            if span:
                span.set_tag("version", version())

    ## Initialize Modules

    extensions.init_app(app)
    pro.init_app(app)
    personal.init_app(app)
    training.init_app(app)

    @app.route("/")
    def root():
        return redirect(url_for("training.auth.login"))

    _log.debug("btcopilot.create_app() complete")
    return app
