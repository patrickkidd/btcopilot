"""The person's own todos: kept only when they say them, in their words, and
picked up first when they come back after a sitting's gap.

Invented names only.
"""

import dataclasses
import datetime

import pytest

from btcopilot import coverage, questions, record
from btcopilot.coachturn import CoachTurn, todos
from btcopilot.discussions import open_session
from btcopilot.extensions import db
from btcopilot.models import Author, Change, ProactiveMessage, Purpose, Statement, Trigger
from btcopilot.recordtext import note_line
from btcopilot.tests.conftest import Model, said, version, wrote
from btcopilot.tests.test_questions import stored
from btcopilot.tests.test_searchchat import says
from btcopilot.tests.test_turnhistory import family  # noqa: F401
from btcopilot.toolbox import ToolError, ToolName, Toolbox

ASK_MOM = "ask my mom when they moved"
BACK = "The person is back after"


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.metered.response_text_sync",
        lambda *a, **k: wrote("A session title"),
    )


def ago(**delta) -> str:
    return (datetime.datetime.utcnow() - datetime.timedelta(**delta)).isoformat()


def turn(discussion, text="Hi, I'm back") -> str:
    """What the coach read: its prompt and the newest message, which carries
    the part of the prompt that changes turn to turn."""
    model = Model(said("Welcome back."))
    CoachTurn(discussion, text, purpose=Purpose.Coach, model=model).run()
    newest = model.histories[0][-1]["content"]
    return model.systems[0] + "".join(b.get("text", "") for b in newest)


def telling(diagram, user, text=f"I'll {ASK_MOM}.", day=None):
    """A toolbox answering the person's words, as a coach turn's is."""
    statement = says(open_session(user, diagram), text, day or ago(days=3))
    toolbox = Toolbox(
        diagram.id, "t1", user_id=user.id, session_id=statement.discussion_id, said=statement
    )
    return toolbox, statement


def keep(toolbox, text=ASK_MOM, state="held", **args):
    return toolbox.call(
        ToolName.AddQuestion, {"text": text, "kind": "todo", "state": state, **args}
    )


@pytest.fixture
def session(test_user):
    """A sitting with the person's and the coach's own speakers, as the app opens one."""
    opened = open_session(test_user, test_user.free_diagram)
    db.session.commit()
    return opened


def test_the_back_block_comes_only_when_the_message_opens_a_new_sitting(session):
    # R-0783
    assert BACK not in turn(session, "My first words")

    says(session, "We talked about my dad.", ago(minutes=30))
    assert BACK not in turn(session)

    Statement.query.filter_by(discussion_id=session.id).update(
        {"created_at": datetime.datetime.utcnow() - datetime.timedelta(days=2, hours=1)}
    )
    db.session.commit()
    assert f"{BACK} 2 day(s). Their own todos, oldest first: none." in turn(session)


def test_a_message_the_coach_sent_unasked_is_not_the_family_speaking(session, test_user):
    # R-0783
    says(session, "We talked about my dad.", ago(days=3, hours=1))
    sent = says(session, "Your move and your dad's illness came close.", ago(hours=1), coach=True)
    db.session.add(
        ProactiveMessage(
            user_id=test_user.id,
            diagram_id=session.diagram_id,
            trigger=Trigger.Correlation,
            key="pair",
            statement_id=sent.id,
            sent_at=sent.created_at,
        )
    )
    db.session.commit()
    assert f"{BACK} 3 day(s)." in turn(session)


def test_the_coach_keeps_a_todo_held_in_their_words_citing_their_message(family, test_user):
    # R-0783
    toolbox, statement = telling(family, test_user)
    text, _ = keep(toolbox)

    assert text == "Added todo q1."
    kept = stored(family)["q1"]
    assert (kept["kind"], kept["state"], kept["text"]) == ("todo", "held", ASK_MOM)
    assert [(e["kind"], e["id"]) for e in kept["evidence"]] == [("statement", statement.id)]
    assert note_line(kept) == (
        f'q1 held todo "{ASK_MOM}" (said {statement.created_at.date().isoformat()})'
    )


@pytest.mark.parametrize(
    "args,plain",
    [
        ({"state": "asked"}, "A todo is kept for later when it is said."),
        ({"fact": "alive"}, "It named what the question asks on something that cannot hold it."),
        ({"case_report_card": "own_part", "state": "asked"}, "A todo cannot go on the case report."),
    ],
)
def test_a_todo_added_asked_with_a_fact_or_on_a_card_is_refused(family, test_user, args, plain):
    # R-0783
    toolbox, _ = telling(family, test_user)
    with pytest.raises(ToolError) as refused:
        keep(toolbox, **args)
    assert refused.value.plain == plain


def test_a_todo_needs_the_persons_message(family):
    # R-0783
    with pytest.raises(ToolError) as refused:
        keep(Toolbox(family.id, "t1", session_id=7))
    assert refused.value.plain == "A todo is only ever something the person said."


def test_a_todo_moves_held_asked_resolved_and_each_step_is_undone(family, test_user):
    # R-0783
    toolbox, statement = telling(family, test_user)
    keep(toolbox)
    before = stored(family)
    start = db.session.query(db.func.max(Change.id)).scalar()
    toolbox.call(ToolName.SetQuestion, {"id": "q1", "version": version(family), "state": "asked"})
    toolbox.call(
        ToolName.SetQuestion,
        {"id": "q1", "version": version(family), "state": "resolved", "outcome": "answered"},
    )

    kept = stored(family)["q1"]
    assert (kept["state"], kept["outcome"], kept["answer"]["id"]) == (
        "resolved",
        "answered",
        statement.id,
    )
    with pytest.raises(ToolError) as refused:
        toolbox.call(
            ToolName.SetQuestion,
            {"id": "q1", "version": version(family), "state": "resolved", "outcome": "fact"},
        )
    assert refused.value.plain == "That todo is already closed."

    rows = [c.id for c in Change.query.filter(Change.id > start)]
    record.undo_changes(family.id, rows, author=Author.Coach)
    after = stored(family)["q1"]
    assert {k: v for k, v in after.items() if v is not None} == {
        k: v for k, v in before["q1"].items() if v is not None
    }


def test_only_open_todos_are_listed_oldest_first_and_none_reach_the_page_or_coverage(
    family, test_user
):
    # R-0783
    toolbox, _ = telling(family, test_user)
    for words in ("ask my mom when they moved", "dig out the old photos", "call my uncle Jory"):
        keep(toolbox, words)
    toolbox.call(
        ToolName.SetQuestion,
        {"id": "q2", "version": version(family), "state": "resolved", "outcome": "let_go"},
    )
    toolbox.call(ToolName.SetQuestion, {"id": "q3", "version": version(family), "state": "asked"})
    db.session.expire_all()
    data = family.get_diagram_data()

    listed = todos(data)
    assert "dig out the old photos" not in listed
    assert listed.index("q1 held todo") < listed.index("q3 asked todo")
    assert questions.asked(family.id, data) == []
    assert coverage.block(data) == coverage.block(dataclasses.replace(data, questions=[]))
