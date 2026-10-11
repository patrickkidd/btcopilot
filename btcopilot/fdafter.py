"""What a diagram catches up on once a desktop file is written into it.

Its clusters are regrouped the way a coach turn that moves an event regroups
them. The case report and coverage need nothing here: the report is out of date
by a rule on the change log the import's write already satisfies (R-0825), and
coverage is worked out from the diagram each time it is read.
"""

from btcopilot import clusters
from btcopilot.extensions import db


def catch_up(diagram_id: int, *, turn_id: str, user_id: int) -> clusters.Regroup | None:
    """Regroup under the import's own turn, so one undo of the import takes the
    grouping off with it; None when the events left nothing to regroup."""
    regrouped = clusters.sync(diagram_id, turn_id=turn_id, user_id=user_id)
    db.session.commit()
    return regrouped
