"""What every coder saw, and the agreement figures.

The ballot's rows are the pairings a model call builds (pairing.py, R-0961).
Once the vote opens the rows are never maintained: they are the event clock
(R-0275).

Agreement is recomputed from the rows whenever a coding finishes and again
after ratification (R-0242). Both figures are kept, because the result screen
shows the first pass and the ratified record side by side.

The coach's replay is snapshotted like any other coding so the result screen
can say where it differed from the room, but it is never a voter: it does not
make an item disputed and it is not counted in the agreement figures (R-0242).
"""

import enum

from btcopilot.extensions import db
from btcopilot.review.models import Coding, Item, ReviewStatus


class AgreementPhase(enum.StrEnum):
    FirstPass = "first_pass"
    Ratified = "ratified"


def done_codings(cut) -> list[Coding]:
    found = [c for c in cut.codings if c.done_at is not None]
    return sorted(found, key=lambda c: (c.done_at, c.id))


def voters(cut) -> list[Coding]:
    """The people who coded: the coach's replay is a coding but never a voter."""
    return [c for c in done_codings(cut) if c.agent is None]


def coach_coding(cut) -> Coding | None:
    return next((c for c in done_codings(cut) if c.agent is not None), None)


def agreement(cut) -> dict:
    """The figures the cut carries: how many items every coder read the same
    way, out of how many, over how many people coded it."""
    rows = Item.query.filter_by(cut_id=cut.id).all()
    counts = {status.value: 0 for status in ReviewStatus}
    for row in rows:
        counts[row.status.value] += 1
    total = len(rows)
    agreed = counts[ReviewStatus.Agreed.value] + counts[ReviewStatus.Decided.value]
    return {
        "codings": len(voters(cut)),
        "items": total,
        "by_status": counts,
        "percent": round(100.0 * agreed / total, 1) if total else None,
    }


def recompute(cut, phase: AgreementPhase = AgreementPhase.FirstPass) -> dict:
    """Both figures are kept: the first pass is what the coders reached on
    their own, the ratified one is what the room reached together."""
    figures = dict(cut.agreement or {})
    figures[phase.value] = agreement(cut)
    cut.agreement = figures
    db.session.flush()
    return figures
