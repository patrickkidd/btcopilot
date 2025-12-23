from datetime import datetime

import pytest

from btcopilot.training.f1_metrics import (
    match_people,
    match_events,
    match_pair_bonds,
    calculate_statement_f1,
    calculate_system_f1,
    invalidate_f1_cache,
    normalize_pdp_for_comparison,
    calculate_hierarchical_sarf_f1,
    normalize_name_for_matching,
    dates_within_tolerance,
    calculate_date_similarity,
    F1Metrics,
    SARFVariableF1,
)
from btcopilot.schema import (
    Person,
    Event,
    PairBond,
    PDPDeltas,
    VariableShift,
    EventKind,
    DateCertainty,
)
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.training.models import Feedback


def test_match_people_exact():
    ai_people = [Person(id=-1, name="John Doe")]
    gt_people = [Person(id=-2, name="John Doe")]

    result, id_map = match_people(ai_people, gt_people)

    assert len(result.matched_pairs) == 1
    assert len(result.ai_unmatched) == 0
    assert len(result.gt_unmatched) == 0
    assert id_map == {-1: -2}


def test_match_people_fuzzy():
    ai_people = [Person(id=-1, name="Jon Doe")]
    gt_people = [Person(id=-2, name="John Doe")]

    result, id_map = match_people(ai_people, gt_people)

    assert len(result.matched_pairs) == 1
    assert len(result.ai_unmatched) == 0
    assert len(result.gt_unmatched) == 0
    assert id_map == {-1: -2}


def test_match_people_with_parents():
    parent_a = Person(id=-1, name="Parent A")
    parent_b = Person(id=-2, name="Parent B")
    ai_child = Person(id=-3, name="Child", parents=[-1, -2])
    gt_parent_a = Person(id=-10, name="Parent A")
    gt_parent_b = Person(id=-20, name="Parent B")
    gt_child = Person(id=-30, name="Child", parents=[-10, -20])

    ai_people = [parent_a, parent_b, ai_child]
    gt_people = [gt_parent_a, gt_parent_b, gt_child]

    result, id_map = match_people(ai_people, gt_people)

    assert len(result.matched_pairs) == 3
    assert len(result.ai_unmatched) == 0
    assert len(result.gt_unmatched) == 0
    assert id_map == {-1: -10, -2: -20, -3: -30}


def test_match_people_below_threshold():
    ai_people = [Person(id=-1, name="John Doe")]
    gt_people = [Person(id=-2, name="Jane Smith")]

    result, id_map = match_people(ai_people, gt_people)

    assert len(result.matched_pairs) == 0
    assert len(result.ai_unmatched) == 1
    assert len(result.gt_unmatched) == 1
    assert id_map == {}


def test_match_people_with_title_prefix():
    """Aunt Carol should match Carol"""
    ai_people = [Person(id=-1, name="Aunt Carol")]
    gt_people = [Person(id=-2, name="Carol")]

    result, id_map = match_people(ai_people, gt_people)

    assert len(result.matched_pairs) == 1
    assert id_map == {-1: -2}


def test_match_people_with_dr_prefix():
    """Dr. Smith should match Smith"""
    ai_people = [Person(id=-1, name="Dr. Smith")]
    gt_people = [Person(id=-2, name="Smith")]

    result, id_map = match_people(ai_people, gt_people)

    assert len(result.matched_pairs) == 1
    assert id_map == {-1: -2}


def test_match_people_with_uncle_prefix():
    """Uncle Bob should match Bob"""
    ai_people = [Person(id=-1, name="Uncle Bob")]
    gt_people = [Person(id=-2, name="Bob")]

    result, id_map = match_people(ai_people, gt_people)

    assert len(result.matched_pairs) == 1
    assert id_map == {-1: -2}


def test_match_people_grandma_prefix():
    """Grandma Jones should match Jones"""
    ai_people = [Person(id=-1, name="Grandma Jones")]
    gt_people = [Person(id=-2, name="Jones")]

    result, id_map = match_people(ai_people, gt_people)

    assert len(result.matched_pairs) == 1
    assert id_map == {-1: -2}


