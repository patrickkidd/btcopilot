"""The coach's replay of a cut, run in the background as a coding like any
other (R-0242): it lands in a codings row with its model and prompt version
and its Done already set, and it is hidden from a coder the same way.
"""

import logging

from btcopilot.extensions import db
from btcopilot.review import adapter, snapshot
from btcopilot.review.models import Coding, Cut

_log = logging.getLogger(__name__)


def replay_cut(
    cut_id: int, user_id: int, model: str | None = None, prompt_version=None
) -> int:
    cut = db.session.get(Cut, cut_id)
    if cut is None:
        raise ValueError(f"no cut {cut_id}")
    coach = db.session.get(adapter.User, user_id)
    if coach is None:
        raise ValueError(f"no user {user_id} for the coach's coding")

    discussion = db.session.get(adapter.Discussion, cut.discussion_id)
    diagram = adapter.coding_diagram(coach, f"coach coding of cut {cut.id}")
    adapter.grant_write(diagram, coach)
    coding = Coding(
        cut_id=cut.id,
        user_id=coach.id,
        diagram_id=diagram.id,
        agent={"model": model, "prompt_version": prompt_version},
    )
    db.session.add(coding)
    db.session.commit()

    statements = adapter.statements_between(
        cut.discussion_id, cut.start_statement_id, cut.end_statement_id
    )
    adapter.replay_into(
        diagram, discussion, statements, model=adapter.coach_model(model)
    )

    coding.done_at = adapter.utcnow()
    if cut.vote_opened_at is not None:
        snapshot.recompute(cut)
    db.session.commit()
    _log.info(f"The coach coded cut {cut.id} as coding {coding.id}")
    return coding.id
