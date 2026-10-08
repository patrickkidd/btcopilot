"""The turn the person says what they are working on, the coach raises an
impression on it and puts it on the card on what to work on right then, resting
on the message that said it, so the card holds their own words from that turn
on (R-0707; Patrick, 2026-10-07: "sounds good to me").

Invented names only.
"""

from btcopilot.extensions import db
from btcopilot.models import Statement
from btcopilot.schema import CaseReportCard, EvidenceKind, QuestionKind, QuestionState
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.live.test_mostgoingon import sitting
from btcopilot.tests.live.test_structurefirst import EARLIER, EVENTS, kept

WORKING_ON = (
    "What I'm really working on is staying in the room when my mother criticizes me, "
    "instead of going quiet and leaving the way I always have."
)


def work_on(coach) -> list[dict]:
    db.session.expire_all()
    return [
        q
        for q in coach.user.free_diagram.get_diagram_data().questions
        if q["kind"] == QuestionKind.Impression
        and q.get("case_report_card") == CaseReportCard.WorkOn
    ]


@passes(2, of=3)
def test_saying_what_they_are_working_on_puts_an_impression_on_the_card_citing_the_message(coach):
    # R-0707, R-0709
    # Patrick, 2026-10-07: "sounds good to me" to filing the work_on impression the turn
    # the person says what they are working on, with their message as its evidence.
    coach.record(events=EVENTS)
    kept(coach, EARLIER)

    coach.say(WORKING_ON)

    said = Statement.query.filter(Statement.text == WORKING_ON).order_by(Statement.id.desc()).first()
    found = work_on(coach)
    assert len(found) >= 1, found
    raised = [q for q in found if q["state"] == QuestionState.Raised]
    assert raised, found
    assert any(
        one["kind"] == EvidenceKind.Statement and str(one["id"]) == str(said.id)
        for q in raised
        for one in q["evidence"]
    ), raised
