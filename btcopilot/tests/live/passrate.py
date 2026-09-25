"""Pass rate by model, read from the live runs' results files:

uv run python -m btcopilot.tests.live.passrate
"""

import json
from collections import defaultdict
from pathlib import Path

from btcopilot.tests.live.run import RESULTS, Outcome, Status

SCORED = (Outcome.Passed, Outcome.Failed)


def rates(results: Path = RESULTS) -> dict[str, dict]:
    """Per model: how its runs ended, and each case's passes over its scored runs."""
    models = defaultdict(
        lambda: {"runs": defaultdict(int), "cases": defaultdict(lambda: [0, 0])}
    )
    for path in sorted(results.glob("????-??-??T*.json")):
        row = json.loads(path.read_text())
        model = models[row["model"]]
        model["runs"][Status(row["status"])] += 1
        for case in row["cases"]:
            if case["outcome"] in SCORED:
                tally = model["cases"][case["case"]]
                tally[0] += case["outcome"] == Outcome.Passed
                tally[1] += 1
    return models


def main() -> None:
    for model, seen in rates().items():
        runs = ", ".join(f"{count} {status}" for status, count in seen["runs"].items())
        passed = sum(p for p, _ in seen["cases"].values())
        scored = sum(n for _, n in seen["cases"].values())
        print(f"{model}: {passed} of {scored} case runs passed ({runs})")
        for case, (p, n) in sorted(seen["cases"].items()):
            print(f"  {p}/{n}  {case}")


if __name__ == "__main__":
    main()
