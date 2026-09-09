"""The agent loop: tools that change the record, chips that resolve, one view
kind at a time, and a play-by-play that cannot invent a move."""

import pytest

from btcopilot.extensions import db
from btcopilot.personal import chips, record
from btcopilot.personal.coachturn import (
    FINISH,
    MAX_STEPS,
    BareList,
    CoachTurn,
    EmptyReply,
    EventKind,
    LabelTooLong,
)
from btcopilot.personal.models import Author, Change, StatementKind
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
        "Show me that cluster.",
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
        "/personal/chat",
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


def test_play_by_play_ends_in_offered_chips(test_user):
    """The walk closes with two or three offers of where to look next. An offer
    carries its own words, not an id, so it survives validation whole."""
    data = DiagramData(
        people=[asdict(Person(id=1, name="Wren"))],
        events=[asdict(Event(id=10, kind=Kind.Moved, person=1, dateTime="1994-06-01"))],
        clusters=[asdict(Cluster(id="c1", title="That year", summary="", eventIds=[10]))],
    )
    model = Model(
        said(
            "[[event:10|he moved out]] is where it starts.\n\n"
            "[[ask:the winter after he left]] [[ask:how Wren took it]]"
        )
    )
    statement = PlayTurn.stored(data, "c1", model=model).run()["statement"]

    offered = [
        target
        for kind, target, _ in chips.parse(statement, data)
        if kind is chips.ChipKind.Ask
    ]
    assert 2 <= len(offered) <= 3
    assert offered == ["the winter after he left", "how Wren took it"]
    assert statement.endswith("[[ask:how Wren took it]]")


def test_a_turn_that_never_stops_calling_tools_still_says_something(
    discussion, family
):
    """The page shows what the coach said, so a turn may not end on a tool
    call. When the steps run out the coach is asked for its reply with no tools
    at all, and that is what the person reads."""
    working = [
        called(
            ToolName.EditPerson,
            text=f"Working out step {n}.",
            name=f"Person {n}",
        )
        for n in range(MAX_STEPS)
    ]
    before = len(discussion.statements)
    model = Model(*working, said("I added them all. Who else was around then?"))
    reply = run(discussion, "There were six of them.", model)

    assert model.offered[-1] == []
    assert FINISH in model.histories[-1][-1]["content"]

    spoken = [s.text for s in discussion.statements]
    assert len(spoken) - before == 2
    assert spoken[-2:] == [
        "There were six of them.",
        "I added them all. Who else was around then?",
    ]
    assert "Working out" not in " ".join(spoken)
    assert discussion.statements[-1].id == reply["statement_id"]


def test_the_edits_of_a_capped_turn_are_all_kept(discussion, family):
    """Running out of steps ends the talking, not the record: everything the
    coach put in before the cap stays in."""
    working = [
        called(ToolName.EditPerson, name=f"Person {n}") for n in range(MAX_STEPS)
    ]
    reply = run(
        discussion,
        "There were six of them.",
        Model(*working, said("All six are down.")),
    )
    assert kinds(reply).count(EventKind.ToolCall.value) == MAX_STEPS

    names = [p.get("name") for p in family.get_diagram_data().people]
    assert [f"Person {n}" for n in range(MAX_STEPS)] == names[-MAX_STEPS:]

    # The forced last call must not roll anything back or run anything twice:
    # the rows are still there and still point at the statement.
    written = Change.query.filter_by(turn_id=reply["turn_id"]).all()
    assert len(written) == MAX_STEPS
    assert {c.statement_id for c in written} == {reply["statement_id"]}


def test_a_turn_with_no_words_at_all_fails_rather_than_showing_a_bare_bubble(
    discussion, family
):
    with pytest.raises(EmptyReply):
        run(discussion, "Hello?", Model(said("")))


def test_a_label_of_exactly_the_limit_is_left_alone(discussion, family):
    """Twenty-eight fits. The boundary is where this goes wrong, so it is
    pinned on both sides."""
    label = "a" * chips.CHIP_MAX
    reply = run(
        discussion,
        "Tell me about that.",
        Model(said(f"[[event:10|{label}]] is where it starts.")),
    )
    assert reply["statement"] == f"[[event:10|{label}]] is where it starts."


def test_one_label_over_the_limit_is_asked_again_never_trimmed(discussion, family):
    """Twenty-nine does not fit. The coach is asked once to shorten it, and its
    own shorter words are what the person reads — nothing here cuts them."""
    long_label = "a" * (chips.CHIP_MAX + 1)
    model = Model(
        said(f"[[event:10|{long_label}]] is where it starts."),
        said("[[event:10|the move]] is where it starts."),
    )
    reply = run(discussion, "Tell me about that.", model)

    assert reply["statement"] == "[[event:10|the move]] is where it starts."
    assert model.offered[-1] == []
    assert long_label in model.histories[-1][-1]["content"]
    assert discussion.statements[-1].text == reply["statement"]


BARE = (
    "Here is the cluster, move by move: [[event:10|moved out]], then "
    "[[person:1|Wren]], then [[cluster:c1|the year he left]]."
)

TOLD = (
    "Bo moved out in the summer of 1994, and [[event:10|that move]] is what "
    "[[person:1|Wren]] still dates everything from. She calls it "
    "[[cluster:c1|the year he left]]."
)


def test_a_reply_that_is_only_chips_is_asked_again_for_sentences(discussion, family):
    """A comma list of chips is not the coach speaking, so it is sent back once
    and the coach's own sentences are what the person reads."""
    model = Model(said(BARE), said(TOLD))
    reply = run(discussion, "Walk me through it.", model)

    assert reply["statement"] == TOLD
    assert BARE in model.histories[-1][-2]["content"]


