"""What tells a coder about a cut on the agenda, through the coach's send path
but outside its budget: one notification when Patrick gives the cut its
meeting date; reminders.py sends the one before the meeting. A notification
waits while an earlier one of its own kind is unopened and less than a week
old, so a meeting with three cuts sends one."""

import datetime
import logging

from pywebpush import WebPushException

import btcopilot
from btcopilot.extensions import db
from btcopilot.review.adapter import (
    Notification,
    NotificationKind,
    User,
    push,
)
from btcopilot.review.models import Cut

_log = logging.getLogger(__name__)

# Unopened this long, a notification stops holding back the next of its kind.
WAITS_FOR = datetime.timedelta(days=7)
WORDS = {
    NotificationKind.Task: (
        "A coding task is waiting for you, due before {day}. Open the app to start."
    ),
    NotificationKind.Reminder: (
        "Your coding task is due before {day} and is not submitted yet. "
        "Open the app to finish it."
    ),
}


def told(cut: Cut, now: datetime.datetime):
    """Not committed: the caller commits it with the date. A coder whose push
    service refuses is left to the reminder, and the log says so."""
    for user in coders(cut):
        if sent(user, cut, NotificationKind.Task) or waiting(
            user, NotificationKind.Task, now
        ):
            continue
        try:
            with db.session.begin_nested():
                send(user, cut, NotificationKind.Task)
        except WebPushException as e:
            _log.error(f"no task notice reached {user.username}: {push.failure(e)}")


def send(user, cut: Cut, kind: NotificationKind) -> str:
    words = WORDS[kind].format(day=cut.meeting_date.strftime("%a, %b %-d"))
    push.send_task(user, cut, kind, words)
    return words


def coders(cut: Cut) -> list[User]:
    """Everyone with the auditor role but whoever put the cut on the agenda."""
    return [
        user
        for user in User.query.order_by(User.id)
        if user.has_role(btcopilot.ROLE_AUDITOR) and user.id != cut.user_id
    ]


def sent(user, cut: Cut, kind: NotificationKind, since=datetime.datetime.min) -> bool:
    return (
        Notification.query.filter(
            Notification.user_id == user.id,
            Notification.cut_id == cut.id,
            Notification.kind == kind,
            Notification.created_at > since,
        ).first()
        is not None
    )


def waiting(user, kind: NotificationKind, now: datetime.datetime) -> bool:
    return (
        Notification.query.filter(
            Notification.user_id == user.id,
            Notification.kind == kind,
            Notification.opened_at.is_(None),
            Notification.created_at > now - WAITS_FOR,
        ).first()
        is not None
    )
