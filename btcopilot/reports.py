"""Bugs and feedback, from the app's page, its service worker and the server
itself, all written here [Oracle: R-0056]."""

import datetime
import logging
import os
import threading
import time
import traceback
from collections import deque

from flask import current_app, g, request
from sqlalchemy.exc import SQLAlchemyError

import btcopilot
from btcopilot import auth
from btcopilot.extensions import db
from btcopilot.models import Diagram, Report, ReportKind, ReportSource, ReportStatus, User
from btcopilot.tuning import reason

_log = logging.getLogger(__name__)

# Where the server's own code lives, and what its frames are named from.
PACKAGE = os.path.dirname(btcopilot.__file__)

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
    """A report as the page or the worker sent it, checked and written. A
    request the server broke on is already its own row, which the page's
    report of it is."""
    if body.get("request_id"):
        found = Report.query.filter_by(request_id=body["request_id"]).first()
        if found:
            return found
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


def signature(error: str, frames: list[str] | None) -> str:
    """What the same fault is counted by: its name and message with the ids
    and quoted names taken out, as the tuning queue groups, and its first
    frame in the app's own code."""
    return " at ".join([reason(error), *(frames or [])[:1]])


def write(row: Report) -> Report:
    """The same fault for the same person in the same release on the same
    day adds to the count of that day's row instead of making another."""
    if row.kind is ReportKind.Bug and row.error:
        row.signature = signature(row.error, row.frames)
        today = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        same = Report.query.filter(
            Report.kind == ReportKind.Bug,
            Report.release == row.release,
            Report.signature == row.signature,
            Report.user_id == row.user_id,
            Report.created_at >= today,
        ).first()
        if same:
            same.count += row.count
            db.session.commit()
            return same
    db.session.add(row)
    db.session.commit()
    return row


def frames(error: BaseException) -> list[str]:
    """The traceback's frames in the server's own code, innermost first, the
    way a page's stack lists them."""
    return [
        f"{os.path.relpath(frame.filename, os.path.dirname(PACKAGE))}:{frame.lineno} in {frame.name}"
        for frame in reversed(traceback.extract_tb(error.__traceback__))
        if frame.filename.startswith(PACKAGE + os.sep)
    ]


def crashed(error: Exception) -> None:
    """The server broke on a request: its own row, in a transaction of its own
    after what the request had begun is rolled back. A row that cannot be
    written is logged, and the request still answers 500."""
    db.session.rollback()
    try:
        user = auth.current_user()
        write(
            Report(
                kind=ReportKind.Bug,
                status=ReportStatus.Sent,
                source=ReportSource.Server,
                user_id=user.id if user else None,
                release=btcopilot.__version__,
                address=request.path,
                count=1,
                error=f"{type(error).__name__}: {error}",
                frames=frames(error),
                request_id=g.request_id,
            )
        )
    except SQLAlchemyError:
        db.session.rollback()
        _log.exception("The server's own report of that error could not be written")
