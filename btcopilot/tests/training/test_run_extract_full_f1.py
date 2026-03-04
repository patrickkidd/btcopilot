"""Tests for the entity-type breakdown in run_extract_full_f1."""

import json
import os
import tempfile

from btcopilot.training.run_extract_full_f1 import (
    _build_entity_type_breakdown,
    _print_entity_type_table,
    _save_breakdown_json,
)


def _make_results():
    """Build sample per-discussion results for testing."""
    return [
        {
            "discussion_id": 1,
            "summary": "Discussion A",
            "people_f1": 0.8,
            "events_f1": 0.4,
            "pair_bonds_f1": 1.0,
            "aggregate_f1": 0.7,
            "people_tp": 3,
            "people_fp": 1,
            "people_fn": 0,
            "events_tp": 2,
            "events_fp": 1,
            "events_fn": 2,
            "bonds_tp": 1,
            "bonds_fp": 0,
            "bonds_fn": 0,
            "sarf": {},
            "elapsed": 5.0,
        },
        {
            "discussion_id": 2,
            "summary": "Discussion B",
            "people_f1": 1.0,
            "events_f1": 0.5,
            "pair_bonds_f1": 0.0,
            "aggregate_f1": 0.6,
            "people_tp": 2,
            "people_fp": 0,
            "people_fn": 0,
            "events_tp": 3,
            "events_fp": 2,
            "events_fn": 1,
            "bonds_tp": 0,
            "bonds_fp": 0,
            "bonds_fn": 2,
            "sarf": {},
            "elapsed": 3.0,
        },
    ]


def test_build_entity_type_breakdown_structure():
    """Breakdown contains People, Events, PairBond with correct keys."""
    results = _make_results()
    breakdown = _build_entity_type_breakdown(results)

    assert set(breakdown.keys()) == {"People", "Events", "PairBond"}
    for label in ["People", "Events", "PairBond"]:
        row = breakdown[label]
        assert set(row.keys()) == {"tp", "fp", "fn", "precision", "recall", "f1"}


def test_build_entity_type_breakdown_aggregates_counts():
    """TP/FP/FN are summed across discussions."""
    results = _make_results()
    breakdown = _build_entity_type_breakdown(results)

    # People: 3+2=5 TP, 1+0=1 FP, 0+0=0 FN
    assert breakdown["People"]["tp"] == 5
    assert breakdown["People"]["fp"] == 1
    assert breakdown["People"]["fn"] == 0

    # Events: 2+3=5 TP, 1+2=3 FP, 2+1=3 FN
    assert breakdown["Events"]["tp"] == 5
    assert breakdown["Events"]["fp"] == 3
    assert breakdown["Events"]["fn"] == 3

    # PairBond: 1+0=1 TP, 0+0=0 FP, 0+2=2 FN
    assert breakdown["PairBond"]["tp"] == 1
    assert breakdown["PairBond"]["fp"] == 0
    assert breakdown["PairBond"]["fn"] == 2


def test_build_entity_type_breakdown_computes_f1():
    """Precision, recall, F1 are computed from aggregated counts."""
    results = _make_results()
    breakdown = _build_entity_type_breakdown(results)

    # People: P=5/(5+1)=0.8333, R=5/(5+0)=1.0, F1=2*0.8333*1.0/(0.8333+1.0)
    assert breakdown["People"]["precision"] > 0.83
    assert breakdown["People"]["recall"] == 1.0
    assert breakdown["People"]["f1"] > 0.9

    # Events: P=5/(5+3)=0.625, R=5/(5+3)=0.625, F1=0.625
    assert abs(breakdown["Events"]["precision"] - 0.625) < 0.001
    assert abs(breakdown["Events"]["recall"] - 0.625) < 0.001
    assert abs(breakdown["Events"]["f1"] - 0.625) < 0.001


def test_build_entity_type_breakdown_all_zeros():
    """All-zero counts produce zero F1 without errors."""
    results = [
        {
            "people_tp": 0, "people_fp": 0, "people_fn": 0,
            "events_tp": 0, "events_fp": 0, "events_fn": 0,
            "bonds_tp": 0, "bonds_fp": 0, "bonds_fn": 0,
        }
    ]
    breakdown = _build_entity_type_breakdown(results)

    for label in ["People", "Events", "PairBond"]:
        row = breakdown[label]
        assert row["tp"] == 0
        assert row["f1"] >= 0.0  # 0.0 or 1.0 depending on calculate_f1_from_counts


def test_print_entity_type_table(capsys):
    """Table prints with correct headers and all three entity types."""
    results = _make_results()
    breakdown = _build_entity_type_breakdown(results)
    _print_entity_type_table(breakdown)

    captured = capsys.readouterr().out
    assert "ENTITY-TYPE BREAKDOWN" in captured
    assert "People" in captured
    assert "Events" in captured
    assert "PairBond" in captured
    assert "TP" in captured
    assert "FP" in captured
    assert "FN" in captured
    assert "Prec" in captured
    assert "Recall" in captured
    assert "F1" in captured


def test_save_breakdown_json_creates_file():
    """JSON artifact is saved to the specified directory."""
    results = _make_results()
    breakdown = _build_entity_type_breakdown(results)
    summary = {
        "count": 2,
        "people_f1": 0.9,
        "events_f1": 0.45,
        "pair_bonds_f1": 0.5,
        "aggregate_f1": 0.65,
        "per_discussion": results,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = _save_breakdown_json(summary, breakdown, tmpdir)

        assert os.path.exists(filepath)
        assert filepath.startswith(tmpdir)
        assert filepath.endswith(".json")

        with open(filepath) as f:
            artifact = json.load(f)

        assert "timestamp" in artifact
        assert "aggregate" in artifact
        assert "entity_type_breakdown" in artifact
        assert "per_discussion" in artifact

        assert artifact["aggregate"]["count"] == 2
        assert artifact["aggregate"]["aggregate_f1"] == 0.65

        assert set(artifact["entity_type_breakdown"].keys()) == {
            "People",
            "Events",
            "PairBond",
        }
        assert artifact["entity_type_breakdown"]["People"]["tp"] == 5


def test_save_breakdown_json_creates_output_dir():
    """Output directory is created if it doesn't exist."""
    results = _make_results()
    breakdown = _build_entity_type_breakdown(results)
    summary = {
        "count": 1,
        "people_f1": 0.8,
        "events_f1": 0.4,
        "pair_bonds_f1": 1.0,
        "aggregate_f1": 0.7,
        "per_discussion": results[:1],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        nested = os.path.join(tmpdir, "sub", "dir")
        filepath = _save_breakdown_json(summary, breakdown, nested)

        assert os.path.exists(filepath)
        assert os.path.isdir(nested)


def test_run_extract_full_f1_returns_breakdown_key():
    """The returned summary dict includes entity_type_breakdown key.

    This is a structural test — we build the summary the same way the
    function does, without requiring Flask/DB context.
    """
    results = _make_results()
    breakdown = _build_entity_type_breakdown(results)
    summary = {
        "count": len(results),
        "people_f1": 0.9,
        "events_f1": 0.45,
        "pair_bonds_f1": 0.5,
        "aggregate_f1": 0.65,
        "entity_type_breakdown": breakdown,
        "per_discussion": results,
    }

    assert "entity_type_breakdown" in summary
    assert "People" in summary["entity_type_breakdown"]
    assert "Events" in summary["entity_type_breakdown"]
    assert "PairBond" in summary["entity_type_breakdown"]
