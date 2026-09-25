"""The agent loop: tools that change the record, chips that resolve, one view
kind at a time, and a play-by-play that cannot invent a move."""

import datetime
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from btcopilot.extensions import db
from btcopilot import chips, pricing, record, tracing
from btcopilot.coachmodel import Spent
from btcopilot.coachturn import (
    FINISH,
    MAX_STEPS,
    BareList,
    CoachTurn,
    EmptyReply,
    LabelTooLong,
)
from btcopilot.turnlog import TurnEventKind as EventKind
from btcopilot.models import Author, Change, ModelCall, StatementKind
from btcopilot.playturn import PlayTurn
from btcopilot.prompts import get_agent_prompt
from btcopilot.toolbox import ToolName
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
from btcopilot.tests.conftest import (
    Model,
    called,
    calling,
    replied,
    said,
)


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
        "btcopilot.models.discussion.response_text_sync",
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
                kind=Kind.Noted,
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
    # R-0086, R-0084
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
    made = next(d for d in change.deltas if d["item_kind"] == ItemKind.Event.value)
    assert made["field"] is None
    assert set(made["after"]) >= {"description", "symptom", "dateTime"}

    added = [e for e in family.get_diagram_data().events if e["id"] == 11]
    assert len(added) == 1
    assert added[0]["description"] == "got sick"
    assert reply["statement"] == "I put that down. [[event:11|that winter]]"


def test_the_coach_can_write_a_noted_event(discussion, family):
    # R-0364, R-0363
    """A move is a noted event carrying what happened and where [Oracle: R-0364]."""
    run(
        discussion,
        "We moved to Arizona in the spring of 2019.",
        Model(
            called(
                ToolName.EditEvent,
                kind=Kind.Noted.value,
                date="2019-03-01",
                description="moved to Arizona",
                location="Arizona",
                person=1,
            ),
            said("I put that down."),
        ),
    )

    added = [e for e in family.get_diagram_data().events if e["id"] == 11]
    assert len(added) == 1
    assert added[0]["kind"] == Kind.Noted.value
    assert added[0]["description"] == "moved to Arizona"
    assert added[0]["location"] == "Arizona"


def test_a_turn_that_fails_before_the_coach_answers_stores_no_words(discussion, family):
    # R-0182
    class Down:
        def turn(self, system, messages, tools, turn_id=""):
            raise RuntimeError("model unreachable")
            yield

    before = len(discussion.statements)
    with pytest.raises(RuntimeError):
        run(discussion, "May of 1971", Down())
    db.session.rollback()
    assert len(discussion.statements) == before


def test_a_chip_the_record_cannot_resolve_never_reaches_the_transcript(
    discussion, family
):
    # R-0085
    reply = run(
        discussion,
        "Tell me about that.",
        Model(said("You mean [[event:999|the fight]] and [[event:10|the move]].")),
    )
    assert reply["statement"] == "You mean the fight and [[event:10|the move]]."


def test_undo_puts_back_what_the_previous_turn_changed(discussion, family):
    # R-0084
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
    # R-0084
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
    # R-0075
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
    # R-0075, R-0085
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


def test_the_coach_is_handed_a_map_of_the_record_and_what_the_user_pointed_at(
    discussion, family
):
    # R-0072, R-0479
    model = Model(said("Say more about that."))
    run(discussion, "[[event:10]]", model)

    assert "2 Bo events=1" in model.systems[0]
    assert "moved out" not in model.systems[0]
    assert "tell me about this" in model.histories[0][-1]["content"]


