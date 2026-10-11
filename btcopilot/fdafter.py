"""What follows once a desktop file is written into a diagram: its clusters
regrouped, the coach's first message after an import, and the import record
mailed, the same for the admin command and the chat [Oracle: R-0878, R-0873].

The clusters are regrouped the way a coach turn that moves an event regroups
them. The case report and coverage need nothing here: the report is out of date
by a rule on the change log the import's write already satisfies (R-0825), and
coverage is worked out from the diagram each time it is read.
"""

import enum

from btcopilot import clusters, fdledger, fdnotice
from btcopilot.extensions import db
from btcopilot.models import ProactiveMessage, Trigger


class Step(enum.StrEnum):
    Regroup = "regroup"
    Notice = "notice"
    Mail = "mail"


def catch_up(diagram_id: int, *, turn_id: str, user_id: int) -> clusters.Regroup | None:
    """Regroup under the import's own turn, so one undo of the import takes the
    grouping off with it; None when the events left nothing to regroup."""
    regrouped = clusters.sync(diagram_id, turn_id=turn_id, user_id=user_id)
    db.session.commit()
    return regrouped


def land(
    diagram_id: int,
    user_id: int,
    summary: fdnotice.Summary,
    mail: dict,
    done: set[Step] | None = None,
) -> ProactiveMessage:
    """The steps after the write, in order; `mail` is what fdledger.send takes.
    Each finished step goes into `done` and one already there is skipped, so
    trying again after a step failed runs only the steps left. The coach's
    message comes last, so the person's own message is still the thread's
    last while any step is left to try again. That message is returned."""
    done = set() if done is None else done
    if Step.Regroup not in done:
        catch_up(diagram_id, turn_id=summary.turn_id, user_id=user_id)
        done.add(Step.Regroup)
    if Step.Mail not in done:
        fdledger.send(**mail)
        done.add(Step.Mail)
    if Step.Notice not in done:
        fdnotice.after_import(diagram_id, user_id, summary)
        done.add(Step.Notice)
    return ProactiveMessage.query.filter_by(
        diagram_id=diagram_id, trigger=Trigger.Import, key=summary.turn_id
    ).one()
