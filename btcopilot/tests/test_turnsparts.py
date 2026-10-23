"""Notes too long for one coach loop go in part by part within one turn: one
turn id, one reply after the last part, one undo when the person stops it."""

import pytest

from btcopilot import turnlog
from btcopilot.extensions import db
from btcopilot.models import Change, Discussion
from btcopilot.schema import Person, asdict
from btcopilot.tests.conftest import Model, called, csrf_token, said, wrote
from btcopilot.tests.test_notesparts import paragraph
from btcopilot.toolbox import ToolName
from btcopilot.turnlog import TurnEventKind

NOTES = "\n\n".join(paragraph(i) for i in range(8))


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.metered.response_text_sync",
        lambda *a, **k: wrote("A session title"),
    )


@pytest.fixture
def family(test_user):
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren"))]
    data.lastItemId = 1
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def post(web, statement=NOTES):
    return web.post(
        "/app/chat",
        json={"statement": statement},
        headers={"X-CSRFToken": csrf_token(web)},
    ).get_json()


def logged(turn_id):
    return [event for _, event in turnlog.read_from(turn_id, 0)]


def asked(history: list[dict]) -> str:
    """The words of the chat one part's model calls were given."""
    return "".join(
        block.get("text", "")
        for message in history
        if isinstance(message["content"], list)
        for block in message["content"]
    )


def three_parts(*names: str, reply: str = "All three are in.") -> list:
    turns = []
    for name in names[:-1]:
        turns += [called(ToolName.EditPerson, name=name), said("")]
    return turns + [called(ToolName.EditPerson, name=names[-1]), said(reply)]


def test_long_notes_go_in_as_one_turn_with_one_reply_part_by_part(
    web, family, monkeypatch
):
    # R-0897
    model = Model(*three_parts("Nell", "Finn", "Ada"))
    monkeypatch.setattr("btcopilot.turns.model_for", lambda *a, **k: model)
    body = post(web)

    events = logged(body["turn_id"])
    assert [e["type"] for e in events] == [
        TurnEventKind.Part.value,
        TurnEventKind.ToolCall.value,
        TurnEventKind.RecordPatch.value,
        TurnEventKind.Part.value,
        TurnEventKind.ToolCall.value,
        TurnEventKind.RecordPatch.value,
        TurnEventKind.Part.value,
        TurnEventKind.ToolCall.value,
        TurnEventKind.RecordPatch.value,
        TurnEventKind.Text.value,
        TurnEventKind.Done.value,
    ]
    assert [(e["part"], e["parts"]) for e in events if e["type"] == "part"] == [
        (1, 3),
        (2, 3),
        (3, 3),
    ]
    assert events[-1]["statement"] == "All three are in."
    assert "part 1 of 3" in asked(model.histories[0])
    assert "part 2 of 3" in asked(model.histories[2])
    assert "last part, 3 of 3" in asked(model.histories[4])
    # each part reads the diagram as the parts before it left it
    assert "Nell" in model.systems[2] and "Finn" not in model.systems[2]
    assert "Finn" in model.systems[4]
    discussion = db.session.get(Discussion, body["discussion_id"])
    assert len(discussion.statements) == 2
    changes = Change.query.filter_by(diagram_id=family.id).all()
    assert {c.turn_id for c in changes} == {body["turn_id"]}
    assert {c.statement_id for c in changes} == {events[-1]["statement_id"]}


class Halting(Model):
    """A coach that is stopped by the person while it ends its first part."""

    def turn(self, system, messages, tools, turn_id=""):
        if len(self.histories) == 1:
            turnlog.halt(turn_id)
        return (yield from super().turn(system, messages, tools, turn_id))


def test_a_stop_between_parts_takes_every_parts_edits_back_as_one(
    web, family, monkeypatch
):
    # R-0897, R-0636
    model = Halting(*three_parts("Nell", "Finn", "Ada"))
    monkeypatch.setattr("btcopilot.turns.model_for", lambda *a, **k: model)
    body = post(web)

    assert len(model.histories) == 2
    db.session.refresh(family)
    assert [p["name"] for p in family.get_diagram_data().people] == ["Wren"]
    turns = [c.turn_id for c in Change.query.filter_by(diagram_id=family.id)]
    assert sorted(turns) == [body["turn_id"], f"undo:{body['turn_id']}"]
    done = logged(body["turn_id"])[-1]
    assert (done["type"], done["stopped"]) == (TurnEventKind.Done.value, True)


def test_a_part_with_no_client_named_enters_what_it_holds_and_asks_nothing(
    web, family, monkeypatch
):
    # R-0897
    data = family.get_diagram_data()
    data.people = [asdict(Person(id=1))]
    family.set_diagram_data(data)
    db.session.commit()
    monkeypatch.setattr("btcopilot.coachturn.onboarding", lambda *a, **k: "ASK FIRST")
    model = Model(
        *three_parts("Nell", "Finn", "Ada", reply="All in. Who is the client?")
    )
    monkeypatch.setattr("btcopilot.turns.model_for", lambda *a, **k: model)
    body = post(web)

    first, second, last = (asked(model.histories[i]) for i in (0, 2, 4))
    assert "ASK FIRST" not in first + second
    assert "ask nothing" in first and "ask nothing" in second
    assert "ASK FIRST" in last
    db.session.refresh(family)
    names = {p["name"] for p in family.get_diagram_data().people}
    assert {"Nell", "Finn", "Ada"} <= names
    assert logged(body["turn_id"])[-1]["statement"] == "All in. Who is the client?"