def test_a_reply_that_stays_a_list_of_chips_fails(discussion, family):
    with pytest.raises(BareList):
        run(discussion, "Walk me through it.", Model(said(BARE), said(BARE)))


def test_a_label_that_stays_too_long_fails_rather_than_being_cut(discussion, family):
    long_label = "a" * (chips.CHIP_MAX + 1)
    with pytest.raises(LabelTooLong):
        run(
            discussion,
            "Tell me about that.",
            Model(
                said(f"[[event:10|{long_label}]]."),
                said(f"[[event:10|{long_label}]] still."),
            ),
        )


def test_a_label_is_measured_in_what_a_reader_sees(discussion, family):
    """An accented letter is two code points and one character to read, so a
    label of accents at the limit fits."""
    label = "e\u0301" * chips.CHIP_MAX
    assert chips.length(label) == chips.CHIP_MAX
    assert len(label) == chips.CHIP_MAX * 2

    reply = run(
        discussion,
        "Tell me about that.",
        Model(said(f"[[event:10|{label}]].")),
    )
    assert reply["statement"] == f"[[event:10|{label}]]."


def test_a_play_by_play_is_marked_as_one_and_names_its_stretch(discussion, family):
    """The page routes a tap by the kind of message it is in: a chip in a walk
    steps the board, a chip anywhere else selects the moment."""
    data = family.get_diagram_data()
    model = Model(said("[[event:10|the move]] is the whole of it."))
    reply = PlayTurn.stored(data, "c1", discussion=discussion, model=model).run()

    assert reply["kind"] == StatementKind.Play.value
    assert reply["cluster_id"] == "c1"

    stored = discussion.statements[-1]
    assert stored.id == reply["statement_id"]
    assert stored.kind is StatementKind.Play
    assert stored.cluster_id == "c1"


def test_every_message_the_page_reads_back_carries_its_kind(web, family, monkeypatch):
    """The page routes a chip tap by the kind of message it sits in, so the
    kind travels with the message everywhere the page reads one."""
    from btcopilot.tests.personal.conftest import csrf_token

    monkeypatch.setattr(
        "btcopilot.personal.coachturn.CoachModel",
        lambda *a, **k: Model(said("Tell me about [[event:10|the move]].")),
    )
    monkeypatch.setattr(
        "btcopilot.personal.playturn.CoachModel",
        lambda *a, **k: Model(said("[[event:10|the move]] is the whole of it.")),
    )
    token = csrf_token(web)

    said_reply = web.post(
        "/personal/chat",
        json={"statement": "My dad moved out."},
        headers={"X-CSRFToken": token},
    ).get_json()
    assert said_reply["kind"] == StatementKind.Turn.value

    played = web.post(
        "/personal/play",
        json={"cluster_id": "c1"},
        headers={"X-CSRFToken": token},
    ).get_json()
    assert played["kind"] == StatementKind.Play.value
    assert played["cluster_id"] == "c1"

    stored = web.get(f"/personal/sessions/{said_reply['discussion_id']}").get_json()
    assert [(s["kind"], s["cluster_id"]) for s in stored["statements"]] == [
        (StatementKind.Turn.value, None),
        (StatementKind.Turn.value, None),
        (StatementKind.Play.value, "c1"),
    ]


TWO_HOURS = 2 * 3600


def test_a_csrf_token_older_than_an_hour_still_posts(web, family, monkeypatch):
    """The token the page is stamped with lives as long as the session it
    belongs to. It expired after an hour, so a reader still signed in and still
    typing had every send refused and read an empty coach bubble."""
    import time

    from btcopilot.tests.personal.conftest import csrf_token

    monkeypatch.setattr(
        "btcopilot.personal.coachturn.CoachModel",
        lambda *a, **k: Model(said("Tell me about [[event:10|the move]].")),
    )
    token = csrf_token(web)
    later = time.time() + TWO_HOURS
    monkeypatch.setattr(time, "time", lambda: later)

    reply = web.post(
        "/personal/chat",
        json={"statement": "My dad moved out."},
        headers={"X-CSRFToken": token},
    )
    assert reply.status_code == 200
    assert reply.get_json()["kind"] == StatementKind.Turn.value


def test_a_moment_the_coach_wrote_traces_to_the_message_that_wrote_it(
    web, family, monkeypatch
):
    """The page offers the way back to where a moment was said. Nothing stamps
    that on the moment itself outside the fixtures, so it is read from the
    command log: the coach's own message against the commands that turn made."""
    from btcopilot.tests.personal.conftest import csrf_token

    monkeypatch.setattr(
        "btcopilot.personal.coachturn.CoachModel",
        lambda *a, **k: Model(
            called(
                ToolName.EditEvent,
                kind="shift",
                date="1994-12-01",
                description="got sick",
                person=1,
                symptom="up",
            ),
            said("I put that down."),
        ),
    )
    token = csrf_token(web)
    reply = web.post(
        "/personal/chat",
        json={"statement": "My mum got sick that winter."},
        headers={"X-CSRFToken": token},
    ).get_json()

    coded = web.get("/personal/timeline").get_json()["coded_in"]
    made = [event["id"] for event in web.get("/personal/timeline").get_json()["events"]]
    newest = str(max(made))
    assert coded[newest]["statement_id"] == reply["statement_id"]
    assert coded[newest]["discussion_id"] == reply["discussion_id"]
