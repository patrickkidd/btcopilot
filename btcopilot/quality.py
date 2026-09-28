"""The quality dashboard's recorded runs, loaded from the repository into
production on every release (R-0517): each kept live run in quality/evals, as
its cases' passes and the share that passed, and the old extraction F1 history.
A run already loaded is updated in place, so loading twice changes nothing."""

import datetime
import enum
import json
from pathlib import Path

from btcopilot.extensions import db
from btcopilot.models import QualityKind, QualityRun
from btcopilot.models.qualityrun import Source

EVALS = Path("quality") / "evals"
F1 = Path("doc") / "f1" / "f1_timeseries.json"
OVERALL = "overall"


class Outcome(enum.StrEnum):
    Passed = "passed"
    Failed = "failed"
    Skipped = "skipped"
    Awaiting = "awaiting"


class Status(enum.StrEnum):
    Passed = "passed"
    Failed = "failed"
    Stopped = "stopped"
    Awaiting = "awaiting"


SCORED = (Outcome.Passed, Outcome.Failed)


def ran(text: str) -> datetime.datetime:
    at = datetime.datetime.fromisoformat(text)
    return at.astimezone(datetime.timezone.utc).replace(tzinfo=None) if at.tzinfo else at


def evals(run: dict) -> list[dict]:
    passed = {
        case["case"]: float(case["outcome"] == Outcome.Passed)
        for case in run["cases"]
        if case["outcome"] in SCORED
    }
    passed[OVERALL] = sum(passed.values()) / len(passed)
    return [
        {
            "ran_at": ran(run["date"]),
            "commit": run["git"],
            "model": run["model"],
            "kind": QualityKind.EvalPassRate,
            "metric": metric,
            "value": value,
            "note": run["note"],
            "source": Source(run["source"]),
        }
        for metric, value in passed.items()
    ]


def f1(history: dict) -> list[dict]:
    return [
        {
            "ran_at": ran(point["date"]),
            "commit": point["commit"],
            "model": point.get("model"),
            "kind": QualityKind.ExtractionF1,
            "metric": metric,
            "value": point[metric],
            "note": point["note"],
            "source": Source.Api,
        }
        for point in history["data"]
        for metric in history["metrics"]
        if point.get(metric) is not None
    ]


def load(root: Path) -> int:
    found = f1(json.loads((root / F1).read_text())) + [
        row
        for path in sorted((root / EVALS).glob("*.json"))
        for row in evals(json.loads(path.read_text()))
    ]
    kept = {
        (row.kind, row.ran_at, row.commit, row.metric): row
        for row in QualityRun.query
    }
    for row in found:
        same = kept.get((row["kind"], row["ran_at"], row["commit"], row["metric"]))
        if same:
            same.update(**row)
        else:
            db.session.add(QualityRun(**row))
    db.session.commit()
    return len(found)
