"""The Pro and training world: the paid services stubbed out, licences,
machines and activations. The chat app's suite lives in chat/ and imports what
it wants by name (R-0332)."""

import pickle
import datetime

import pytest
from unittest.mock import Mock
import btcopilot
import btcopilot.extensions as extension_module
from btcopilot.extensions import db
from btcopilot.pro.models import (
    Session,
    Activation,
    License,
    Machine,
    Policy,
    Diagram,
)
from btcopilot.tests.fixtures import (
    PRO_STUBS,
    HARDWARE_UUID,
    add_e2e_option,
    add_markers,
    stubbed,
    anonymous,  # noqa: F401
    db_session,  # noqa: F401
    e2e,  # noqa: F401
    fast_passwords,  # noqa: F401
    flask_app,  # noqa: F401
    test_license,  # noqa: F401
    test_policy,  # noqa: F401
    test_user,  # noqa: F401
    test_user_2,  # noqa: F401
    unmocks,  # noqa: F401
)


def pytest_addoption(parser):
    add_e2e_option(parser)


def pytest_configure(config):
    add_markers(config)


@pytest.fixture(scope="session", autouse=True)
def extensions():
    with stubbed(PRO_STUBS) as originals:
        yield originals


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
        code=btcopilot.LICENSE_CLIENT_ONCE,
        product=btcopilot.LICENSE_CLIENT,
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
def mock_celery():
    original = extension_module.celery
    celery = Mock()
    extension_module.celery = celery
    yield celery
    extension_module.celery = original


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
        user = test_user if i % 2 == 0 else test_user_2
        diagram = Diagram(
            user_id=user.id, data=data, updated_at=datetime.datetime.now()
        )
        db.session.add(diagram)
        db.session.merge(diagram)
        ids.append(diagram.id)
    return Diagram.query.filter(Diagram.id.in_(ids)).all()
