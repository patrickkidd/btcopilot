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
    F1Metrics,
)
from btcopilot.schema import (
    Person,
    Event,
    PairBond,
    PDPDeltas,
    VariableShift,
    EventKind,
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
