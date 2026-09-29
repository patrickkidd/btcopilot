"""A pointer to a coach message already in the thread, or to a coding task on
the agenda: a web push to every browser its person subscribed, or one email
when none is left. The service worker shows each kind under its own tag, so the
phone shows one of each kind and the newest replaces that kind's unread one.

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
from btcopilot.auth.emails import send_notification
from btcopilot.extensions import db
from btcopilot.models import (
    Notification,
    NotificationChannel,
    NotificationKind,
    PushSubscription,
)

# A phone that is off for a week still gets it when it wakes.
TTL_S = 7 * 24 * 3600
# pywebpush waits forever unless told otherwise.
TIMEOUT_S = 10
# The push service's answer for a subscription the browser has let go.
GONE = (404, 410)
_SENTENCE = re.compile(r".+?[.?!](?=\s|$)")
SUBJECT = {
    NotificationKind.Coach: "The coach wrote to you",
    NotificationKind.Task: "A coding task is waiting for you",
    NotificationKind.Reminder: "Your coding task is due soon",
}


def first_sentence(text: str) -> str:
    words = " ".join(chips.plain(text).split())
    found = _SENTENCE.match(words)
    return found.group(0) if found else words


def send(user, statement) -> Notification:
    """Not committed: the caller commits it with the message it points at."""
    notification = Notification(
        user_id=user.id, kind=NotificationKind.Coach, statement_id=statement.id
    )
    return _deliver(user, notification, first_sentence(statement.text))


def send_task(user, cut, kind: NotificationKind, words: str) -> Notification:
    """Not committed: the caller commits it with what made it due."""
    notification = Notification(user_id=user.id, kind=kind, cut_id=cut.id)
    return _deliver(user, notification, words)


def failure(e: WebPushException) -> str:
    """A refusal from a push service, as one line for a run to print."""
    said = f"{e.response.status_code} {e.response.text}"
    return f"push failed: {' '.join(said.split())}"


def _deliver(user, notification: Notification, words: str) -> Notification:
    notification.channel = NotificationChannel.Push
    db.session.add(notification)
    db.session.flush()
    payload = json.dumps(
        {"id": notification.id, "kind": notification.kind.value, "body": words}
    )
    subscriptions = PushSubscription.query.filter_by(user_id=user.id).all()
    if not [s for s in subscriptions if _push(s, payload)]:
        notification.channel = NotificationChannel.Email
        site = current_app.config["SITE_URL"].rstrip("/")
        send_notification(
            user.username,
            SUBJECT[notification.kind],
            words,
            f"{site}/app/?notification={notification.id}",
        )
    return notification


def _push(subscription: PushSubscription, payload: str) -> bool:
    config = current_app.config
    try:
        # No Topic header to any service: Apple's refused "coach" with 400
        # BadWebPushTopic although it meets Apple's documented rule. The tag
        # in web/public/sw.js does the replacing.
        webpush(
            subscription.info(),
            payload,
            vapid_private_key=config["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": config["VAPID_SUBJECT"]},
            ttl=TTL_S,
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
