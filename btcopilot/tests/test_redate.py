"""The catch-up that re-dates events stored at a stand-in date by rereading the
conversation they were written from: plan, apply, undo (R-0960)."""

import importlib
import json

from mock import patch

from btcopilot import diagramjson, record
from btcopilot.admin import admin
from btcopilot.coachmodel import ModelTurn, ToolCall
from btcopilot.extensions import db
from btcopilot.llmutil import Served
from btcopilot.models import Author, Diagram, Discussion, ModelCall, Purpose, Speaker, SpeakerType, Statement
from btcopilot.review.models import Coding, Cut, Note

# the package exports the command group under the module's own name
REDATE = importlib.import_module("btcopilot.admin.redate")

SAID = "Things got bad for Ann around high school."
LATER = "My mother died in 2001."
WORDS = "around high school"


class Answer:
    """A model that answers each call with the calls it was given, and keeps
    what it was asked."""

    def __init__(self, *calls):
        self.calls = list(calls)
        self.asked = []

    def turn(self, system, messages, tools, turn_id=""):
        if False:
            yield
        self.asked.append(messages[0]["content"])
        args = self.calls.pop(0)
        return ModelTurn(
            calls=[ToolCall(id="c1", name="edit_event", args=args)] if args else [],
            blocks=[],
            served=Served("claude-opus-5-5"),
        )


ANN = {"people": [{"id": 1, "name": "Ann"}], "lastItemId": 1}
STANDIN = {
    "id": 2,
    "kind": "shift",
    "person": 1,
    "symptom": "up",
    "title": "Things got bad",
    "description": "Things got bad",
    "dateTime": "1900-01-01",
    "dateCertainty": "unknown",
}


def family(user, said: str = SAID, data: dict = ANN, event: dict = STANDIN) -> tuple[Diagram, Statement]:
    """A family whose person said `said`, then something later, and an event
    written from `said` at a stand-in date."""
    diagram = Diagram(user_id=user.id, name="Family", data=diagramjson.dumps(data))
    db.session.add(diagram)
    db.session.flush()
    discussion = Discussion(user_id=user.id, diagram_id=diagram.id)
    db.session.add(discussion)
    db.session.flush()
    person = Speaker(discussion_id=discussion.id, name="Ann", type=SpeakerType.Subject)
    db.session.add(person)
    db.session.flush()
    discussion.chat_user_speaker_id = person.id
    said = Statement(discussion_id=discussion.id, speaker_id=person.id, text=said, order=0)
    later = Statement(discussion_id=discussion.id, speaker_id=person.id, text=LATER, order=1)
    db.session.add_all([said, later])
    db.session.commit()
    record.apply(
        diagram.id,
        [
            {"item_kind": "event", "item_id": event["id"], "field": field, "after": value}
            for field, value in event.items()
            if field != "id"
        ],
        author=Author.Coach,
        turn_id="t1",
        statement_id=said.id,
    )
    return diagram, said


def redate(flask_app, *args) -> list[dict]:
    result = flask_app.test_cli_runner().invoke(
        admin, ["diagrams", "redate", *args, "--json"]
    )
    assert result.exit_code == 0, (result.output, result.exception)
    return json.loads(result.stdout)


def dated(diagram) -> tuple:
    db.session.refresh(diagram)
    (event,) = diagram.get_diagram_data().events
    return event.get("dateTime"), event.get("dateCertainty"), event.get("dateEvidence")


def test_the_plan_rereads_up_to_the_message_and_writes_nothing(flask_app, test_user, tmp_path):
    # R-0960, R-0772
    diagram, _ = family(test_user)
    model = Answer(
        {"id": 2, "date": "1996", "date_certainty": "unknown", "date_evidence": WORDS, "kind_of_date": "a"}
    )
    with patch.object(REDATE, "model_for", return_value=model):
        (row,) = redate(flask_app, "plan", "--plans", str(tmp_path))
    assert SAID in model.asked[0]
    assert LATER not in model.asked[0]
    assert (row["old"], row["new"], row["certainty"], row["evidence"], row["kind"]) == (
        "1900-01-01",
        "1996-01-01",
        "unknown",
        WORDS,
        "a",
    )
    assert dated(diagram) == ("1900-01-01", "unknown", None)
    assert ModelCall.query.filter_by(purpose=Purpose.Backfill).count() == 1


