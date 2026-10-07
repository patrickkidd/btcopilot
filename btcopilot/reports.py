"""Bugs and feedback the coach offered from the conversation and the person
answered on the page, all written here [Oracle: R-0056]; each one sent is
emailed to Patrick [Oracle: R-0824]. An error in the code is never a row: the
page's and the server's errors go to Grafana."""

import threading
import time
from collections import deque

from flask import current_app, request

import btcopilot
from btcopilot.auth import emails
from btcopilot.extensions import db
from btcopilot.models import Diagram, Report, ReportKind, ReportStatus, User

# At most this many reports an hour from one sender, so a page caught in a
# loop, or a stranger's script, cannot fill the table.
LIMIT = 20
HOUR_S = 3600
_lock = threading.Lock()

# What the page may send.
FIELDS = {"kind", "status", "release", "address", "turn_id", "statement_id", "words"}


def sender(user: User | None) -> str:
    """Who a report is counted against: the person, or for a signed-out page
    the address it came from, which the box's proxy passes on."""
    if user:
        return f"user {user.id}"
    return request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()


def allowed(who: str) -> bool:
    sent: dict[str, deque] = current_app.extensions["reports"]
    now = time.monotonic()
    with _lock:
        times = sent.setdefault(who, deque())
        while times and now - times[0] > HOUR_S:
            times.popleft()
        if len(times) >= LIMIT:
            return False
        times.append(now)
        return True


def take(body: dict, user: User | None, diagram: Diagram | None) -> Report:
    """A report as the page sent it, checked and written."""
    unknown = set(body) - FIELDS
    if unknown:
        raise ValueError(f"A report does not carry {', '.join(sorted(unknown))}")
    kind = ReportKind(body["kind"])
    status = ReportStatus(body["status"])
    # what the person turned down keeps only where it was
    if (status is ReportStatus.Sent) != bool(body.get("words")):
        raise ValueError("A report sent carries the words the coach offered; one declined, none")
    if btcopilot.BETA and kind is ReportKind.Bug and status is ReportStatus.Declined:
        raise ValueError("A bug cannot be turned down during the beta")
    row = Report(
        kind=kind,
        status=status,
        user_id=user.id if user else None,
        diagram_id=diagram.id if diagram else None,
        turn_id=body.get("turn_id"),
        statement_id=body.get("statement_id"),
        release=body["release"],
        address=body.get("address"),
        words=body.get("words"),
    )
    db.session.add(row)
    db.session.commit()
    if status is ReportStatus.Sent:
        emails.send_report(row, sender(user))
    return row
