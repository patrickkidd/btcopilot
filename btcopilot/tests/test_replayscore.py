"""A session replayed on another model onto a scratch record, scored against a
corrected record, with the watcher's mistakes counted and one ledger line
appended. Invented names only; the coach is scripted, never called."""

import json

import pytest

from btcopilot import diagramjson, ledger, replayscore
from btcopilot.admin import admin
from btcopilot.admin.quality import PRODUCTION
from btcopilot.coachmodel import Spent
from btcopilot.extensions import db
from btcopilot.models import Diagram, TokenMeter
from btcopilot.routes.diagrams import readable
from btcopilot.toolbox import ToolName
from btcopilot.tests.conftest import Model, called, said

NELL = {"id": 1, "name": "Nell", "last_name": "Hale", "gender": "female"}


@pytest.fixture
def reference(test_user):
    diagram = Diagram(
        user_id=test_user.id,
        name="Corrected record",
        data=diagramjson.dumps({"people": [NELL]}),
    )
    db.session.add(diagram)
    db.session.commit()
    return diagram


@pytest.fixture(autouse=True)
def path(tmp_path, monkeypatch):
    path = tmp_path / "ledger.jsonl"
    monkeypatch.setattr("btcopilot.ledger.PATH", path)
    return path


@pytest.fixture
def coach(monkeypatch):
    added = called(ToolName.EditPerson, name="Nell", last_name="Hale")
    added.spent = Spent(input=1000, output=50)
    model = Model(
        called(ToolName.ReadPeople),
        added,
        called(ToolName.EditPerson, name="Nell", last_name="Hale"),
        called(ToolName.EditEvent, kind="noted", person=1, date_certainty="certain"),
        said("Nell is in."),
    )
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name: model)
    return model


def test_a_refused_call_and_a_person_added_twice_are_counted(
    discussion, reference, coach
):
    # R-0596
    row = replayscore.replay(discussion, "sonnet-5", reference)
    assert row["faults"]["tool_refused"] == 1
    assert row["faults"]["duplicate_person"] == 1
    assert row["turns"] == 1
    assert row["scores"]["people"] == 0.67


def test_a_replay_charges_no_one(discussion, reference, coach):
    # R-0596
    replayscore.replay(discussion, "sonnet-5", reference)
    assert TokenMeter.query.count() == 0


def test_the_replay_record_is_scratch_and_never_listed(
    discussion, reference, coach, test_user
):
    # R-0596
    row = replayscore.replay(discussion, "sonnet-5", reference)
    assert db.session.get(Diagram, row["scratch_diagram_id"]).scratch
    assert row["scratch_diagram_id"] not in {d.id for d in readable(test_user)}


def test_an_event_on_january_first_with_unknown_certainty_is_counted(test_user):
    # R-0596
    data = {
        "people": [NELL],
        "events": [
            {
                "id": 2,
                "kind": "noted",
                "person": 1,
                "description": "Moved",
                "dateTime": "1985-01-01",
                "dateCertainty": "unknown",
            },
            {
                "id": 3,
                "kind": "noted",
                "person": 1,
                "description": "Wed",
                "dateTime": "1990-06-12",
                "dateCertainty": "certain",
            },
        ],
    }
    found = replayscore.faults(test_user.free_diagram_id, data)
    assert (found["jan1_placeholder"], found["certainty_unknown"]) == (1, 1)


def test_the_command_appends_one_line_on_the_schema(
    flask_app, discussion, reference, coach, path
):
    # R-0596
    result = flask_app.test_cli_runner().invoke(
        admin, ["quality", "replay", str(discussion.id), "sonnet-5", str(reference.id)]
    )
    assert result.exit_code == 0, result.output
    lines = path.read_text().splitlines()
    assert len(lines) == 1
    line = json.loads(lines[0])
    assert line.keys() == ledger.FIELDS
    assert line["kind"] == ledger.LedgerKind.Replay.value
    assert line["reference_diagram_id"] == reference.id
    assert "duplicate_person" in result.output


def test_the_command_refuses_production(flask_app, discussion, reference, coach):
    # R-0596
    flask_app.config["CONFIG"] = PRODUCTION
    result = flask_app.test_cli_runner().invoke(
        admin, ["quality", "replay", str(discussion.id), "sonnet-5", str(reference.id)]
    )
    assert result.exit_code != 0
    assert Diagram.query.count() == 2
