"""The agent loop: tools that change the record, chips that resolve, one view
kind at a time, and a play-by-play that cannot invent a move."""

import datetime
import re
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from btcopilot.extensions import db
import btcopilot
from btcopilot import chips, pricing, record, tracing
from btcopilot.coachmodel import Spent
from btcopilot.llmutil import EXTRACTION_MODEL, Served, Text
from btcopilot.metered import Metered
from btcopilot.coachturn import (
    FINISH,
    MAX_STEPS,
    BareList,
    CoachTurn,
    EmptyReply,
    LabelTooLong,
)
from btcopilot.turnlog import TurnEventKind as EventKind
from btcopilot.models import (
    Author,
    Change,
    Discussion,
    ModelCall,
    Observation,
    Purpose,
    Speaker,
    SpeakerType,
    Statement,
    StatementKind,
    User,
)
from btcopilot.prompts import get_agent_prompt
from btcopilot.toolbox import Toolbox, ToolName, schemas
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
    wrote,
)


def run(discussion, statement, model) -> dict:
    return CoachTurn(discussion, statement, purpose=Purpose.Coach, model=model).run()


def kinds(reply: dict) -> list[str]:
    return [event["type"] for event in reply["events"]]


def event(reply: dict, kind: EventKind) -> dict:
    return next(e for e in reply["events"] if e["type"] == kind.value)


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    """Naming a session is its own model call; the agent loop is what is under
    test here."""
    monkeypatch.setattr(
        "btcopilot.metered.response_text_sync",
        lambda *a, **k: wrote("A session title"),
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
                symptom="up", date_certainty="certain",
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
                person=1, date_certainty="certain",
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


def test_a_turn_whose_tool_step_raises_keeps_its_model_calls(discussion, family, monkeypatch):
    # R-0388
    def broken(self, args):
        raise RuntimeError("tool broke")

    monkeypatch.setattr(Toolbox, "_read_people", broken)
    with pytest.raises(RuntimeError):
        run(discussion, "My aunt Nell.", Model(called(ToolName.ReadPeople), said("Noted.")))
    db.session.rollback()
    assert ModelCall.query.filter_by(purpose=Purpose.Coach).count() == 1


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


def test_navigate_moves_the_app_and_its_line_names_the_place(discussion, family):
    # R-0055
    reply = run(
        discussion,
        "Where is the year he left?",
        Model(called(ToolName.Navigate, address="/app/cluster/c1"), said("It is open now.")),
    )
    assert event(reply, EventKind.Navigate)["address"] == "/app/cluster/c1"
    call = event(reply, EventKind.ToolCall)
    assert call["names"] == {"it": "the cluster The year he left"}
    assert call["refusal"] is None


@pytest.mark.parametrize(
    "address, reason",
    [("/app/cluster/c9", "No cluster c9"), ("/app/nowhere", "no address in the app")],
)
def test_navigate_to_a_place_the_app_or_the_record_lacks_is_refused(
    discussion, family, address, reason
):
    # R-0055
    model = Model(called(ToolName.Navigate, address=address), said("I cannot open that."))
    reply = run(discussion, "Open it.", model)
    assert EventKind.Navigate.value not in kinds(reply)
    refused = model.histories[-1][-1]["content"][0]
    assert refused["is_error"] is True
    assert reason in refused["content"]


@pytest.mark.parametrize("coder", [False, True])
def test_navigate_lists_coder_screens_only_for_a_coder(coder):
    # R-0055
    tool = next(s for s in schemas(coder) if s["name"] == ToolName.Navigate.value)
    listed = tool["input_schema"]["properties"]["address"]["description"]
    assert ("/app/vote/:n," in listed) is coder
    assert ("/app/account/coding-task," in listed) is coder
    assert "/app/account/profile," in listed


def test_navigate_to_a_coder_screen_is_refused_for_a_person_without_the_role(
    discussion, family
):
    # R-0055
    model = Model(called(ToolName.Navigate, address="/app/coding/3"), said("I cannot open that."))
    reply = run(discussion, "Open it.", model)
    assert EventKind.Navigate.value not in kinds(reply)
    refused = model.histories[-1][-1]["content"][0]
    assert refused["is_error"] is True
    assert "no coder" in refused["content"]


def test_navigate_to_a_coder_screen_opens_for_a_coder(discussion, family):
    # R-0055
    db.session.get(User, discussion.user_id).roles = btcopilot.ROLE_AUDITOR
    db.session.commit()
    model = Model(called(ToolName.Navigate, address="/app/coding/3"), said("It is open now."))
    reply = run(discussion, "Open it.", model)
    assert event(reply, EventKind.Navigate)["address"] == "/app/coding/3"


def test_a_report_asks_the_page_and_keeps_no_observation(discussion, family):
    # R-0056
    words = "I wish the picture were bigger."
    reply = run(
        discussion,
        words,
        Model(called(ToolName.Report, kind="feedback", words=words), said("Good to know.")),
    )
    assert event(reply, EventKind.Report)["report"] == {"kind": "feedback", "words": words}
    assert event(reply, EventKind.ToolCall)["names"] == {}
    assert Observation.query.count() == 0


@pytest.mark.parametrize(
    "args, reason",
    [
        ({"kind": "turn_failed", "words": "It broke."}, "not one of the kinds of report"),
        ({"kind": "bug", "words": " "}, "own words"),
    ],
)
def test_a_report_of_no_kind_or_no_words_is_refused(discussion, family, args, reason):
    # R-0056
    model = Model(called(ToolName.Report, **args), said("Noted."))
    reply = run(discussion, "The app keeps freezing.", model)
    assert EventKind.Report.value not in kinds(reply)
    refused = model.histories[-1][-1]["content"][0]
    assert refused["is_error"] is True
    assert reason in refused["content"]


def test_the_coach_is_handed_a_map_of_the_record_and_what_the_user_pointed_at(
    discussion, family
):
    # R-0072, R-0479
    model = Model(said("Say more about that."))
    run(discussion, "[[event:10]]", model)

    assert "2 Bo events=1" in model.systems[0]
    assert model.systems[0].count("moved out") == get_agent_prompt().count("moved out")
    assert "tell me about this" in model.histories[0][-1]["content"][-1]["text"]


def test_chat_returns_the_words_and_the_events_behind_them(web, family, monkeypatch):
    # R-0185
    from btcopilot.tests.conftest import csrf_token

    monkeypatch.setattr(
        "btcopilot.turns.model_for",
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
                    {"date_certainty": "certain",
                        "kind": "noted",
                        "date": "1994-01-01",
                        "person": 11,
                        "description": "left",
                    },
                ),
                (
                    ToolName.EditEvent,
                    {"date_certainty": "certain",
                        "kind": "shift",
                        "date": "1996-01-01",
                        "person": 12,
                        "symptom": "up",
                        "description": "got ill",
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


def coach_asked(discussion, text: str, **told) -> Statement:
    coach = next(s for s in discussion.speakers if s.type == SpeakerType.Expert)
    statement = Statement(
        discussion_id=discussion.id,
        speaker_id=coach.id,
        text=text,
        order=discussion.next_order(),
        **told,
    )
    db.session.add(statement)
    db.session.commit()
    return statement


def test_the_coach_is_told_which_of_its_questions_the_reader_answers(discussion, family):
    # R-0587, R-0072
    closing = coach_asked(discussion, "Bo moved out in 1994. Who did you turn to then?")
    play = coach_asked(
        discussion,
        "Bo left, then Wren got sick.",
        kind=StatementKind.Play,
        told_case={"cluster_id": "c1", "point": "", "snapshots": [], "question": "Where was Bo that winter?"},
    )
    model = Model(said("Thank you."))
    run(
        discussion,
        f"To answer your question [[message:{closing.id}|Who did you turn to then?]] my aunt, "
        f"and [[message:{play.id}|Where was Bo that winter?]] away.",
        model,
    )
    told = model.histories[0][-1]["content"][-1]["text"]
    assert f'the question you asked in message {closing.id}: "Who did you turn to then?"' in told
    assert f'the question you asked in message {play.id}: "Where was Bo that winter?"' in told


def test_a_message_chip_this_family_did_not_ask_becomes_its_words(discussion, family, test_user_2):
    # R-0587, R-0072
    test_user_2.set_free_diagram()
    theirs = Discussion(user_id=test_user_2.id, diagram_id=test_user_2.free_diagram_id)
    theirs.speakers = [Speaker(name="Coach", type=SpeakerType.Expert)]
    db.session.add(theirs)
    db.session.commit()
    other = coach_asked(theirs, "Who else knew?")
    plain = coach_asked(discussion, "Bo moved out in 1994.")
    mine = next(s for s in discussion.statements if s.speaker.type == SpeakerType.Subject)
    text = chips.validate(
        f"[[message:{other.id}|Who else knew?]] [[message:{plain.id}|that]] "
        f"[[message:{mine.id}|Hello]] [[message:x|this]]",
        family.get_diagram_data(),
        family.id,
    )
    assert text == "Who else knew? that Hello this"


def test_offered_chips_never_reach_the_transcript():
    # R-0361
    """Offered answers are dropped (Patrick, 2026-09-21): people type their own
    words. A model that still writes them loses only the offers."""
    data = DiagramData(people=[asdict(Person(id=1, name="Wren"))])
    kept = chips.validate(
        "[[person:1|Wren]] is where it starts. What came next?\n\n"
        "[[ask:the winter after he left]] [[ask:how Wren took it]]",
        data,
        None,
    )
    assert kept == "[[person:1|Wren]] is where it starts. What came next?"


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


def test_every_message_the_page_reads_back_carries_its_kind(web, family, monkeypatch):
    # R-0170
    """The page routes a chip tap by the kind of message it sits in, so the
    kind travels with the message everywhere the page reads one."""
    from btcopilot.tests.conftest import csrf_token

    monkeypatch.setattr(
        "btcopilot.turns.model_for",
        lambda *a, **k: Model(said("Tell me about [[event:10|the move]].")),
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

    stored = web.get(f"/app/sessions/{said_reply['discussion_id']}").get_json()
    assert [(s["kind"], s["cluster_id"]) for s in stored["statements"]] == [
        (StatementKind.Turn.value, None),
        (StatementKind.Turn.value, None),
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
        "btcopilot.turns.model_for",
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
        "btcopilot.turns.model_for",
        lambda *a, **k: Model(
            called(
                ToolName.EditEvent,
                kind="shift",
                date="1994-12-01",
                description="got sick",
                person=1,
                symptom="up", date_certainty="certain",
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

    named = ModelCall.query.filter_by(purpose=Purpose.Summary).all()
    assert [(c.diagram_id, c.turn_id) for c in named] == [
        (discussion.diagram_id, reply["turn_id"])
    ] * 2
    calls = (
        ModelCall.query.filter_by(purpose=Purpose.Coach).order_by(ModelCall.id).all()
    )
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


def test_the_notes_stay_out_of_every_call_and_the_read_that_shows_them_is_offered(
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
    assert all(ToolName.ReadEvents.value in offered for offered in model.offered)


def test_the_coach_reads_an_events_notes_when_it_asks_for_them(discussion, family):
    # R-0446
    _with_notes(family)
    model = Model(
        called(ToolName.ReadEvents, ids=[10], fields=["notes"]),
        said("What happened next?"),
    )
    run(discussion, "What did he say about the house?", model)
    answer = model.histories[-1][-1]["content"][-1]
    assert answer["type"] == "tool_result"
    assert answer["content"].splitlines()[1] == f"  notes: {QUOTE}"


def test_the_coach_is_told_to_end_its_reply_with_a_question():
    # R-0436
    prompt = " ".join(get_agent_prompt().split())
    assert "A reply usually ends with one question in your own words" in prompt
    assert "it always does while the record still lacks any of the minimum data" in prompt


def test_the_coach_is_told_how_to_raise_an_impression():
    # R-0482, R-0618
    prompt = " ".join(get_agent_prompt().split())
    assert "Raise it with `add_impression` before you say it" in prompt
    assert "an impression you have not raised is one you do not say" in prompt
    assert "make or extend the cluster with `edit_cluster`, giving that as its `reason`" in prompt
    assert "a remembered episode, each reported on its own" in prompt
    assert "Never treat shifts as a series or a trend" in prompt
    assert "close it with `set_impression` as `revised`" in prompt


def test_the_coach_is_told_to_give_every_date_its_certainty():
    # R-0482
    prompt = " ".join(get_agent_prompt().split())
    assert "Whenever you add an event or change its date" in prompt
    assert "date_certainty" in prompt
    assert re.search(r"certain (when they gave the exact day|only when the day is known)", prompt)
    assert re.search(r'approximate when they g[ai]ve only the month, as "June 1998"', prompt)
    assert 'unknown when they hedge, as "sometime around 1998"' in prompt


def test_the_coach_is_told_how_to_keep_its_questions():
    # R-0482, R-0618
    prompt = " ".join(get_agent_prompt().split())
    assert "people usually require questions to stimulate their thinking" in prompt
    assert "Family Evaluation, ch. 10" in prompt
    assert "When in doubt, include it rather than leave it out" in prompt
    assert "Never ask again a question the map marks declined" in prompt
    assert "never keep one the record already answers" in prompt
    assert "keep the one whose words ask it best" in prompt
    assert "a thinking question about patterns or meaning" in prompt
    assert "Facts to find (`fact`): anything with a factual answer" in prompt
    assert 'It says "you" and "your" for them' in prompt
    assert "Asking a question and keeping it are one act" in prompt
    assert "What you keep is the question alone" in prompt
    assert "a lead-in, a hedge or a reason stays out of what you keep" in prompt
    assert "Keep it first, then ask it" in prompt
    assert "so the reply is the words of your last round" in prompt
    for tool in (ToolName.AddQuestion, ToolName.SetQuestion, ToolName.ReadQuestions):
        assert f"`{tool.value}`" in prompt



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


def test_a_read_tells_the_page_which_events_it_read(discussion, family):
    # R-0539
    reply = run(
        discussion,
        "Tell me about when he moved out.",
        Model(
            called(ToolName.ReadEvents, cluster="c1"),
            called(ToolName.ReadEvents, ids=[10], fields=["notes"]),
            called(ToolName.ReadPeople),
            said("What happened next?"),
        ),
    )
    reads = [e for e in reply["events"] if e["type"] == EventKind.ToolCall.value]
    assert [e.get("read") for e in reads] == [[10], [10], None]


def test_sitting_title_and_summary_run_on_the_extraction_model(discussion, monkeypatch):
    # R-0388
    asked = []

    def flash(*a, **k):
        asked.append(k["model"])
        return Text("Words", Spent(input=10, output=5), Served(k["model"]))

    monkeypatch.setattr("btcopilot.metered.gemini_text_sync", flash)
    summary = Metered(discussion.user_id, discussion.diagram_id, "t1", Purpose.Summary)
    discussion.update_title(summary)
    discussion.update_summary(summary)
    assert asked == [EXTRACTION_MODEL] * 2
    rows = ModelCall.query.filter_by(purpose=Purpose.Summary).all()
    assert [r.model for r in rows] == [EXTRACTION_MODEL] * 2