def test_normalize_name_strips_titles():
    assert normalize_name_for_matching("Aunt Carol") == "carol"
    assert normalize_name_for_matching("Dr. Smith") == "smith"
    assert normalize_name_for_matching("Uncle Bob") == "bob"
    assert normalize_name_for_matching("Grandma Jones") == "jones"
    assert normalize_name_for_matching("Mr. John Doe") == "john doe"
    assert normalize_name_for_matching("Mrs. Jane Smith") == "jane smith"


def test_normalize_name_preserves_non_title_names():
    assert normalize_name_for_matching("Carol") == "carol"
    assert normalize_name_for_matching("John Doe") == "john doe"


def test_normalize_name_handles_empty():
    assert normalize_name_for_matching("") == ""
    assert normalize_name_for_matching(None) == ""


def test_match_people_extra_ai_detection():
    ai_people = [Person(id=-1, name="John"), Person(id=-2, name="Jane")]
    gt_people = [Person(id=-10, name="John")]

    result, id_map = match_people(ai_people, gt_people)

    assert len(result.matched_pairs) == 1
    assert len(result.ai_unmatched) == 1
    assert len(result.gt_unmatched) == 0


def test_match_people_missing_ai_detection():
    ai_people = [Person(id=-1, name="John")]
    gt_people = [Person(id=-10, name="John"), Person(id=-20, name="Jane")]

    result, id_map = match_people(ai_people, gt_people)

    assert len(result.matched_pairs) == 1
    assert len(result.ai_unmatched) == 0
    assert len(result.gt_unmatched) == 1


def test_match_events_exact():
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Bonded,
            description="Family dinner",
            dateTime=datetime(2024, 1, 1),
            person=-10,
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Bonded,
            description="Family dinner",
            dateTime=datetime(2024, 1, 1),
            person=-20,
        )
    ]
    id_map = {-10: -20}

    result = match_events(ai_events, gt_events, id_map)

    assert len(result.matched_pairs) == 1
    assert len(result.ai_unmatched) == 0
    assert len(result.gt_unmatched) == 0


def test_match_events_fuzzy_description():
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Bonded,
            description="big family dinner party",
            dateTime=datetime(2024, 1, 1),
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Bonded,
            description="family dinner",
            dateTime=datetime(2024, 1, 1),
        )
    ]

    result = match_events(ai_events, gt_events, {})

    assert len(result.matched_pairs) == 1


def test_match_events_date_tolerance():
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Bonded,
            description="Family dinner",
            dateTime=datetime(2024, 1, 1),
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Bonded,
            description="Family dinner",
            dateTime=datetime(2024, 1, 6),
        )
    ]

    result = match_events(ai_events, gt_events, {})

    assert len(result.matched_pairs) == 1


def test_match_events_date_outside_tolerance():
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Bonded,
            description="Family dinner",
            dateTime=datetime(2024, 1, 1),
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Bonded,
            description="Family dinner",
            dateTime=datetime(2024, 1, 15),
        )
    ]

    result = match_events(ai_events, gt_events, {})

    assert len(result.matched_pairs) == 0
    assert len(result.ai_unmatched) == 1
    assert len(result.gt_unmatched) == 1


def test_match_events_different_kind():
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Bonded,
            description="Family dinner",
            dateTime=datetime(2024, 1, 1),
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Shift,
            description="Family dinner",
            dateTime=datetime(2024, 1, 1),
        )
    ]

    result = match_events(ai_events, gt_events, {})

    assert len(result.matched_pairs) == 0
    assert len(result.ai_unmatched) == 1
    assert len(result.gt_unmatched) == 1


def test_match_events_with_resolved_links():
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Bonded,
            description="Wedding",
            dateTime=datetime(2024, 1, 1),
            spouse=-10,
            relationshipTargets=[-10, -20],
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Bonded,
            description="Wedding",
            dateTime=datetime(2024, 1, 1),
            spouse=-100,
            relationshipTargets=[-100, -200],
        )
    ]
    id_map = {-10: -100, -20: -200}

    result = match_events(ai_events, gt_events, id_map)

    assert len(result.matched_pairs) == 1