def test_apply_writes_the_plan_through_the_event_tool_and_undo_takes_it_back(
    flask_app, test_user, tmp_path
):
    # R-0960, R-0957, R-0772
    diagram, _ = family(test_user)
    model = Answer(
        {"id": 2, "date": "1996", "date_certainty": "unknown", "date_evidence": WORDS, "kind_of_date": "a"}
    )
    with patch.object(REDATE, "model_for", return_value=model):
        (row,) = redate(flask_app, "plan", "--plans", str(tmp_path))
    redate(flask_app, "apply", row["plan"])
    assert dated(diagram) == ("1996-01-01", "unknown", WORDS)
    redate(flask_app, "undo", row["plan"])
    assert dated(diagram) == ("1900-01-01", "unknown", None)


def test_a_standing_pattern_is_left_with_no_date_and_its_kind_is_kept(flask_app, test_user, tmp_path):
    # R-0958, R-0960
    diagram, _ = family(test_user)
    model = Answer({"id": 2, "clear": ["date", "date_evidence"], "kind_of_date": "c"})
    with patch.object(REDATE, "model_for", return_value=model):
        (row,) = redate(flask_app, "plan", "--plans", str(tmp_path))
    assert (row["kind"], row["new"]) == ("c", None)
    redate(flask_app, "apply", row["plan"])
    assert dated(diagram)[0] is None


def test_an_event_dated_since_the_plan_is_left_as_it_is(flask_app, test_user, tmp_path):
    # R-0960
    diagram, _ = family(test_user)
    model = Answer({"id": 2, "date": "1996", "date_certainty": "unknown", "kind_of_date": "b"})
    with patch.object(REDATE, "model_for", return_value=model):
        (row,) = redate(flask_app, "plan", "--plans", str(tmp_path))
    record.apply(
        diagram.id,
        [{"item_kind": "event", "item_id": 2, "field": "dateTime", "after": "1997-01-01"}],
        author=Author.Coach,
        turn_id="t2",
    )
    (left,) = redate(flask_app, "apply", row["plan"])
    assert left["left"] == "its date changed since the plan"
    assert dated(diagram)[0] == "1997-01-01"


def test_a_date_marked_surer_than_unknown_on_1970_is_not_a_stand_in():
    # R-0960
    assert record.standin({"dateTime": "1970-01-01", "dateCertainty": "unknown"})
    assert not record.standin({"dateTime": "1970-01-01", "dateCertainty": "approximate"})
    assert record.standin({"dateTime": "1900-01-01", "dateCertainty": "certain"})
    assert record.standin({"dateTime": "0001-01-01"})
    assert not record.standin({"dateTime": "1971-01-01", "dateCertainty": "unknown"})


