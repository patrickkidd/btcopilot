import os
import sys
import pickle
import datetime
import warnings
import subprocess
import logging
import contextlib
import typing_extensions  # preemptive

import pytest
import flask
from flask.testing import FlaskClient

# from flask.testing import FlaskClient
import pydantic
from mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# prevent error "Instance <...> is not bound to a Session; attribute refresh operation cannot proceed"
from sqlalchemy.orm import scoped_session
from flask_mail import Mail


import vedana
from btcopilot import create_app
from btcopilot.extensions import db
from btcopilot.params import truthy
from btcopilot.pro.models import (
    Session,
    Activation,
    License,
    Machine,
    User,
    Policy,
    Diagram,
)

# Import personal models to register them with SQLAlchemy
from btcopilot.personal.models import Discussion, Statement, Speaker


# HARDWARE_UUID = (
#     subprocess.check_output(
#         "system_profiler SPHardwareDataType | awk '/UUID/ { print $3; }'", shell=True
#     )
#     .decode("utf-8")
#     .strip()
# )
HARDWARE_UUID = "1B825A8F-32CB-5419-B6C2-BB08A7DEA901"


def pytest_addoption(parser):
    parser.addoption(
        "--e2e",
        action="store_true",
        default=False,
        help="Run end-to-end tests with third-party api calls (costs money)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "access_rights: set access rights prior to init",
    )
    config.addinivalue_line(
        "markers", "e2e: Run end-to-end test cases which access paid third-party tools"
    )
    config.addinivalue_line(
        "markers", "init_datadog: Un-mock the init_datadog extension"
    )
    warnings.filterwarnings(
        "ignore",
        category=pydantic.warnings.PydanticDeprecatedSince211,
        module="chromadb.types",
    )


# def pytest_collection_modifyitems(config, items):
#     skip_marker = pytest.mark.skip(reason=f"needs --e2e to run")
#     for item in items:
#         if item.get_closest_marker("e2e") and not config.getoption("--e2e"):
#             item.add_marker(skip_marker)


@pytest.fixture(autouse=True)
def e2e(request):
    if request.node.get_closest_marker("e2e") is not None:
        if not request.config.getoption("--e2e"):
            pytest.skip("need --e2e option to run")


@pytest.fixture(scope="session", autouse=True)
def extensions():
    """
    These extension initializers are like modules. Can re-enable for certain
    tests through marks if needed.
    """
    import btcopilot.extensions

    originals = {
        "init_logging": btcopilot.extensions.init_logging,
        "init_excepthook": btcopilot.extensions.init_excepthook,
        "init_mail": btcopilot.extensions.init_mail,
        "init_datadog": btcopilot.extensions.init_datadog,
        "init_stripe": btcopilot.extensions.init_stripe,
        "init_chroma": btcopilot.extensions.init_chroma,
        "init_celery": btcopilot.extensions.init_celery,
    }
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("btcopilot.extensions.init_logging"))
        stack.enter_context(patch("btcopilot.extensions.init_excepthook"))
        stack.enter_context(patch("btcopilot.extensions.init_datadog"))
        stack.enter_context(patch("btcopilot.extensions.init_stripe"))
        stack.enter_context(patch("btcopilot.extensions.init_chroma"))
        stack.enter_context(patch("btcopilot.extensions.init_celery"))
        # assert sys.excepthook == sys.__excepthook__
        yield originals


@pytest.fixture(autouse=True)
def unmocks(request, extensions):
    """
    Un-mock anything automatically mocked out (currently just extensions init
    funcs) by name.
    """
    unmocked = []
    with contextlib.ExitStack() as stack:
        for init_funcname, original in extensions.items():
            if request.node.get_closest_marker(init_funcname):
                stack.enter_context(
                    patch(f"btcopilot.extensions.{init_funcname}", original)
                )
                unmocked.append(init_funcname)
        yield unmocked


@pytest.fixture
def flask_app(request, tmp_path):

    logging.getLogger("btcopilot").setLevel(logging.DEBUG)

    vector_db = request.node.get_closest_marker("vector_db")
    if vector_db and "path" in vector_db.kwargs:
        VECTOR_DB_PATH = vector_db.kwargs["path"]
    else:
        VECTOR_DB_PATH = os.path.join(tmp_path, "vector_db")

    kwargs = {
        "ENV": "unittest",
        "CONFIG": "testing",
        "TESTING": True,
        "SECRET_KEY": "test_secret_key",
        "FD_DIR": tmp_path,
        "DATABASE": tmp_path,
        "VECTOR_DB_PATH": VECTOR_DB_PATH,
        "MAIL_DEFAULT_SENDER": "patrickkidd@gmail.com",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SERVER_NAME": "127.0.0.1",
        "STRIPE_ENABLED": truthy(os.getenv("ENABLE_STRIPE", False)),
        "STRIPE_KEY": os.getenv("FD_TEST_STRIPE_KEY"),
        "CHROMA_PERSIST_PATH": f"{tmp_path}/vector_db",
        "SCHEDULER_API_ENABLED": False,
        "CELERY_BROKER_URL": "memory://",
        "CELERY_RESULT_BACKEND": "cache+memory://",
    }

    # class TestApp(flask.Flask):
    #     def test_client(self, **kwargs):
    #         return super().test_client(app=self, **kwargs)

    app = create_app(app_class=flask.Flask, instance_path=tmp_path, config=kwargs)

    # db.session = app.db.create_scoped_session()
    # A default. Just override to have something else.

    # Apparently, required for app.config['TESTING'] == True
    extensions.mail = Mail()
    extensions.mail.init_app(app)

    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture
