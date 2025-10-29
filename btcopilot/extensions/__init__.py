"""
Logging topology:

A) Send all imperative log statements like log.info, log.warning, etc. to both
   stdout and to a json file appropriate for Datadog-agent to pick up,
   including:
  1. Module-level logging
  2. A subsystem activity log for user-level actions for analytics
B) Log all unhandled exceptions to:
  1. The standard ways they are usually printed to stdout or stderr
  2. The json file for datadog-agent to pick up.
  3. bugsnag via the official bugsnag python api package.
C) Include the current user's username and full name in every json log entry for
   datadog so it shows up in the datadog web UI as { user: { username:
   'some-username', 'name': 'Some Name } }, using flask's like g.user to access
   the user which I set in my request handler.
"""

import sys
import logging
import datetime
import os.path
import json
import logging

from flask import Flask, g, current_app, has_app_context, has_request_context, request
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from celery import Celery

from btcopilot import version
from .handlers import ColorfulSMTPHandler
from .llm import LLM, LLMFunction
from .chroma import Chroma

SERVER_FOLDER_PATH = os.path.realpath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")
)


EMBEDDINGS_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# # Best so far
# LLM_MODEL = "mistral"

LLM_MODEL = "gpt-4o-mini"

# LLM_MODEL = "mistral:7b-text-q8_0"

# LLM_MODEL = "tinyllama" # Had dirty answers

# LLM_MODEL = "deepseek-r1:14b"
# LLM_MODEL = "deepseek-r1:1.5b"


_log = logging.getLogger(__name__)


chroma = Chroma()
llm = LLM()
db = SQLAlchemy()
mail = Mail()
csrf = CSRFProtect()
celery = None

# Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def time_2_iso8601(x: float) -> str:
    return (
        datetime.datetime.fromtimestamp(x, tz=datetime.timezone.utc).isoformat() + "Z"
    )


class UserDataFilter(logging.Filter):
    """
    Add user and module info to log records. Has no knowledge of third-party
    services like datadog or bugsnag.
    """

    def filter(self, record):
        if has_app_context() and hasattr(g, "user"):
            record.user = g.user
        return True


class DatadogJSONFormatter(logging.Formatter):
    """
    A simple JSON formatter that turns log records into JSON strings.
    """

    def format(self, record):

        if os.getenv("DD_SERVICE"):
            service = os.getenv("DD_SERVICE")
        elif os.getenv("FD_IS_CELERY"):
            service = "celery"
        else:
            service = "btcopilot"

        dd_log = {
            "ddsource": "celery" if os.getenv("FD_IS_CELERY") else "flask",
            "ddtags": "desktop",
            "host": os.getenv("DD_HOSTNAME", ""),
            "service": service,
            "date": time_2_iso8601(record.created),
            "status": record.levelname,
            "message": record.getMessage(),
            "btcopilot": {
                "version": version.VERSION,
            },
            "version": (
                getattr(g, "fd_client_version", None) if has_app_context() else None
            ),
        }

        if has_request_context():
            dd_log["btcopilot"]["remote_addr"] = request.remote_addr
            dd_log["btcopilot"]["method"] = request.method
            dd_log["btcopilot"]["path"] = request.path

        if hasattr(record, "user") and hasattr(record.user, "id"):
            dd_log["user"] = {
                "id": record.user.id,
                "name": f"{record.user.first_name} {record.user.last_name}",
                "username": record.user.username,
                "free_diagram_id": record.user.free_diagram_id,
                "licenses": (
                    [y.policy.code for y in record.user.licenses]
                    if record.user.licenses
                    else []
                ),
            }

        return json.dumps(dd_log)


class MyFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)


