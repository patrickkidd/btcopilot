"""Regression tests for birth event self-reference bug (T7-10 / GitHub #70).

Birth events must use child = who was born, person/spouse = optional parent links.
A person must never appear as both child and person/spouse on the same birth event.

Three-layer defense:
1. Prompt: LLM instructions specify correct semantics
2. Sanitizer: _fix_birth_self_references() clears invalid person/spouse before validation
3. Validator: validate_pdp_deltas() rejects any remaining self-references
"""

import pytest

from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
    PDPValidationError,
)
from btcopilot.pdp import (
    validate_pdp_deltas,
    apply_deltas,
    _fix_birth_self_references,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Validation layer tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidationRejectsSelfReference:
    """validate_pdp_deltas must reject birth events with person == child."""

    def test_rejects_person_equals_child_on_birth(self):
        pdp = PDP(people=[Person(id=-1, name="Barbara")])
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    person=-1,
                    child=-1,
                    dateTime="1953-01-01",
                )
            ]
        )
        with pytest.raises(PDPValidationError, match="self-referential.*child == person"):
            validate_pdp_deltas(pdp, deltas)

    def test_rejects_spouse_equals_child_on_birth(self):
        pdp = PDP(
            people=[
                Person(id=-1, name="Barbara"),
                Person(id=-2, name="Mom"),
            ]
        )
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Birth,
                    person=-2,
                    spouse=-1,
                    child=-1,
                    dateTime="1953-01-01",
                )
            ]
        )
        with pytest.raises(PDPValidationError, match="self-referential.*child == spouse"):
            validate_pdp_deltas(pdp, deltas)

    def test_rejects_person_equals_child_on_adopted(self):
        pdp = PDP(people=[Person(id=-1, name="Alex")])
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Adopted,
                    person=-1,
                    child=-1,
                    dateTime="1990-06-15",
                )
            ]
        )
        with pytest.raises(PDPValidationError, match="self-referential.*child == person"):
            validate_pdp_deltas(pdp, deltas)

    def test_rejects_spouse_equals_child_on_adopted(self):
        pdp = PDP(
            people=[
                Person(id=-1, name="Alex"),
                Person(id=-2, name="Parent"),
            ]
        )
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Adopted,
                    person=-2,
                    spouse=-1,
                    child=-1,
                    dateTime="1990-06-15",
                )
            ]
        )
        with pytest.raises(PDPValidationError, match="self-referential.*child == spouse"):
            validate_pdp_deltas(pdp, deltas)


class TestValidationAcceptsCorrectSemantics:
    """validate_pdp_deltas must accept correctly formed birth events."""

    def test_accepts_child_only_birth(self):
        """Birth with child only (no parents known) is valid."""
        pdp = PDP(people=[Person(id=-1, name="Barbara")])
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    child=-1,
                    dateTime="1953-01-01",
                )
            ]
        )
        # Should not raise
        validate_pdp_deltas(pdp, deltas)

    def test_accepts_child_with_different_person(self):
        """Birth with child != person (correct: person is parent) is valid."""
        pdp = PDP(
            people=[
                Person(id=-1, name="Barbara"),
                Person(id=-2, name="Mom"),
            ]
        )
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Birth,
                    person=-2,
                    child=-1,
                    dateTime="1953-01-01",
                )
            ]
        )
        validate_pdp_deltas(pdp, deltas)

    def test_accepts_full_birth_with_parents(self):
        """Birth with child, person (parent1), spouse (parent2) all different is valid."""
        pdp = PDP(
            people=[
                Person(id=-1, name="Barbara"),
                Person(id=-2, name="Mom"),
                Person(id=-3, name="Dad"),
            ]
        )
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-4,
                    kind=EventKind.Birth,
                    person=-2,
                    spouse=-3,
                    child=-1,
                    dateTime="1953-01-01",
                )
            ]
        )
        validate_pdp_deltas(pdp, deltas)

    def test_accepts_person_none_birth(self):
        """Birth with person=None (unknown parent) is legitimate per data model."""
        pdp = PDP(people=[Person(id=-1, name="Barbara")])
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    person=None,
                    child=-1,
                    dateTime="1953-01-01",
                )
            ]
        )
        validate_pdp_deltas(pdp, deltas)


