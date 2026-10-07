"""Every coach turn's tool calls are kept and shown on the thread in every
session, a failed turn goes on from where it stopped, and the coach is given the
family's latest words from every session rather than its past tool calls.

Invented names only.
"""

import datetime

import pytest
from mock import patch

from btcopilot.extensions import db
from btcopilot import record, turnlog, turns
from btcopilot.coachmodel import CACHE
from btcopilot.coachturn import run_call
from btcopilot.discussions import open_session
from btcopilot.models import (
    Author,
    Change,
    Discussion,
    ShadowTurn,
    Statement,
    TurnEvent,
)
from btcopilot.schema import ItemKind, Person, asdict
from btcopilot.toolbox import ToolName
from btcopilot.turnlog import TurnEventKind
from btcopilot.tests.conftest import (
    Model,
    called,
    csrf_token,
    run_then_stop,
    said,
    wrote,
)


NELL = [
    {
        "name": "edit_person",
        "args": {"name": "Nell"},
        "names": {"it": "Nell"},
        "refusal": None,
    }
]


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.metered.response_text_sync",
        lambda *a, **k: wrote("A session title"),
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
    monkeypatch.setattr("btcopilot.turns.model_for", lambda *a, **k: model)
    return model


def post(web, token, statement="My sister is Nell."):
    return web.post(
        "/app/chat", json={"statement": statement}, headers={"X-CSRFToken": token}
    )


def say_in(web, token, discussion_id: int, statement: str):
    return web.post(
        f"/app/sessions/{discussion_id}/statements",
        json={"statement": statement},
        headers={"X-CSRFToken": token},
    )


def words(message: dict) -> str:
    content = message["content"]
    return content if isinstance(content, str) else " ".join(b["text"] for b in content)


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


def test_a_coach_reply_says_how_many_shadow_replies_its_turn_has(
    web, token, family, test_user, monkeypatch
):
    # R-0636
    coach(monkeypatch, Model(said("Tell me about Nell."), said("How much older?")))
    body = post(web, token).get_json()
    post(web, token, "She is older.")
    for model in ("sonnet", "gemini-pro"):
        db.session.add(
            ShadowTurn(
                turn_id=body["turn_id"],
                user_id=test_user.id,
                diagram_id=family.id,
                discussion_id=body["discussion_id"],
                statement_id=body["statement_id"],
                model=model,
            )
        )
    db.session.commit()

    shown = statements(web, body["discussion_id"])
    assert [s["feedback"] for s in shown] == [0, 2, 0, 0]


def test_the_words_of_a_stopped_turn_say_so_on_the_thread(
    web, token, family, monkeypatch
):
    # R-0636
    coach(
        monkeypatch,
        Model(
            called(ToolName.EditPerson, name="Nell"),
            called(ToolName.EditPerson, name="Finn"),
            said("Tell me about Finn."),
        ),
    )

    def run_change_stop(toolbox, call):
        answer = run_then_stop(toolbox, call)
        finn = {"item_kind": ItemKind.Person.value, "item_id": 2, "field": "name"}
        record.apply(
            family.id, [dict(finn, after="Finley")], author=Author.User, turn_id="by-hand"
        )
        return answer

    monkeypatch.setattr("btcopilot.coachturn.run_call", run_then_stop)
    body = post(web, token).get_json()
    monkeypatch.setattr("btcopilot.coachturn.run_call", run_change_stop)
    post(web, token, "My brother is Finn.")
    monkeypatch.setattr("btcopilot.coachturn.run_call", run_call)
    post(web, token, "He is older.")

    shown = statements(web, body["discussion_id"])
    assert [(s["role"], s["stopped"]) for s in shown] == [
        ("user", True),
        ("user", True),
        ("user", False),
        ("coach", False),
    ]
    assert shown[0]["conflict"] is None
    assert "Finley" in shown[1]["conflict"]


