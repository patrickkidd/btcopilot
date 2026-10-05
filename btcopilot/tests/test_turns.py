"""The turn runs in the worker and the page follows it.

The POST stores the words and hands the turn over; everything the coach does
lands in the turn's log, in order, and the page reads that log from wherever it
got to.
"""

import json
import re

import aiohttp
import pytest
from freezegun import freeze_time
from google.genai.errors import ServerError
from mock import patch

import btcopilot

from btcopilot.extensions import db
from btcopilot import record, turnlog, turns
from btcopilot.coachmodel import Refusal
from btcopilot.llmutil import Served, Spent
from btcopilot.coachturn import EmptyReply, run_call
from btcopilot.discussions import SITTING_GAP
from btcopilot.models import Author, Change, Discussion, Statement, TurnEvent
from btcopilot.toolbox import ToolName
from btcopilot.turnlog import TurnEventKind
from btcopilot.schema import ItemKind, Person, asdict
from btcopilot.tests.conftest import (
    Model,
    called,
    calling,
    csrf_token,
    run_then_stop,
    said,
    wrote,
)


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    """Naming a session is its own model call; the turn is what is under test
    here."""
    monkeypatch.setattr(
        "btcopilot.metered.response_text_sync",
        lambda *a, **k: wrote("A session title"),
    )


@pytest.fixture
def token(web):
    return csrf_token(web)


@pytest.fixture
def family(test_user):
    """One person to hang a turn on. Invented names only."""
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren"))]
    data.lastItemId = 1
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def coach(monkeypatch, *scripted):
    monkeypatch.setattr(
        "btcopilot.turns.model_for",
        lambda *a, **k: Model(*scripted),
    )


def post(web, token, statement="My sister is Nell.", **body):
    return web.post(
        "/app/chat",
        json={"statement": statement, **body},
        headers={"X-CSRFToken": token},
    )


def logged(turn_id):
    return [event for _, event in turnlog.read_from(turn_id, 0)]


@pytest.fixture
def anchorage_evening():
    """21:30 on 27 September in Anchorage, where it is still the 27th while UTC
    is already the 28th: the production fault was the coach taking UTC's day.
    Asked for before `web`, so the sign-in cookie is dated by the same clock."""
    with freeze_time("2026-09-28 05:30:00"):
        yield


def told_today(model: Model) -> str:
    """The day the coach was told it is, from the prompt's own line."""
    return re.search(
        r"[Tt]oday(?:'s date)? is (\d{4}-\d{2}-\d{2})", model.systems[0]
    ).group(1)


def test_today_is_the_persons_day_in_the_zone_sent_with_the_message(
    anchorage_evening, web, token, family, monkeypatch
):
    # R-0758
    """An evening in Alaska when UTC is already tomorrow: the coach is told the
    Alaska date, so "turns 70 tomorrow" is not said a day early."""
    model = Model(said("Go on."))
    monkeypatch.setattr("btcopilot.turns.model_for", lambda *a, **k: model)
    response = post(web, token, "Dad turns 70 tomorrow.", time_zone="America/Anchorage")
    assert response.status_code == 202
    assert told_today(model) == "2026-09-27"


@pytest.mark.parametrize(
    "body",
    [{}, {"time_zone": "Mars/Olympus"}, {"time_zone": 7}],
    ids=["none", "unknown", "not-a-name"],
)
def test_a_message_with_no_zone_or_one_the_server_does_not_know_gets_the_servers_day(
    anchorage_evening, web, token, family, monkeypatch, body
):
    # R-0758
    """The server's own day, UTC on the box, as before the zone was sent."""
    model = Model(said("Go on."))
    monkeypatch.setattr("btcopilot.turns.model_for", lambda *a, **k: model)
    response = post(web, token, "Dad turns 70 tomorrow.", **body)
    assert response.status_code == 202
    assert told_today(model) == "2026-09-28"


def test_the_task_run_with_no_zone_keeps_the_servers_day(
    anchorage_evening, discussion, family, monkeypatch
):
    # R-0758
    """A resumed turn is re-run from the stored words, with no zone: its day is
    the server's own, UTC on the box, as it always was."""
    model = Model(said("Go on."))
    monkeypatch.setattr("btcopilot.turns.model_for", lambda *a, **k: model)
    said_statement = Statement(
        discussion_id=discussion.id,
        text="Dad turns 70 tomorrow.",
        speaker=discussion.chat_user_speaker,
        order=discussion.next_order(),
    )
    db.session.add(said_statement)
    db.session.commit()
    turnlog.start(discussion.id, "t1")
    turns.run("t1", discussion.id, said_statement.id, resume=True)
    assert told_today(model) == "2026-09-28"