def test_play_by_play_names_every_event_once_in_date_order(test_user):
    # R-0074
    data = DiagramData(
        people=[asdict(Person(id=1, name="Wren"))],
        events=[
            asdict(
                Event(
                    id=10,
                    kind=Kind.Noted,
                    person=1,
                    dateTime="1994-06-01",
                    description="moved out",
                )
            ),
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
    # R-0185
    from btcopilot.tests.conftest import csrf_token

    monkeypatch.setattr(
        "btcopilot.coachturn.CoachModel",
        lambda *a, **k: Model(
            called(ToolName.EditPerson, name="Nell"), said("Added [[person:11|Nell]].")
        ),
    )
    token = csrf_token(web)
    response = web.post(
        "/app/chat",
        json={"statement": "My sister is Nell."},
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 202

    reply = replied(response)
    assert reply["statement"] == "Added [[person:11|Nell]]."
    assert [e["type"] for e in reply["events"]] == ["tool_call", "record_patch"]
    assert reply["events"][0]["name"] == "edit_person"
    assert reply["events"][1]["turn_id"] == reply["turn_id"]
    assert reply["statement_id"] is not None
    assert reply["session"]["id"] == reply["discussion_id"]


def test_people_and_their_events_all_land_in_one_turn(discussion, family):
    # R-0078
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
                        "kind": "noted",
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


def test_offered_chips_never_reach_the_transcript(test_user):
    # R-0361
    """Offered answers are dropped (Patrick, 2026-09-21): people type their own
    words. A model that still writes them loses only the offers."""
    data = DiagramData(
        people=[asdict(Person(id=1, name="Wren"))],
        events=[
            asdict(
                Event(
                    id=10,
                    kind=Kind.Noted,
                    person=1,
                    dateTime="1994-06-01",
                    description="moved out",
                )
            )
        ],
        clusters=[asdict(Cluster(id="c1", title="That year", summary="", eventIds=[10]))],
    )
    model = Model(
        said(
            "[[event:10|he moved out]] is where it starts. What came next?\n\n"
            "[[ask:the winter after he left]] [[ask:how Wren took it]]"
        )
    )
    statement = PlayTurn.stored(data, "c1", model=model).run()["statement"]

    assert "[[ask:" not in statement
    assert statement.endswith("What came next?")
    assert chips.parse(statement, data) == [(chips.ChipKind.Event, "10", "he moved out")]


def test_a_turn_that_never_stops_calling_tools_still_says_something(
    discussion, family
):
    # R-0411
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


def test_the_edits_of_a_capped_turn_are_all_kept(discussion, family, caplog):
    # R-0411
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
    capped = [r for r in caplog.records if "hit the step cap" in r.message]
    assert [r.levelname for r in capped] == ["WARNING"]
    assert reply["turn_id"] in capped[0].message
    assert f"{MAX_STEPS} steps used" in capped[0].message
    assert ToolName.EditPerson.value in capped[0].message
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
    # R-0182
    with pytest.raises(EmptyReply):
        run(discussion, "Hello?", Model(said("")))


def test_a_label_of_exactly_the_limit_is_left_alone(discussion, family):
    # R-0169
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
    # R-0169
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
    # R-0160
    """A comma list of chips is not the coach speaking, so it is sent back once
    and the coach's own sentences are what the person reads."""
    model = Model(said(BARE), said(TOLD))
    reply = run(discussion, "Walk me through it.", model)

    assert reply["statement"] == TOLD
    assert BARE in model.histories[-1][-2]["content"]


def test_a_reply_that_stays_a_list_of_chips_fails(discussion, family):
    # R-0160
    with pytest.raises(BareList):
        run(discussion, "Walk me through it.", Model(said(BARE), said(BARE)))


def test_a_label_that_stays_too_long_fails_rather_than_being_cut(discussion, family):
    # R-0169
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
    # R-0169
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
    # R-0170
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
    # R-0170
    """The page routes a chip tap by the kind of message it sits in, so the
    kind travels with the message everywhere the page reads one."""
    from btcopilot.tests.conftest import csrf_token

    monkeypatch.setattr(
        "btcopilot.coachturn.CoachModel",
        lambda *a, **k: Model(said("Tell me about [[event:10|the move]].")),
    )
    monkeypatch.setattr(
        "btcopilot.playturn.CoachModel",
        lambda *a, **k: Model(said("[[event:10|the move]] is the whole of it.")),
    )
    token = csrf_token(web)

    said_reply = replied(
        web.post(
            "/app/chat",
            json={"statement": "My dad moved out."},
            headers={"X-CSRFToken": token},
        )
    )
    assert said_reply["kind"] == StatementKind.Turn.value

    played = web.post(
        "/app/play",
        json={"cluster_id": "c1"},
        headers={"X-CSRFToken": token},
    ).get_json()
    assert played["kind"] == StatementKind.Play.value
    assert played["cluster_id"] == "c1"

    stored = web.get(f"/app/sessions/{said_reply['discussion_id']}").get_json()
    assert [(s["kind"], s["cluster_id"]) for s in stored["statements"]] == [
        (StatementKind.Turn.value, None),
        (StatementKind.Turn.value, None),
        (StatementKind.Play.value, "c1"),
    ]


TWO_HOURS = 2 * 3600


def test_a_csrf_token_older_than_an_hour_still_posts(web, family, monkeypatch):
    # R-0337
    """The token the page is stamped with lives as long as the session it
    belongs to. It expired after an hour, so a reader still signed in and still
    typing had every send refused and read an empty coach bubble."""
    import time

    from btcopilot.tests.conftest import csrf_token

    monkeypatch.setattr(
        "btcopilot.coachturn.CoachModel",
        lambda *a, **k: Model(said("Tell me about [[event:10|the move]].")),
    )
    token = csrf_token(web)
    later = time.time() + TWO_HOURS
    monkeypatch.setattr(time, "time", lambda: later)

    reply = web.post(
        "/app/chat",
        json={"statement": "My dad moved out."},
        headers={"X-CSRFToken": token},
    )
    assert reply.status_code == 202
    assert replied(reply)["kind"] == StatementKind.Turn.value


def test_a_moment_the_coach_wrote_traces_to_the_message_that_wrote_it(
    web, family, monkeypatch
):
    # R-0140
    """The page offers the way back to where a moment was said. Nothing stamps
    that on the moment itself outside the fixtures, so it is read from the
    command log: the coach's own message against the commands that turn made."""
    from btcopilot.tests.conftest import csrf_token

    monkeypatch.setattr(
        "btcopilot.coachturn.CoachModel",
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
    reply = replied(
        web.post(
            "/app/chat",
            json={"statement": "My mum got sick that winter."},
            headers={"X-CSRFToken": token},
        )
    )

    coded = web.get("/app/timeline").get_json()["coded_in"]
    made = [event["id"] for event in web.get("/app/timeline").get_json()["events"]]
    newest = str(max(made))
    assert coded[newest]["statement_id"] == reply["statement_id"]
    assert coded[newest]["discussion_id"] == reply["discussion_id"]


def test_a_turn_charges_every_model_call_to_the_user_for_the_month(discussion, family):
    # R-0388
    from btcopilot.models import TokenMeter

    first = called(ToolName.EditPerson, name="Nell")
    first.spent = Spent(input=1000, output=50, cache_creation=800, cache_read=0)
    second = said("Added [[person:11|Nell]].")
    second.spent = Spent(input=1100, output=40, cache_creation=0, cache_read=800)
    run(discussion, "My aunt Nell.", Model(first, second))
    run(discussion, "Thanks.", Model(said("Any time.")))

    meter = TokenMeter.query.filter_by(user_id=discussion.user_id).one()
    assert meter.period == datetime.date.today().strftime("%Y-%m")
    assert (
        meter.input_tokens,
        meter.output_tokens,
        meter.cache_creation_tokens,
        meter.cache_read_tokens,
    ) == (2100, 90, 800, 800)


def test_a_turn_writes_down_each_model_call_with_its_cost(discussion, family):
    # R-0388
    first = called(ToolName.EditPerson, name="Nell")
    first.spent = Spent(input=1000, output=50, cache_creation=800, cache_read=0)
    second = said("Added [[person:11|Nell]].")
    second.spent = Spent(input=1100, output=40, cache_creation=0, cache_read=800)
    reply = run(discussion, "My aunt Nell.", Model(first, second))

    calls = ModelCall.query.order_by(ModelCall.id).all()
    rate = pricing.PRICES["claude-opus-5-5"]
    assert [
        (
            c.user_id,
            c.diagram_id,
            c.turn_id,
            c.model,
            c.input_tokens,
            c.output_tokens,
            c.cache_creation_tokens,
            c.cache_read_tokens,
            c.tool_calls,
            c.cost_usd,
        )
        for c in calls
    ] == [
        (
            discussion.user_id,
            discussion.diagram_id,
            reply["turn_id"],
            "claude-opus-5-5",
            1000,
            50,
            800,
            0,
            1,
            (1000 * rate.input + 50 * rate.output + 800 * rate.cache_write)
            / 1_000_000,
        ),
        (
            discussion.user_id,
            discussion.diagram_id,
            reply["turn_id"],
            "claude-opus-5-5",
            1100,
            40,
            0,
            800,
            0,
            (1100 * rate.input + 40 * rate.output + 800 * rate.cache_read)
            / 1_000_000,
        ),
    ]


def test_a_model_with_no_price_raises():
    # R-0453
    with pytest.raises(KeyError):
        pricing.cost("gpt-5", Spent())


def test_tracing_provider(monkeypatch):
    # R-0370
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert isinstance(tracing.provider(), trace.NoOpTracerProvider)

    exported = InMemorySpanExporter()
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://fd-alloy:4318")
    monkeypatch.setattr(tracing, "OTLPSpanExporter", lambda: exported)
    sdk = tracing.provider()
    sdk.get_tracer(__name__).start_span("coach.turn").end()
    sdk.force_flush()
    assert [s.name for s in exported.get_finished_spans()] == ["coach.turn"]


QUOTE = "He said he would never go back to that house"


def _with_notes(diagram):
    data = diagram.get_diagram_data()
    data.events[0]["notes"] = QUOTE
    diagram.set_diagram_data(data)
    db.session.commit()


def test_the_notes_stay_out_of_every_call_and_the_tool_to_read_them_is_offered(
    discussion, family
):
    # R-0446
    _with_notes(family)
    model = Model(called(ToolName.ReadEvents), said("What happened next?"))
    run(discussion, "Tell me about when he moved out.", model)
    assert len(model.systems) == 2
    assert "(has notes)" in str(model.histories[1][-1])
    for system, history in zip(model.systems, model.histories):
        assert QUOTE not in system + str(history)
    assert all(ToolName.ReadNotes.value in offered for offered in model.offered)


def test_the_coach_reads_an_events_notes_when_it_asks_for_them(discussion, family):
    # R-0446
    _with_notes(family)
    model = Model(called(ToolName.ReadNotes, event=10), said("What happened next?"))
    run(discussion, "What did he say about the house?", model)
    answer = model.histories[-1][-1]["content"][-1]
    assert answer["type"] == "tool_result"
    assert answer["content"].splitlines()[0] == f"10: {QUOTE}"


def test_the_coach_is_told_to_end_its_reply_with_a_question():
    # R-0436
    prompt = " ".join(get_agent_prompt().split())
    assert "A reply usually ends with one question in your own words" in prompt
    assert "it always does while the record still lacks any of the minimum data" in prompt



def test_a_remove_of_a_kind_the_record_does_not_hold_is_refused(discussion, family):
    # R-0478
    model = Model(
        called(ToolName.Remove, item_kind="household", item_id="1", version=family.version),
        said("There is no household to remove."),
    )
    reply = run(discussion, "Remove the household.", model)

    asked = event(reply, EventKind.ToolCall)
    assert asked["names"] == {"it": "something the record has no kind for"}
    assert asked["refusal"] == "There is no such kind of thing to remove."
    refused = model.histories[-1][-1]["content"][0]
    assert refused["is_error"] is True
