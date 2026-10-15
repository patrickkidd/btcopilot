"""The cluster F1 suite: the app's grouping call, `detect_clusters` on Gemini as
production makes it, run once on each case and scored against the case's
expected clusters (score.py) [Oracle: R-0856]. The cases are in cases/; the
one built from Patrick's diagram is the one the prompts are tuned on, the
others are placeholders until real cases arrive. How to run it, and what it
costs: README.md, "Cluster F1".

CLUSTER_ANSWERS, when set, is a folder of answers served in place of Gemini,
one `<case>.json` each holding `{"answers": [...]}` in the order the calls are
made: answers/ holds hand-written ones that prove the runner with no network,
and every run's own folder under runs/ replays that run at $0. Each case's
answers, stored clusters and score go to runs/<time>/<case>.json, and one line
per case to the eval ledger (CLUSTER_LEDGER, by default the live suite's).
"""

import datetime
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from btcopilot import ledger
from btcopilot.clusters import (
    ClusterError,
    ClusterListResponse,
    detect_clusters,
)
from btcopilot.llmutil import (
    EXTRACTION_MODEL,
    Billed,
    Served,
    Spent,
    gemini_structured_sync,
)
from btcopilot.pricing import cost
from btcopilot.quality import Outcome, Source
from btcopilot.schema import from_dict
from btcopilot.tests.live.clusters.cases import Case, load
from btcopilot.tests.live.clusters.score import Rule, Score, score
from btcopilot.tests.live.criterion import once

HERE = Path(__file__).parent
ANSWERS = os.environ.get("CLUSTER_ANSWERS")
LEDGER = Path(os.environ.get("CLUSTER_LEDGER", ledger.PATH))
GIT = subprocess.run(
    ["git", "-C", str(HERE), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
).stdout.strip()
RUN = HERE / "runs" / f"{datetime.datetime.now():%Y-%m-%dT%H%M%S}"
CASES = load()


@dataclass(frozen=True)
class Bar:
    """What a case must reach to pass: cluster F1, event-membership F1 within
    the paired clusters, and the rules that may not miss."""

    clusters: float
    members: float
    rules: frozenset[Rule] = frozenset(Rule) - {Rule.Opening}


BARS = {
    "patrick": Bar(0.8, 0.7),
    "patrick-unasked": Bar(0.8, 0.7),
    # the birth must be named as the run's opening
    "addition": Bar(1.0, 0.8, frozenset(Rule)),
    # nothing stored: no cluster expected, so any stored one fails it
    "thin": Bar(1.0, 1.0),
    "dense": Bar(0.8, 0.7),
}


class Asker:
    """`ask` for detect_clusters: Gemini, or the case's saved answers."""

    def __init__(self, case: Case):
        self.saved = (
            json.loads((Path(ANSWERS) / f"{case.name}.json").read_text())
            if ANSWERS
            else None
        )
        self.answers: list[dict] = []
        self.spent = Spent()
        self.cost = Decimal(0)
        self.model = self.saved.get("model", "hand-written") if self.saved else None

    def _charge(self, served: Served, spent: Spent) -> None:
        self.model = served.model
        self.spent.add(spent)
        self.cost += cost(served.model, spent)

    def __call__(self, prompt: str, schema: dict, limit: int) -> ClusterListResponse:
        if self.saved is not None:
            if len(self.answers) == len(self.saved["answers"]):
                raise LookupError(f"no saved answer for call {len(self.answers) + 1}")
            answer = from_dict(ClusterListResponse, self.saved["answers"][len(self.answers)])
        else:
            try:
                parsed = gemini_structured_sync(
                    prompt, ClusterListResponse, schema=schema, limit=limit
                )
            except Billed as paid:
                self._charge(paid.served, paid.spent)
                raise
            self._charge(parsed.served, parsed.spent)
            answer = parsed.value
        self.answers.append(asdict(answer))
        return answer


def numbers(result: Score) -> dict:
    agreed, of = result.openings
    return {
        "clusters": asdict(result.clusters),
        "members": asdict(result.members),
        "openings": [agreed, of],
    }


def line(case: Case, stored, result: Score, refused: list[str], misses) -> str:
    c = result.clusters
    agreed, of = result.openings
    verdict = "pass" if not misses else "FAIL " + "; ".join(misses)
    tag = " (placeholder)" if case.placeholder else ""
    return (
        f"{case.name:18}{len(case.expected):>5}{len(stored):>5}{len(result.pairs):>7}"
        f"{c.precision:>6.2f}{c.recall:>6.2f}{c.f1:>6.2f}{result.members.f1:>10.2f}"
        f"{f'{agreed}/{of}':>9}{len(refused):>8}  {verdict}{tag}"
    )


def keep(case: Case, ask: Asker, stored, result: Score, refused, misses, ms) -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / f"{case.name}.json").write_text(
        json.dumps(
            {
                "model": ask.model,
                "answers": ask.answers,
                "refused": refused,
                "stored": [asdict(c) for c in stored],
                "score": numbers(result),
                "misses": misses,
                "cost": float(ask.cost),
            },
            indent=1,
        )
    )
    ledger.append(
        {
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(
                timespec="seconds"
            ),
            "kind": ledger.LedgerKind.Live,
            "git": GIT,
            "model": ask.model,
            "requested": EXTRACTION_MODEL,
            "discussion_id": None,
            "reference_diagram_id": None,
            "scratch_diagram_id": None,
            "scratch_discussion_id": None,
            "case": f"clusters/{case.name}",
            "outcome": Outcome.Failed if misses else Outcome.Passed,
            "turns": len(ask.answers),
            "scores": numbers(result),
            "faults": [*misses, *refused],
            "tokens": asdict(ask.spent),
            "cost": float(ask.cost),
            "duration_ms": ms,
            "source": None if ANSWERS else Source.Api,
        },
        LEDGER,
    )


@once
@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_grouping_matches_the_expected_clusters(case, board):
    # R-0856, R-0850, R-0853
    """Pass: the case's bar in BARS, cluster F1 and event F1 at least its
    numbers, and none of its rules missed."""
    ask = Asker(case)
    refused: list[str] = []
    started = time.monotonic()
    try:
        stored = detect_clusters(
            case.data,
            ask,
            lambda n, error, _: refused.append(f"answer {n}: {error.check.value}: {error}"),
            case.said,
        ).clusters
    except ClusterError as failed:
        # production keeps what was stored before, here nothing
        refused.append(f"gave up: {failed.check.value}: {failed}")
        stored = []
    ms = round((time.monotonic() - started) * 1000)
    result = score(stored, case.expected, case.data, case.theirs)
    bar = BARS[case.name]
    misses = result.missed(bar.rules)
    if result.clusters.f1 < bar.clusters:
        misses.append(f"cluster F1 {result.clusters.f1:.2f} under {bar.clusters}")
    if result.members.f1 < bar.members:
        misses.append(f"event F1 {result.members.f1:.2f} under {bar.members}")
    keep(case, ask, stored, result, refused, misses, ms)
    board.append(line(case, stored, result, refused, misses))
    for cluster in stored:
        print(
            f"  {cluster.source} {cluster.startDate[:7]}..{cluster.endDate[:7]} "
            f"{cluster.eventIds} opens {cluster.openingEventId} {cluster.name!r}"
        )
    print(f"  {ask.model}: ${ask.cost:.4f}; {refused}")
    assert not misses
