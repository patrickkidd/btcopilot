from datetime import datetime, timedelta

from btcopilot.extensions import db
from btcopilot.app import create_app
from btcopilot.pro.models import Session
from btcopilot.pro import tasks, SESSION_EXPIRATION_DAYS, DEACTIVATED_VERSIONS


# @pytest.fixture(autouse=True, scope="module", params=["1.4.4", None])
# def pre_1_5_0_encrypted_client(request):
#     if request.param:
#         with mock.patch.object(version, "VERSION", request.param):
#             yield request.param
#     else:
#         yield request.param


def test_config():
    assert not create_app(
        config={
            "ENV": "unittest",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    ).testing
    assert create_app(
        config={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    ).testing


def test_hello(flask_app):
    with flask_app.test_client() as client:
        response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.data == b"Hello, World!"


def test_404(flask_app):
    with flask_app.test_client() as client:
        response = client.get("/should_not_exist")
    assert response.status_code == 404


def test_deactivated_versions(flask_app):
    with flask_app.test_client() as client:
        response = client.get("/v1/deactivated_versions")
    assert response.data.decode("utf-8") == "\n".join(pro.DEACTIVATED_VERSIONS)


def test_expire_stale_sessions(flask_app, test_session):
    session = Session.query.get(test_session.id)
    session.updated_at = datetime.utcnow() - timedelta(
        days=SESSION_EXPIRATION_DAYS + 10
    )
    db.session.commit()
    tasks._expire_stale_sessions()
    assert Session.query.get(test_session.id) is None
