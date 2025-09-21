import pickle
import datetime

from btcopilot.extensions import db
from btcopilot.pro import DEACTIVATED_VERSIONS, SESSION_EXPIRATION_DAYS
from btcopilot.pro.models import Session


def test_sessions_login(flask_app, test_user, test_license, test_activation):
    args = {"username": test_user.username, "password": test_user._plaintext_password}
    bdata = pickle.dumps(args)
    with flask_app.test_client() as client:
        response = client.post("/v1/sessions", data=bdata)
    assert response.status_code == 200

    session = Session.query.filter_by(user_id=test_user.id).first()
    data = pickle.loads(response.data)
    assert data["session"]["token"] == session.token
    assert data["session"]["user"]["username"] == args["username"]
    assert len(data["session"]["user"]["licenses"]) == 1
    assert len(data["session"]["user"]["licenses"][0]["activations"]) == 1
    assert (
        data["session"]["user"]["licenses"][0]["policy"]["id"] == test_license.policy.id
    )
    assert data["deactivated_versions"] == DEACTIVATED_VERSIONS


def test_sessions_login_incorrect_password(flask_app, test_user):
    with flask_app.test_client() as client:
        response = client.post(
            "/v1/sessions",
            data=pickle.dumps(
                {"username": test_user.username, "password": "wrong pass"}
            ),
        )
    assert response.status_code == 401


def test_sessions_verify(flask_app, test_session, test_license, test_activation):
    updated_at = test_session.updated_at
    with flask_app.test_client() as client:
        response = client.get("/v1/sessions/%s" % test_session.token)
    assert response.status_code == 200
    data = pickle.loads(response.data)
    assert data["session"]["user"]["username"] == test_session.user.username
    assert not "password" in data["session"]["user"]
    assert len(data["session"]["user"]["licenses"]) == 1
    assert len(data["session"]["user"]["licenses"][0]["activations"]) == 1
    assert (
        data["session"]["user"]["licenses"][0]["activations"][0]["machine"]["code"]
        == test_activation.machine.code
    )
    assert (
        data["session"]["user"]["licenses"][0]["policy"]["id"] == test_license.policy.id
    )
    assert data["deactivated_versions"] == DEACTIVATED_VERSIONS
    assert data["session"]["updated_at"] != updated_at


def test_sessions_verify_not_found(flask_app, test_session):
    with flask_app.test_client() as client:
        response = client.get("/v1/sessions/asdasd")
    assert response.status_code == 404


def test_sessions_delete_not_found(flask_app):
    with flask_app.test_client() as client:
        response = client.delete("/v1/sessions/asdasdas")
    assert response.status_code == 404


def test_sessions_expire(flask_app, test_session):
    test_session.updated_at = datetime.datetime.utcnow() - datetime.timedelta(
        days=SESSION_EXPIRATION_DAYS
    )
    db.session.commit()
    with flask_app.test_client() as client:
        response = client.get("/v1/sessions/%s" % test_session.token)
    assert response.status_code == 404
