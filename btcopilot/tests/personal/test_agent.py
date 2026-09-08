"""The agent loop: tools that change the record, chips that resolve, one view
kind at a time, and a play-by-play that cannot invent a move."""

import pytest

from btcopilot.extensions import db
from btcopilot.personal import chips, record
from btcopilot.personal.coachturn import CoachTurn, EventKind
from btcopilot.personal.models import Author, Change
from btcopilot.personal.playturn import PlayTurn
from btcopilot.personal.toolbox import ToolName
from btcopilot.schema import (
    Cluster,
    DateCertainty,
    DiagramData,
    Event,
    EventKind as Kind,
    ItemKind,
    Person,
    asdict,
)
from btcopilot.tests.personal.conftest import Model, called, calling, said


def run(discussion, statement, model) -> dict:
    return CoachTurn(discussion, statement, model=model).run()


def kinds(reply: dict) -> list[str]:
    return [event["type"] for event in reply["events"]]


def event(reply: dict, kind: EventKind) -> dict:
    return next(e for e in reply["events"] if e["type"] == kind.value)


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    """Naming a session is its own model call; the agent loop is what is under
    test here."""
    monkeypatch.setattr(
        "btcopilot.personal.models.discussion.response_text_sync",
        lambda *a, **k: "A session title",
    )


@pytest.fixture
def family(test_user):
    """Two people and one dated event. Invented names only."""
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren")), asdict(Person(id=2, name="Bo"))]
    data.events = [
        asdict(
            Event(
                id=10,
                kind=Kind.Moved,
                person=2,
                dateTime="1994-06-01",
                description="moved out",
                dateCertainty=DateCertainty.Certain,
            )
        )
    ]
    data.clusters = [
        asdict(Cluster(id="c1", title="The year he left", summary="", eventIds=[10]))
    ]
    data.lastItemId = 10
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def test_edit_writes_a_coach_change_and_the_record_moves(discussion, family):
    reply = run(
        discussion,
        "My dad moved out in 1994 and my mum got sick that winter.",
        Model(
            called(
                ToolName.EditEvent,
                kind="shift",
                date="1994-12-01",
                description="got sick",
                person=1,
                symptom="up",
            ),
            said("I put that down. [[event:11|that winter]]"),
        ),
    )
    assert kinds(reply) == [EventKind.ToolCall.value, EventKind.RecordPatch.value]

    change = Change.query.filter_by(diagram_id=family.id).one()
    assert change.author is Author.Coach
    assert {d["field"] for d in change.deltas} >= {"description", "symptom", "dateTime"}

    added = [e for e in family.get_diagram_data().events if e["id"] == 11]
    assert len(added) == 1
    assert added[0]["description"] == "got sick"
    assert reply["statement"] == "I put that down. [[event:11|that winter]]"


def test_a_chip_the_record_cannot_resolve_never_reaches_the_transcript(
    discussion, family
):
    reply = run(
        discussion,
        "Tell me about that.",
        Model(said("You mean [[event:999|the fight]] and [[event:10|the move]].")),
    )
    assert reply["statement"] == "You mean the fight and [[event:10|the move]]."


def test_undo_puts_back_what_the_previous_turn_changed(discussion, family):
    record.apply(
        family.id,
        [{"item_kind": ItemKind.Person, "item_id": 1, "field": "name", "after": "Wrenn"}],
        author=Author.Coach,
        turn_id="earlier",
        user_id=discussion.user_id,
    )
    assert family.get_diagram_data().people[0]["name"] == "Wrenn"

    reply = run(
        discussion,
        "Put that back.",
        Model(called(ToolName.Undo), said("Put back.")),
    )
    assert EventKind.RecordPatch.value in kinds(reply)
    assert family.get_diagram_data().people[0]["name"] == "Wren"
    assert Change.query.filter_by(turn_id="undo:earlier").count() == 1


def test_undoing_the_same_turn_twice_is_refused_in_plain_words(discussion, family):
    record.apply(
        family.id,
        [{"item_kind": ItemKind.Person, "item_id": 1, "field": "name", "after": "Wrenn"}],
        author=Author.Coach,
        turn_id="earlier",
        user_id=discussion.user_id,
    )
    run(discussion, "Put that back.", Model(called(ToolName.Undo), said("Done.")))
    assert family.get_diagram_data().people[0]["name"] == "Wren"

    model = Model(called(ToolName.Undo), said("That is already back."))
    reply = run(discussion, "Put that back again.", model)
    assert EventKind.RecordPatch.value not in kinds(reply)
    assert family.get_diagram_data().people[0]["name"] == "Wren"

    refused = model.histories[-1][-1]["content"][0]
    assert refused["is_error"] is True
    assert "cannot be put back" in refused["content"]