def init_datadog(app):
    """Configure unified logging for btcopilot application code

    All btcopilot.* loggers will:
    - Write to console in Flask format: [timestamp] LEVEL in module: message
    - Write to JSON file for Datadog agent
    - Not propagate to root (prevents duplicate logs)
    """

    os.makedirs(os.path.join(app.instance_path, "logs"), exist_ok=True)
    is_celery = os.getenv("FD_IS_CELERY")
    if is_celery:
        fpath = os.path.join(app.instance_path, "logs", "celery.json")
    else:
        fpath = os.path.join(app.instance_path, "logs", "flask.json")
    print(f"Outputting datadog log: {fpath}")

    logger = logging.getLogger("btcopilot")

    # Check if already initialized (idempotent)
    has_console = any(
        isinstance(h, logging.StreamHandler) and h.stream == sys.stdout
        for h in logger.handlers
    )
    has_datadog = any(isinstance(h, MyFileHandler) for h in logger.handlers)

    if has_console and has_datadog:
        return

    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not has_datadog:
        datadogHandler = MyFileHandler(fpath, mode="a+")
        datadogHandler.setLevel(logging.DEBUG)
        datadogHandler.setFormatter(DatadogJSONFormatter())
        datadogHandler.addFilter(UserDataFilter())
        logger.addHandler(datadogHandler)

    if not has_console:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
        )
        logger.addHandler(console)


def _bugsnag_before_notify(event):
    from btcopilot import v1

    if isinstance(event.exception, KeyboardInterrupt):
        return False

    # Custom behavior can be added based on the request context
    # if event.request is not None and event.request.status_code == 505:
    #     return False

    if not current_app:
        return

    user = g.user

    if isinstance(user, v1.AnonUser):
        return

    event.user = {
        "id": user.username,
        "name": user.full_name,
        "email": user.username,
    }
    event.add_tab(
        "account",
        {
            "licenses": [
                license.policy.name for license in user.licenses if license.active
            ]
        },
    )


def init_bugsnag(app):

    import bugsnag.flask

    bugsnag.configure(
        api_key="fb81f498bb09829ce33d774fff6c0d05",
        project_root=SERVER_FOLDER_PATH,
    )

    bugsnag.flask.handle_exceptions(app)
    bugsnag.before_notify(_bugsnag_before_notify)


def init_stripe(app):

    if "STRIPE_KEY" in app.config:
        import stripe

        stripe.api_key = app.config["STRIPE_KEY"]

    if app.config.get("STRIPE_ENABLED"):
        # debug build; hide warnings from auto-closed sockets in stripe api
        if hasattr(sys, "gettotalrefcount"):
            import warnings

            warnings.simplefilter("ignore", ResourceWarning)


_excepthooks = []


def _excepthook(exc_type, exc_value, exc_traceback):
    global _excepthook

    if _excepthooks:
        for hook in _excepthooks:
            hook(exc_type, exc_value, exc_traceback)
    else:
        if issubclass(exc_type, KeyboardInterrupt):
            # Don't log KeyboardInterrupt exceptions
            return

        # Log the exception to ai_log
        _log.error(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )


def init_excepthook(app):
    if sys.excepthook != sys.__excepthook__:
        _excepthooks.append(sys.excepthook)
    sys.excepthook = _excepthook


ai_log = logging.Logger(__name__ + ".ai_log")
ai_log.propagate = False


def init_logging(app: Flask):
    """
    Should be mockable for tests. So everything you don't want to run in tests.
    """
    global ai_log

    ai_handler = logging.FileHandler("ai_log.txt")
    formatter = logging.Formatter("%(asctime)s - %(message)s")
    ai_handler.setFormatter(formatter)
    ai_log.addHandler(ai_handler)
    ai_log.propagate = False

    # formatter = logging.Formatter(
    #     "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    # )
    # console_handler = logging.StreamHandler(sys.stdout)
    # console_handler.setFormatter(formatter)
    # logging.getLogger("btcopilot").addHandler(console_handler)

    if "MAIL_SERVER" in app.config:
        mail_handler = ColorfulSMTPHandler(
            mailhost=(app.config["MAIL_SERVER"], app.config["MAIL_PORT"]),
            fromaddr=app.config["MAIL_DEFAULT_SENDER"],
            toaddrs=[app.config["ADMIN_EMAIL"]],
            subject=None,
            credentials=(
                app.config["MAIL_USERNAME"],
                app.config["MAIL_PASSWORD"],
            ),
        )
        mail_handler.setLevel(logging.ERROR)
        mail_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
        )
        app.logger.addHandler(mail_handler)