def test_match_events_mismatched_links():
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Bonded,
            description="Wedding",
            dateTime=datetime(2024, 1, 1),
            spouse=-10,
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Bonded,
            description="Wedding",
            dateTime=datetime(2024, 1, 1),
            spouse=-999,
        )
    ]
    id_map = {-10: -100}

    result = match_events(ai_events, gt_events, id_map)

    assert len(result.matched_pairs) == 0
    assert len(result.ai_unmatched) == 1
    assert len(result.gt_unmatched) == 1


def test_match_events_uncertain_always_matches():
    """Unknown dates always match regardless of actual date distance."""
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Shift,
            description="Something happened",
            dateTime=datetime(2020, 1, 1),
            dateCertainty=DateCertainty.Unknown,
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Shift,
            description="Something happened",
            dateTime=datetime(2025, 12, 31),
            dateCertainty=DateCertainty.Certain,
        )
    ]

    result = match_events(ai_events, gt_events, {})

    assert len(result.matched_pairs) == 1


def test_match_events_approximate_within_tolerance():
    """Approximate dates match within ±270 days (9 months)."""
    # 214 days apart - within 270 day tolerance
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Shift,
            description="Event in the 80s",
            dateTime=datetime(2024, 6, 1),
            dateCertainty=DateCertainty.Approximate,
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Shift,
            description="Event in the 80s",
            dateTime=datetime(2025, 1, 1),
            dateCertainty=DateCertainty.Certain,
        )
    ]

    result = match_events(ai_events, gt_events, {})

    assert len(result.matched_pairs) == 1


def test_match_events_approximate_outside_tolerance():
    """Approximate dates do not match beyond ±270 days (9 months)."""
    # 730 days apart - outside 270 day tolerance
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Shift,
            description="Event years ago",
            dateTime=datetime(2023, 1, 1),
            dateCertainty=DateCertainty.Approximate,
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Shift,
            description="Event years ago",
            dateTime=datetime(2025, 1, 1),
            dateCertainty=DateCertainty.Certain,
        )
    ]

    result = match_events(ai_events, gt_events, {})

    assert len(result.matched_pairs) == 0


def test_match_events_certainty_none_backward_compat():
    """None certainty treated as Certain (backward compat)."""
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Shift,
            description="Event",
            dateTime=datetime(2025, 1, 1),
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Shift,
            description="Event",
            dateTime=datetime(2025, 1, 5),
        )
    ]

    result = match_events(ai_events, gt_events, {})
    assert len(result.matched_pairs) == 1

    gt_events[0].dateTime = datetime(2025, 1, 15)
    result = match_events(ai_events, gt_events, {})
    assert len(result.matched_pairs) == 0


def test_dates_within_tolerance_unknown():
    """Unknown dates always match regardless of actual date."""
    assert dates_within_tolerance(
        "2020-01-01",
        "2025-12-31",
        DateCertainty.Unknown,
        DateCertainty.Certain,
    )
    assert dates_within_tolerance(
        "2020-01-01",
        "2025-12-31",
        DateCertainty.Certain,
        DateCertainty.Unknown,
    )


def test_dates_within_tolerance_approximate():
    """Approximate dates use 270-day (9 month) tolerance."""
    # 214 days apart - within 270 day tolerance
    assert dates_within_tolerance(
        "2024-06-01",
        "2025-01-01",
        DateCertainty.Approximate,
        DateCertainty.Certain,
    )
    # 730 days apart - outside 270 day tolerance
    assert not dates_within_tolerance(
        "2023-01-01",
        "2025-01-01",
        DateCertainty.Approximate,
        DateCertainty.Certain,
    )
    # Edge case: exactly at 270 days should pass
    assert dates_within_tolerance(
        "2024-04-06",  # 270 days before 2025-01-01
        "2025-01-01",
        DateCertainty.Approximate,
        DateCertainty.Certain,
    )
    # Just outside 270 days should fail
    assert not dates_within_tolerance(
        "2024-04-05",  # 271 days before 2025-01-01
        "2025-01-01",
        DateCertainty.Approximate,
        DateCertainty.Certain,
    )


