"""Fixtures shared by more than one suite.

R-0332: a suite imports what it wants by name. Nothing here is applied to a
test by virtue of the directory it sits in.
"""

import os
import sys

# The private prompts are encrypted. Without a key that opens them the run uses
# the open-source ones, rather than failing to start — and says which it used, so
# a green run is never mistaken for a run against the real wording.
from btcopilot.personal.promptdir import key_present

if not key_present():
    os.environ.setdefault("FD_PRIVATE_PROMPTS", "/nonexistent")
    print("no sops key: running on the open-source prompts", file=sys.stderr)

import pickle
import contextlib
import logging
import datetime

import pytest
import typing_extensions  # noqa: F401  preemptive
from mock import patch
from flask.testing import FlaskClient
from flask_mail import Mail
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import btcopilot
from btcopilot.app import create_app
from btcopilot.extensions import db
import btcopilot.extensions as extension_module
from btcopilot.params import truthy
from btcopilot.models import License, Policy, User

# Importing the chat's models registers them with SQLAlchemy.
from btcopilot.personal.models import Discussion, Statement, Speaker  # noqa: F401
from btcopilot.tests.pro.fdencryptiontestclient import FDEncryptionTestClient


HARDWARE_UUID = "1B825A8F-32CB-5419-B6C2-BB08A7DEA901"

# Initializers every suite replaces: they write logs, install excepthooks, or
# reach Datadog.
CORE_STUBS = ("init_logging", "init_excepthook", "init_datadog")

# The chat app owns a task queue, and a unit run should not start it. Stripe
# is Pro's and the chat never reaches it.
CHAT_STUBS = CORE_STUBS + ("init_celery",)

PRO_STUBS = CORE_STUBS + ("init_stripe", "init_celery")

MARKERS = (
    "access_rights: set access rights prior to init",
    "e2e: Run end-to-end test cases which access paid third-party tools",
    "init_datadog: Un-mock the init_datadog extension",
    "real_passwords: Use real bcrypt hashing instead of mocks",
)


def add_e2e_option(parser):
    """The suites are independent, so whichever of them a run collects declares
    the option; a run that collects two has it already."""
    try:
        parser.addoption(
            "--e2e",
            action="store_true",
            default=False,
            help="Run end-to-end tests with third-party api calls (costs money)",
        )
    except ValueError:
        pass


def add_markers(config):
    for marker in MARKERS:
        config.addinivalue_line("markers", marker)


# Read before any suite stubs anything, so a run that collects two suites still
# hands a marked test the real initializer rather than the other suite's stand-in.
ORIGINALS = {name: getattr(extension_module, name) for name in PRO_STUBS}


@contextlib.contextmanager
def stubbed(names):
    """Replace the named extension initializers for the session, handing back
    the real ones so a marked test can put one back."""
    with contextlib.ExitStack() as stack:
        for name in names:
            stack.enter_context(patch(f"btcopilot.extensions.{name}"))
        yield {name: ORIGINALS[name] for name in names}


@pytest.fixture(autouse=True)
def e2e(request):
    if request.node.get_closest_marker("e2e") is not None:
        if not request.config.getoption("--e2e"):
            pytest.skip("need --e2e option to run")


@pytest.fixture(autouse=True)
def fast_passwords(request):
    """Skip bcrypt hashing for speed. @pytest.mark.real_passwords puts the real
    hashing back for the tests that are about passwords."""
    if request.node.get_closest_marker("real_passwords"):
        yield
        return

    def set_password(self, plaintext):
        self.password = f"hashed:{plaintext}"
        self.reset_password_code = None

    def check_password(self, plaintext):
        return self.password == f"hashed:{plaintext}"

    def set_reset_code(self, plaintext):
        self.reset_password_code = f"hashed:{plaintext}"

    def check_reset_code(self, plaintext):
        return self.reset_password_code == f"hashed:{plaintext}"

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(User, "set_password", set_password))
        stack.enter_context(patch.object(User, "check_password", check_password))
        stack.enter_context(
            patch.object(User, "set_reset_password_code", set_reset_code)
        )
        stack.enter_context(
            patch.object(User, "check_reset_password_code", check_reset_code)
        )
        yield


@pytest.fixture(autouse=True)
def unmocks(request, extensions):
    """Put back by name anything the suite stubbed out."""
    unmocked = []
    with contextlib.ExitStack() as stack:
        for name, original in extensions.items():
            if request.node.get_closest_marker(name):
                stack.enter_context(patch(f"btcopilot.extensions.{name}", original))
                unmocked.append(name)
        yield unmocked


