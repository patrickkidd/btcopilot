import base64
import json
import os

import http_ece
import pytest
import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pywebpush import WebPushException

from btcopilot import extensions, push
from btcopilot.auth.signin import SESSION_TOKEN
from btcopilot.auth.websession import WebSession
from btcopilot.extensions import db
from btcopilot.models import Notification, NotificationChannel, PushSubscription
from btcopilot.tests.conftest import csrf_token

SAID = "[[person:1|Your mother]] called on Sunday. What did she want?"
HOOK = "Your mother called on Sunday."


@pytest.fixture
def statement(discussion):
    said = discussion.statements[1]
    said.text = SAID
    db.session.commit()
    return said


@pytest.fixture
def service(monkeypatch):
    """The push service behind pywebpush: every post kept, and an endpoint
    named in `refuse` answered with that status instead of 201."""
    posts, refuse = [], {}

    def post(endpoint, data, headers, timeout):
        posts.append({"endpoint": endpoint, "data": data, "headers": headers})
        response = requests.Response()
        response.status_code = refuse.get(endpoint, 201)
        return response

    monkeypatch.setattr(requests, "post", post)
    return posts, refuse


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def subscribe(user, endpoint: str) -> tuple[ec.EllipticCurvePrivateKey, bytes]:
    """A browser's subscription, with the keys only the browser holds."""
    key = ec.generate_private_key(ec.SECP256R1())
    secret = os.urandom(16)
    public = key.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )
    db.session.add(
        PushSubscription(
            user_id=user.id, endpoint=endpoint, p256dh=b64(public), auth=b64(secret)
        )
    )
    db.session.commit()
    return key, secret


def test_every_browser_gets_the_first_sentence_under_one_tag(
    flask_app, test_user, statement, service
):
    # R-0055
    posts, _ = service
    browsers = {
        endpoint: subscribe(test_user, endpoint)
        for endpoint in ("https://push.example/phone", "https://push.example/laptop")
    }
    with extensions.mail.record_messages() as outbox:
        sent = push.send(test_user, statement)
    assert sent.channel == NotificationChannel.Push
    assert outbox == []
    assert [p["endpoint"] for p in posts] == list(browsers)
    for post in posts:
        key, secret = browsers[post["endpoint"]]
        body = http_ece.decrypt(
            post["data"], private_key=key, auth_secret=secret, version="aes128gcm"
        )
        assert json.loads(body) == {"id": sent.id, "body": HOOK}
        assert (post["headers"]["Topic"], post["headers"]["TTL"]) == (
            push.TAG,
            str(push.TTL_S),
        )
        assert (
            f"k={flask_app.config['VAPID_PUBLIC_KEY']}"
            in post["headers"]["Authorization"]
        )


@pytest.mark.parametrize("gone", [404, 410])
def test_an_expired_subscription_is_deleted_and_email_takes_over(
    test_user, statement, service, gone
):
    # R-0055
    posts, refuse = service
    subscribe(test_user, "https://push.example/old")
    refuse["https://push.example/old"] = gone
    with extensions.mail.record_messages() as outbox:
        sent = push.send(test_user, statement)
    assert len(posts) == 1
    assert PushSubscription.query.count() == 0
    assert (sent.channel, len(outbox)) == (NotificationChannel.Email, 1)


def test_a_refusal_that_is_not_expiry_fails(test_user, statement, service):
    # R-0055
    _, refuse = service
    subscribe(test_user, "https://push.example/phone")
    refuse["https://push.example/phone"] = 429
    with pytest.raises(WebPushException):
        push.send(test_user, statement)


def test_no_subscription_sends_one_email_with_a_link(
    flask_app, test_user, statement, service
):
    # R-0055
    posts, _ = service
    with extensions.mail.record_messages() as outbox:
        sent = push.send(test_user, statement)
    assert (posts, sent.channel) == ([], NotificationChannel.Email)
    [mail] = outbox
    assert mail.recipients == [test_user.username]
    link = f"{flask_app.config['SITE_URL']}/app/?notification={sent.id}"
    assert mail.body == f"{HOOK}\n\n{link}\n"


def test_a_browser_subscribes_once_per_endpoint(web, test_user):
    # R-0055
    # Signed in the way a browser is, so each request loads its user afresh.
    with web.session_transaction() as cookie:
        cookie[SESSION_TOKEN] = WebSession.start(test_user, 1, "").token
    assert (
        web.get("/app/push-subscriptions").json["key"]
        == web.application.config["VAPID_PUBLIC_KEY"]
    )
    body = {
        "endpoint": "https://push.example/phone",
        "keys": {"p256dh": "p1", "auth": "a1"},
    }
    for p256dh in ("p1", "p2"):
        body["keys"]["p256dh"] = p256dh
        response = web.post(
            "/app/push-subscriptions",
            json=body,
            headers={"X-CSRFToken": csrf_token(web)},
        )
        assert response.status_code == 201
    [row] = PushSubscription.query.all()
    assert (row.user_id, row.p256dh) == (test_user.id, "p2")


def test_opening_is_stamped_once_and_says_where_the_thread_opens(
    web, test_user, test_user_2, statement
):
    # R-0055
    sent = push.send(test_user, statement)
    path = f"/app/notifications/{sent.id}"
    headers = {"X-CSRFToken": csrf_token(web)}
    first = web.patch(path, json={"opened": True}, headers=headers)
    assert (first.json["statement_id"], first.json["discussion_id"]) == (
        statement.id,
        statement.discussion_id,
    )
    again = web.patch(path, json={"opened": True}, headers=headers)
    assert again.json["opened_at"] == first.json["opened_at"]

    theirs = push.send(test_user_2, statement)
    response = web.patch(
        f"/app/notifications/{theirs.id}", json={"opened": True}, headers=headers
    )
    assert response.status_code == 404
    assert db.session.get(Notification, theirs.id).opened_at is None
