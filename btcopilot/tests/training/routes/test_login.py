import pytest
from mock import patch

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


def test_success_existng(anonymous, test_user):
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
