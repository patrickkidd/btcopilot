"""Who is coding what is on the table, and how far each of them has got.

The state is read across every cut of one meeting, because that is what the
table screen shows: one line per coder, not one line per cut (R-0258).
"""

import enum

from flask import jsonify, request

from btcopilot import ROLE_ADMIN, ROLE_AUDITOR
from btcopilot.review.adapter import User
from btcopilot.review.models import Coding, Cut
from btcopilot.review.routes import bp, coder, voted
from btcopilot.review.routes.cuts import table_cuts


class CoderState(str, enum.Enum):
    NotStarted = "not started"
    Coding = "coding"
    Done = "done"
    Voted = "voted"


#: The state that closes a coder out of the meeting's work.
CLOSED = CoderState.Voted


def roster(cuts: list[Cut]) -> list[User]:
    """Everyone who codes: the auditors, Patrick, who codes too, and anyone
    who has already started on what is on the table."""
    started = {
        coding.user_id for cut in cuts for coding in cut.codings
    }
    return [
        user
        for user in User.query.order_by(User.id).all()
        if user.has_role(ROLE_AUDITOR)
        or user.has_role(ROLE_ADMIN)
        or user.id in started
    ]


def initials(user) -> str:
    """Initials where a coder has a name, and the name part of their address
    otherwise: a whole email address does not fit a phone's line."""
    letters = [part[0] for part in (user.first_name, user.last_name) if part]
    if letters:
        return ".".join(letters) + "."
    return user.username.split("@")[0]


def state_of(user, cuts: list[Cut]) -> CoderState:
    codings = [
        Coding.query.filter_by(cut_id=cut.id, user_id=user.id).first() for cut in cuts
    ]
    if not cuts or all(one is None for one in codings):
        return CoderState.NotStarted
    if any(one is None or one.done_at is None for one in codings):
        return CoderState.Coding
    if all(voted(cut, user) for cut in cuts):
        return CoderState.Voted
    return CoderState.Done


@bp.route("/coders")
def coder_index():
    """One line per coder for the meeting asked for, or for everything on the
    table when no date is given."""
    me = coder()
    cuts = table_cuts(request.args.get("meeting_date"))
    rows = [(user, state_of(user, cuts)) for user in roster(cuts)]
    return jsonify(
        [
            {
                "user_id": user.id,
                "name": "you" if user.id == me.id else initials(user),
                "state": state.value,
                "closed_out": state is CLOSED,
            }
            for user, state in rows
        ]
    )