def test_dates_within_tolerance_certain():
    """Certain dates use 7-day tolerance."""
    assert dates_within_tolerance(
        "2025-01-01",
        "2025-01-05",
        DateCertainty.Certain,
        DateCertainty.Certain,
    )
    assert not dates_within_tolerance(
        "2025-01-01",
        "2025-01-15",
        DateCertainty.Certain,
        DateCertainty.Certain,
    )


def test_dates_within_tolerance_none_is_certain():
    """None certainty treated as Certain."""
    assert dates_within_tolerance("2025-01-01", "2025-01-05", None, None)
    assert not dates_within_tolerance("2025-01-01", "2025-01-15", None, None)


def test_calculate_date_similarity_unknown():
    """Unknown dates always return 1.0."""
    assert (
        calculate_date_similarity(
            "2020-01-01",
            "2025-12-31",
            DateCertainty.Unknown,
            DateCertainty.Certain,
        )
        == 1.0
    )


def test_calculate_date_similarity_approximate():
    """Approximate dates use 270-day (9 month) tolerance for similarity."""
    # 214 days apart - within tolerance, partial similarity
    sim = calculate_date_similarity(
        "2024-06-01",
        "2025-01-01",
        DateCertainty.Approximate,
        DateCertainty.Certain,
    )
    assert sim > 0.0
    assert sim < 1.0

    # 730 days apart - outside 270-day tolerance
    sim_far = calculate_date_similarity(
        "2023-01-01",
        "2025-01-01",
        DateCertainty.Approximate,
        DateCertainty.Certain,
    )
    assert sim_far == 0.0


def test_match_pair_bonds_exact():
    ai_bonds = [PairBond(person_a=-1, person_b=-2)]
    gt_bonds = [PairBond(person_a=-10, person_b=-20)]
    id_map = {-1: -10, -2: -20}

    result = match_pair_bonds(ai_bonds, gt_bonds, id_map)

    assert len(result.matched_pairs) == 1
    assert len(result.ai_unmatched) == 0
    assert len(result.gt_unmatched) == 0


def test_match_pair_bonds_reversed():
    ai_bonds = [PairBond(person_a=-1, person_b=-2)]
    gt_bonds = [PairBond(person_a=-20, person_b=-10)]
    id_map = {-1: -10, -2: -20}

    result = match_pair_bonds(ai_bonds, gt_bonds, id_map)

    assert len(result.matched_pairs) == 1


def test_match_pair_bonds_missing():
    ai_bonds = [PairBond(person_a=-1, person_b=-2)]
    gt_bonds = [
        PairBond(person_a=-10, person_b=-20),
        PairBond(person_a=-30, person_b=-40),
    ]
    id_map = {-1: -10, -2: -20}

    result = match_pair_bonds(ai_bonds, gt_bonds, id_map)

    assert len(result.matched_pairs) == 1
    assert len(result.ai_unmatched) == 0
    assert len(result.gt_unmatched) == 1


def test_normalize_pdp_parent_a_parent_b():
    deltas = {
        "people": [
            {
                "id": -1,
                "name": "Child",
                "parent_a": -2,
                "parent_b": -3,
            }
        ]
    }

    normalized = normalize_pdp_for_comparison(deltas)

    assert normalized["people"][0]["parents"] == [-2, -3]
    assert "parent_a" not in normalized["people"][0]
    assert "parent_b" not in normalized["people"][0]


def test_normalize_pdp_parents_already_present():
    deltas = {
        "people": [
            {
                "id": -1,
                "name": "Child",
                "parents": [-2, -3],
            }
        ]
    }

    normalized = normalize_pdp_for_comparison(deltas)

    assert normalized["people"][0]["parents"] == [-2, -3]