@pytest.fixture
def flask_app(request, tmp_path):
    yield from make_app(request, tmp_path)


def make_app(request, tmp_path, tables=None):
    """The test app on an empty in-memory database. `tables` narrows what is
    created to one deployment's own set, so a path that reaches a table that
    deployment does not have fails here rather than on its server."""

    logging.getLogger("btcopilot").setLevel(logging.DEBUG)

    kwargs = {
        "ENV": "unittest",
        "CONFIG": "testing",
        "TESTING": True,
        "SECRET_KEY": "test_secret_key",
        "FD_DIR": tmp_path,
        "DATABASE": tmp_path,
        "MAIL_DEFAULT_SENDER": "patrickkidd@gmail.com",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SERVER_NAME": "127.0.0.1",
        "STRIPE_ENABLED": truthy(os.getenv("ENABLE_STRIPE", False)),
        "STRIPE_KEY": os.getenv("FD_TEST_STRIPE_KEY"),
        "SCHEDULER_API_ENABLED": False,
        "CELERY_BROKER_URL": "memory://",
        "CELERY_RESULT_BACKEND": "cache+memory://",
    }

    app = create_app(config=kwargs)
    app.instance_path = str(tmp_path)

    extension_module.mail = Mail()
    extension_module.mail.init_app(app)

    with app.app_context():
        if tables is None:
            db.create_all()
        else:
            db.Model.metadata.create_all(
                db.engine, tables=[db.Model.metadata.tables[t] for t in tables]
            )
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    db.Model.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    with patch.object(db, "session", session):
        yield session

    session.close()
    db.Model.metadata.drop_all(engine)


TEST_USER_ATTRS = {
    "username": "patrickkidd+unittest@gmail.com",
    "password": "something",
    "first_name": "Unit",
    "last_name": "Tester",
}

TEST_USER_2_ATTRS = {
    "username": "patrickkidd+unittest+2@gmail.com",
    "password": "something else",
    "first_name": "Unit",
    "last_name": "Tester 2",
}


@pytest.fixture
def test_user(flask_app):
    user = User(status="confirmed", **TEST_USER_ATTRS)
    user._plaintext_password = TEST_USER_ATTRS["password"]
    db.session.add(user)
    db.session.merge(user)
    user.set_free_diagram(pickle.dumps({}))
    db.session.commit()
    return user


@pytest.fixture
def test_user_2(flask_app):
    user = User(status="confirmed", **TEST_USER_2_ATTRS)
    user._plaintext_password = TEST_USER_2_ATTRS["password"]
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def anonymous(flask_app):
    flask_app.test_client_class = FlaskClient
    with flask_app.test_client() as client:
        yield client


def set_test_session(sess, user_id):
    sess["user_id"] = user_id
    sess["logged_in_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()


@pytest.fixture(autouse=True)
def pro_client(flask_app):
    flask_app.test_client_class = FDEncryptionTestClient


@pytest.fixture
def subscriber(test_user, flask_app):
    test_user.roles = btcopilot.ROLE_SUBSCRIBER
    db.session.merge(test_user)
    db.session.commit()
    with flask_app.test_client(use_cookies=True, user=test_user) as client:
        client.user = test_user
        with client.session_transaction() as sess:
            set_test_session(sess, test_user.id)
        yield client


@pytest.fixture
def admin(flask_app, test_user):
    test_user.roles = btcopilot.ROLE_ADMIN
    db.session.merge(test_user)
    db.session.commit()
    with flask_app.test_client(use_cookies=True, user=test_user) as client:
        client.user = test_user
        with client.session_transaction() as sess:
            set_test_session(sess, test_user.id)
        yield client


@pytest.fixture
def test_policy(flask_app):
    policy = Policy(
        code=btcopilot.LICENSE_PROFESSIONAL_MONTHLY,
        product=btcopilot.LICENSE_PROFESSIONAL,
        name="Unit Test Monthly",
        interval="month",
        amount=0.99,
        maxActivations=2,
        active=True,
        public=True,
    )
    db.session.add(policy)
    db.session.commit()
    return policy


@pytest.fixture
def test_license(test_user, test_policy):
    license = License(user=test_user, policy=test_policy)
    db.session.add(license)
    db.session.commit()
    return license