def init_celery(app):
    """Initialize Celery with Flask app using factory pattern"""
    global celery

    # Only initialize if not already done
    if celery is None:
        celery = Celery(app.import_name)

    # Configure with app config
    celery.conf.update(
        broker_url=app.config.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        result_backend=app.config.get(
            "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
        ),
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        worker_hijack_root_logger=False,
        worker_redirect_stdouts=False,
        beat_schedule={
            "sync-with-stripe-daily": {
                "task": "sync_with_stripe",
                "schedule": 86400.0,  # 24 hours
            },
            "expire-stale-sessions-hourly": {
                "task": "expire_stale_sessions",
                "schedule": 3600.0,  # 1 hour
            },
        },
    )

    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context."""

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # Register tasks only once
    if not hasattr(celery, "_tasks_registered"):

        from btcopilot import pro, personal, training

        pro.init_celery(celery)
        personal.init_celery(celery)
        training.init_celery(celery)

        # Mark tasks as registered to avoid duplicate registration
        celery._tasks_registered = True


def cron_daily():
    from btcopilot import commands

    _log.info(f"cron_daily() {datetime.datetime.now()}")
    sync_with_stripe()
    commands.expire_stale_sessions()


def cron_hourly():
    from btcopilot import commands

    _log.info(f"cron_hourly() {datetime.datetime.now()}")
    commands.expire_stale_sessions()


def init_chroma(app):
    chroma.init_app(app)


def init_mail(app):
    mail.init_app(app)


def init_csrf(app):
    csrf.init_app(app)


def init_app(app):

    init_excepthook(app)
    init_logging(app)
    init_celery(app)

    # if app.config.get("CONFIG") == "production":
    #     init_bugsnag(app)

    init_datadog(app)
    init_stripe(app)

    db.init_app(app)
    init_mail(app)
    mail.init_app(app)
    init_csrf(app)
    init_chroma(app)

    if os.environ.get("ENABLE_GRAPHQL", False) and "pytest" not in sys.modules:
        from btcopilot.extensions import graphql

        graphql.init_app(app)


_log = logging.getLogger(__name__)


def ensure_stripe_Customer(user):
    import stripe

    customers = stripe.Customer.list(email=user.username, expand=["data.sources"])[
        "data"
    ]
    if len(customers) == 0:
        customer = stripe.Customer.create(
            email=user.username, metadata={"fd_user_id": user.id}
        )
    else:
        customer = customers[0]
    return customer


def ensure_stripe_Plan(policy):
    import stripe

    from btcopilot import params

    if not params.truthy(current_app.config.get("STRIPE_ENABLED")):
        return
    stripeProduct = None
    for product in stripe.Product.list()["data"]:
        if product["metadata"]["fd_id"] == policy.product:
            stripeProduct = product
            break
    if not stripeProduct:
        stripeProduct = stripe.Product.create(
            name=policy.name,
            type="service",
            description=policy.description,
            metadata={"fd_id": policy.product},
        )
    stripePlan = None
    for plan in stripe.Plan.list()["data"]:
        if plan["metadata"]["fd_id"] == policy.code:
            stripePlan = plan
            break
    if not stripePlan:
        stripePlan = stripe.Plan.create(
            amount=int(policy.amount * 100),
            currency="usd",
            interval=policy.interval and policy.interval or "year",
            product=stripeProduct["id"],
            metadata={"fd_id": policy.code},
        )
    return stripePlan


def create_stripe_Subscription(user, policy, license, card):
    import stripe

    stripeCustomer = ensure_stripe_Customer(user)
    stripePlan = ensure_stripe_Plan(policy)
    # 1) Get card Token - only good for a couple of minutes
    token = stripe.Token.create(card=card)
    tokenCard = token["card"]
    # 3) Check if card exists in Customer sources by matching Token (fingerprint, mon, year)
    stripePM = None
    sources = stripe.PaymentMethod.list(customer=stripeCustomer["id"], type="card")
    for source in sources["data"]:
        sourceCard = source["card"]
        if (
            tokenCard["fingerprint"],
            tokenCard["exp_month"],
            tokenCard["exp_year"],
        ) == (
            sourceCard["fingerprint"],
            sourceCard["exp_month"],
            sourceCard["exp_year"],
        ):
            stripePM = source
            break
    # 4) Add card to Customer as PaymentMethod (i.e. "source") if it doesn't exist
    if not stripePM:
        stripePM = stripe.PaymentMethod.create(type="card", card=card)
        stripe.PaymentMethod.attach(stripePM["id"], customer=stripeCustomer["id"])
    # 5) Create Subscription
    stripeSub = stripe.Subscription.create(
        customer=stripeCustomer["id"],
        items=[{"plan": stripePlan["id"]}],
        default_payment_method=stripePM["id"],
        metadata={"fd_id": license.id},
    )
    return stripeSub


## TODO: Maybe also cancel licenses in a webhook from Stripe?
def sync_with_stripe():
    import stripe
    from btcopilot.pro.models import License, Policy, User

    _log.info(f"Starting...")
    # Expire old subscriptions
    stripeSubs = stripe.Subscription.list(status="canceled")["data"]
    licenses = License.query.filter_by(active=True).all()
    _log.info(f"Found {len(licenses)} active local licenses.")
    for license in licenses:
        stripeSub = None
        for entry in stripeSubs:
            if entry["id"] == license.stripe_id:
                stripeSub = entry
                break
        if stripeSub:
            _log.info("Canceling license: %s" % license.as_dict())
            if (
                stripeSub["ended_at"] != None
            ):  # stripeSub['status'] in ('active', 'trialing', 'past_due'):
                license.active = False
            if stripeSub["status"] == "canceled":
                license.canceled = True
    deactivated = [l for l in licenses if l.active is False]
    canceled = [l for l in licenses if l.canceled is True]
    _log.info(
        f"Deactivated {len(deactivated)} licenses, canceled {len(canceled)} licenses."
    )
    db.session.commit()

    # Sync new subscriptions added through web interface.
    num_created = 0
    stripeSubs = stripe.Subscription.list(status="active")["data"]
    _log.info(f"Found {len(stripeSubs)} active Stripe subscriptions.")
    for subEntry in stripeSubs:
        if not subEntry["metadata"].get(
            "fd_id"
        ):  # Assume no metadata means subscription was manually entered online.
            _log.info(
                "Found manually entered Stripe Subscription %s, creating local License to match."
                % subEntry["id"]
            )
            customerId = subEntry["customer"]
            _log.info("Querying Stripe Customer", subEntry["customer"])
            try:
                stripeCustomer = stripe.Customer.retrieve(subEntry["customer"])
            except stripe.error.InvalidRequestError as e:
                _log.error(e, exc_info=True)
                continue
            # Assume that a customer can only be added through the app and so has appropriate metadata.
            fd_user_id = stripeCustomer["metadata"]["fd_user_id"]
            user = User.query.get(fd_user_id)
            _log.info(
                "Found local user ID %s, %s for this subscription."
                % (user.id, user.full_name())
            )
            # Also assume that the Policy/Product don't need any further setup.
            priceEntry = subEntry["items"]["data"][0]["price"]
            fd_policy_id = priceEntry["metadata"]["fd_id"]
            policy = Policy.query.filter_by(code=fd_policy_id)[0]
            if not policy:
                _log.info(
                    "Could not find Policy %s that matched Stripe Price %s for Stripe Product %s"
                    % (fd_policy_id, priceEntry["id"], priceEntry["product"])
                )
                continue
            _log.info("")
            license = License(
                user=user, policy=policy, activated_at=datetime.datetime.utcnow()
            )
            db.session.add(license)
            db.session.commit()
            db.session.refresh(license)
            _log.info(f"Created License {license.id} for user {user.id}.")
            _log.info("Updating subscription metadata with License info.")
            stripe.Subscription.modify(subEntry["id"], metadata={"fd_id": license.id})
    _log.info(f"Created {num_created} local licenses for Stripe subscriptions.")
    _log.info(f"Done.")