def test_show_with_an_unknown_id_fails_where_the_model_can_see_it(discussion, family):
    model = Model(
        called(ToolName.Show, kind="triangle", persons=[1, 2, 77]),
        said("I cannot draw that yet."),
    )
    reply = run(discussion, "Draw the triangle.", model)
    assert EventKind.View.value not in kinds(reply)
    assert reply["views"] == []

    refused = model.histories[-1][-1]["content"][0]
    assert refused["is_error"] is True
    assert "No person 77" in refused["content"]


def test_show_stores_the_view_on_the_coach_statement(discussion, family):
    reply = run(
        discussion,
        "Show me that stretch.",
        Model(
            called(ToolName.Show, kind="span", start="1994-01-01", end="1995-01-01"),
            said("Here it is."),
        ),
    )
    span = {"kind": "span", "start": "1994-01-01", "end": "1995-01-01"}
    assert event(reply, EventKind.View)["view"] == span
    assert reply["views"] == [span]


def test_the_coach_is_handed_the_record_and_what_the_user_pointed_at(
    discussion, family
):
    model = Model(said("Say more about that."))
    run(discussion, "[[event:10]]", model)

    assert "10 1994-06-01 [moved] person=2 \"moved out\"" in model.systems[0]
    assert "tell me about this" in model.histories[0][-1]["content"]


def test_play_by_play_names_every_event_once_in_date_order(test_user):
    data = DiagramData(
        people=[asdict(Person(id=1, name="Wren"))],
        events=[
            asdict(Event(id=10, kind=Kind.Moved, person=1, dateTime="1994-06-01")),
            asdict(Event(id=11, kind=Kind.Shift, person=1, dateTime="1994-12-01")),
        ],
        clusters=[asdict(Cluster(id="c1", title="That year", summary="", eventIds=[10, 11]))],
    )
    model = Model(
        said("[[event:10|he moved out]] then [[event:11|she got sick]]. [[event:10]]")
    )
    reply = PlayTurn.stored(data, "c1", model=model).run()

    assert reply["cluster_id"] == "c1"
    assert [target for _, target, _ in chips.parse(reply["statement"], data)] == [
        "10",
        "11",
        "10",
    ]
    assert "10 1994-06-01" in model.histories[0][-1]["content"]
    assert "11 1994-12-01" in model.histories[0][-1]["content"]


def test_chat_returns_the_words_and_the_events_behind_them(web, family, monkeypatch):
    from btcopilot.tests.personal.conftest import csrf_token

    monkeypatch.setattr(
        "btcopilot.personal.coachturn.CoachModel",
        lambda *a, **k: Model(
            called(ToolName.EditPerson, name="Nell"), said("Added [[person:11|Nell]].")
        ),
    )
    token = csrf_token(web)
    response = web.post(
        "/companion/chat",
        json={"statement": "My sister is Nell."},
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 200

    reply = response.get_json()
    assert reply["statement"] == "Added [[person:11|Nell]]."
    assert [e["type"] for e in reply["events"]] == ["tool_call", "record_patch"]
    assert reply["events"][0]["name"] == "edit_person"
    assert reply["events"][1]["turn_id"] == reply["turn_id"]
    assert reply["statement_id"] is not None
    assert reply["session"]["id"] == reply["discussion_id"]


def test_people_and_their_events_all_land_in_one_turn(discussion, family):
    """A turn that adds the people and stops has lost what was said about them:
    the coach keeps calling tools until every dated fact is in the record."""
    reply = run(
        discussion,
        "My dad Ray left in 1994 and my mum Ivy got ill in 1996.",
        Model(
            calling(
                (ToolName.EditPerson, {"name": "Ray", "gender": "male"}),
                (ToolName.EditPerson, {"name": "Ivy", "gender": "female"}),
            ),
            calling(
                (
                    ToolName.EditEvent,
                    {
                        "kind": "moved",
                        "date": "1994-01-01",
                        "person": 11,
                        "description": "left",
                    },
                ),
                (
                    ToolName.EditEvent,
                    {
                        "kind": "shift",
                        "date": "1996-01-01",
                        "person": 12,
                        "symptom": "up",
                    },
                ),
            ),
            said("Both are down now."),
        ),
    )
    assert kinds(reply).count(EventKind.ToolCall.value) == 4

    data = family.get_diagram_data()
    assert [p["name"] for p in data.people if p["id"] in (11, 12)] == ["Ray", "Ivy"]
    assert [
        (e["dateTime"], e["person"]) for e in data.events if e["id"] in (13, 14)
    ] == [("1994-01-01", 11), ("1996-01-01", 12)]


def test_the_words_before_a_tool_call_are_not_the_coach_speaking(discussion, family):
    """The model works out what to do in the open. Only its last words, the
    ones with no tool call behind them, are the reply."""
    reply = run(
        discussion,
        "My sister is Nell.",
        Model(
            called(
                ToolName.EditPerson,
                text="I need to add a placeholder person first.",
                name="Nell",
            ),
            said("Got her - [[person:11|Nell]]."),
        ),
    )
    assert reply["statement"] == "Got her - [[person:11|Nell]]."

    spoken = [s.text for s in discussion.statements]
    assert "placeholder" not in " ".join(spoken)