def test_a_question_asked_in_the_evening_in_anchorage_is_dated_that_day(
    anchorage_evening, web, token, family, monkeypatch
):
    # R-0758
    coach(
        monkeypatch,
        calling(
            (
                ToolName.AddQuestion,
                {
                    "text": "Who is older, you or Nell?",
                    "kind": "thought",
                    "state": "asked",
                },
            )
        ),
        said("Who is older, you or Nell?"),
    )
    body = post(web, token, time_zone="America/Anchorage").get_json()
    assert logged(body["turn_id"])[-1]["type"] == TurnEventKind.Done.value
    db.session.refresh(family)
    assert [q["asked_at"] for q in family.get_diagram_data().questions] == [
        "2026-09-27"
    ]


def test_a_follow_up_for_tomorrow_in_anchorage_is_not_refused_as_today(
    anchorage_evening, web, token, family, monkeypatch
):
    # R-0758
    """The 28th is tomorrow in Anchorage at 21:30 on the 27th; UTC's clock
    already says the 28th and would refuse it as not after today."""
    coach(
        monkeypatch,
        called(ToolName.FollowUp, when="2026-09-28", question="How was the party?"),
        said("I will ask tomorrow."),
    )
    body = post(web, token, time_zone="America/Anchorage").get_json()
    events = logged(body["turn_id"])
    assert events[0]["type"] == TurnEventKind.ToolCall.value
    assert "not after today" not in events[0]["result"]
    assert events[-1]["type"] == TurnEventKind.Done.value


def test_the_turn_is_handed_over_and_the_post_answers_at_once(
    web, token, family, monkeypatch
):
    # R-0369
    coach(monkeypatch, said("Tell me about Nell."))
    response = post(web, token)
    assert response.status_code == 202

    body = response.get_json()
    assert set(body) == {"turn_id", "discussion_id", "statement_id"}
    assert db.session.get(Statement, body["statement_id"]).text == "My sister is Nell."


def test_the_turn_writes_what_it_did_in_order_and_ends_in_done(
    web, token, family, monkeypatch
):
    # R-0369
    coach(
        monkeypatch,
        called(ToolName.EditPerson, name="Nell"),
        said("Added Nell."),
    )
    body = post(web, token).get_json()

    events = logged(body["turn_id"])
    assert [e["type"] for e in events] == [
        TurnEventKind.ToolCall.value,
        TurnEventKind.RecordPatch.value,
        TurnEventKind.Text.value,
        TurnEventKind.Done.value,
    ]
    assert events[-1]["statement"] == "Added Nell."
    assert events[-1]["session"]["id"] == body["discussion_id"]


@pytest.mark.parametrize(
    "down",
    [
        ServerError(503, {"error": {"message": "unavailable"}}),
        aiohttp.ClientConnectionError("unreachable"),
        TimeoutError(),
    ],
    ids=["error", "unreachable", "timeout"],
)
def test_a_title_call_that_fails_leaves_the_reply_and_the_sitting_unnamed(
    web, token, family, monkeypatch, down
):
    # R-0097, R-0661
    coach(monkeypatch, said("Tell me about Nell."))
    with patch("btcopilot.metered.gemini_text_sync", side_effect=down):
        body = post(web, token).get_json()

    discussion = db.session.get(Discussion, body["discussion_id"])
    assert [s.text for s in discussion.statements] == [
        "My sister is Nell.",
        "Tell me about Nell.",
    ]
    assert discussion.title is None
    assert logged(body["turn_id"])[-1]["type"] == TurnEventKind.Done.value


def test_a_sitting_is_not_named_until_its_summary_is_written(
    web, token, family, monkeypatch
):
    # R-0097, R-0661
    coach(monkeypatch, said("Tell me about Nell."), said("Go on."))
    calls = [wrote("A summary"), TimeoutError(), wrote("A summary"), wrote("Nell")]
    with patch("btcopilot.metered.gemini_text_sync", side_effect=calls):
        body = post(web, token).get_json()
        discussion = db.session.get(Discussion, body["discussion_id"])
        assert discussion.title is None

        post(web, token, "She is older.")
    db.session.refresh(discussion)
    assert (discussion.title, discussion.summary) == ("Nell", "A summary")


