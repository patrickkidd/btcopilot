"""A session replayed on another model onto a scratch record, scored against a
corrected record, with the watcher's mistakes counted and one ledger line
appended. Invented names only; the coach is scripted, never called."""

import json

import pytest

import btcopilot

from btcopilot import diagramjson, ledger, prompts, record, replayscore
from btcopilot.admin import admin
from btcopilot.admin.quality import PRODUCTION
from btcopilot.coachmodel import COACH_EFFORT, Spent, model_for
from btcopilot.extensions import db
from btcopilot.llmutil import resolve_model
from btcopilot.models import (
    Author,
    Change,
    Diagram,
    Discussion,
    ModelCall,
    Purpose,
    ReplayPass,
    Speaker,
    SpeakerType,
    Statement,
    StatementKind,
    TokenMeter,
)
from btcopilot.review import adapter
from btcopilot.routes.diagrams import readable
from btcopilot.schema import ItemKind
from btcopilot.toolbox import ToolName
from btcopilot.tests.conftest import Model, called, calling, said

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


def test_a_replay_asks_a_question_in_its_scratch_session(
    discussion, reference, monkeypatch
):
    # R-0597
    model = Model(
        calling(
            (
                ToolName.AddQuestion,
                {"text": "Who raised Nell?", "kind": "thought", "state": "asked"},
            )
        ),
        said("Who raised Nell?"),
    )
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name, effort: model)
    row = replayscore.replay(discussion, "sonnet-5", reference)
    asked = (
        db.session.get(Diagram, row["scratch_diagram_id"]).get_diagram_data().questions
    )
    assert [q["session_id"] for q in asked] == [row["scratch_discussion_id"]]


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


def test_a_replay_refuses_default_and_names_the_aliases(flask_app, test_user):
    # R-0597
    result = flask_app.test_cli_runner().invoke(
        admin, ["quality", "replay-person", str(test_user.id), "default"]
    )
    assert result.exit_code == 2
    assert "'opus-5.5'" in result.output


def test_a_prompt_dir_replaces_the_coach_prompt_for_the_replay_only(
    discussion, reference, tmp_path, monkeypatch
):
    # R-0597
    (tmp_path / "agent.prompty").write_text(PROMPT)
    model = Model(said("Noted."))
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name, effort: model)
    replayscore.replay(discussion, "sonnet-5", reference, prompt=tmp_path)
    assert model.systems[0].startswith("You coach Brother Cadfael")
    assert "Cadfael" not in prompts.get_agent_prompt()


def test_a_prompt_dir_fragment_renders_into_the_usual_coach_prompt(
    discussion, reference, tmp_path, monkeypatch
):
    # R-0597
    (tmp_path / "fragments").mkdir()
    (tmp_path / "fragments" / "narration.md").write_text(
        "Narrate as Brother Cadfael.\n"
    )
    model = Model(said("Noted."))
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name, effort: model)
    replayscore.replay(discussion, "sonnet-5", reference, prompt=tmp_path)
    assert "Narrate as Brother Cadfael." in model.systems[0]
    assert "Cadfael" not in prompts.get_agent_prompt()


def _turn(discussion, order, words, turn_id=None, reply_id=None):
    """The person's words at `order` and the coach's reply after them, or no
    reply when `reply_id` is False."""
    subject, expert = discussion.speakers
    for speaker, text, stamp in (
        (subject, words, turn_id),
        (expert, "Noted.", reply_id),
    ):
        if speaker is expert and reply_id is False:
            continue
        db.session.add(
            Statement(
                discussion_id=discussion.id,
                speaker_id=speaker.id,
                text=text,
                order=order if speaker is subject else order + 1,
                kind=StatementKind.Turn,
                turn_id=stamp,
            )
        )
    db.session.commit()


def test_turns_caps_a_persons_replay_and_pairs_the_turn_ids(
    flask_app, discussion, reference, test_user, monkeypatch
):
    # R-0597
    _turn(discussion, 2, "My sister Nell moved.", "live2", "live2")
    _turn(discussion, 4, "Then she wed.", "live4", "live4")
    model = Model(said("Noted."), said("Noted."))
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name, effort: model)
    result = flask_app.test_cli_runner().invoke(
        admin,
        ["quality", "replay-person", str(test_user.id), "sonnet-5"]
        + ["--reference", str(reference.id), "--turns", "2"],
    )
    assert result.exit_code == 0, result.output
    assert "2 turns" in result.output
    assert "live2 -> " in result.output
    assert "live4" not in result.output


