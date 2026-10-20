"""Pass rate and cost of the cluster F1 suite's tries, per model and case, read
from the eval ledger's `clusters/` lines and printed as a markdown table
[Oracle: R-0856]:

    uv run python -m btcopilot.tests.live.clusters.passrate [ledger.jsonl]

The ledger is the live suite's unless one is named, such as a saved worker run's own in the private
corpus under $BTCOPILOT_SOURCES/btcopilot-runs/clusters/runs-worker/. Point it at one run's lines: tries are counted per line. The cost
columns read the paid lines only, so a ledger of replays shows its pass rate
with no cost. Per user-month is the cost of one call times 37.8 calls: 4.5
turns a day for 30 days, 28% of them making a grouping call.
"""

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from btcopilot import ledger
from btcopilot.models.qualityrun import Source
from btcopilot.provider import app_model
from btcopilot.quality import Outcome

CALLS_PER_USER_MONTH = 4.5 * 30 * 0.28
HEADER = (
    "| model | case | tries | passes | pass rate | cost per call "
    "| tokens in per call | tokens out per call | per user-month |"
)


@dataclass
class Tally:
    tries: int = 0
    passes: int = 0
    calls: int = 0
    cost: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0


def tallies(path: Path = ledger.PATH) -> dict[tuple[str, str], Tally]:
    """Per model, by the app's name for it, and case: tries and passes over
    every line, calls, dollars and tokens over the paid ones."""
    found: dict[tuple[str, str], Tally] = defaultdict(Tally)
    for text in path.read_text().splitlines():
        row = json.loads(text)
        if not row["case"].startswith("clusters/"):
            continue
        model = app_model(row["model"] or row["requested"])
        tally = found[model, row["case"].removeprefix("clusters/")]
        tally.tries += 1
        tally.passes += row["outcome"] == Outcome.Passed
        if row["source"] != Source.Api:
            continue
        spent = row["tokens"]
        tally.calls += row["turns"]
        tally.cost += row["cost"]
        tally.tokens_in += (
            spent["input"] + spent["cache_creation"] + spent["cache_read"]
        )
        tally.tokens_out += spent["output"]
    return found


def table(found: dict[tuple[str, str], Tally]) -> str:
    lines = [HEADER, "|" + " --- |" * HEADER.count(" | ") + " --- |"]
    for (model, case), tally in sorted(found.items()):
        if tally.calls:
            per = tally.cost / tally.calls
            spend = (
                f"${per:.4f} | {tally.tokens_in / tally.calls:,.0f} "
                f"| {tally.tokens_out / tally.calls:,.0f} "
                f"| ${per * CALLS_PER_USER_MONTH:.2f}"
            )
        else:
            spend = "- | - | - | -"
        lines.append(
            f"| {model} | {case} | {tally.tries} | {tally.passes} "
            f"| {tally.passes / tally.tries:.0%} | {spend} |"
        )
    return "\n".join(lines)


def main() -> None:
    print(table(tallies(Path(sys.argv[1]) if len(sys.argv) > 1 else ledger.PATH)))


if __name__ == "__main__":
    main()
