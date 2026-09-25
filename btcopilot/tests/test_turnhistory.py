"""Every coach turn's tool calls are kept, shown on the thread in every session,
given back to the coach, and a failed turn goes on from where it stopped.

Invented names only.
"""

import pytest
from mock import patch

from btcopilot.extensions import db
from btcopilot import record, turnlog, turns
from btcopilot.coachturn import NOT_KEPT
from btcopilot.models import Author, Change, Discussion, Statement, TurnEvent
from btcopilot.schema import ItemKind, Person, asdict
from btcopilot.toolbox import ToolName
from btcopilot.turnlog import TurnEventKind
from btcopilot.tests.conftest import Model, called, csrf_token, said


NELL = [{"name": "edit_person", "args": {"name": "Nell"}, "names": {"it": "Nell"}}]


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.models.discussion.response_text_sync",
        lambda *a, **k: "A session title",
    )


@pytest.fixture
def token(web):
    return csrf_token(web)


@pytest.fixture
def family(test_user):
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren"))]
    data.lastItemId = 1
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


class Breaks(Model):
    """A coach that runs its script and then fails, the way a turn does when
    the model's service goes down halfway through."""

    def turn(self, system, messages, tools, turn_id=""):
        if not self.turns:
            raise RuntimeError("the model went away")
        return (yield from super().turn(system, messages, tools, turn_id))


def coach(monkeypatch, model):
    monkeypatch.setattr("btcopilot.coachturn.CoachModel", lambda *a, **k: model)
    return model


def post(web, token, statement="My sister is Nell."):
    return web.post(
        "/app/chat", json={"statement": statement}, headers={"X-CSRFToken": token}
    )


def resume(web, token, turn_id):
    return web.post(f"/app/turns/{turn_id}/resume", headers={"X-CSRFToken": token})


def fail(web, token, monkeypatch) -> dict:
    """A turn that adds Nell and then breaks before it answers."""
    coach(monkeypatch, Breaks(called(ToolName.EditPerson, name="Nell")))
    with patch("btcopilot.turns.enqueue"):
        body = post(web, token).get_json()
    with pytest.raises(RuntimeError):
        turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])
    return body


def statements(web, discussion_id) -> list[dict]:
    return web.get(f"/app/sessions/{discussion_id}").get_json()["statements"]


def nells(family) -> int:
    db.session.expire_all()
    return sum(p.get("name") == "Nell" for p in family.get_diagram_data().people)


def test_a_replys_tool_calls_are_on_the_thread_after_the_live_log_is_gone(
    web, token, family, monkeypatch
):
    # R-0478
    coach(
        monkeypatch,
        Model(called(ToolName.EditPerson, name="Nell"), said("Nell is in.")),
    )
    body = post(web, token).get_json()
    turnlog.forget(body["turn_id"])

    shown = statements(web, body["discussion_id"])
    assert [s["role"] for s in shown] == ["user", "coach"]
    assert shown[1]["tools"] == NELL
    assert shown[0]["tools"] == []


def test_a_failed_turn_keeps_its_edits_and_shows_them_on_the_words_that_asked(
    web, token, family, monkeypatch
):
    # R-0477, R-0478
    body = fail(web, token, monkeypatch)

    assert nells(family) == 1
    change = Change.query.filter_by(turn_id=body["turn_id"]).one()
    assert change.statement_id == body["statement_id"]
    shown = statements(web, body["discussion_id"])
    assert len(shown) == 1
    assert shown[0]["unfinished"] is True
    assert shown[0]["failure"] == turns.BROKE
    assert shown[0]["tools"] == NELL


def test_trying_again_goes_on_from_where_it_stopped_and_stores_no_new_words(
    web, token, family, monkeypatch
):
    # R-0477
    body = fail(web, token, monkeypatch)
    finishes = coach(monkeypatch, Model(said("Nell is your sister, then.")))

    response = resume(web, token, body["turn_id"])
    assert response.status_code == 202
    assert response.get_json()["statement_id"] == body["statement_id"]

    history = finishes.histories[0]
    assert history[-2]["role"] == "assistant"
    assert history[-2]["content"][0]["name"] == "edit_person"
    assert history[-1]["content"][0]["content"] == "Added person 2."
    assert nells(family) == 1

    live = [event for _, event in turnlog.read_from(body["turn_id"], 0)]
    assert live[0] == {
        "type": TurnEventKind.ToolCall.value,
        "name": "edit_person",
        "args": {"name": "Nell"},
        "names": {"it": "Nell"},
        "result": "Added person 2.",
    }
    assert live[-1]["type"] == TurnEventKind.Done.value

    shown = statements(web, body["discussion_id"])
    assert [s["text"] for s in shown] == [
        "My sister is Nell.",
        "Nell is your sister, then.",
    ]
    assert shown[0]["unfinished"] is False
    assert shown[1]["tools"] == NELL
    change = Change.query.filter_by(turn_id=body["turn_id"]).one()
    assert change.statement_id == shown[1]["id"]


