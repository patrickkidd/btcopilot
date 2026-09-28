import json

import pytest

from btcopilot import ledger


def row(**changes) -> dict:
    return {
        "at": "2026-09-28T10:00:00+00:00",
        "kind": ledger.LedgerKind.Replay.value,
        "git": "ee416c19",
        "model": "claude-sonnet-5",
        "requested": "sonnet-5",
        "discussion_id": 1,
        "reference_diagram_id": 2,
        "scratch_diagram_id": 3,
        "scratch_discussion_id": 4,
        "case": None,
        "outcome": None,
        "turns": 12,
        "scores": {"people": 0.9, "pair_bonds": 1.0},
        "faults": {"tool_refused": 1},
        "tokens": {"input": 10, "output": 5, "cache_creation": 0, "cache_read": 0},
        "cost": 0.01,
        "duration_ms": 900,
        "source": "api",
        **changes,
    }


def test_each_append_is_one_line(tmp_path):
    # R-0590
    path = tmp_path / "ledger.jsonl"
    ledger.append(row(), path)
    ledger.append(row(kind=ledger.LedgerKind.Live.value, case="t1"), path)
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert lines == [row(), row(kind="live", case="t1")]


def test_a_row_off_the_schema_is_refused(tmp_path):
    # R-0590
    path = tmp_path / "ledger.jsonl"
    with pytest.raises(KeyError):
        ledger.append(row(score=1.0), path)
    missing = row()
    del missing["faults"]
    with pytest.raises(KeyError):
        ledger.append(missing, path)
    with pytest.raises(ValueError):
        ledger.append(row(kind="rerun"), path)
    assert not path.exists()
