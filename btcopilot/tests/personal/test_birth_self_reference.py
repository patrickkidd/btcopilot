"""Regression tests for birth event self-reference bug (T7-10 / GitHub #70).

Birth events must use child = who was born, person/spouse = optional parent links.
A person must never appear as both child and person/spouse on the same birth event.
"""

import pytest

from btcopilot.schema import (
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
    DiagramData,
    PDPValidationError,
)
from btcopilot.pdp import (
    validate_pdp_deltas,
    apply_deltas,
    _fix_birth_self_references,
)


class TestBirthSelfReferenceValidation:
    """validate_pdp_deltas must reject self-referential birth events."""

    def test_birth_event_person_equals_child_rejected(self):
        """Birth event where person == child is invalid (self-referential)."""
        pdp = PDP(
            people=[Person(id=-1, name="Barbara", gender="female")],
        )
        deltas = PDPDeltas(
            people=[],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    person=-1,
                    child=-1,
                    description="Born",
                    dateTime="1953-01-01",
                )
            ],
        )
        with pytest.raises(PDPValidationError, match="self-referential"):
            validate_pdp_deltas(pdp, deltas)

    def test_birth_event_spouse_equals_child_rejected(self):
        """Birth event where spouse == child is invalid."""
        pdp = PDP(
            people=[
                Person(id=-1, name="Barbara", gender="female"),
                Person(id=-2, name="John", gender="male"),
            ],
        )
        deltas = PDPDeltas(
            people=[],
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Birth,
                    person=-2,
                    spouse=-1,
                    child=-1,
                    description="Born",
                    dateTime="1953-01-01",
                )
            ],
        )
        with pytest.raises(PDPValidationError, match="self-referential"):
            validate_pdp_deltas(pdp, deltas)

    def test_adopted_event_person_equals_child_rejected(self):
        """Adopted event where person == child is also invalid."""
        pdp = PDP(
            people=[Person(id=-1, name="Child", gender="female")],
        )
        deltas = PDPDeltas(
            people=[],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Adopted,
                    person=-1,
                    child=-1,
                    description="Adopted",
                    dateTime="2000-01-01",
                )
            ],
        )
        with pytest.raises(PDPValidationError, match="self-referential"):
            validate_pdp_deltas(pdp, deltas)

    def test_birth_event_with_correct_semantics_accepted(self):
        """Birth event with child != person is valid."""
        pdp = PDP(
            people=[
                Person(id=-1, name="Barbara", gender="female"),
                Person(id=-2, name="Mother", gender="female"),
            ],
        )
        deltas = PDPDeltas(
            people=[],
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Birth,
                    person=-2,
                    child=-1,
                    description="Born",
                    dateTime="1953-01-01",
                )
            ],
        )
        # Should not raise
        validate_pdp_deltas(pdp, deltas)

    def test_birth_event_with_person_none_accepted(self):
        """Birth event with person=None (parent unknown) is valid per spec."""
        pdp = PDP(
            people=[Person(id=-1, name="Barbara", gender="female")],
        )
        deltas = PDPDeltas(
            people=[],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    person=None,
                    child=-1,
                    description="Born",
                    dateTime="1953-01-01",
                )
            ],
        )
        # Should not raise
        validate_pdp_deltas(pdp, deltas)


class TestFixBirthSelfReferences:
    """_fix_birth_self_references sanitizes LLM output before validation."""

    def test_fixes_person_equals_child(self):
        """When person == child on birth, person is cleared to None."""
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    person=-1,
                    child=-1,
                    description="Born",
                    dateTime="1953-01-01",
                )
            ],
        )
        _fix_birth_self_references(deltas)
        assert deltas.events[0].person is None
        assert deltas.events[0].child == -1

    def test_fixes_spouse_equals_child(self):
        """When spouse == child on birth, spouse is cleared to None."""
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Birth,
                    person=-2,
                    spouse=-1,
                    child=-1,
                    description="Born",
                    dateTime="1953-01-01",
                )
            ],
        )
        _fix_birth_self_references(deltas)
        assert deltas.events[0].spouse is None
        assert deltas.events[0].person == -2
        assert deltas.events[0].child == -1

    def test_does_not_touch_correct_birth_events(self):
        """Valid birth events are not modified."""
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Birth,
                    person=-2,
                    child=-1,
                    description="Born",
                    dateTime="1953-01-01",
                )
            ],
        )
        _fix_birth_self_references(deltas)
        assert deltas.events[0].person == -2
        assert deltas.events[0].child == -1

    def test_does_not_touch_non_birth_events(self):
        """Shift events with person == child are not affected."""
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Shift,
                    person=-1,
                    child=-1,
                    description="Something",
                    dateTime="2020-01-01",
                )
            ],
        )
        _fix_birth_self_references(deltas)
        assert deltas.events[0].person == -1
        assert deltas.events[0].child == -1

    def test_fixes_adopted_event_too(self):
        """Adopted events also get self-reference fix."""
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Adopted,
                    person=-1,
                    child=-1,
                    description="Adopted",
                    dateTime="2000-01-01",
                )
            ],
        )
        _fix_birth_self_references(deltas)
        assert deltas.events[0].person is None
        assert deltas.events[0].child == -1


class TestBirthEventEndToEnd:
    """End-to-end tests ensuring birth events flow correctly through the pipeline."""

    def test_birth_event_commit_with_child_only(self):
        """Birth event with only child set commits correctly and infers parents."""
        pdp = PDP(
            people=[Person(id=-1, name="Barbara", gender="female")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    person=None,
                    child=-1,
                    description="Born",
                    dateTime="1953-01-01",
                )
            ],
        )
        diagram_data = DiagramData(pdp=pdp)
        diagram_data.commit_pdp_items([-2])

        # Barbara should be committed
        committed_names = [p["name"] for p in diagram_data.people]
        assert "Barbara" in committed_names

        # The birth event's child should reference Barbara
        birth_event = diagram_data.events[0]
        assert birth_event["child"] is not None

    def test_apply_deltas_preserves_correct_birth_semantics(self):
        """apply_deltas correctly adds birth events with child-centric semantics."""
        pdp = PDP()
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Barbara", gender="female", confidence=0.9)],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    person=None,
                    child=-1,
                    description="Born",
                    dateTime="1953-01-01",
                    confidence=0.8,
                )
            ],
        )
        new_pdp = apply_deltas(pdp, deltas)

        assert len(new_pdp.events) == 1
        birth = new_pdp.events[0]
        assert birth.child == -1
        assert birth.person is None
        assert birth.kind == EventKind.Birth