def test_only_the_last_unanswered_message_can_be_tried_again(
    web, token, family, monkeypatch
):
    # R-0477
    body = fail(web, token, monkeypatch)
    coach(monkeypatch, Model(said("Go on.")))
    later = post(web, token, "And my brother is Ash.").get_json()

    assert resume(web, token, body["turn_id"]).status_code == 409
    assert resume(web, token, later["turn_id"]).status_code == 409
    assert resume(web, token, "nosuchturn").status_code == 404


def test_another_users_failed_turn_is_not_found(
    web, token, family, monkeypatch, test_user_2
):
    # R-0080
    body = fail(web, token, monkeypatch)
    discussion = db.session.get(Discussion, body["discussion_id"])
    discussion.user_id = test_user_2.id
    db.session.commit()

    assert resume(web, token, body["turn_id"]).status_code == 404


def test_the_coach_is_given_the_tool_calls_its_earlier_turns_made(
    web, token, family, monkeypatch
):
    # R-0479
    coach(
        monkeypatch,
        Model(
            called(ToolName.ReadPeople),
            called(ToolName.EditPerson, name="Nell"),
            said("Nell is in."),
        ),
    )
    post(web, token)
    second = coach(monkeypatch, Model(said("Tell me about Ash.")))
    post(web, token, "My brother is Ash.")

    history = second.histories[0]
    assert [m["role"] for m in history] == [
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
    ]
    asked, answered = history[1]["content"], history[2]["content"]
    assert [b["name"] for b in asked] == ["read_people", "edit_person"]
    assert [b["content"] for b in answered] == [NOT_KEPT, "Added person 2."]
    assert [b["tool_use_id"] for b in answered] == [b["id"] for b in asked]
    assert history[3]["content"] == "Nell is in."


def test_a_turns_events_are_kept_in_order_and_end_in_how_it_ended(
    web, token, family, monkeypatch
):
    # R-0478
    body = fail(web, token, monkeypatch)

    kinds = [
        row.kind
        for row in TurnEvent.query.filter_by(turn_id=body["turn_id"]).order_by(
            TurnEvent.seq
        )
    ]
    assert kinds == [
        TurnEventKind.ToolCall.value,
        TurnEventKind.Step.value,
        TurnEventKind.Failed.value,
    ]
    assert Statement.query.filter_by(turn_id=body["turn_id"]).count() == 1


def test_a_line_names_what_the_call_touched_as_it_was_when_it_was_made(
    web, token, family, monkeypatch
):
    # R-0478
    coach(
        monkeypatch,
        Model(
            called(ToolName.EditPerson, id=1, version=family.version, name="Wrenna"),
            called(ToolName.EditEvent, kind="birth", child=1, date="1931-01-01"),
            said("Wrenna, born 1931."),
        ),
    )
    body = post(web, token).get_json()
    record.apply(
        family.id,
        [{"item_kind": ItemKind.Person.value, "item_id": 1, "field": None, "after": None}],
        author=Author.User,
        turn_id="by-hand",
    )

    tools = statements(web, body["discussion_id"])[1]["tools"]
    assert [t["names"] for t in tools] == [
        {"it": "Wren"},
        {"it": "Wrenna's birth", "child": "Wrenna"},
    ]


def test_a_call_kept_without_names_is_named_from_the_record_as_it_is_now(
    web, token, family, monkeypatch
):
    # R-0478
    coach(monkeypatch, Model(said("Wren, then.")))
    body = post(web, token).get_json()
    for seq, args in enumerate(({"id": 1, "name": "Wrenna"}, {"id": 9, "name": "Ash"})):
        event = {"type": TurnEventKind.ToolCall.value, "name": "edit_person", "args": args}
        db.session.add(
            TurnEvent(
                turn_id=body["turn_id"],
                discussion_id=body["discussion_id"],
                seq=100 + seq,
                kind=event["type"],
                payload=event,
            )
        )
    db.session.commit()

    tools = statements(web, body["discussion_id"])[1]["tools"]
    assert [t["names"] for t in tools] == [
        {"it": "Wren"},
        {"it": "a person no longer in the record"},
    ]
