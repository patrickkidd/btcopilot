import math

import pytest
from sklearn.metrics import cohen_kappa_score

from btcopilot.training.irr_metrics import (
    calculate_cohens_kappa,
    calculate_fleiss_kappa,
    calculate_pairwise_irr,
    safe_avg,
)
from btcopilot.schema import Person, Event, EventKind, VariableShift, PDPDeltas


def test_calculate_cohens_kappa_perfect_agreement():
    labels_a = ["up", "down", "same", "up", "down"]
    labels_b = ["up", "down", "same", "up", "down"]

    kappa = calculate_cohens_kappa(labels_a, labels_b)

    assert kappa == 1.0


def test_calculate_cohens_kappa_no_agreement():
    # Complete disagreement with varied categories
    labels_a = ["up", "down", "same", "up"]
    labels_b = ["down", "up", "up", "down"]

    kappa = calculate_cohens_kappa(labels_a, labels_b)

    assert kappa <= 0


def test_calculate_cohens_kappa_partial_agreement():
    labels_a = ["up", "down", "same", "up"]
    labels_b = ["up", "down", "up", "down"]

    kappa = calculate_cohens_kappa(labels_a, labels_b)

    assert 0 < kappa < 1


def test_calculate_cohens_kappa_empty():
    kappa = calculate_cohens_kappa([], [])
    assert kappa is None


def test_calculate_cohens_kappa_single_sample():
    # Less than 2 samples - returns None
    labels_a = ["up"]
    labels_b = ["up"]

    kappa = calculate_cohens_kappa(labels_a, labels_b)

    assert kappa is None


def test_calculate_fleiss_kappa_perfect_agreement():
    # 3 raters, 4 items, 2 categories, all agree
    ratings = [
        [3, 0],  # All 3 raters said category 0
        [3, 0],
        [0, 3],  # All 3 raters said category 1
        [0, 3],
    ]

    kappa = calculate_fleiss_kappa(ratings)

    assert kappa == 1.0


def test_calculate_fleiss_kappa_no_agreement():
    # 3 raters, 3 items, 3 categories, no agreement
    ratings = [
        [1, 1, 1],  # Each rater chose different category
        [1, 1, 1],
        [1, 1, 1],
    ]

    kappa = calculate_fleiss_kappa(ratings)

    assert kappa < 0


def test_calculate_fleiss_kappa_empty():
    kappa = calculate_fleiss_kappa([])
    assert kappa is None


def test_safe_avg_with_values():
    assert safe_avg([1.0, 2.0, 3.0]) == 2.0


def test_safe_avg_with_nones():
    assert safe_avg([1.0, None, 3.0]) == 2.0


def test_safe_avg_empty():
    assert safe_avg([]) is None


def test_safe_avg_all_nones():
    assert safe_avg([None, None]) is None


def test_calculate_pairwise_irr_identical():
    person = Person(id=-1, name="John Doe")
    event = Event(
        id=-1,
        kind=EventKind.Shift,
        person=-1,
        symptom=VariableShift.Up,
        anxiety=VariableShift.Down,
    )

    extraction_a = PDPDeltas(people=[person], events=[event], pair_bonds=[])
    extraction_b = PDPDeltas(people=[person], events=[event], pair_bonds=[])

    result = calculate_pairwise_irr(extraction_a, extraction_b, "coder_a", "coder_b")

    assert result.people_f1 == 1.0
    assert result.events_f1 == 1.0
    assert result.aggregate_f1 == 1.0


def test_calculate_pairwise_irr_disjoint():
    person_a = Person(id=-1, name="John Doe")
    person_b = Person(id=-2, name="Jane Smith")

    extraction_a = PDPDeltas(people=[person_a], events=[], pair_bonds=[])
    extraction_b = PDPDeltas(people=[person_b], events=[], pair_bonds=[])

    result = calculate_pairwise_irr(extraction_a, extraction_b, "coder_a", "coder_b")

    assert result.people_f1 == 0.0


def test_calculate_pairwise_irr_empty():
    extraction_a = PDPDeltas(people=[], events=[], pair_bonds=[])
    extraction_b = PDPDeltas(people=[], events=[], pair_bonds=[])

    result = calculate_pairwise_irr(extraction_a, extraction_b, "coder_a", "coder_b")

    # Empty vs empty = perfect agreement (vacuously)
    assert result.people_f1 == 1.0
    assert result.events_f1 == 1.0
    assert result.matched_event_count == 0
