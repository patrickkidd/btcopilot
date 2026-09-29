import os, os.path, logging, uuid
from flask import Flask, g, jsonify, redirect, request, url_for
from werkzeug.exceptions import Unauthorized, HTTPException

import btcopilot

from btcopilot import tracing
from btcopilot.turnlog import TurnLogBackend


_log = logging.getLogger(__name__)

# A push goes out long after the message it points at is committed, so these
# are read when the app is made rather than at the first send.
VAPID = ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT")

# The header naming the request each response answers, which every line logged
# while serving it names too; only this server sets it, so a proxy's own error
# page never carries it [Oracle: R-0056].
REQUEST_ID = "X-Request-Id"


def create_app(config: dict = None, **kwargs):
    from btcopilot import auth, extensions, routes
    from btcopilot.review import routes as review_routes
    from btcopilot import admin
    from btcopilot.auth import signin
    from btcopilot.routes.web import FRESH

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
        # The box sets these unprefixed for the worker; the app reads the same
        # values so the turn log and the queue share one Redis.
        CELERY_BROKER_URL=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        CELERY_RESULT_BACKEND=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
        WTF_CSRF_CHECK_DEFAULT=False,
        # A token stamped into a page lives as long as the session that page
        # belongs to. The default hour expires it under a reader who is still
        # signed in and still typing, and every post after that is refused.
        WTF_CSRF_TIME_LIMIT=None,
        # The concept pages (FD-364); the token is FLASK_THEORY_GITHUB_TOKEN.
        THEORY_REPO="patrickkidd/btcopilot-sources",
        THEORY_REF="master",
        THEORY_PATH="theory/CONCEPTS",
        # How often celery beat looks for a message the coach may write first.
        PROACTIVE_EVERY_S=15 * 60,
    )

    if config and config.get("CONFIG"):
        app.config["CONFIG"] = config.get("CONFIG")
    elif os.getenv("FLASK_CONFIG"):
        app.config["CONFIG"] = os.getenv("FLASK_CONFIG")

    # Redis in production, so the worker's events reach the web process; in
    # one process everywhere else, where no separate worker is assumed to be
    # running and the turn log needs no Redis of its own.
    app.config["TURN_LOG"] = (
        TurnLogBackend.Redis
        if app.config["CONFIG"] == "production"
        else TurnLogBackend.Memory
    )

    # 2. Overrides from environment vars (i.e. from Docker)
    _log.debug("Importing config overrides from environment variables.")
    app.config.from_prefixed_env()  # "FLASK_" default prefix

    if app.config["CONFIG"] == "development":
        app.config["SECRET_KEY"] = "dev-secret-key-for-sessions-change-in-production"
    else:
        if "SECRET_KEY" not in app.config:
            raise ValueError("SECRET_KEY must be set in production! ")

    # 3. - Overrides from passed kwargs
    if config:
        # load the test config if passed in
        _log.debug("Importing config overrides passed to create_app().")
        app.config.from_mapping(config)

    missing = [f"FLASK_{key}" for key in VAPID if not app.config.get(key)]
    if missing:
        raise ValueError(
            f"{', '.join(missing)} must be set: python -m btcopilot.push makes"
            " the key pair, and the subject is mailto: and an address"
        )

    ## Instance

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    else:
        _log.info(f"Created instance dir {app.instance_path}")

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
        from btcopilot.auth import is_chat_app_request

        if is_chat_app_request():
            return "Forbidden", 403
        return redirect(url_for("auth.login", next=request.url))

    @app.errorhandler(404)
    def _(e):
        return "Not Found", 404

    @app.before_request
    def _():
        g.request_id = uuid.uuid4().hex
        if request.path == "/health":
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

    @app.after_request
    def _(response):
        response.headers[REQUEST_ID] = g.request_id
        return response

    ## Initialize Modules

    tracing.init_app()
    extensions.init_app(app)
    auth.init_app(app)
    routes.init_app(app)
    review_routes.init_app(app)
    admin.init_app(app)

    @app.route("/health")
    def health():
        return btcopilot.__version__

    # A home-screen app signed out months ago still has to find the new
    # release, and the version is already public on /health; only /app reaches
    # the server through the box's proxy.
    @app.route("/app/version")
    def version():
        return jsonify(version=btcopilot.__version__), FRESH

    @app.route("/")
    def root():
        if signin.current_web_session():
            return redirect(app.config["APP_HOME"])
        return redirect(url_for("auth.login"))

    _log.debug("btcopilot.create_app() complete")
    return app