def test_the_sitting_before_is_titled_again_from_all_of_it_when_the_next_opens(
    web, token, family, monkeypatch
):
    # R-0097, R-0662
    coach(monkeypatch, said("Tell me more."), said("Go on."), said("And then?"))
    first = post(web, token, "My dad called last night.").get_json()["discussion_id"]
    for statement in Statement.query:
        statement.created_at -= 2 * SITTING_GAP
    db.session.commit()
    titles = [
        wrote("A summary"),
        wrote("The move"),
        wrote("Conflict with father over care of mother"),
    ]
    with patch("btcopilot.metered.gemini_text_sync", side_effect=titles) as gemini:
        second = post(web, token, "We moved in May.").get_json()["discussion_id"]
        post(web, token, "It was hard.")

    assert gemini.call_count == 3
    assert "My dad called last night." in gemini.call_args.kwargs["prompt"]
    assert second != first
    assert db.session.get(Discussion, second).title == "The move"
    assert (
        db.session.get(Discussion, first).title
        == "Conflict with father over care of mother"
    )


def test_the_turns_done_row_carries_the_release_it_ran_on(
    web, token, family, monkeypatch
):
    # R-0595
    coach(monkeypatch, said("Go on."))
    body = post(web, token).get_json()
    done = TurnEvent.query.filter_by(
        turn_id=body["turn_id"], kind=TurnEventKind.Done.value
    ).one()
    assert done.payload["release"] == btcopilot.__version__


def test_a_turn_that_breaks_ends_in_failed_and_stores_no_coach_words(
    web, token, family, monkeypatch
):
    # R-0182
    """A coach that says nothing is a bare bubble on the page, so the turn
    fails — and the page is told in a sentence, not left waiting."""
    coach(monkeypatch, said(""))
    with patch("btcopilot.turns.enqueue"):
        body = post(web, token).get_json()
    with pytest.raises(EmptyReply):
        turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])

    assert logged(body["turn_id"])[-1] == {
        "type": TurnEventKind.Failed.value,
        "message": turns.BROKE,
    }
    discussion = Discussion.query.one()
    assert [s.text for s in discussion.statements] == ["My sister is Nell."]
    assert turnlog.running(discussion.id) is None


class Refuses:
    """A coach every model of which declines the message."""

    model = "claude-opus-5-5"

    def __init__(self):
        self.calls = 0

    def turn(self, system, messages, tools, turn_id=""):
        self.calls += 1
        raise Refusal("refused", "bio", Served(self.model), Spent())
        yield


def test_a_refused_turn_says_so_in_the_coachs_voice_and_is_not_retried(
    web, token, family, monkeypatch
):
    # R-0410
    refuses = Refuses()
    monkeypatch.setattr("btcopilot.turns.model_for", lambda *a, **k: refuses)
    with patch("btcopilot.turns.enqueue"):
        body = post(web, token).get_json()
    turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])

    assert refuses.calls == 1
    assert logged(body["turn_id"])[-1] == {
        "type": TurnEventKind.Refused.value,
        "message": turns.REFUSED,
    }
    assert turns.REFUSED == (
        "I can't take that one up here. Say it another way, or tell me what "
        "happened next."
    )
    discussion = Discussion.query.one()
    assert turnlog.running(discussion.id) is None


def test_a_hold_left_by_a_dead_worker_runs_out(web, token, family, monkeypatch):
    # R-0182
    """A worker that dies mid-turn says nothing. The hold on the session has to
    run out on its own, or the reader can never send anything again."""
    coach(monkeypatch, said("Still going."), said("Back to you."))
    monkeypatch.setattr(turnlog, "RUNNING_TTL", 0)
    with patch("btcopilot.turns.enqueue"):
        body = post(web, token).get_json()
    assert turnlog.running(body["discussion_id"]) is None

    assert post(web, token, "And another thing.").status_code == 202


def test_the_session_says_which_turn_is_running(web, token, family, monkeypatch):
    # R-0369
    coach(monkeypatch, said("Still going."))
    with patch("btcopilot.turns.enqueue"):
        body = post(web, token).get_json()

    session = web.get(f"/app/sessions/{body['discussion_id']}").get_json()
    assert session["turn"] == body["turn_id"]

    turnlog.clear(body["discussion_id"])
    assert web.get(f"/app/sessions/{body['discussion_id']}").get_json()["turn"] is None


def read(response) -> list[dict]:
    """The events an SSE response carried, in order."""
    out = []
    for block in response.get_data(as_text=True).split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                out.append(json.loads(line[len("data: ") :]))
    return out