def test_calculate_statement_f1_perfect_match():
    ai_deltas = PDPDeltas(
        people=[Person(id=-1, name="John")],
        events=[
            Event(
                id=-2,
                kind=EventKind.Bonded,
                description="Dinner",
                dateTime=datetime(2024, 1, 1),
            )
        ],
    )
    gt_deltas = PDPDeltas(
        people=[Person(id=-10, name="John")],
        events=[
            Event(
                id=-20,
                kind=EventKind.Bonded,
                description="Dinner",
                dateTime=datetime(2024, 1, 1),
            )
        ],
    )

    metrics = calculate_statement_f1(ai_deltas, gt_deltas)

    assert metrics.aggregate_micro_f1 == 1.0
    assert metrics.people_f1 == 1.0
    assert metrics.events_f1 == 1.0
    assert metrics.exact_match is True


def test_calculate_statement_f1_partial_match():
    ai_deltas = PDPDeltas(
        people=[Person(id=-1, name="John"), Person(id=-2, name="Jane")]
    )
    gt_deltas = PDPDeltas(people=[Person(id=-10, name="John")])

    metrics = calculate_statement_f1(ai_deltas, gt_deltas)

    assert 0 < metrics.aggregate_micro_f1 < 1.0
    assert 0 < metrics.people_f1 < 1.0
    assert metrics.exact_match is False


def test_calculate_statement_f1_sarf_variables():
    ai_deltas = PDPDeltas(
        events=[
            Event(
                id=-1,
                kind=EventKind.Bonded,
                description="Therapy",
                dateTime=datetime(2024, 1, 1),
                symptom=VariableShift.Up,
                anxiety=VariableShift.Down,
            )
        ]
    )
    gt_deltas = PDPDeltas(
        events=[
            Event(
                id=-2,
                kind=EventKind.Bonded,
                description="Therapy",
                dateTime=datetime(2024, 1, 1),
                symptom=VariableShift.Up,
                anxiety=VariableShift.Down,
            )
        ]
    )

    metrics = calculate_statement_f1(ai_deltas, gt_deltas)

    assert metrics.symptom_macro_f1 == 1.0
    assert metrics.anxiety_macro_f1 == 1.0


def test_calculate_statement_f1_empty():
    ai_deltas = PDPDeltas()
    gt_deltas = PDPDeltas()

    metrics = calculate_statement_f1(ai_deltas, gt_deltas)

    assert metrics.aggregate_micro_f1 == 1.0
    assert metrics.exact_match is True


def test_calculate_system_f1_no_approved_feedbacks(flask_app, test_user):
    with flask_app.app_context():
        metrics = calculate_system_f1()

        assert metrics.total_statements == 0
        assert metrics.aggregate_micro_f1 == 0.0


def test_calculate_system_f1_with_approved_feedbacks(flask_app, test_user):
    with flask_app.app_context():
        discussion = Discussion(
            user_id=test_user.id,
            summary="Test",
        )
        db.session.add(discussion)
        db.session.commit()

        speaker = Speaker(
            discussion_id=discussion.id,
            name="User",
            type=SpeakerType.Subject,
        )
        db.session.add(speaker)
        db.session.commit()

        stmt = Statement(
            discussion_id=discussion.id,
            speaker_id=speaker.id,
            text="Test",
            order=0,
            pdp_deltas={"people": [{"id": -1, "name": "John"}]},
        )
        db.session.add(stmt)
        db.session.commit()

        feedback = Feedback(
            statement_id=stmt.id,
            auditor_id=test_user.username,
            feedback_type="extraction",
            approved=True,
            edited_extraction={"people": [{"id": -10, "name": "John"}]},
        )
        db.session.add(feedback)
        db.session.commit()

        metrics = calculate_system_f1()

        assert metrics.total_statements == 1
        assert metrics.aggregate_micro_f1 == 1.0
        assert metrics.people_f1 == 1.0


def test_invalidate_f1_cache_specific_statement(flask_app):
    from btcopilot.training.f1_metrics import _f1_cache

    with flask_app.app_context():
        _f1_cache["stmt_1_2_abc123"] = "test_data"
        _f1_cache["stmt_2_3_def456"] = "other_data"

        invalidate_f1_cache(statement_id=1)

        assert "stmt_1_2_abc123" not in _f1_cache
        assert "stmt_2_3_def456" in _f1_cache