def test_a_refused_call_stays_on_the_thread_with_why_in_plain_words(
    web, token, family, monkeypatch
):
    # R-0478
    read = family.version
    record.apply(
        family.id,
        [{"item_kind": ItemKind.Person.value, "item_id": 1, "field": "name", "after": "Wrenn"}],
        author=Author.User,
        turn_id="by-hand",
    )
    coach(
        monkeypatch,
        Model(
            called(ToolName.Show, kind="triangle"),
            called(ToolName.EditPerson, id=1, version=read, name="Wrenna"),
            called(
                ToolName.EditEvent,
                kind="noted",
                person=1,
                date="2019-03-01",
                date_certainty="certain",
            ),
            said("I cannot do any of that."),
        ),
    )
    body = post(web, token, "Show me the triangle.").get_json()
    turnlog.forget(body["turn_id"])

    tools = statements(web, body["discussion_id"])[1]["tools"]
    assert tools[0] == {
        "name": "show",
        "args": {"kind": "triangle"},
        "names": {},
        "refusal": "No people were named.",
    }
    assert [t["refusal"] for t in tools[1:]] == [
        "The diagram had changed since it was read; read it again.",
        "A noted event needs a few words saying what happened.",
    ]


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
        "refusal": None,
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


def test_the_coach_is_given_the_words_but_none_of_its_earlier_tool_calls(
    web, token, family, monkeypatch
):
    # R-0481
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
    assert [m["role"] for m in history] == ["user", "assistant", "user"]
    assert history[1]["content"] == [
        {"type": "text", "text": "Nell is in.", "cache_control": CACHE}
    ]
    assert "tool_use" not in str(history)


def test_the_latest_words_come_from_every_one_of_the_users_sessions_on_the_family(
    web, token, family, monkeypatch, test_user, test_user_2
):
    # R-0520
    monkeypatch.setattr("btcopilot.coachturn.RECENT_STATEMENTS", 3)
    monkeypatch.setattr("btcopilot.coachturn.RECENT_STEP", 1)
    coach(monkeypatch, Model(said("Who is Nell?")))
    post(web, token)
    later = open_session(test_user, family)
    theirs = open_session(test_user_2, family)
    db.session.add(
        Statement(
            discussion_id=theirs.id,
            text="Words from someone else's session.",
            speaker_id=theirs.chat_user_speaker_id,
            order=0,
        )
    )
    db.session.commit()
    coach(monkeypatch, Model(said("How old is Ash?")))
    say_in(web, token, later.id, "My brother is Ash.")
    third = coach(monkeypatch, Model(said("Ten, then.")))
    say_in(web, token, later.id, "He is ten.")

    history = third.histories[0]
    assert [words(m) for m in history[:-1]] == [
        "Hello",
        "Who is Nell?",
        "My brother is Ash.",
        "How old is Ash?",
    ]
    assert words(history[-1]).endswith("He is ten.")


def test_the_chat_read_back_moves_on_in_steps_so_it_stays_cached(
    web, token, family, monkeypatch
):
    # R-0595
    monkeypatch.setattr("btcopilot.coachturn.RECENT_STATEMENTS", 4)
    monkeypatch.setattr("btcopilot.coachturn.RECENT_STEP", 4)
    model = coach(monkeypatch, Model(*(said(f"Reply {n}.") for n in range(1, 6))))
    for n in range(1, 6):
        post(web, token, f"Message {n}.")
    third, fourth, fifth = model.histories[2:5]

    def settled(history: list[dict]) -> list[tuple]:
        return [(m["role"], words(m)) for m in history[:-1]]

    assert settled(fourth)[: len(third) - 1] == settled(third)
    assert words(fifth[0]) == "Message 3."
    today = datetime.date.today().isoformat()
    assert "Record version" in words(fourth[-1]) and today in words(fourth[-1])
    assert not any(
        "Record version" in words(m) or today in words(m) for m in fourth[:-1]
    )


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
            called(ToolName.EditEvent, kind="birth", child=1, date="1931-01-01", date_certainty="certain"),
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
        {"it": "Wrenna \u00b7 born", "child": "Wrenna"},
    ]



def test_a_kept_event_call_is_named_by_the_shared_label_even_from_before_it(
    web, token, family, monkeypatch
):
    # R-0478
    coach(
        monkeypatch,
        Model(
            called(
                ToolName.EditEvent,
                kind="death",
                person=1,
                date="1990-07-04",
                date_certainty="approximate",
                description="died, possibly around July 4",
            ),
            said("Wren died around 1990."),
        ),
    )
    body = post(web, token).get_json()
    line = "Wren · died, possibly around July 4"
    assert statements(web, body["discussion_id"])[1]["tools"][0]["names"]["it"] == line

    kept = TurnEvent.query.filter_by(
        discussion_id=body["discussion_id"], kind=TurnEventKind.ToolCall.value
    ).one()
    kept.payload = {**kept.payload, "names": {**kept.payload["names"], "it": "Wren's death"}}
    db.session.commit()
    assert statements(web, body["discussion_id"])[1]["tools"][0]["names"]["it"] == line
