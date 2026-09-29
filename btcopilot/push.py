"""A pointer to a coach message already in the thread: a web push to every
browser its person subscribed, or one email when none is left. Every push
carries one tag, so the phone shows one at a time and the newest replaces the
unread one.

A VAPID key pair for a new server: python -m btcopilot.push
"""

import base64
import json
import re

from cryptography.hazmat.primitives import serialization
from flask import current_app
from py_vapid import Vapid02
from pywebpush import WebPushException, webpush

from btcopilot import chips
from btcopilot.auth.emails import send_coach_message
from btcopilot.extensions import db
from btcopilot.models import Notification, NotificationChannel, PushSubscription

# The notification's tag in web/public/sw.js, and the push service's topic,
# which drops an undelivered push when a newer one arrives.
TAG = "coach"
# A phone that is off for a week still gets the newest one when it wakes.
TTL_S = 7 * 24 * 3600
# pywebpush waits forever unless told otherwise.
TIMEOUT_S = 10
# The push service's answer for a subscription the browser has let go.
GONE = (404, 410)
_SENTENCE = re.compile(r".+?[.?!](?=\s|$)")


def first_sentence(text: str) -> str:
    words = " ".join(chips.plain(text).split())
    found = _SENTENCE.match(words)
    return found.group(0) if found else words


def send(user, statement) -> Notification:
    """Not committed: the caller commits it with the message it points at."""
    words = first_sentence(statement.text)
    notification = Notification(
        user_id=user.id, statement_id=statement.id, channel=NotificationChannel.Push
    )
    db.session.add(notification)
    db.session.flush()
    payload = json.dumps({"id": notification.id, "body": words})
    subscriptions = PushSubscription.query.filter_by(user_id=user.id).all()
    if not [s for s in subscriptions if _push(s, payload)]:
        notification.channel = NotificationChannel.Email
        site = current_app.config["SITE_URL"].rstrip("/")
        send_coach_message(
            user.username, words, f"{site}/app/?notification={notification.id}"
        )
    return notification


def _push(subscription: PushSubscription, payload: str) -> bool:
    config = current_app.config
    try:
        webpush(
            subscription.info(),
            payload,
            vapid_private_key=config["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": config["VAPID_SUBJECT"]},
            ttl=TTL_S,
            headers={"Topic": TAG},
            timeout=TIMEOUT_S,
        )
    except WebPushException as e:
        if e.response is None or e.response.status_code not in GONE:
            raise
        db.session.delete(subscription)
        return False
    return True


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def keypair() -> tuple[str, str]:
    """Public then private, in the form the browser and pywebpush read."""
    vapid = Vapid02()
    vapid.generate_keys()
    public = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    private = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    return _b64(public), _b64(private)


if __name__ == "__main__":
    public, private = keypair()
    print(f"FLASK_VAPID_PUBLIC_KEY={public}")
    print(f"FLASK_VAPID_PRIVATE_KEY={private}")
