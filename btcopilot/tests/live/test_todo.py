"""What the person says they will find out themselves is kept as their todo,
in their words; when they come back a day later with nothing, it is offered
as one of two doors, and when they come back with something else, that is
followed instead; when they come back with the answer, it is recorded and the
todo closed.

Invented names only.
"""

import re

from btcopilot.extensions import db
from btcopilot.models import Statement
from btcopilot.schema import QuestionKind, QuestionOutcome, QuestionState
from btcopilot.tests.live.checks import leads_with_todo, offers_todo, questions as asked
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.live.test_mostgoingon import back, sitting
from btcopilot.toolbox import ToolName, Toolbox

TODO = "ask my mom when they moved"
# An earlier sitting where the person could not say when the family moved.
EARLIER = [
    "We moved from Ohio to Oregon when I was little, and everything changed after that.",
    "When did your family move to Oregon?",
    f"I'm not sure, I was too young. I'll {TODO}.",
    "That would help. What do you remember of the first year there?",
]


def todos(coach) -> list[dict]:
    db.session.expire_all()
    return [
        q
        for q in coach.user.free_diagram.get_diagram_data().questions
        if q["kind"] == QuestionKind.Todo
    ]


def kept(coach) -> None:
    """The earlier sitting, its todo kept as the coach keeps one, a day ago."""
    sitting(coach, EARLIER)
    said = (
        Statement.query.filter(Statement.text == EARLIER[2])
        .order_by(Statement.id.desc())
        .first()
    )
    diagram = coach.user.free_diagram
    Toolbox(
        diagram.id,
        "t0",
        user_id=coach.user.id,
        session_id=said.discussion_id,
        said=said,
    ).call(ToolName.AddQuestion, {"text": TODO, "kind": "todo", "state": "held"})
    db.session.commit()
    back(1)


@passes(3, of=3)
def test_a_todo_the_person_says_is_kept_held_in_their_words(coach):
    # R-0803
    coach.record()
    sitting(coach, EARLIER[:2])
    coach.say(EARLIER[2])

    found = todos(coach)
    assert len(found) == 1, found
    words = found[0]["text"].lower()
    assert found[0]["state"] == QuestionState.Held, found
    assert "mom" in words and "mov" in words, found


@passes(3, of=3)
def test_the_person_back_a_day_later_with_nothing_is_offered_their_todo(coach):
    # R-0815, R-0803
    coach.record()
    kept(coach)

    reply = coach.say("Hi, I'm back")
    assert offers_todo(reply, TODO), reply


@passes(3, of=3)
def test_the_person_back_a_day_later_with_news_is_followed_not_led_to_the_todo(coach):
    # R-0815, R-0803
    coach.record()
    kept(coach)

    reply = coach.say("My dad called last night, out of the blue.")
    assert not leads_with_todo(reply, TODO), reply
    assert re.search(r"\b(call|dad|father|he)\b", reply.lower()), reply


@passes(2, of=3)
def test_the_person_back_with_the_answer_has_it_recorded_and_the_todo_closed(coach):
    # R-0803
    coach.record()
    kept(coach)

    reply = coach.say("I asked her, they moved in 1991.")
    found = todos(coach)
    assert [(q["state"], q["outcome"]) for q in found] == [
        (QuestionState.Resolved, QuestionOutcome.Answered)
    ], found
    assert any(
        (e.get("dateTime") or "").startswith("1991") for e in coach.events
    ), coach.events
    assert not [q for q in asked(reply) if "mov" in q.lower()], reply