def test_invalidate_f1_cache_all(flask_app):
    from btcopilot.training.f1_metrics import _f1_cache

    with flask_app.app_context():
        _f1_cache["stmt_1_2_abc123"] = "test_data"
        _f1_cache["stmt_2_3_def456"] = "other_data"

        invalidate_f1_cache()

        assert len(_f1_cache) == 0


def test_normalize_pdp_handles_dict_and_pdpdeltas():
    dict_deltas = {"people": [{"id": -1, "name": "John"}]}
    pdp_deltas = PDPDeltas(people=[Person(id=-1, name="John")])

    normalized_dict = normalize_pdp_for_comparison(dict_deltas)
    normalized_pdp = normalize_pdp_for_comparison(pdp_deltas)

    assert normalized_dict["people"] == normalized_pdp["people"]


def test_f1_metrics_precision_recall():
    metrics = F1Metrics(tp=8, fp=2, fn=3, precision=0.8, recall=8 / 11, f1=0.744)

    assert metrics.precision == 0.8
    assert abs(metrics.recall - 8 / 11) < 0.001


def test_f1_metrics_construction():
    metrics = F1Metrics(tp=10, fp=5, fn=2)

    assert metrics.tp == 10
    assert metrics.fp == 5
    assert metrics.fn == 2


def test_calculate_statement_f1_with_pair_bonds():
    ai_deltas = PDPDeltas(
        people=[Person(id=-1, name="John"), Person(id=-2, name="Jane")],
        pair_bonds=[PairBond(person_a=-1, person_b=-2)],
    )
    gt_deltas = PDPDeltas(
        people=[Person(id=-10, name="John"), Person(id=-20, name="Jane")],
        pair_bonds=[PairBond(person_a=-10, person_b=-20)],
    )

    metrics = calculate_statement_f1(ai_deltas, gt_deltas)

    assert metrics.pair_bonds_f1 == 1.0
    assert metrics.aggregate_micro_f1 == 1.0


def test_hierarchical_sarf_f1_perfect_detection_and_value():
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Shift,
            description="Therapy",
            dateTime=datetime(2024, 1, 1),
            person=-1,
            symptom=VariableShift.Up,
            anxiety=VariableShift.Down,
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Shift,
            description="Therapy",
            dateTime=datetime(2024, 1, 1),
            person=-10,
            symptom=VariableShift.Up,
            anxiety=VariableShift.Down,
        )
    ]
    id_map = {-1: -10}

    hierarchical = calculate_hierarchical_sarf_f1(ai_events, gt_events, id_map)

    assert hierarchical["symptom"].detection_f1 == 1.0
    assert hierarchical["symptom"].value_match_f1 == 1.0
    assert hierarchical["anxiety"].detection_f1 == 1.0
    assert hierarchical["anxiety"].value_match_f1 == 1.0


def test_hierarchical_sarf_f1_detection_without_value_match():
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Shift,
            description="Test",
            dateTime=datetime(2024, 1, 1),
            person=-1,
            symptom=VariableShift.Up,
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Shift,
            description="Test",
            dateTime=datetime(2024, 1, 1),
            person=-10,
            symptom=VariableShift.Down,
        )
    ]
    id_map = {-1: -10}

    hierarchical = calculate_hierarchical_sarf_f1(ai_events, gt_events, id_map)

    assert hierarchical["symptom"].detection_f1 == 1.0
    assert hierarchical["symptom"].value_match_f1 == 0.0


def test_hierarchical_sarf_f1_missed_detection():
    ai_events = []
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Shift,
            description="Test",
            dateTime=datetime(2024, 1, 1),
            person=-10,
            symptom=VariableShift.Up,
        )
    ]
    id_map = {}

    hierarchical = calculate_hierarchical_sarf_f1(ai_events, gt_events, id_map)

    assert hierarchical["symptom"].detection_f1 == 0.0
    assert hierarchical["symptom"].value_match_f1 == 1.0


def test_hierarchical_sarf_f1_false_positive_detection():
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Shift,
            description="Test",
            dateTime=datetime(2024, 1, 1),
            person=-1,
            symptom=VariableShift.Up,
        )
    ]
    gt_events = []
    id_map = {-1: -10}

    hierarchical = calculate_hierarchical_sarf_f1(ai_events, gt_events, id_map)

    assert hierarchical["symptom"].detection_f1 == 0.0
    assert hierarchical["symptom"].value_match_f1 == 1.0


