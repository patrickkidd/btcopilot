"""The turn runs in the worker and the page follows it.

The POST stores the words and hands the turn over; everything the coach does
lands in the turn's log, in order, and the page reads that log from wherever it
got to.
"""

import json

import pytest
from mock import patch

from btcopilot.extensions import db
from btcopilot import turnlog, turns
from btcopilot.coachmodel import Refusal
from btcopilot.coachturn import EmptyReply
from btcopilot.models import Discussion, Statement
from btcopilot.toolbox import ToolName
from btcopilot.turnlog import TurnEventKind
from btcopilot.schema import Person, asdict
from btcopilot.tests.conftest import Model, called, csrf_token, said


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    """Naming a session is its own model call; the turn is what is under test
    here."""
    monkeypatch.setattr(
        "btcopilot.models.discussion.response_text_sync",
        lambda *a, **k: "A session title",
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
        "btcopilot.coachturn.CoachModel",
        lambda *a, **k: Model(*scripted),
    )


def post(web, token, statement="My sister is Nell."):
    return web.post(
        "/app/chat", json={"statement": statement}, headers={"X-CSRFToken": token}
    )


def logged(turn_id):
    return [event for _, event in turnlog.read_from(turn_id, 0)]


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
        raise Refusal("refused", "bio")
        yield


def test_a_refused_turn_says_so_in_the_coachs_voice_and_is_not_retried(
    web, token, family, monkeypatch
):
    # R-0410
    refuses = Refuses()
    monkeypatch.setattr(
        "btcopilot.coachturn.CoachModel", lambda *a, **k: refuses
    )
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
