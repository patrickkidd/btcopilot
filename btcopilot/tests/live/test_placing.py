"""Early on, three dated facts are given back once in one sentence, in order
of time, and not again on the next turn.

Invented names only.
"""

from freezegun import freeze_time

from btcopilot.extensions import db
from btcopilot.models import Author, Statement
from btcopilot.tests.live.checks import places_in_time
from btcopilot.tests.live.conftest import TODAY
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.live.test_waiting import MOST, said
from btcopilot.toolbox import ToolName, Toolbox

YEARS = [1988, 1990, 1991]
SISTER = {"id": 4, "name": "Ivy", "last_name": "Hale", "gender": "female", "parents": 10}
MARRIED = {"id": 40, "kind": "married", "person": 2, "spouse": 3, "dateTime": "1988-06-18", "dateCertainty": "certain"}
SISTER_BORN = {"id": 41, "kind": "birth", "person": 2, "spouse": 3, "child": 4, "dateTime": "1990-02-03", "dateCertainty": "certain"}
MOVED = {
    "id": 42, "kind": "noted", "person": 3, "description": "Moved the family to Tacoma",
    "dateTime": "1991-08-01", "dateCertainty": "approximate",
}
SAID = [
    "I keep feeling like I'm the one holding my family together and I'm worn out.",
    MOST,
    "Honestly it goes way back. Mom and Dad married in 1988, I was already three.",
    "So you were there before the wedding. Who else came along after that?",
    "My sister Ivy, in 1990. Mom was really sick for a while after she was born.",
    "How sick, and who looked after the two of you then?",
    "Mostly me, as much as a five year old can. Then in 1991 Dad moved us to Tacoma for work.",
    "A move on top of a sick mom and a new baby. How did Tacoma go?",
]
NEXT = "It was lonely. Mom stayed in bed a lot that first year."
AFTER = "Ivy and I shared a room, and I'd read to her at night."


def told(coach):
    """The thread so far, with the two or three times question already
    answered, so the reply is free for what this case looks at."""
    coach.record([SISTER], events=[MARRIED, SISTER_BORN, MOVED])
    talk = said(coach, SAID)
    answer = Statement.query.filter_by(discussion_id=talk.id, text=SAID[2]).one()
    toolbox = Toolbox(coach.user.free_diagram_id, "earlier", session_id=talk.id, author=Author.Coach)
    with freeze_time(TODAY):
        toolbox.call(ToolName.AddQuestion, {
            "text": MOST, "kind": "fact", "state": "resolved", "outcome": "answered",
            "fact": "most_going_on", "item_kind": "person", "item_id": 1, "answer": answer.id,
        })
    db.session.commit()


@passes(2, of=3)
def test_three_dated_facts_are_given_back_in_order_of_time_early(coach):
    # R-0784
    told(coach)
    reply = coach.say(NEXT)
    assert places_in_time(reply, YEARS), reply


@passes(2, of=3)
def test_the_placing_is_not_said_again_on_the_next_turn(coach):
    # R-0784
    told(coach)
    first = coach.say(NEXT)
    second = coach.say(AFTER)
    assert not (places_in_time(first, YEARS) and places_in_time(second, YEARS)), second
