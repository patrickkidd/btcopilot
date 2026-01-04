import datetime

import pytest
from mock import patch

import btcopilot
from btcopilot.extensions import db
from btcopilot.pro.models import Session

from btcopilot.tests.training.conftest import flask_json


def test_success_new(anonymous, test_user):
    assert Session.query.count() == 0
    with patch("btcopilot.pro.models.User.check_password", return_value=True):
        response = anonymous.post(
            "/training/login",
            data={"username": test_user.username, "password": "bad-password"},
        )
    assert response.status_code == 200
    assert response.json == flask_json(
        Session.query.one_or_none().account_editor_dict()
    )


def test_success_existing(anonymous, test_user):
    session = Session(user_id=test_user.id)
    db.session.add(session)
    db.session.commit()
    assert Session.query.count() == 1
    with patch("btcopilot.pro.models.User.check_password", return_value=True):
        response = anonymous.post(
            "/training/login",
            data={"username": test_user.username, "password": "bad-password"},
        )
    assert response.status_code == 200
    assert Session.query.count() == 1
    assert response.json == flask_json(session.account_editor_dict())


def test_login_fail(anonymous, test_user):
    response = anonymous.post(
        "/training/login",
        data={"username": test_user.username, "password": "bad password"},
    )
    assert response.status_code == 401


def test_session_expires_server_side(flask_app, test_user):
    """Session should expire based on logged_in_at timestamp, not just cookie."""
    test_user.roles = btcopilot.ROLE_AUDITOR
    db.session.merge(test_user)
    db.session.commit()

    with flask_app.test_client(use_cookies=True) as client:
        # Set up expired session (9 hours ago, lifetime is 8 hours)
        expired_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            hours=9
        )
        with client.session_transaction() as sess:
            sess["user_id"] = test_user.id
            sess["logged_in_at"] = expired_time.isoformat()

        response = client.get("/training/audit/")
        assert response.status_code == 302
        assert "/auth/login" in response.headers.get("Location", "")


def test_session_without_logged_in_at_expires(flask_app, test_user):
    """Session without logged_in_at should be treated as expired."""
    test_user.roles = btcopilot.ROLE_AUDITOR
    db.session.merge(test_user)
    db.session.commit()

    with flask_app.test_client(use_cookies=True) as client:
        with client.session_transaction() as sess:
            sess["user_id"] = test_user.id
            # No logged_in_at set

        response = client.get("/training/audit/")
        assert response.status_code == 302
        assert "/auth/login" in response.headers.get("Location", "")