def test_a_coders_copy_is_reread_from_the_case_and_the_coders_own_words(
    flask_app, test_user, tmp_path
):
    # R-0960, R-0958
    case, said = family(test_user)
    case.data = diagramjson.dumps(
        {
            "people": [{"id": 1, "name": "Ann", "primary": True}],
            "events": [{"id": 3, "kind": "birth", "child": 1, "dateTime": "1980-05-11", "dateCertainty": "certain", "datePrecision": "day"}],
        }
    )
    cut = Cut(diagram_id=case.id, start_statement_id=said.id, end_statement_id=said.id, user_id=test_user.id)
    copy = Diagram(
        user_id=test_user.id,
        name="coding",
        data=diagramjson.dumps({"people": [{"id": 1, "name": "Ann"}], "lastItemId": 1}),
    )
    db.session.add_all([cut, copy])
    db.session.flush()
    coding = Coding(cut_id=cut.id, user_id=test_user.id, diagram_id=copy.id)
    db.session.add(coding)
    db.session.flush()
    db.session.add(Note(coding_id=coding.id, statement_id=said.id, text="Ann's symptom up in high school", turn_id="s1"))
    db.session.flush()
    db.session.add(Note(coding_id=coding.id, statement_id=said.id, text="a later note", turn_id="s2"))
    db.session.commit()
    record.apply(
        copy.id,
        [
            {"item_kind": "event", "item_id": 2, "field": field, "after": value}
            for field, value in {
                "kind": "shift",
                "person": 1,
                "symptom": "up",
                "title": "Symptom up",
                "description": "Symptom up",
                "dateTime": "1900-01-01",
                "dateCertainty": "unknown",
            }.items()
        ],
        author=Author.Review,
        turn_id="s1",
        statement_id=said.id,
    )
    model = Answer(
        {"id": 2, "date": "1995", "date_certainty": "unknown", "date_evidence": "in high school", "kind_of_date": "a"}
    )
    with patch.object(REDATE, "model_for", return_value=model):
        rows = redate(flask_app, "plan", "--diagram", str(copy.id), "--plans", str(tmp_path))
    assert [(r["diagram"], r["copy"], r["new"]) for r in rows] == [(copy.id, True, "1995-01-01")]
    asked = model.asked[0]
    assert "The person the case belongs to: Ann, born 11 May 1980." in asked
    assert SAID in asked and "Ann's symptom up in high school" in asked
    assert "a later note" not in asked


def test_a_copy_whose_coding_was_reset_is_reread_from_the_cut_holding_its_message(
    flask_app, test_user, tmp_path
):
    # R-0960
    case, said = family(test_user)
    case.data = diagramjson.dumps(
        {
            "people": [{"id": 1, "name": "Ann", "primary": True}],
            "events": [{"id": 3, "kind": "birth", "child": 1, "dateTime": "1980-05-11", "dateCertainty": "certain", "datePrecision": "day"}],
        }
    )
    cut = Cut(diagram_id=case.id, start_statement_id=said.id, end_statement_id=said.id, user_id=test_user.id)
    copy = Diagram(
        user_id=test_user.id,
        name="coding",
        data=diagramjson.dumps({"people": [{"id": 1, "name": "Ann"}], "lastItemId": 1}),
    )
    db.session.add_all([cut, copy])
    db.session.commit()
    record.apply(
        copy.id,
        [
            {"item_kind": "event", "item_id": 2, "field": field, "after": value}
            for field, value in STANDIN.items()
            if field != "id"
        ],
        author=Author.Review,
        turn_id="s1",
        statement_id=said.id,
    )
    model = Answer({"id": 2, "date": "1995", "date_certainty": "unknown", "kind_of_date": "a"})
    with patch.object(REDATE, "model_for", return_value=model):
        (row,) = redate(flask_app, "plan", "--diagram", str(copy.id), "--plans", str(tmp_path))
    assert (row["copy"], row["new"], row["left"]) == (True, "1995-01-01", None)
    assert "The person the case belongs to: Ann, born 11 May 1980." in model.asked[0]
    assert SAID in model.asked[0] and LATER not in model.asked[0]


class Broken(Answer):
    """A model whose call for event 2 fails."""

    def turn(self, system, messages, tools, turn_id=""):
        if "Event 2 " in messages[0]["content"]:
            raise RuntimeError("the call broke")
        return (yield from super().turn(system, messages, tools, turn_id))


def test_a_planned_write_the_tool_refuses_is_failed_and_called_again_on_a_rerun(
    flask_app, test_user, tmp_path
):
    # R-0956, R-0960
    family(test_user)
    model = Answer(
        {"id": 2, "date": "1970", "date_certainty": "unknown", "date_evidence": WORDS, "kind_of_date": "b"}
    )
    with patch.object(REDATE, "model_for", return_value=model):
        (row,) = redate(flask_app, "plan", "--plans", str(tmp_path))
    assert row["left"].startswith("failed: ") and "stand-in" in row["left"]
    again = Answer(
        {"id": 2, "date": "1996", "date_certainty": "unknown", "date_evidence": WORDS, "kind_of_date": "a"}
    )
    with patch.object(REDATE, "model_for", return_value=again):
        (rerun,) = redate(flask_app, "plan", "--plans", str(tmp_path))
    assert (rerun["new"], rerun["left"], rerun["plan"]) == ("1996-01-01", None, row["plan"])