# ═══════════════════════════════════════════════════════════════════════════════
# Sanitizer layer tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSanitizerFixesSelfReferences:
    """_fix_birth_self_references must clear invalid person/spouse fields."""

    def test_clears_person_when_equals_child(self):
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    person=-1,
                    child=-1,
                    dateTime="1953-01-01",
                )
            ]
        )
        _fix_birth_self_references(deltas)
        assert deltas.events[0].person is None
        assert deltas.events[0].child == -1

    def test_clears_spouse_when_equals_child(self):
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Birth,
                    person=-2,
                    spouse=-1,
                    child=-1,
                    dateTime="1953-01-01",
                )
            ]
        )
        _fix_birth_self_references(deltas)
        assert deltas.events[0].spouse is None
        assert deltas.events[0].child == -1
        assert deltas.events[0].person == -2  # Preserved

    def test_does_not_modify_correct_birth(self):
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Birth,
                    person=-2,
                    child=-1,
                    dateTime="1953-01-01",
                )
            ]
        )
        _fix_birth_self_references(deltas)
        assert deltas.events[0].person == -2
        assert deltas.events[0].child == -1

    def test_does_not_modify_non_birth_events(self):
        """Shift events with person == child fields should not be touched."""
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Shift,
                    person=-1,
                    child=-1,
                    description="some shift",
                    dateTime="2025-01-01",
                )
            ]
        )
        _fix_birth_self_references(deltas)
        assert deltas.events[0].person == -1
        assert deltas.events[0].child == -1

    def test_handles_adopted_events(self):
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Adopted,
                    person=-1,
                    child=-1,
                    dateTime="1990-06-15",
                )
            ]
        )
        _fix_birth_self_references(deltas)
        assert deltas.events[0].person is None
        assert deltas.events[0].child == -1

    def test_handles_mixed_events(self):
        """Multiple events, only birth ones with self-refs get fixed."""
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    person=-1,
                    child=-1,
                    dateTime="1953-01-01",
                ),
                Event(
                    id=-3,
                    kind=EventKind.Death,
                    person=-1,
                    dateTime="2020-01-01",
                ),
                Event(
                    id=-4,
                    kind=EventKind.Birth,
                    child=-5,
                    person=-6,
                    dateTime="1980-01-01",
                ),
            ]
        )
        _fix_birth_self_references(deltas)
        # First birth: self-ref fixed
        assert deltas.events[0].person is None
        assert deltas.events[0].child == -1
        # Death: untouched
        assert deltas.events[1].person == -1
        # Second birth: already correct, untouched
        assert deltas.events[2].person == -6
        assert deltas.events[2].child == -5


# ═══════════════════════════════════════════════════════════════════════════════
# End-to-end pipeline tests (sanitizer + validator + apply)
# ═══════════════════════════════════════════════════════════════════════════════


class TestE2EPipeline:
    """Test that sanitizer + validator + apply_deltas work together correctly."""

    def test_self_ref_birth_sanitized_then_applied(self):
        """Simulates LLM output with self-ref: sanitizer fixes, validator passes, apply works."""
        pdp = PDP(people=[Person(id=-1, name="Barbara")])
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Barbara")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    person=-1,
                    child=-1,  # BUG: self-reference
                    dateTime="1953-01-01",
                )
            ],
        )

        # Sanitizer fixes the self-reference
        _fix_birth_self_references(deltas)
        assert deltas.events[0].person is None

        # Validator accepts the sanitized deltas
        validate_pdp_deltas(pdp, deltas)

        # Apply works correctly
        new_pdp = apply_deltas(pdp, deltas)
        birth_event = new_pdp.events[0]
        assert birth_event.child == -1
        assert birth_event.person is None

    def test_correct_birth_passes_full_pipeline(self):
        """Correct birth event (child-only) passes all layers."""
        pdp = PDP(people=[Person(id=-1, name="Barbara")])
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Barbara")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    child=-1,
                    dateTime="1953-01-01",
                )
            ],
        )

        _fix_birth_self_references(deltas)
        validate_pdp_deltas(pdp, deltas)
        new_pdp = apply_deltas(pdp, deltas)

        assert len(new_pdp.events) == 1
        assert new_pdp.events[0].child == -1
        assert new_pdp.events[0].person is None

    def test_commit_birth_with_sanitized_self_ref(self):
        """After sanitization, commit should create inferred parents for child-only birth."""
        pdp = PDP(
            people=[Person(id=-1, name="Barbara")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    child=-1,
                    dateTime="1953-01-01",
                )
            ],
        )
        diagram_data = DiagramData(pdp=pdp)

        # Commit the birth event - should infer parents
        id_mapping = diagram_data.commit_pdp_items([-2])

        # Barbara should be committed
        committed_people = [p["name"] for p in diagram_data.people]
        assert "Barbara" in committed_people

        # Inferred parents should also exist
        assert any("mother" in p["name"].lower() for p in diagram_data.people)
        assert any("father" in p["name"].lower() for p in diagram_data.people)