def test_the_stream_replays_from_where_the_page_got_to(web, token, family, monkeypatch):
    # R-0369
    coach(
        monkeypatch,
        called(ToolName.EditPerson, name="Nell"),
        said("Added Nell."),
    )
    body = post(web, token).get_json()

    whole = web.get(f"/app/turns/{body['turn_id']}/events")
    assert whole.status_code == 200
    assert [e["type"] for e in read(whole)] == [
        TurnEventKind.ToolCall.value,
        TurnEventKind.RecordPatch.value,
        TurnEventKind.Text.value,
        TurnEventKind.Done.value,
    ]

    rest = web.get(
        f"/app/turns/{body['turn_id']}/events", headers={"Last-Event-ID": "2"}
    )
    assert [e["type"] for e in read(rest)] == [
        TurnEventKind.Text.value,
        TurnEventKind.Done.value,
    ]


def test_a_page_that_stops_listening_mid_turn_leaves_the_turn_to_finish(
    web, token, family, monkeypatch
):
    # R-0369
    coach(monkeypatch, said("Tell me about Nell."))
    with patch("btcopilot.turns.enqueue"):
        body = post(web, token).get_json()
    turnlog.append(body["turn_id"], {"type": TurnEventKind.Text.value, "text": "Tell"})

    stream = web.get(f"/app/turns/{body['turn_id']}/events", buffered=False)
    assert b"Tell" in next(iter(stream.response))
    stream.close()

    reply = turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])
    assert reply["statement"] == "Tell me about Nell."
    discussion = db.session.get(Discussion, body["discussion_id"])
    assert [s.text for s in discussion.statements] == [
        "My sister is Nell.",
        "Tell me about Nell.",
    ]
    assert (
        TurnEvent.query.filter_by(
            turn_id=body["turn_id"], kind=TurnEventKind.Done.value
        ).count()
        == 1
    )
    assert turnlog.running(discussion.id) is None


def test_stop_ends_a_turn_before_its_next_model_call_with_no_reply(
    web, token, family, monkeypatch
):
    # R-0636
    coach(monkeypatch, said("Tell me about Nell."))
    with patch("btcopilot.turns.enqueue"):
        body = post(web, token).get_json()
    turn_id = body["turn_id"]
    response = web.post(f"/app/turns/{turn_id}/stop", headers={"X-CSRFToken": token})
    assert response.status_code == 202

    with patch("btcopilot.shadow.start") as shadowed:
        turns.run(turn_id, body["discussion_id"], body["statement_id"])
    shadowed.assert_not_called()
    discussion = db.session.get(Discussion, body["discussion_id"])
    assert [s.text for s in discussion.statements] == ["My sister is Nell."]
    done = logged(turn_id)[-1]
    assert (done["type"], done["stopped"]) == (TurnEventKind.Done.value, True)
    assert turnlog.running(discussion.id) is None
    again = web.post(f"/app/turns/{turn_id}/stop", headers={"X-CSRFToken": token})
    assert again.status_code == 409


def test_a_turn_stopped_between_two_tool_calls_takes_its_edits_back(
    web, token, family, monkeypatch
):
    # R-0636
    coach(
        monkeypatch,
        calling(
            (ToolName.EditPerson, {"name": "Nell"}),
            (ToolName.EditPerson, {"name": "Finn"}),
        ),
        said("Added both."),
    )

    monkeypatch.setattr("btcopilot.coachturn.run_call", run_then_stop)
    body = post(web, token).get_json()

    db.session.refresh(family)
    assert [p["name"] for p in family.get_diagram_data().people] == ["Wren"]
    changes = Change.query.filter_by(diagram_id=family.id).order_by(Change.id).all()
    assert [c.turn_id for c in changes] == [
        body["turn_id"],
        f"undo:{body['turn_id']}",
    ]
    discussion = db.session.get(Discussion, body["discussion_id"])
    assert [s.text for s in discussion.statements] == ["My sister is Nell."]
    done = logged(body["turn_id"])[-1]
    assert (done["type"], done["stopped"], done["version"]) == (
        TurnEventKind.Done.value,
        True,
        family.version,
    )
    assert "conflict" not in done
    kept = TurnEvent.query.filter_by(turn_id=body["turn_id"]).all()
    assert [k.kind for k in kept] == [TurnEventKind.Done.value]


def test_a_turn_stopped_while_its_sitting_is_named_keeps_no_reply(
    web, token, family, monkeypatch
):
    # R-0636
    coach(monkeypatch, said("Tell me about Nell."))

    def stop(turn):
        turnlog.halt(turn.turn_id)

    monkeypatch.setattr("btcopilot.coachturn.CoachTurn._title", stop)
    body = post(web, token).get_json()

    discussion = db.session.get(Discussion, body["discussion_id"])
    assert [s.text for s in discussion.statements] == ["My sister is Nell."]
    done = logged(body["turn_id"])[-1]
    assert (done["type"], done["stopped"]) == (TurnEventKind.Done.value, True)