def test_a_failed_event_is_kept_in_the_plan_and_a_rerun_calls_only_the_failed_and_unplanned(
    flask_app, test_user, tmp_path
):
    # R-0960, R-0772
    diagram, said = family(test_user)
    record.apply(
        diagram.id,
        [
            {"item_kind": "event", "item_id": 4, "field": field, "after": value}
            for field, value in dict(STANDIN, kind="noted", symptom=None, title="Moved away", description="Moved away").items()
            if field != "id"
        ],
        author=Author.Coach,
        turn_id="t1",
        statement_id=said.id,
    )
    model = Broken({"id": 4, "date": "1996", "date_certainty": "unknown", "kind_of_date": "a"})
    with patch.object(REDATE, "model_for", return_value=model):
        rows = redate(flask_app, "plan", "--plans", str(tmp_path))
    assert [(r["event"], r["new"], (r["left"] or "")[:7]) for r in rows] == [
        (2, None, "failed:"),
        (4, "1996-01-01", ""),
    ]
    again = Answer({"id": 2, "clear": ["date", "date_evidence"], "kind_of_date": "c"})
    with patch.object(REDATE, "model_for", return_value=again):
        rerun = redate(flask_app, "plan", "--plans", str(tmp_path))
    assert len(again.asked) == 1 and "Event 2 " in again.asked[0]
    assert [(r["event"], r["kind"], r["left"], r["plan"]) for r in rerun] == [
        (2, "c", None, rows[0]["plan"]),
        (4, "a", None, rows[0]["plan"]),
    ]


def test_an_event_with_no_message_to_reread_is_planned_cleared_with_no_call(
    flask_app, test_user, tmp_path
):
    # R-0956, R-0960
    diagram = Diagram(user_id=test_user.id, name="Family", data=diagramjson.dumps(ANN))
    db.session.add(diagram)
    db.session.commit()
    record.apply(
        diagram.id,
        [
            {"item_kind": "event", "item_id": 2, "field": field, "after": value}
            for field, value in dict(STANDIN, dateTime="1970-01-01").items()
            if field != "id"
        ],
        author=Author.Coach,
        turn_id="t1",
    )
    model = Answer()
    with patch.object(REDATE, "model_for", return_value=model):
        (row,) = redate(flask_app, "plan", "--plans", str(tmp_path))
    assert model.asked == []
    assert (row["kind"], row["message"], row["new"], row["left"]) == ("none", None, None, None)
    redate(flask_app, "apply", row["plan"])
    assert dated(diagram) == (None, "unknown", None)


def test_apply_ends_with_what_it_did_saves_it_and_runs_once(flask_app, test_user, tmp_path):
    # R-0960, R-0772
    family(test_user)
    model = Answer(
        {"id": 2, "date": "1996", "date_certainty": "unknown", "date_evidence": WORDS, "kind_of_date": "a"}
    )
    with patch.object(REDATE, "model_for", return_value=model):
        (row,) = redate(flask_app, "plan", "--plans", str(tmp_path))
    runner = flask_app.test_cli_runner()
    ran = runner.invoke(admin, ["diagrams", "redate", "apply", row["plan"]])
    line = "1 events written; 0 left as they were (none); 0 refused; 1 diagrams; 1 users"
    assert ran.output.rstrip().endswith(line)
    with open(row["plan"]) as saved:
        assert json.load(saved)["applied"] == {
            "written": 1, "left": {}, "refused": 0, "diagrams": 1, "users": 1
        }
    again = runner.invoke(admin, ["diagrams", "redate", "apply", row["plan"]])
    assert again.exit_code != 0 and "applied already" in again.output
