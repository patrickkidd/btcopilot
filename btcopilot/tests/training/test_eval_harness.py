"""Tests for the extraction evaluation harness per-entity-type F1 breakdown."""

import json

import pytest

from btcopilot.training.f1_metrics import F1Metrics, CumulativeF1Metrics, calculate_f1_from_counts
from btcopilot.training.eval_harness import (
    build_eval_result,
    format_table,
    format_json,
    EvalResult,
    DiscussionEvalResult,
    EntityTypeBreakdown,
    AggregateBreakdown,
)


def _make_cumulative(
    disc_id: int,
    people_tp=2,
    people_fp=1,
    people_fn=0,
    events_tp=3,
    events_fp=2,
    events_fn=1,
    bonds_tp=0,
    bonds_fp=0,
    bonds_fn=1,
    summary="Test discussion",
) -> CumulativeF1Metrics:
    """Helper to build a CumulativeF1Metrics with known counts."""

    people_m = calculate_f1_from_counts(people_tp, people_fp, people_fn)
    events_m = calculate_f1_from_counts(events_tp, events_fp, events_fn)
    bonds_m = calculate_f1_from_counts(bonds_tp, bonds_fp, bonds_fn)

    total_tp = people_tp + events_tp + bonds_tp
    total_fp = people_fp + events_fp + bonds_fp
    total_fn = people_fn + events_fn + bonds_fn
    agg = calculate_f1_from_counts(total_tp, total_fp, total_fn)

    return CumulativeF1Metrics(
        discussion_id=disc_id,
        discussion_summary=summary,
        auditor_id="test@example.com",
        aggregate_micro_f1=agg.f1,
        people_f1=people_m.f1,
        events_f1=events_m.f1,
        pair_bonds_f1=bonds_m.f1,
        people_metrics=people_m,
        events_metrics=events_m,
        pair_bonds_metrics=bonds_m,
        ai_people_count=people_tp + people_fp,
        ai_events_count=events_tp + events_fp,
        gt_people_count=people_tp + people_fn,
        gt_events_count=events_tp + events_fn,
    )


class TestBuildEvalResult:
    """Tests for build_eval_result()."""

    def test_empty_input(self):
        result = build_eval_result([])
        assert result.discussion_count == 0
        assert result.per_discussion == []
        assert result.aggregate == []

    def test_single_discussion(self):
        m = _make_cumulative(50, people_tp=3, people_fp=1, people_fn=0)
        result = build_eval_result([m])

        assert result.discussion_count == 1
        assert len(result.per_discussion) == 1
        assert len(result.aggregate) == 5

        disc = result.per_discussion[0]
        assert disc.discussion_id == 50
        assert len(disc.entity_types) == 5

        # Verify entity type names
        names = [e.entity_type for e in disc.entity_types]
        assert names == ["People", "Events", "Structural", "Shift", "PairBonds"]

    def test_multiple_discussions(self):
        metrics = [
            _make_cumulative(50, people_tp=2, people_fp=1, people_fn=0),
            _make_cumulative(51, people_tp=4, people_fp=0, people_fn=1),
        ]
        result = build_eval_result(metrics)

        assert result.discussion_count == 2
        assert len(result.per_discussion) == 2

        # Check aggregate People TP is sum
        people_agg = result.aggregate[0]
        assert people_agg.entity_type == "People"
        assert people_agg.total_tp == 6  # 2 + 4
        assert people_agg.total_fp == 1  # 1 + 0
        assert people_agg.total_fn == 1  # 0 + 1

    def test_per_discussion_entity_counts(self):
        m = _make_cumulative(
            50,
            people_tp=3,
            people_fp=1,
            people_fn=2,
            events_tp=5,
            events_fp=0,
            events_fn=3,
        )
        result = build_eval_result([m])
        disc = result.per_discussion[0]

        people = disc.entity_types[0]
        assert people.tp == 3
        assert people.fp == 1
        assert people.fn == 2
        assert people.ai_count == 4  # tp + fp
        assert people.gt_count == 5  # tp + fn

        events = disc.entity_types[1]
        assert events.tp == 5
        assert events.fp == 0
        assert events.fn == 3

    def test_aggregate_micro_f1(self):
        """Micro F1 should be computed from pooled TP/FP/FN, not averaged."""
        metrics = [
            _make_cumulative(50, people_tp=5, people_fp=0, people_fn=0),
            _make_cumulative(51, people_tp=0, people_fp=5, people_fn=5),
        ]
        result = build_eval_result(metrics)

        people_agg = result.aggregate[0]
        # Pooled: TP=5, FP=5, FN=5 → P=0.5, R=0.5, F1=0.5
        assert people_agg.total_tp == 5
        assert people_agg.total_fp == 5
        assert people_agg.total_fn == 5
        assert people_agg.micro_f1 == pytest.approx(0.5)

        # Avg F1: (1.0 + 0.0) / 2 = 0.5 — same in this case
        assert people_agg.avg_f1 == pytest.approx(0.5)


