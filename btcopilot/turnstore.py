"""A coach turn's events, kept in the database once the turn ends.

The live log in Redis is for following a turn while it runs and expires within
the hour. What is kept here is what the thread shows for every turn ever run,
and what a failed turn picks up from.
"""

from sqlalchemy import func

from btcopilot.extensions import db
from btcopilot.models import TurnEvent
from btcopilot.turnlog import TurnEventKind


def save(turn_id: str, discussion_id: int, kept: list[dict]) -> None:
    """Append after whatever the turn already kept, which is how a resumed turn
    continues the one that failed."""
    last = (
        db.session.query(func.max(TurnEvent.seq))
        .filter(TurnEvent.turn_id == turn_id)
        .scalar()
        or 0
    )
    for seq, event in enumerate(kept, start=last + 1):
        db.session.add(
            TurnEvent(
                turn_id=turn_id,
                discussion_id=discussion_id,
                seq=seq,
                kind=TurnEventKind(event["type"]).value,
                payload=event,
            )
        )


def kept(turn_ids: set[str]) -> dict[str, list[dict]]:
    """Each turn's events in order."""
    if not turn_ids:
        return {}
    found: dict[str, list[dict]] = {}
    for row in (
        TurnEvent.query.filter(TurnEvent.turn_id.in_(turn_ids))
        .order_by(TurnEvent.turn_id, TurnEvent.seq)
        .all()
    ):
        found.setdefault(row.turn_id, []).append(row.payload)
    return found


def failed(events: list[dict]) -> bool:
    """A turn whose last word is that it did not finish. A turn resumed after
    failing ends in done, so it is not."""
    ends = [
        e["type"]
        for e in events
        if e["type"] in (TurnEventKind.Done.value, TurnEventKind.Failed.value)
    ]
    return bool(ends) and ends[-1] == TurnEventKind.Failed.value
