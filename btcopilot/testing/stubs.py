"""Third-party stand-ins for a sandbox server process.

The sandbox runs the real create_app, so the extensions that talk to Datadog,
Stripe and SMTP are replaced with no-ops and bcrypt with a fast fake.
Celery stays live when a real broker is given, which is what makes background
work (Rebuild diagram) actually run in the sandbox.

Not used under pytest: btcopilot/tests/conftest.py installs its own patches so
individual tests can opt back into the real implementations by marker.
"""

from btcopilot import extensions
from btcopilot.pro.models import User

NOOP_EXTENSIONS = (
    "init_logging",
    "init_excepthook",
    "init_datadog",
    "init_stripe",
    "init_mail",
)
LIVE_BROKER_SCHEMES = ("redis://", "rediss://", "amqp://")
MEMORY_BROKER = "memory://"
MEMORY_BACKEND = "cache+memory://"
MOCK_HASH_PREFIX = "mock_hash:"


def configure_test_app(app, *, broker: str | None = None):
    if app.config.get("CONFIG") == "production":
        raise RuntimeError("configure_test_app() called on a production config")

    live_celery = bool(broker) and broker.startswith(LIVE_BROKER_SCHEMES)
    app.config.update(
        STRIPE_ENABLED=False,
        SCHEDULER_API_ENABLED=False,
        WTF_CSRF_CHECK_DEFAULT=False,
        CELERY_BROKER_URL=broker if live_celery else MEMORY_BROKER,
        CELERY_RESULT_BACKEND=broker if live_celery else MEMORY_BACKEND,
    )

    for name in NOOP_EXTENSIONS:
        setattr(extensions, name, _noop)
    if not live_celery:
        extensions.init_celery = _noop

    User.set_password = _set_password
    User.check_password = _check_password
    User.set_reset_password_code = _set_reset_code
    User.check_reset_password_code = _check_reset_code

    return live_celery


def _noop(app):
    return None


def _set_password(self, plaintext):
    self.password = f"{MOCK_HASH_PREFIX}{plaintext}"
    self.reset_password_code = None


def _check_password(self, plaintext):
    return self.password == f"{MOCK_HASH_PREFIX}{plaintext}"


def _set_reset_code(self, plaintext):
    self.reset_password_code = f"{MOCK_HASH_PREFIX}{plaintext}"


def _check_reset_code(self, plaintext):
    return self.reset_password_code == f"{MOCK_HASH_PREFIX}{plaintext}"
