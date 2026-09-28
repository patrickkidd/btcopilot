"""A cluster's play-by-play is told once and kept until what the coach is
shown of the cluster changes [R-0576]. Invented names only: the Whitlock
stand-in family."""

import pytest
import sqlalchemy as sa
from alembic import command

from btcopilot import playturn, prompts
from btcopilot.admin.database import config
from btcopilot.case import Tool
from btcopilot.extensions import db
from btcopilot.models import Discussion, ModelCall, Statement, StatementKind
from btcopilot.playturn import PlayTurn
from btcopilot.schema import Event, EventKind, PairBond, Person, asdict
from btcopilot.timeline import build_timeline
from btcopilot.tests.conftest import Model, called
from btcopilot.tests.test_case import SHOTS, record, told
from btcopilot.tests.test_turnbackfill import at, rows, seed


def explain(data, discussion, model) -> dict:
    return PlayTurn.stored(data, "apart", discussion=discussion, model=model).run()


def test_a_second_explain_of_an_unchanged_cluster_makes_no_call(discussion):
    # R-0563, R-0542, R-0576
    data = record()
    model = Model(called(Tool.PlayByPlay, **told()))
    first = explain(data, discussion, model)
    again = explain(data, discussion, model)

    assert len(model.histories) == 1
    assert again == first
    assert again["digest"] == playturn.digests(data, build_timeline(data))["apart"]
    assert Statement.query.filter_by(kind=StatementKind.Play).count() == 1


def test_a_play_kept_in_another_session_joins_this_one_with_no_call(discussion):
    # R-0563, R-0542, R-0576
    data = record()
    model = Model(called(Tool.PlayByPlay, **told()))
    first = explain(data, discussion, model)
    other = Discussion(user_id=discussion.user_id, diagram_id=discussion.diagram_id)
    db.session.add(other)
    db.session.commit()
    again = explain(data, other, model)

    assert len(model.histories) == 1
    kept = db.session.get(Statement, again["statement_id"])
    assert (kept.discussion_id, kept.told_case, kept.turn_id) == (other.id, first["case"], None)
    assert ModelCall.query.count() == 1


def edited(data):
    data.events[1]["description"] = "Took a flat"
    return told()


def added(data):
    data.events.append(asdict(Event(id=209, kind=EventKind.Noted, person=5, dateTime="1983-02-15", description="Changed schools")))
    data.clusters[0]["eventIds"].append(209)
    return told()


def removed(data):
    data.events = [e for e in data.events if e["id"] != 202]
    data.clusters[0]["eventIds"].remove(202)
    return told(snapshots=[{**SHOTS[0], "event_ids": [201]}, *SHOTS[1:]])


def renamed(data):
    data.people[0]["name"] = "Marc"
    return told()


@pytest.mark.parametrize("change", [edited, added, removed, renamed])
def test_a_changed_cluster_is_told_again(discussion, change):
    # R-0563, R-0542, R-0576
    data = record()
    model = Model(called(Tool.PlayByPlay, **told()))
    first = explain(data, discussion, model)
    model.turns.append(called(Tool.PlayByPlay, **change(data)))
    again = explain(data, discussion, model)

    assert len(model.histories) == 2
    assert again["statement_id"] != first["statement_id"]
    assert again["digest"] == playturn.digests(data, build_timeline(data))["apart"] != first["digest"]


def test_a_new_title_on_a_named_cluster_is_told_again(discussion):
    # R-0563, R-0542
    data = record()
    data.clusters[0]["name"] = "Apart"
    model = Model(called(Tool.PlayByPlay, **told()), called(Tool.PlayByPlay, **told()))
    first = explain(data, discussion, model)
    data.clusters[0]["title"] = "Marcus and Delphine come apart"
    again = explain(data, discussion, model)

    assert len(model.histories) == 2
    assert again["digest"] != first["digest"]


def test_a_renamed_relative_the_drawer_draws_is_told_again_and_a_stranger_is_not(discussion):
    # R-0563, R-0542, R-0546
    data = record()
    data.people[0]["parents"] = 10
    data.people += [
        asdict(Person(id=6, name="Harold")),
        asdict(Person(id=7, name="Iris")),
        {**asdict(Person(id=8, name="Nell", parents=10)), "primary": True},
        asdict(Person(id=9, name="Otto")),
    ]
    data.pair_bonds = [asdict(PairBond(id=10, person_a=6, person_b=7))]
    model = Model(called(Tool.PlayByPlay, **told()), called(Tool.PlayByPlay, **told()))
    explain(data, discussion, model)
    data.people[-1]["name"] = "Otis"
    explain(data, discussion, model)

    assert len(model.histories) == 1
    data.people[3]["name"] = "Hal"
    explain(data, discussion, model)

    assert len(model.histories) == 2


def test_a_couple_marked_married_or_not_is_told_again(discussion):
    # R-0563, R-0542, R-0560
    data = record()
    data.events = [e for e in data.events if e["id"] != 204]
    data.clusters[0]["eventIds"].remove(204)
    data.pair_bonds = [asdict(PairBond(id=11, person_a=3, person_b=4, married=True))]
    model = Model(called(Tool.PlayByPlay, **told()), called(Tool.PlayByPlay, **told()))
    explain(data, discussion, model)
    data.pair_bonds[0]["married"] = False
    explain(data, discussion, model)

    assert len(model.histories) == 2


def test_a_tuned_play_prompt_retells_the_cluster(discussion, monkeypatch):
    # R-0563, R-0542
    data = record()
    model = Model(called(Tool.PlayByPlay, **told()), called(Tool.PlayByPlay, **told()))
    explain(data, discussion, model)
    monkeypatch.setattr(prompts, "PLAY_BY_PLAY_PROMPT", prompts.PLAY_BY_PLAY_PROMPT + "\nTuned.")
    explain(data, discussion, model)

    assert len(model.histories) == 2


def test_the_revision_keeps_old_plays_with_no_digest_so_they_are_told_again(flask_app, tmp_path):
    # R-0563, R-0542
    said = [
        {"id": 1, "discussion_id": 1, "speaker_id": 2, "kind": "play", "turn_id": "told",
         "cluster_id": "apart", "text": "Wren moved when Nell left.", "order": 0,
         "told_case": "{}", "created_at": at(0)},
    ]
    seeded = rows({}, said, [])
    seeded.pop("diagram_changes")
    engine = seed(flask_app, tmp_path, seeded, revision="1b00000000b2")

    with flask_app.app_context():
        command.upgrade(config(), "head")

    with engine.connect() as conn:
        kept = conn.execute(sa.text("SELECT id, text, digest FROM statements")).all()
    assert kept == [(1, "Wren moved when Nell left.", None)]
