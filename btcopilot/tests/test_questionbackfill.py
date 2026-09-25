"""The one pass back over past sessions that fills in the questions asked in
them: each question keeps the message and the day it was asked, words not in
that message are refused, and a session is never gone through twice.

Invented names only.
"""

import datetime
import json

import pytest
from mock import patch

from btcopilot import questions, record
from btcopilot.admin import admin
from btcopilot.extensions import db
from btcopilot.models import Change, ModelCall, Statement
from btcopilot.tests.conftest import Model, called, calling, csrf_token, said, version
from btcopilot.tests.test_turnhistory import coach, family, post, statements, titles  # noqa: F401
from btcopilot.toolbox import ToolName

RUTH = "When did your grandmother Ruth die?"
ASKED_ON = datetime.datetime(2026, 9, 12, 18, 30)


@pytest.fixture
def past(web, family, monkeypatch) -> dict:
    """A session from before questions were kept: the coach asked about Ruth
    on 12 Sep and nobody wrote it down."""
    coach(monkeypatch, Model(said(f"That sounds hard. {RUTH}"), said("Tell me more.")))
    body = post(web, csrf_token(web), "My grandmother raised me.").get_json()
    post(web, csrf_token(web), "I am not sure.")
    reply = statements(web, body["discussion_id"])[1]["id"]
    db.session.get(Statement, reply).created_at = ASKED_ON
    db.session.commit()
    return {"session": body["discussion_id"], "reply": reply}


def backfill(flask_app, *turns, args=("--yes",)) -> tuple[list[dict], Model]:
    model = Model(*turns)
    with patch("btcopilot.questions.CoachModel", return_value=model):
        result = flask_app.test_cli_runner().invoke(
            admin, ["questions", "backfill", *args, "--json"]
        )
    assert result.exit_code == 0, result.output
    return json.loads(result.output), model


def asking(past, text=RUTH):
    return calling(
        (
            ToolName.AddQuestion,
            {"text": text, "kind": "fact", "state": "asked", "asked_in": past["reply"]},
        )
    )


def test_a_backfilled_question_keeps_the_message_and_day_it_was_asked(
    flask_app, family, past
):
    # R-0006
    done, _ = backfill(flask_app, asking(past), said(""))

    assert done == [{"diagram": family.id, "session": past["session"], "model_calls": 2}]
    db.session.expire_all()
    data = family.get_diagram_data()
    assert [(q["text"], q["session_id"], q["asked_at"]) for q in data.questions] == [
        (RUTH, past["session"], "2026-09-12")
    ]
    assert data.questions_backfilled == [past["session"]]
    assert record.asked_in(family.id) == {
        "q1": {"discussion_id": past["session"], "statement_id": past["reply"]}
    }
    assert (
        ModelCall.query.filter_by(turn_id=f"backfill:{past['session']}").count() == 2
    )


def test_words_the_message_does_not_hold_are_refused(flask_app, family, past):
    # R-0006
    _, model = backfill(flask_app, asking(past, "When was Ruth born?"), said(""))

    result = model.histories[1][-1]["content"][0]
    assert result["is_error"] is True
    db.session.expire_all()
    assert family.get_diagram_data().questions == []


def test_a_session_is_gone_through_once_and_the_preview_writes_nothing(
    flask_app, family, past
):
    # R-0006
    before = version(family)
    preview, _ = backfill(flask_app, args=())
    assert preview == [
        {
            "diagram": family.id,
            "sessions_to_do": 1,
            "sessions_done": 0,
            "estimated_model_calls": 3,
            "most_model_calls": 20,
        }
    ]
    assert (version(family), ModelCall.query.filter(ModelCall.turn_id.like("backfill:%")).count()) == (before, 0)

    backfill(flask_app, asking(past), said(""))
    after = version(family)
    rows = Change.query.count()
    again, model = backfill(flask_app)

    assert again == []
    assert model.systems == []
    assert (version(family), Change.query.count()) == (after, rows)
    assert backfill(flask_app, args=())[0][0]["sessions_done"] == 1


def test_a_stopped_run_gone_through_again_does_not_add_a_question_twice(
    flask_app, family, past
):
    # R-0006
    stopped = Model(
        asking(past),
        called(ToolName.SetQuestion, id="q1", version=version(family) + 1, state="resolved", outcome="unknown"),
    )
    with pytest.raises(IndexError):
        questions.run([family], model=stopped)

    _, model = backfill(flask_app, asking(past), said(""))

    assert model.histories[1][-1]["content"][0]["is_error"] is True
    db.session.expire_all()
    data = family.get_diagram_data()
    assert [(q["text"], q["state"]) for q in data.questions] == [(RUTH, "resolved")]
    assert data.questions_backfilled == [past["session"]]


def test_the_backfill_can_read_the_whole_record_and_write_only_questions(
    flask_app, family, past
):
    # R-0479
    _, model = backfill(
        flask_app, calling((ToolName.EditPerson, {"name": "Nell"})), said("")
    )

    assert sorted(model.offered[0]) == [
        "add_question",
        "read_changes",
        "read_events",
        "read_notes",
        "read_people",
        "read_questions",
        "set_question",
    ]
    assert model.histories[1][-1]["content"][0]["is_error"] is True
    db.session.expire_all()
    assert [p["name"] for p in family.get_diagram_data().people] == ["Wren"]