class TestFormatJson:
    """Tests for format_json() output schema."""

    def test_json_schema_keys(self):
        m = _make_cumulative(50)
        result = build_eval_result([m])
        output = format_json(result)

        # Top-level keys
        assert "discussion_count" in output
        assert "aggregate_f1" in output
        assert "aggregate" in output
        assert "per_discussion" in output

    def test_json_aggregate_schema(self):
        m = _make_cumulative(50)
        result = build_eval_result([m])
        output = format_json(result)

        assert len(output["aggregate"]) == 5
        for agg in output["aggregate"]:
            assert "entity_type" in agg
            assert "avg_f1" in agg
            assert "micro_f1" in agg
            assert "micro_precision" in agg
            assert "micro_recall" in agg
            assert "total_tp" in agg
            assert "total_fp" in agg
            assert "total_fn" in agg

        entity_types = [a["entity_type"] for a in output["aggregate"]]
        assert entity_types == ["People", "Events", "Structural", "Shift", "PairBonds"]

    def test_json_per_discussion_schema(self):
        m = _make_cumulative(50)
        result = build_eval_result([m])
        output = format_json(result)

        assert len(output["per_discussion"]) == 1
        disc = output["per_discussion"][0]
        assert "discussion_id" in disc
        assert "summary" in disc
        assert "auditor_id" in disc
        assert "aggregate_f1" in disc
        assert "entity_types" in disc
        assert len(disc["entity_types"]) == 5

        for et in disc["entity_types"]:
            assert "entity_type" in et
            assert "f1" in et
            assert "precision" in et
            assert "recall" in et
            assert "tp" in et
            assert "fp" in et
            assert "fn" in et
            assert "ai_count" in et
            assert "gt_count" in et

    def test_json_serializable(self):
        """Ensure output can be serialized to JSON without errors."""
        metrics = [_make_cumulative(50), _make_cumulative(51)]
        result = build_eval_result(metrics)
        output = format_json(result)

        # Should not raise
        json_str = json.dumps(output)
        parsed = json.loads(json_str)
        assert parsed["discussion_count"] == 2

    def test_json_values_match_input(self):
        m = _make_cumulative(
            50, people_tp=4, people_fp=1, people_fn=2, events_tp=6, events_fp=0, events_fn=3
        )
        result = build_eval_result([m])
        output = format_json(result)

        disc = output["per_discussion"][0]
        people = disc["entity_types"][0]
        assert people["entity_type"] == "People"
        assert people["tp"] == 4
        assert people["fp"] == 1
        assert people["fn"] == 2

        events = disc["entity_types"][1]
        assert events["entity_type"] == "Events"
        assert events["tp"] == 6
        assert events["fp"] == 0
        assert events["fn"] == 3

    def test_empty_result_json(self):
        result = build_eval_result([])
        output = format_json(result)
        assert output["discussion_count"] == 0
        assert output["per_discussion"] == []
        assert output["aggregate"] == []


class TestFormatTable:
    """Tests for format_table() human-readable output."""

    def test_table_contains_entity_types(self):
        m = _make_cumulative(50)
        result = build_eval_result([m])
        table = format_table(result)

        assert "People" in table
        assert "Events" in table
        assert "PairBonds" in table

    def test_table_contains_discussion_id(self):
        m = _make_cumulative(50, summary="Test family")
        result = build_eval_result([m])
        table = format_table(result)

        assert "Discussion 50" in table
        assert "Test family" in table

    def test_table_contains_aggregate_section(self):
        m = _make_cumulative(50)
        result = build_eval_result([m])
        table = format_table(result)

        assert "AGGREGATE" in table

    def test_table_contains_pass_fail(self):
        m = _make_cumulative(50, people_tp=10, people_fp=0, people_fn=0)
        result = build_eval_result([m])
        table = format_table(result)

        # People F1 = 1.0 > 0.7, so should PASS
        assert "PASS" in table

    def test_table_empty_result(self):
        result = build_eval_result([])
        table = format_table(result)
        assert "No discussions" in table

    def test_table_multiple_discussions(self):
        metrics = [
            _make_cumulative(50, summary="Family A"),
            _make_cumulative(51, summary="Family B"),
        ]
        result = build_eval_result(metrics)
        table = format_table(result)

        assert "Discussion 50" in table
        assert "Discussion 51" in table
        assert "Family A" in table
        assert "Family B" in table
        assert "2 discussions" in table

    def test_table_contains_header_columns(self):
        m = _make_cumulative(50)
        result = build_eval_result([m])
        table = format_table(result)

        assert "F1" in table
        assert "Prec" in table
        assert "Rec" in table
        assert "TP" in table
        assert "FP" in table
        assert "FN" in table