def test_a_stopped_turn_keeps_edits_changed_since_and_says_so(
    web, token, family, monkeypatch
):
    # R-0636
    coach(monkeypatch, called(ToolName.EditPerson, name="Nell"), said("Added Nell."))

    def run_change_stop(toolbox, call):
        answer = run_call(toolbox, call)
        nell = {"item_kind": ItemKind.Person.value, "item_id": 2, "field": "name"}
        record.apply(
            family.id, [dict(nell, after="Nelly")], author=Author.User, turn_id="by-hand"
        )
        turnlog.halt(toolbox.turn_id)
        return answer

    monkeypatch.setattr("btcopilot.coachturn.run_call", run_change_stop)
    body = post(web, token).get_json()

    db.session.refresh(family)
    assert [p["name"] for p in family.get_diagram_data().people] == ["Wren", "Nelly"]
    done = logged(body["turn_id"])[-1]
    assert (done["stopped"], done["version"]) == (True, family.version)
    assert "Nelly" in done["conflict"]


def test_another_users_turn_is_not_found(web, token, family, monkeypatch, test_user_2):
    # R-0080
    coach(monkeypatch, said("Tell me about Nell."))
    body = post(web, token).get_json()
    discussion = db.session.get(Discussion, body["discussion_id"])
    discussion.user_id = test_user_2.id
    db.session.commit()

    assert web.get(f"/app/turns/{body['turn_id']}/events").status_code == 404


def test_a_turn_nobody_started_is_not_found(web, token):
    # R-0453
    assert web.get("/app/turns/nosuchturn/events").status_code == 404


def test_the_task_can_be_run_on_its_own(discussion, family, monkeypatch):
    # R-0369
    """The worker calls the task with ids, and what it returns is the reply the
    page would have been handed before."""
    coach(monkeypatch, said("Go on."))
    said_statement = Statement(
        discussion_id=discussion.id,
        text="My sister is Nell.",
        speaker=discussion.chat_user_speaker,
        order=discussion.next_order(),
    )
    db.session.add(said_statement)
    db.session.commit()
    turnlog.start(discussion.id, "t1")

    reply = turns.run("t1", discussion.id, said_statement.id)
    assert reply["statement"] == "Go on."
    assert reply["turn_id"] == "t1"


def test_the_log_hands_a_watcher_what_lands_after_it_started(turn_log):
    # R-0369
    """Following is how the page sees a turn that is still running: what is
    appended after it attaches reaches it without asking again."""
    watching = turnlog.subscribe("t2")
    turnlog.append("t2", {"type": TurnEventKind.Text.value, "text": "a word"})

    seen = next(carried for carried in watching if carried is not None)
    assert seen == (1, {"type": TurnEventKind.Text.value, "text": "a word"})


def test_an_event_kind_that_does_not_exist_is_refused_and_the_turn_goes_on(
    web, token, family, monkeypatch
):
    # R-0075
    coach(
        monkeypatch,
        called(
            ToolName.EditEvent,
            kind="symptom",
            date="2019-03-01",
            date_certainty="certain",
            person=1,
            description="Headaches",
        ),
        said("Noted the headaches."),
    )
    response = post(web, token)
    assert response.status_code == 202

    body = response.get_json()
    events = logged(body["turn_id"])
    assert "is not one of the event kinds" in events[0]["result"]
    assert "shift" in events[0]["result"]
    assert events[-1]["type"] == TurnEventKind.Done.value
    assert family.get_diagram_data().events == []


def test_an_evidence_kind_that_does_not_exist_is_refused_and_the_turn_goes_on(
    web, token, family, monkeypatch
):
    # R-0075
    coach(
        monkeypatch,
        calling(
            (
                ToolName.AddImpression,
                {
                    "text": "Wren goes quiet when things get tense.",
                    "state": "held",
                    "evidence": [{"kind": "feeling", "id": "1"}],
                },
            )
        ),
        said("Go on."),
    )
    response = post(web, token)
    assert response.status_code == 202

    body = response.get_json()
    events = logged(body["turn_id"])
    assert "is not one of the evidence kinds" in events[0]["result"]
    assert events[-1]["type"] == TurnEventKind.Done.value
    assert family.get_diagram_data().questions == []
