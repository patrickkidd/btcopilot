"""The quality dashboard's recorded runs: a kept live run and the old extraction
F1 history load into one table on every release, the same rows however often
the release runs."""

import datetime
import json
import shutil

import pytest

from btcopilot import quality
from btcopilot.admin import admin
from btcopilot.models import QualityKind, QualityRun
from btcopilot.quality import Source
from btcopilot.tests.live import record
from btcopilot.tests.live.run import Outcome, Status
from btcopilot.tests.repo import REPO

RAN = "2026-09-26T05:36:32+00:00"


def run(status=Status.Passed, second=Outcome.Failed) -> dict:
    return {
        "date": RAN,
        "model": "claude-opus-5-5",
        "git": "5b2a6bbf65600e2944c6a0728e36120accdded8f",
        "status": status,
        "reason": None,
        "source": Source.Api,
        "cases": [
            {"case": "test_one", "criterion": "once", "outcome": Outcome.Passed},
            {"case": "test_two", "criterion": "2 of 3", "outcome": second},
            {"case": "test_three", "criterion": "once", "outcome": Outcome.Skipped},
        ],
    }


@pytest.fixture
def root(tmp_path):
    (tmp_path / "doc" / "f1").mkdir(parents=True)
    shutil.copy(REPO / quality.F1, tmp_path / quality.F1)
    return tmp_path


def recorded(root, row: dict, note="kept: asks before adding a parent"):
    results = root / "results"
    results.mkdir(exist_ok=True)
    path = results / "2026-09-26T053632-5b2a6bbf.json"
    path.write_text(json.dumps(row))
    return record.record(path, note, root / quality.EVALS)


def rows() -> dict:
    return {
        (row.kind, row.metric): row
        for row in QualityRun.query.filter_by(kind=QualityKind.EvalPassRate)
    }


def test_a_recorded_run_loads_once_however_often_the_release_runs(flask_app, root):
    # R-0517
    recorded(root, run())
    load = flask_app.test_cli_runner().invoke(admin, ["quality", "load", str(root)])
    again = flask_app.test_cli_runner().invoke(admin, ["quality", "load", str(root)])
    assert load.exit_code == 0 and again.exit_code == 0, load.output + again.output
    loaded = rows()
    assert {metric: row.value for (_, metric), row in loaded.items()} == {
        "test_one": 1.0,
        "test_two": 0.0,
        quality.OVERALL: 0.5,
    }
    one = loaded[(QualityKind.EvalPassRate, "test_one")]
    assert (one.commit, one.model, one.note) == (
        "5b2a6bbf65600e2944c6a0728e36120accdded8f",
        "claude-opus-5-5",
        "kept: asks before adding a parent",
    )
    assert one.ran_at == datetime.datetime(2026, 9, 26, 5, 36, 32)

    recorded(root, run(second=Outcome.Passed))
    quality.load(root)
    assert rows()[(QualityKind.EvalPassRate, quality.OVERALL)].value == 1.0
    assert len(rows()) == 3


def test_the_old_extraction_f1_history_loads_with_its_era_break(flask_app, root):
    # R-0475
    history = json.loads((root / quality.F1).read_text())["data"]
    quality.load(root)
    aggregate = QualityRun.query.filter_by(
        kind=QualityKind.ExtractionF1, metric="aggregate"
    ).order_by(QualityRun.ran_at)
    assert aggregate.count() == len(history)
    last = aggregate.all()[-1]
    assert last.ran_at == datetime.datetime(2026, 7, 22)
    assert last.note.startswith("ERA BREAK")
    assert QualityRun.query.filter_by(kind=QualityKind.ExtractionF1, value=None).count() == 0


def test_a_run_that_stopped_partway_or_scored_no_case_is_never_recorded(root):
    # R-0517
    with pytest.raises(ValueError, match="stopped"):
        recorded(root, run(status=Status.Stopped))
    with pytest.raises(ValueError, match="measured nothing"):
        recorded(root, {**run(status=Status.Failed), "cases": []})
    assert not (root / quality.EVALS).exists()


def test_every_release_loads_the_recorded_runs_after_the_migrations():
    # R-0517
    deploy = (REPO / ".github" / "workflows" / "release.yml").read_text()
    assert deploy.index("flask admin db upgrade") < deploy.index("flask admin quality load")
    image = (REPO / "Dockerfile").read_text()
    assert f"COPY {quality.EVALS} /app/{quality.EVALS}" in image
    assert f"COPY {quality.F1} /app/{quality.F1}" in image


def test_a_subscription_run_is_kept_apart_from_paid_runs(flask_app, root):
    # R-0568
    recorded(root, {**run(), "source": Source.Subscription, "cost": 0.0})
    quality.load(root)
    assert {row.source for row in rows().values()} == {Source.Subscription}
    f1 = QualityRun.query.filter_by(kind=QualityKind.ExtractionF1)
    assert {row.source for row in f1} == {Source.Api}
