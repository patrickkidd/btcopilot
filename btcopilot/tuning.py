"""The short queue of what shows the coach or the app needing tuning, for
Patrick to accept or reject [Oracle: R-0517].

A group is a kind of observation and its reason with the ids, dates and quoted
values taken out, so the same fault on different records and turns counts as
one. The dashboard's queue panel groups the same way in SQL: the key is the
first 8 hex digits of the md5 of "kind:reason".
"""

import hashlib
import re

from btcopilot.extensions import db
from btcopilot.models import (
    Diagram,
    Observation,
    ObservationKind,
    ObservationReject,
    User,
)

QUEUE = 10
# How a message the coach wrote first fared: measurements, not findings to rule on.
MEASURES = (
    ObservationKind.ProactiveSent,
    ObservationKind.ProactiveOpened,
    ObservationKind.ProactiveReplied,
    ObservationKind.ProactiveReturned,
)
TEST_ACCOUNTS = "claude-test%"
QUOTED = re.compile(r"(?<!\w)'[^']*'(?!\w)")
IDS = re.compile(r"\b[0-9a-f]{8,}\b|\d+")


def reason(text: str) -> str:
    return " ".join(IDS.sub("#", QUOTED.sub("'…'", text)).split())


def key(kind: str, said: str) -> str:
    return hashlib.md5(f"{kind}:{said}".encode()).hexdigest()[:8]


def groups() -> dict[str, dict]:
    """Every group from accounts that are not test accounts, rejected or not."""
    found: dict[str, dict] = {}
    rows = (
        Observation.query.join(Diagram, Diagram.id == Observation.diagram_id)
        .join(User, User.id == Diagram.user_id)
        .filter(User.username.notlike(TEST_ACCOUNTS), Observation.kind.notin_(MEASURES))
        .order_by(Observation.created_at)
    )
    for row in rows:
        said = row.detail.get("reason", "")
        group = found.setdefault(
            key(row.kind.value, said),
            {
                "key": key(row.kind.value, said),
                "kind": row.kind.value,
                "reason": said,
                "count": 0,
                "first_seen": row.created_at,
            },
        )
        group["count"] += 1
        group["last_seen"] = row.created_at
        group["example_turn"] = row.turn_id
    return found


def queue(limit: int = QUEUE) -> list[dict]:
    rejected = {r.key for r in ObservationReject.query}
    kept = [g for k, g in groups().items() if k not in rejected]
    return sorted(kept, key=lambda g: -g["count"])[:limit]


def reject(group_key: str) -> ObservationReject:
    group = groups().get(group_key)
    if group is None:
        raise KeyError(f"no group with key {group_key}")
    row = ObservationReject(key=group_key, kind=group["kind"], reason=group["reason"])
    db.session.add(row)
    db.session.commit()
    return row
