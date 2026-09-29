"""Bugs and feedback, from the app's page, its service worker and the server
itself, all written here [Oracle: R-0056]."""

import threading
import time
from collections import deque

from flask import current_app, request

from btcopilot.extensions import db
from btcopilot.models import Diagram, Report, ReportKind, ReportSource, ReportStatus, User

# At most this many reports an hour from one sender, so a page caught in a
# loop, or a stranger's script, cannot fill the table.
LIMIT = 20
HOUR_S = 3600
_lock = threading.Lock()

# What a page or the worker may send of each kind; the server writes its own.
COMMON = {"kind", "status", "release", "address", "turn_id", "statement_id"}
FIELDS = {
    ReportKind.Feedback: {"words"},
    ReportKind.Bug: {"source", "error", "frames", "request_id", "count", "words"},
}
SENDERS = (ReportSource.Page, ReportSource.Worker)


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
    """A report as the page or the worker sent it, checked and written."""
    kind = ReportKind(body["kind"])
    unknown = set(body) - COMMON - FIELDS[kind]
    if unknown:
        raise ValueError(f"A {kind} does not carry {', '.join(sorted(unknown))}")
    status = ReportStatus(body["status"])
    if kind is ReportKind.Feedback and (status is ReportStatus.Sent) != bool(body.get("words")):
        raise ValueError("Feedback sent carries the person's words, and declined none")
    source = None
    if kind is ReportKind.Bug:
        source = ReportSource(body["source"])
        if source not in SENDERS:
            raise ValueError("Only the server reports as the server")
        if not body.get("error") and not body.get("words"):
            raise ValueError("A bug carries what broke or the person's words")
    return write(
        Report(
            kind=kind,
            status=status,
            user_id=user.id if user else None,
            diagram_id=diagram.id if diagram else None,
            turn_id=body.get("turn_id"),
            statement_id=body.get("statement_id"),
            release=body["release"],
            address=body.get("address"),
            count=body.get("count", 1),
            source=source,
            error=body.get("error"),
            frames=body.get("frames"),
            request_id=body.get("request_id"),
            words=body.get("words"),
        )
    )


def write(row: Report) -> Report:
    db.session.add(row)
    db.session.commit()
    return row
