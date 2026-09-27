"""Keeps a live run for the quality dashboard: its results file is copied into
quality/evals with why the change was kept, and the next release loads it.
Committing the copy is the one step by hand.

uv run python -m btcopilot.tests.live.record <results file> "<why it was kept>"
"""

import json
import sys
from pathlib import Path

from btcopilot.quality import EVALS, SCORED, Status
from btcopilot.tests.repo import REPO


def record(path: Path, note: str, kept: Path = REPO / EVALS) -> Path:
    run = json.loads(path.read_text())
    if run["status"] == Status.Stopped:
        raise ValueError(f"{path.name} stopped partway ({run['reason']}); a stopped run is never kept")
    if not any(case["outcome"] in SCORED for case in run["cases"]):
        raise ValueError(f"{path.name} passed or failed no case; it measured nothing")
    kept.mkdir(parents=True, exist_ok=True)
    out = kept / path.name
    out.write_text(json.dumps({**run, "note": note}, indent=2))
    return out


if __name__ == "__main__":
    print(record(Path(sys.argv[1]), sys.argv[2]))
