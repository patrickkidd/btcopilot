"""What the person says they will find out themselves is kept as their todo,
in their words, and picked up first when they come back a day later; when
they come back with the answer, it is recorded and the todo closed.

Invented names only.
"""

from btcopilot.extensions import db
from btcopilot.models import Statement
from btcopilot.schema import QuestionKind, QuestionOutcome, QuestionState
from btcopilot.tests.live.checks import picks_up_todo, questions as asked
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
    said = Statement.query.filter(Statement.text == EARLIER[2]).order_by(Statement.id.desc()).first()
    diagram = coach.user.free_diagram
    Toolbox(
        diagram.id, "t0", user_id=coach.user.id, session_id=said.discussion_id, said=said
    ).call(ToolName.AddQuestion, {"text": TODO, "kind": "todo", "state": "held"})
    db.session.commit()
    back(1)


@passes(3, of=3)
def test_a_todo_the_person_says_is_kept_held_in_their_words(coach):
    # R-0783
    coach.record()
    sitting(coach, EARLIER[:2])
    coach.say(EARLIER[2])

    found = todos(coach)
    assert len(found) == 1, found
    words = found[0]["text"].lower()
    assert found[0]["state"] == QuestionState.Held, found
    assert "mom" in words and "mov" in words, found


@passes(3, of=3)
def test_the_person_back_a_day_later_is_asked_about_their_todo_first(coach):
    # R-0783
    coach.record()
    kept(coach)

    reply = coach.say("Hi, I'm back")
    assert picks_up_todo(reply, TODO), reply


@passes(2, of=3)
def test_the_person_back_with_the_answer_has_it_recorded_and_the_todo_closed(coach):
    # R-0783
    coach.record()
    kept(coach)

    reply = coach.say("I asked her, they moved in 1991.")
    found = todos(coach)
    assert [(q["state"], q["outcome"]) for q in found] == [
        (QuestionState.Resolved, QuestionOutcome.Answered)
    ], found
    assert any((e.get("dateTime") or "").startswith("1991") for e in coach.events), coach.events
    assert not [q for q in asked(reply) if "mov" in q.lower()], reply
