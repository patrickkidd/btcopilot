"""The eval ledger: one JSON line per replay of a discussion or per live eval
case, so models can be compared on the same work over time."""

import enum
import json
from pathlib import Path

PATH = Path(__file__).parent / "tests" / "live" / "results" / "ledger.jsonl"

FIELDS = frozenset(
    {
        "at",
        "kind",
        "git",
        "model",
        "requested",
        "discussion_id",
        "reference_diagram_id",
        "scratch_diagram_id",
        "scratch_discussion_id",
        "case",
        "outcome",
        "turns",
        "scores",
        "faults",
        "tokens",
        "cost",
        "duration_ms",
        "source",
    }
)


class LedgerKind(enum.StrEnum):
    Replay = "replay"
    Live = "live"


def append(row: dict, path: Path = PATH) -> None:
    if row.keys() != FIELDS:
        raise KeyError(
            f"Ledger row missing {sorted(FIELDS - row.keys())}, "
            f"unknown {sorted(row.keys() - FIELDS)}"
        )
    LedgerKind(row["kind"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")
