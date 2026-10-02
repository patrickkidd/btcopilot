"""The coders' reminder: two days before the meeting, one to each coder who
has not submitted, sent by the coach's own scheduled run and outside its
budget. Patrick's switch for nudging the coders turns it off too (R-0258)."""

import datetime

from pywebpush import WebPushException

from btcopilot.admin.setting import nudges_on
from btcopilot.extensions import db
from btcopilot.review import notify
from btcopilot.review.adapter import NotificationKind, proactive, push
from btcopilot.review.models import Coding, Cut

REMIND_BEFORE = datetime.timedelta(days=2)


def run(now: datetime.datetime | None = None, dry_run: bool = False) -> list[dict]:
    """The one scheduled run: the coach's messages, then the coders'
    reminders, in the day only and never on a dry run."""
    now = now or datetime.datetime.utcnow()
    rows = proactive.run(now, dry_run)
    if proactive.daytime(now) and not dry_run:
        rows += remind(now, proactive.local(now).date())
    return rows


def remind(now: datetime.datetime, today: datetime.date) -> list[dict]:
    """Once per coder and cut, and not to someone told of the cut inside the
    last two days; each committed as it goes. A row per reminder, in the shape
    the proactive run prints."""
    if not nudges_on():
        return []
    rows = []
    cuts = Cut.query.filter(
        Cut.ratified_at.is_(None),
        Cut.meeting_date > today,
        Cut.meeting_date <= today + REMIND_BEFORE,
    ).order_by(Cut.id)
    for cut in cuts:
        for user in notify.coders(cut):
            if (
                _submitted(user, cut)
                or notify.sent(user, cut, NotificationKind.Reminder)
                or notify.sent(user, cut, NotificationKind.Task, now - REMIND_BEFORE)
                or notify.waiting(user, NotificationKind.Reminder, now)
            ):
                continue
            row = {
                "email": user.username,
                "trigger": NotificationKind.Reminder.value,
                "text": None,
                "refused": None,
                "reason": None,
            }
            try:
                with db.session.begin_nested():
                    row["text"] = notify.send(user, cut, NotificationKind.Reminder)
            except WebPushException as e:
                row["reason"] = push.failure(e)
            db.session.commit()
            rows.append(row)
    return rows


def _submitted(user, cut: Cut) -> bool:
    return (
        Coding.query.filter(
            Coding.cut_id == cut.id,
            Coding.user_id == user.id,
            Coding.done_at.isnot(None),
        ).first()
        is not None
    )