def test_hierarchical_sarf_f1_relationship_people_match():
    from btcopilot.schema import RelationshipKind

    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Shift,
            description="Test",
            dateTime=datetime(2024, 1, 1),
            person=-1,
            relationship=RelationshipKind.Conflict,
            relationshipTargets=[-2, -3],
            relationshipTriangles=[-4],
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Shift,
            description="Test",
            dateTime=datetime(2024, 1, 1),
            person=-10,
            relationship=RelationshipKind.Conflict,
            relationshipTargets=[-20, -30],
            relationshipTriangles=[-40],
        )
    ]
    id_map = {-1: -10, -2: -20, -3: -30, -4: -40}

    hierarchical = calculate_hierarchical_sarf_f1(ai_events, gt_events, id_map)

    assert hierarchical["relationship"].detection_f1 == 1.0
    assert hierarchical["relationship"].value_match_f1 == 1.0
    assert hierarchical["relationship"].people_match_f1 == 1.0


def test_hierarchical_sarf_f1_relationship_wrong_people():
    from btcopilot.schema import RelationshipKind

    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Shift,
            description="Test",
            dateTime=datetime(2024, 1, 1),
            person=-1,
            relationship=RelationshipKind.Conflict,
            relationshipTargets=[-2],
            relationshipTriangles=[],
        )
    ]
    gt_events = [
        Event(
            id=-2,
            kind=EventKind.Shift,
            description="Test",
            dateTime=datetime(2024, 1, 1),
            person=-10,
            relationship=RelationshipKind.Conflict,
            relationshipTargets=[-20, -30],
            relationshipTriangles=[-40],
        )
    ]
    id_map = {-1: -10, -2: -20, -3: -30, -4: -40}

    hierarchical = calculate_hierarchical_sarf_f1(ai_events, gt_events, id_map)

    assert hierarchical["relationship"].detection_f1 == 1.0
    assert hierarchical["relationship"].value_match_f1 == 1.0
    assert hierarchical["relationship"].people_match_f1 == 0.0


def test_hierarchical_sarf_f1_multiple_events_same_person_variable():
    ai_events = [
        Event(
            id=-1,
            kind=EventKind.Shift,
            description="Event 1",
            dateTime=datetime(2024, 1, 1),
            person=-1,
            symptom=VariableShift.Up,
        ),
        Event(
            id=-2,
            kind=EventKind.Shift,
            description="Event 2",
            dateTime=datetime(2024, 1, 2),
            person=-1,
            symptom=VariableShift.Down,
        ),
    ]
    gt_events = [
        Event(
            id=-10,
            kind=EventKind.Shift,
            description="Event 1",
            dateTime=datetime(2024, 1, 1),
            person=-10,
            symptom=VariableShift.Up,
        )
    ]
    id_map = {-1: -10}

    hierarchical = calculate_hierarchical_sarf_f1(ai_events, gt_events, id_map)

    assert hierarchical["symptom"].detection_f1 == 1.0
    assert hierarchical["symptom"].value_match_f1 == 1.0


def test_calculate_statement_f1_includes_hierarchical_metrics():
    ai_deltas = PDPDeltas(
        people=[Person(id=-1, name="John")],
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                description="Therapy",
                dateTime=datetime(2024, 1, 1),
                person=-1,
                symptom=VariableShift.Up,
            )
        ],
    )
    gt_deltas = PDPDeltas(
        people=[Person(id=-10, name="John")],
        events=[
            Event(
                id=-20,
                kind=EventKind.Shift,
                description="Therapy",
                dateTime=datetime(2024, 1, 1),
                person=-10,
                symptom=VariableShift.Up,
            )
        ],
    )

    metrics = calculate_statement_f1(ai_deltas, gt_deltas)

    assert isinstance(metrics.symptom_hierarchical, SARFVariableF1)
    assert metrics.symptom_hierarchical.detection_f1 == 1.0
    assert metrics.symptom_hierarchical.value_match_f1 == 1.0