def db_session():
    from sqlalchemy.orm import declarative_base

    # Base = declarative_base()
    Base = db.Model

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    with patch.object(db, "session", session):
        yield session

    session.close()
    Base.metadata.drop_all(engine)


TEST_USER_ATTRS = {
    "username": "patrickkidd+unittest@gmail.com",
    "password": "something",
    "first_name": "Unit",
    "last_name": "Tester",
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


TEST_USER_2_ATTRS = {
    "username": "patrickkidd+unittest+2@gmail.com",
    "password": "something else",
    "first_name": "Unit",
    "last_name": "Tester 2",
}


@pytest.fixture
def test_user_2(flask_app):
    user = User(status="confirmed", **TEST_USER_2_ATTRS)
    user._plaintext_password = TEST_USER_2_ATTRS["password"]
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def test_policy(flask_app):
    policy = Policy(
        code=vedana.LICENSE_PROFESSIONAL_MONTHLY,
        product=vedana.LICENSE_PROFESSIONAL,
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


@pytest.fixture
def test_machine(test_user):
    machine = Machine(user=test_user, name="Some user's iMac", code=HARDWARE_UUID)
    db.session.add(machine)
    db.session.commit()
    return machine


@pytest.fixture
def test_activation(test_license, test_machine):
    activation = Activation(license=test_license, machine=test_machine)
    db.session.add(activation)
    db.session.commit()
    return activation


@pytest.fixture
def test_session(test_user):
    session = Session(user=test_user)
    db.session.add(session)
    db.session.commit()
    return session


@pytest.fixture
def test_client_policy(flask_app):
    policy = Policy(
        code=vedana.LICENSE_CLIENT_ONCE,
        product=vedana.LICENSE_CLIENT,
        name="Automated Test Client Once",
        interval=None,
        amount=0.99,
        maxActivations=2,
        active=True,
        public=True,
    )
    db.session.add(policy)
    db.session.commit()
    return policy


@pytest.fixture
def test_client_license(test_user, test_client_policy):
    license = License(user=test_user, policy=test_client_policy)
    db.session.add(license)
    db.session.commit()
    return license


@pytest.fixture
def test_client_activation(test_client_license, test_machine):
    activation = Activation(license=test_client_license, machine=test_machine)
    db.session.add(activation)
    db.session.commit()
    return activation


@pytest.fixture
def test_session(test_user):
    session = Session(user=test_user)
    db.session.add(session)
    db.session.commit()
    return session


@pytest.fixture
def mock_celery():
    from btcopilot import extensions
    from unittest.mock import Mock

    original_celery = extensions.celery
    mock = Mock()
    extensions.celery = mock

    yield mock

    extensions.celery = original_celery


NEW_SCENE_DATA = {
    "id": None,
    "tags": [],
    "loggedDateTime": None,
    "uuid": None,
    "masterKey": None,
    "alias": None,
    "readOnly": None,
    "lastItemId": 0,
    "contributeToResearch": False,
    "useRealNames": False,
    "password": "kj%grux%rk%u&#gq",
    "requirePasswordForRealNames": False,
    "showAliases": False,
    "hideNames": False,
    "hideToolBars": False,
    "hideEmotionalProcess": False,
    "hideEmotionColors": False,
    "hideDateSlider": False,
    "hideVariablesOnDiagram": False,
    "hideVariableSteadyStates": False,
    "exclusiveLayerSelection": True,
    "storePositionsInLayers": False,
    "currentDateTime": None,
    "scaleFactor": 0.33,
    "pencilColor": None,
    "eventProperties": [],
    "legendData": {"shown": False, "size": None, "anchor": "south-east"},
    "version": "2.0.0b4",
    "versionCompat": "1.3.0",
    "items": [],
    "name": "",
}


@pytest.fixture
def test_user_diagrams(test_user, test_user_2):

    NUM_DIAGRAMS = 10

    data = pickle.dumps(NEW_SCENE_DATA)
    ids = []
    for i in range(NUM_DIAGRAMS):
        if i % 2 == 0:
            user = test_user
        else:
            user = test_user_2
        diagram = Diagram(
            user_id=user.id, data=data, updated_at=datetime.datetime.now()
        )
        db.session.add(diagram)
        db.session.merge(diagram)
        ids.append(diagram.id)
    return Diagram.query.filter(Diagram.id.in_(ids)).all()


@pytest.fixture
def anonymous(flask_app):
    flask_app.test_client_class = FlaskClient
    with flask_app.test_client() as client:
        yield client


# # TODO: Should go away, but (was once?) used in a lot of familydiagram tests.
# @pytest.fixture
# def test_user_client(flask_qnam, test_user):
#     """A logged in client that is also encrypted."""
#     from flaskr import customclient

#     flask_app.test_client_class = customclient.CustomClient
#     return flask_app.test_client(app=flask_app, user=test_user)

# from btcopilot.extensions.chroma import Chroma


# @pytest.fixture
# def chroma_client(app):
#     app.config["CHROMA_PERSIST_PATH"] = "/tmp/test_chroma"
#     chroma = Chroma()
#     chroma.init_app(app)
#     return chroma
