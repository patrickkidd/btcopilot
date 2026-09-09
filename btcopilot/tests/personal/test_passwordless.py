import datetime
import email.utils
import re

import flask
import flask.testing
import pytest
from flask_wtf.csrf import generate_csrf

from btcopilot import extensions
from btcopilot.auth.invitation import Invitation
from btcopilot.auth.logincode import LoginCode
from btcopilot.auth.signin import SESSION_TOKEN
from btcopilot.auth.websession import WebSession
from btcopilot.extensions import db
from btcopilot.pro.models import User

INVITED = "invited+unittest@gmail.com"


CSRF_SEED = "unittest-csrf-seed"


@pytest.fixture
def browser(flask_app):
    flask_app.test_client_class = flask.testing.FlaskClient
    with flask_app.test_client(use_cookies=True) as client:
        with client.session_transaction() as cookie:
            cookie["csrf_token"] = CSRF_SEED
        client.app = flask_app
        yield client


def token(browser) -> str:
    with browser.session_transaction() as cookie:
        cookie["csrf_token"] = CSRF_SEED
    with browser.app.test_request_context():
        flask.session["csrf_token"] = CSRF_SEED
        return generate_csrf()


def request_code(browser, email: str):
    with extensions.mail.record_messages() as outbox:
        response = browser.post(
            "/personal/login", data={"csrf_token": token(browser), "email": email}
        )
    return response, outbox


def test_invite_creates_user_and_signs_in(flask_app, browser):
    invitation = Invitation.issue(INVITED, flask_app.config["INVITATION_DAYS"])
    response = browser.get(f"/personal/invite/{invitation.token}")
    assert response.status_code == 302
    assert response.headers["Location"] == flask_app.config["CHAT_HOME"]

    assert User.query.filter_by(username=INVITED).first() is not None
    assert browser.get("/personal/me").get_json()["user"]["email"] == INVITED


def test_coming_back_to_the_site_root_lands_in_the_chat(flask_app, browser):
    invitation = Invitation.issue(INVITED, flask_app.config["INVITATION_DAYS"])
    browser.get(f"/personal/invite/{invitation.token}")

    response = browser.get("/")
    assert response.headers["Location"] == flask_app.config["CHAT_HOME"]


def test_signing_in_stamps_the_session_the_training_app_ages(flask_app, browser):
    invitation = Invitation.issue(INVITED, flask_app.config["INVITATION_DAYS"])
    browser.get(f"/personal/invite/{invitation.token}")
    with browser.session_transaction() as cookie:
        assert cookie["logged_in_at"]


def test_fixture_token_signs_in(flask_app, browser):
    """The visual suite mints its links through the fixture installer, so the
    installer's own token has to open a session, not the sign-in page."""
    printed = flask_app.test_cli_runner().invoke(args=["personal", "fixtures", "empty"])
    assert printed.exit_code == 0, printed.output
    minted = printed.output.strip().split()[-1]

    response = browser.get(f"/personal/invite/{minted}")
    assert response.status_code == 302
    assert browser.get("/personal/me").get_json()["user"] is not None


def test_chat_cookie_outlives_the_training_timeout(flask_app, browser):
    """The training app pins the cookie to eight hours; a chat sign-in must
    still come back months later."""
    invitation = Invitation.issue(INVITED, flask_app.config["INVITATION_DAYS"])
    response = browser.get(f"/personal/invite/{invitation.token}")
    expires = email.utils.parsedate_to_datetime(
        re.search(r"[Ee]xpires=([^;]+)", response.headers["Set-Cookie"]).group(1)
    )
    days = (expires - datetime.datetime.now(datetime.timezone.utc)).days
    assert days > 30


def test_invite_is_single_use(flask_app, browser):
    invitation = Invitation.issue(INVITED, flask_app.config["INVITATION_DAYS"])
    browser.get(f"/personal/invite/{invitation.token}")
    assert browser.get(f"/personal/invite/{invitation.token}").status_code == 400


def test_code_signs_in_an_existing_user(flask_app, browser, test_user):
    response, outbox = request_code(browser, test_user.username)
    assert response.status_code == 200
    code = re.search(r"\b(\d{6})\b", outbox[0].body).group(1)

    response = browser.post(
        "/personal/login/verify",
        data={"csrf_token": token(browser), "email": test_user.username, "code": code},
    )
    assert response.status_code == 302
    assert browser.get("/personal/me").get_json()["user"]["email"] == test_user.username


def test_expired_code_is_rejected(flask_app, browser, test_user):
    _, outbox = request_code(browser, test_user.username)
    code = re.search(r"\b(\d{6})\b", outbox[0].body).group(1)
    issued = LoginCode.query.filter_by(email=test_user.username).one()
    issued.expires_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
    db.session.commit()

    response = browser.post(
        "/personal/login/verify",
        data={"csrf_token": token(browser), "email": test_user.username, "code": code},
    )
    assert response.status_code == 401
    assert browser.get("/personal/me").status_code == 401


def test_used_code_is_rejected(flask_app, browser, test_user):
    _, outbox = request_code(browser, test_user.username)
    code = re.search(r"\b(\d{6})\b", outbox[0].body).group(1)
    form = {"csrf_token": token(browser), "email": test_user.username, "code": code}
    assert browser.post("/personal/login/verify", data=form).status_code == 302

    browser.post("/personal/logout", data={"csrf_token": token(browser)})
    response = browser.post(
        "/personal/login/verify",
        data={"csrf_token": token(browser), "email": test_user.username, "code": code},
    )
    assert response.status_code == 401


def test_unknown_email_gets_no_code(flask_app, browser):
    response, outbox = request_code(browser, "nobody+unittest@gmail.com")
    assert response.status_code == 200
    assert outbox == []


def test_code_requests_are_rate_limited(flask_app, browser, test_user):
    for _ in range(flask_app.config["LOGIN_CODES_PER_HOUR"]):
        assert request_code(browser, test_user.username)[0].status_code == 200
    assert request_code(browser, test_user.username)[0].status_code == 429


def test_revoking_the_session_logs_out(flask_app, browser):
    invitation = Invitation.issue(INVITED, flask_app.config["INVITATION_DAYS"])
    browser.get(f"/personal/invite/{invitation.token}")
    listed = browser.get("/personal/signins").get_json()["sessions"]
    assert len(listed) == 1 and listed[0]["current"] is True

    response = browser.post(
        f"/personal/signins/{listed[0]['id']}/revoke", data={"csrf_token": token(browser)}
    )
    assert response.get_json()["revoked"] is True
    assert browser.get("/personal/me").status_code == 401


def test_logout_revokes_the_session_record(flask_app, browser):
    invitation = Invitation.issue(INVITED, flask_app.config["INVITATION_DAYS"])
    browser.get(f"/personal/invite/{invitation.token}")
    with browser.session_transaction() as cookie:
        web_session_token = cookie[SESSION_TOKEN]

    browser.post("/personal/logout", data={"csrf_token": token(browser)})
    assert WebSession.query.filter_by(token=web_session_token).one().live() is False
    assert browser.get("/personal/me").status_code == 401