def _added(diagram_id, user_id, person_id, name, turn_id):
    record.apply(
        diagram_id,
        [
            {
                "item_kind": ItemKind.Person,
                "item_id": person_id,
                "field": field,
                "after": value,
            }
            for field, value in (("name", name), ("last_name", "Hale"))
        ],
        author=Author.Coach,
        turn_id=turn_id,
        user_id=user_id,
    )


@pytest.fixture
def lived(discussion, test_user):
    """An older turn with no turn id that added Nell, then three live turns
    that each added one sibling."""
    _added(discussion.diagram_id, test_user.id, 1, "Nell", "before-turn-ids")
    for order, name in ((2, "Wren"), (4, "Ada"), (6, "Bo")):
        _turn(discussion, order, f"My brother {name}.", f"live{order}", f"live{order}")
        _added(discussion.diagram_id, test_user.id, order, name, f"live{order}")
    return discussion


def _person(flask_app, test_user, *extra):
    return flask_app.test_cli_runner().invoke(
        admin,
        ["quality", "replay-person", str(test_user.id), "sonnet-5", "--turns", "2"]
        + list(extra),
    )


def test_a_replay_starts_before_its_first_turn_and_is_scored_after_its_last(
    flask_app, lived, test_user, path, monkeypatch
):
    # R-0597
    model = Model(
        called(ToolName.EditPerson, name="Nell", last_name="Hale"),
        said("Noted."),
        called(ToolName.EditPerson, name="Wren", last_name="Hale"),
        said("Noted."),
    )
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name, effort: model)
    result = _person(flask_app, test_user)
    assert result.exit_code == 0, result.output
    first, second = replayscore.turned(test_user.id, 2)
    assert f"statements {first.id}..{second.id} (2)" in result.output
    line = json.loads(path.read_text())
    assert line["scores"]["people"] == 1.0
    assert line["case"] in result.output
    scratch = db.session.get(Diagram, line["scratch_diagram_id"])
    assert [p["name"] for p in adapter.record_of(scratch)["people"]] == [
        "Nell",
        "Wren",
    ]


def test_an_anchor_on_a_change_without_a_version_names_the_row(lived, test_user):
    # R-0597
    change = Change.query.filter_by(diagram_id=lived.diagram_id, turn_id="live2").one()
    change.version = None
    db.session.commit()
    words = Statement.query.filter_by(
        turn_id="live2", speaker_id=lived.speakers[0].id
    ).one()
    with pytest.raises(
        ValueError, match=f"row {change.id} on diagram {lived.diagram_id}"
    ):
        replayscore.anchor(lived.diagram, words)


def test_a_pass_is_kept_in_the_table(flask_app, lived, test_user, monkeypatch):
    # R-0597
    model = Model(said("Noted."), said("Noted."))
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name, effort: model)
    result = _person(flask_app, test_user)
    assert result.exit_code == 0, result.output
    kept = ReplayPass.query.one()
    assert (kept.model, kept.thinking, kept.turns, kept.release) == (
        resolve_model("sonnet-5"),
        COACH_EFFORT,
        2,
        btcopilot.__version__,
    )
    assert f"key: {kept.key}" in result.output
    shown = _person(flask_app, test_user, "--key")
    assert "kept " in shown.output and "2 turns" in shown.output


def test_a_kept_key_is_not_run_again_without_again(
    flask_app, lived, test_user, path, monkeypatch
):
    # R-0597
    model = Model(said("Noted."), said("Noted."), said("Noted."), said("Noted."))
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name, effort: model)
    assert _person(flask_app, test_user).exit_code == 0
    path.unlink()
    result = _person(flask_app, test_user)
    assert result.exit_code != 0
    assert ReplayPass.query.count() == 1
    assert _person(flask_app, test_user, "--again").exit_code == 0
    assert ReplayPass.query.count() == 2


