"""The cluster F1 suite: cluster detection, `detect_clusters` on Gemini as
production calls it, or on CLUSTER_MODEL, tried CLUSTER_TRIES times (once by
default) on each case and scored against the case's expected clusters
(score.py) [Oracle: R-0856]. The cases are in cases/; the four-generation one,
`deep`, is the one the prompts are tuned on, its key signed by Patrick
[Oracle: R-0857]; the others are placeholders until real cases arrive. How to
use it, and what it costs: README.md, "Cluster F1".

CLUSTER_ANSWERS, when set, is a folder of answers served in place of the LLM's,
one `<case>-<try>.json` per try (or one `<case>.json` for every try) holding
`{"answers": [...]}` in the order the calls are made, a failed call saved in
its place: `answers/` holds hand-written ones that prove the harness with no
network, and the folder each earlier session wrote under `runs/` replays it at
$0. Each try's answers, stored clusters and score go to
`runs/<time>-<model>-<process>/<case>-<try>.json`, and one line per try to the
eval ledger (CLUSTER_LEDGER, by default the live suite's).
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
    UNANSWERED,
    Billed,
    OutputTruncatedError,
    Served,
    Spent,
    Unreadable,
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
MODEL = os.environ.get("CLUSTER_MODEL", EXTRACTION_MODEL)
TRIES = range(int(os.environ.get("CLUSTER_TRIES", "1")))
GIT = subprocess.run(
    ["git", "-C", str(HERE), "rev-parse", "HEAD"],
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()
# Each session's folder names its start, CLUSTER_MODEL (or "replay") and its
# process, so two sessions started in the same second never share one.
STARTED = f"{datetime.datetime.now():%Y-%m-%dT%H%M%S}"
RUN = HERE / "runs" / f"{STARTED}-{'replay' if ANSWERS else MODEL}-{os.getpid()}"
CASES = load()


@dataclass(frozen=True)
class Bar:
    """What a case must reach to pass: cluster F1, event-membership F1 within
    the paired clusters, and the rules that may not miss."""

    clusters: float
    members: float
    rules: frozenset[Rule] = frozenset(Rule) - {Rule.Opening}


BARS = {
    "deep": Bar(0.8, 0.7),
    "deep-unasked": Bar(0.8, 0.7),
    "orchard": Bar(0.8, 0.7),
    "orchard-unasked": Bar(0.8, 0.7),
    # the birth must be named as the cluster's opening
    "addition": Bar(1.0, 0.8, frozenset(Rule)),
    # nothing stored: no cluster expected, so any stored one fails it
    "thin": Bar(1.0, 1.0),
    "dense": Bar(0.8, 0.7),
}


# A call that failed is saved in its place among the answers, so a replay fails
# it the same way; one that never came back replays as a timeout.
FAILED = {kind.__name__: kind for kind in (OutputTruncatedError, Unreadable, Billed)}


def failure(error: Exception) -> dict:
    return {"failed": type(error).__name__, "error": str(error)}


def saved(case: Case, k: int) -> Path:
    """Try k's saved answers, or the case's when the folder has one try."""
    tried = Path(ANSWERS) / f"{case.name}-{k}.json"
    return tried if tried.exists() else Path(ANSWERS) / f"{case.name}.json"


class Asker:
    """`ask` for detect_clusters: a call to CLUSTER_MODEL, or try k's saved
    answers."""

    def __init__(self, case: Case, k: int):
        self.saved = json.loads(saved(case, k).read_text()) if ANSWERS else None
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
            said = self.saved["answers"][len(self.answers)]
            if "failed" in said:
                self.answers.append(said)
                kind = FAILED.get(said["failed"])
                if kind is None:
                    raise TimeoutError(said["error"])
                raise kind(said["error"], Served(model=self.model), Spent())
            answer = from_dict(ClusterListResponse, said)
        else:
            try:
                parsed = gemini_structured_sync(
                    prompt, ClusterListResponse, model=MODEL, schema=schema, limit=limit
                )
            except Billed as paid:
                self._charge(paid.served, paid.spent)
                self.answers.append(failure(paid))
                raise
            except UNANSWERED as lost:
                self.answers.append(failure(lost))
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
        "hypotheses": len(result.hypotheses),
        "not clusters": result.count(Rule.NotACluster),
        "voice": result.count(Rule.Voice),
        "cause": result.count(Rule.Cause),
        "id violations": result.count(Rule.Id),
    }


def signed(case: Case) -> int:
    """The clusters a try is scored on: the case's key less its hypotheses."""
    return sum(not e.hypothesis for e in case.expected)


def line(case: Case, k: int, stored, result: Score, refused: list[str], misses) -> str:
    c = result.clusters
    agreed, of = result.openings
    verdict = "pass" if not misses else "FAIL " + "; ".join(misses)
    tag = " (placeholder)" if case.placeholder else ""
    name = case.name if len(TRIES) == 1 else f"{case.name}-{k}"
    return (
        f"{name:18}{signed(case):>5}{len(stored):>5}{len(result.pairs):>7}"
        f"{c.precision:>6.2f}{c.recall:>6.2f}{c.f1:>6.2f}{result.members.f1:>10.2f}"
        f"{f'{agreed}/{of}':>9}{len(refused):>8}"
        f"{result.count(Rule.Voice):>6}{result.count(Rule.Cause):>6}  {verdict}{tag}"
    )


def keep(
    case: Case, k: int, ask: Asker, stored, result: Score, refused, misses, ms
) -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / f"{case.name}-{k}.json").write_text(
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
            "requested": MODEL,
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
@pytest.mark.parametrize("k", TRIES)
@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_grouping_matches_the_expected_clusters(case, k, board):
    # R-0856, R-0857, R-0850, R-0853
    """Pass: the case's bar in BARS, cluster F1 and event F1 at least its
    numbers, and none of its rules missed. Each try is one call of cluster
    detection on the same inputs, two when the first answer is refused. A
    cluster the case marks hypothesis counts neither way; storing a period the
    case says is not a cluster misses."""
    ask = Asker(case, k)
    refused: list[str] = []
    started = time.monotonic()
    try:
        stored = detect_clusters(
            case.data,
            ask,
            lambda n, error, _: refused.append(
                f"answer {n}: {error.check.value}: {error}"
            ),
            case.said,
        ).clusters
    except ClusterError as failed:
        # production keeps what was stored before, here nothing
        refused.append(f"gave up: {failed.check.value}: {failed}")
        stored = []
    ms = round((time.monotonic() - started) * 1000)
    result = score(stored, case.expected, case.data, case.theirs, case.not_clusters)
    bar = BARS[case.name]
    misses = result.missed(bar.rules | {Rule.Voice, Rule.Cause, Rule.Id})
    if result.clusters.f1 < bar.clusters:
        misses.append(f"cluster F1 {result.clusters.f1:.2f} under {bar.clusters}")
    if result.members.f1 < bar.members:
        misses.append(f"event F1 {result.members.f1:.2f} under {bar.members}")
    keep(case, k, ask, stored, result, refused, misses, ms)
    board.append(line(case, k, stored, result, refused, misses))
    held = {c.id: e.name for c, e in result.hypotheses}
    for cluster in stored:
        aside = f" (the hypothesis {held[cluster.id]!r})" if cluster.id in held else ""
        print(
            f"  {cluster.source} {cluster.startDate[:7]}..{cluster.endDate[:7]} "
            f"{cluster.eventIds} opens {cluster.openingEventId} {cluster.name!r}{aside}"
        )
    print(f"  {ask.model}: ${ask.cost:.4f}; {refused}")
    assert not misses
