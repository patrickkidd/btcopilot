import datetime

import pytest

import btcopilot
from btcopilot.extensions import db


from btcopilot.tests.pro.fdencryptiontestclient import FDEncryptionTestClient


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