def test_the_passes_of_september_30_are_kept(flask_app):
    # R-0597
    result = flask_app.test_cli_runner().invoke(admin, ["quality", "keep-passes"])
    assert result.exit_code == 0, result.output
    assert ReplayPass.query.count() == 5
    gemini = ReplayPass.query.filter_by(model="gemini-3.1-pro-preview").one()
    assert (gemini.cache_read_tokens, gemini.overall, gemini.release) == (
        335346,
        0.92,
        None,
    )


@pytest.fixture
def thread(test_user):
    """The old layout of a live thread: the first words sent twice, the turn id
    on the first send only; the second turn's id on the reply alone; the third
    stamped on both. Each turn added one person."""
    thread = Discussion(
        user_id=test_user.id,
        diagram_id=test_user.free_diagram_id,
        speakers=[
            Speaker(name="Client", type=SpeakerType.Subject, person_id=1),
            Speaker(name="Coach", type=SpeakerType.Expert),
        ],
    )
    db.session.add(thread)
    db.session.commit()
    _turn(thread, 1, "My sister Nell sleeps badly.", "t1", False)
    _added(thread.diagram_id, test_user.id, 1, "Nell", "t1")
    _turn(thread, 2, "My sister Nell sleeps badly.")
    _turn(thread, 4, "I am Wren Hale.", None, "t2")
    _added(thread.diagram_id, test_user.id, 2, "Wren", "t2")
    _turn(thread, 6, "Our brother is Ada.", "t3", "t3")
    _added(thread.diagram_id, test_user.id, 3, "Ada", "t3")
    return thread


def test_a_replay_feeds_every_answered_turn_in_order_and_records_on_scratch(
    flask_app, thread, test_user, path, monkeypatch
):
    # R-0597
    assert [s.text for s in replayscore.turned(test_user.id)] == [
        "My sister Nell sleeps badly.",
        "I am Wren Hale.",
        "Our brother is Ada.",
    ]
    model = Model(
        called(ToolName.EditPerson, name="Nell", last_name="Hale"),
        said("Nell is in."),
        called(ToolName.EditPerson, name="Wren", last_name="Hale"),
        said("Wren is in."),
    )
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name, effort: model)
    result = _person(flask_app, test_user)
    assert result.exit_code == 0, result.output
    assert "Nell" not in model.systems[0]
    second = json.dumps(model.histories[2])
    assert all(
        words in second
        for words in ("My sister Nell sleeps badly.", "Nell is in.", "I am Wren Hale.")
    )
    assert "Nell" in model.systems[2]
    assert "Ada" not in second
    line = json.loads(path.read_text())
    assert line["scores"]["people"] == 1.0
    assert line["git"] == btcopilot.__version__
    scratch = db.session.get(Diagram, line["scratch_diagram_id"])
    assert (
        scratch.version
        == 1 + Change.query.filter_by(diagram_id=scratch.id).count()
        == 3
    )


def test_a_replay_from_a_later_turn_goes_on_in_the_kept_pass(
    flask_app, lived, test_user, monkeypatch
):
    # R-0568
    model = Model(said("Noted."), said("Noted."), said("Noted."))
    monkeypatch.setattr("btcopilot.replayscore.model_for", lambda name, effort: model)
    assert _person(flask_app, test_user).exit_code == 0
    first = ReplayPass.query.one()
    result = flask_app.test_cli_runner().invoke(
        admin,
        ["quality", "replay-person", str(test_user.id), "sonnet-5"]
        + ["--start", "3", "--turns", "3", "--after", str(first.id)],
    )
    assert result.exit_code == 0, result.output
    third = replayscore.turned(test_user.id)[2]
    assert f"statements {third.id}..{third.id} (1)" in result.output
    later = ReplayPass.query.order_by(ReplayPass.id.desc()).first()
    assert (later.turns, later.scratch_diagram_id) == (1, first.scratch_diagram_id)
    (session,) = db.session.get(Diagram, first.scratch_diagram_id).discussions
    assert [s.text for s in adapter.spoken(session.statements)] == [
        "Hello",
        "My brother Wren.",
        "My brother Ada.",
    ]
