"""A session replayed on another model onto a scratch record, scored against a
corrected record, with the watcher's mistakes counted and one ledger line
appended. Invented names only; the coach is scripted, never called."""

import json

import pytest

from btcopilot import diagramjson, ledger, prompts, replayscore
from btcopilot.admin import admin
from btcopilot.admin.quality import PRODUCTION
from btcopilot.coachmodel import Spent, model_for
from btcopilot.extensions import db
from btcopilot.models import (
    Diagram,
    ModelCall,
    Purpose,
    Statement,
    StatementKind,
    TokenMeter,
)
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
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name, effort: model)
    return model


@pytest.fixture
def efforts(monkeypatch):
    """The thinking level each replay's real coach model was built with; the
    scripted coach answers in its place."""
    built = []
    model = Model(said("Noted."))

    def made(name, effort):
        built.append(model_for(name, effort).effort)
        return model

    monkeypatch.setattr("btcopilot.replayscore.model_for", made)
    return built


PROMPT = """---
name: agent
inputs:
  committed_state:
    type: string
  interactions:
    type: string
  today:
    type: string
---
You coach Brother Cadfael about his herb garden.

{{ committed_state }}
{{ interactions }}
{{ today }}
"""


def test_a_refused_call_and_a_person_added_twice_are_counted(
    discussion, reference, coach
):
    # R-0597
    row = replayscore.replay(discussion, "sonnet-5", reference)
    assert row["faults"]["tool_refused"] == 1
    assert row["faults"]["duplicate_person"] == 1
    assert row["turns"] == 1
    assert row["scores"]["people"] == 0.67


def test_a_replay_charges_no_one(discussion, reference, coach):
    # R-0597
    row = replayscore.replay(discussion, "sonnet-5", reference)
    assert TokenMeter.query.count() == 0
    assert {
        c.purpose
        for c in ModelCall.query.filter_by(diagram_id=row["scratch_diagram_id"])
    } == {Purpose.Replay}


def test_the_replay_record_is_scratch_and_never_listed(
    discussion, reference, coach, test_user
):
    # R-0597
    row = replayscore.replay(discussion, "sonnet-5", reference)
    assert db.session.get(Diagram, row["scratch_diagram_id"]).scratch
    assert row["scratch_diagram_id"] not in {d.id for d in readable(test_user)}


def test_an_event_on_january_first_with_unknown_certainty_is_counted(test_user):
    # R-0597
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
    # R-0597
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
    # R-0597
    flask_app.config["CONFIG"] = PRODUCTION
    result = flask_app.test_cli_runner().invoke(
        admin, ["quality", "replay", str(discussion.id), "sonnet-5", str(reference.id)]
    )
    assert result.exit_code != 0
    assert Diagram.query.count() == 2


def test_the_thinking_level_reaches_the_coach_model(
    flask_app, discussion, reference, efforts
):
    # R-0597
    result = flask_app.test_cli_runner().invoke(
        admin,
        ["quality", "replay", str(discussion.id), "sonnet-5", str(reference.id)]
        + ["--thinking", "low"],
    )
    assert result.exit_code == 0, result.output
    assert efforts == ["low"]


def test_a_prompt_file_replaces_the_coach_prompt_for_the_replay_only(
    discussion, reference, tmp_path, monkeypatch
):
    # R-0597
    path = tmp_path / "agent.prompty"
    path.write_text(PROMPT)
    model = Model(said("Noted."))
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name, effort: model)
    replayscore.replay(discussion, "sonnet-5", reference, prompt=path)
    assert model.systems[0].startswith("You coach Brother Cadfael")
    assert "Cadfael" not in prompts.get_agent_prompt()


def test_turns_caps_a_persons_replay_and_pairs_the_turn_ids(
    flask_app, discussion, reference, test_user, monkeypatch
):
    # R-0597
    subject = discussion.speakers[0]
    for order, words in ((2, "My sister Nell moved."), (3, "Then she wed.")):
        db.session.add(
            Statement(
                discussion_id=discussion.id,
                speaker_id=subject.id,
                text=words,
                order=order,
                kind=StatementKind.Turn,
                turn_id=f"live{order}",
            )
        )
    db.session.commit()
    model = Model(said("Noted."))
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name, effort: model)
    result = flask_app.test_cli_runner().invoke(
        admin,
        ["quality", "replay-person", str(test_user.id), "sonnet-5"]
        + ["--reference", str(reference.id), "--turns", "1"],
    )
    assert result.exit_code == 0, result.output
    assert "1 turns" in result.output
    assert "live2 -> " in result.output
    assert "live3" not in result.output
