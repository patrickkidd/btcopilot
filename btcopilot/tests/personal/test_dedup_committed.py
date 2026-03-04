"""Tests for deterministic dedup of extracted items against committed diagram items.

The LLM is prompted to skip committed items but doesn't reliably do so.
`dedup_against_committed()` provides a rules-based post-filter in Python.

Covers:
- No-op when no committed items
- People dedup by exact name match
- People dedup with case-insensitive matching
- People dedup with whitespace tolerance
- Event reference remapping after person dedup
- PairBond dedup by dyad after person remapping
- Self-describing event dedup (birth, death, married, etc.)
- Novel items preserved (no false positives)
"""

from btcopilot.pdp import dedup_against_committed, _normalize_name
from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
    PersonKind,
    DateCertainty,
    VariableShift,
    asdict,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_diagram_data(
    people: list[dict] | None = None,
    events: list[dict] | None = None,
    pair_bonds: list[dict] | None = None,
) -> DiagramData:
    """Build a DiagramData with committed items (positive IDs, dict form)."""
    return DiagramData(
        people=people or [],
        events=events or [],
        pair_bonds=pair_bonds or [],
    )


def _committed_person(id: int, name: str, **kwargs) -> dict:
    """Helper to create a committed person dict."""
    d = {"id": id, "name": name, "gender": "unknown"}
    d.update(kwargs)
    return d


def _committed_event(id: int, kind: str, person: int, **kwargs) -> dict:
    """Helper to create a committed event dict."""
    d = {
        "id": id,
        "kind": kind,
        "person": person,
        "description": kind.capitalize(),
    }
    d.update(kwargs)
    return d


def _committed_pair_bond(id: int, person_a: int, person_b: int) -> dict:
    return {"id": id, "person_a": person_a, "person_b": person_b}


# ── normalize_name ──────────────────────────────────────────────────────────


class TestNormalizeName:
    def test_none(self):
        assert _normalize_name(None) == ""

    def test_empty(self):
        assert _normalize_name("") == ""

    def test_lowercase(self):
        assert _normalize_name("Maria") == "maria"

    def test_strip_whitespace(self):
        assert _normalize_name("  Maria  ") == "maria"

    def test_collapse_internal_whitespace(self):
        assert _normalize_name("Mary  Jane") == "mary jane"

    def test_mixed_case_and_whitespace(self):
        assert _normalize_name("  MARY   JANE  ") == "mary jane"


# ── Phase 1: People dedup ──────────────────────────────────────────────────


class TestDedupPeopleNoCommitted:
    """No committed items → deltas pass through unchanged."""

    def test_noop_empty_diagram(self):
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Alice", gender=PersonKind.Female),
                Person(id=-2, name="Bob", gender=PersonKind.Male),
            ],
            events=[
                Event(id=-3, kind=EventKind.Shift, person=-1, description="Feeling anxious"),
            ],
        )
        diagram_data = _make_diagram_data()

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 2
        assert len(deltas.events) == 1
        assert deltas.events[0].person == -1

    def test_noop_no_people_events_pair_bonds(self):
        """Completely empty diagram_data — early return."""
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice")],
        )
        diagram_data = DiagramData()

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 1


class TestDedupPeopleExactMatch:
    """People with names matching committed items are removed."""

    def test_exact_name_removed(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Maria")]
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Maria", gender=PersonKind.Female)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 0

    def test_multiple_people_partial_match(self):
        """Only matching people are removed; novel ones survive."""
        diagram_data = _make_diagram_data(
            people=[
                _committed_person(10, "Maria"),
                _committed_person(11, "Carlos"),
            ]
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Maria"),
                Person(id=-2, name="Carlos"),
                Person(id=-3, name="Sofia"),  # novel
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 1
        assert deltas.people[0].name == "Sofia"


class TestDedupPeopleCaseInsensitive:
    """Case-insensitive name matching."""

    def test_lowercase_matches_titlecase(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Maria")]
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="maria")],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 0

    def test_uppercase_matches(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Maria")]
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="MARIA")],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 0

    def test_mixed_case_matches(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Mary Jane")]
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="mary jane")],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 0


class TestDedupPeopleWhitespace:
    """Whitespace tolerance in name matching."""

    def test_leading_trailing_whitespace(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Maria")]
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="  Maria  ")],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 0

    def test_extra_internal_whitespace(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Mary Jane")]
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Mary   Jane")],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 0


# ── Event reference remapping ───────────────────────────────────────────────


class TestDedupRemapsEventReferences:
    """After person dedup, event person/spouse/child refs use committed IDs."""

    def test_event_person_remapped(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Maria")]
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Maria")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Shift,
                    person=-1,
                    description="Started new job",
                    dateTime="2024-01-15",
                ),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        # Person removed
        assert len(deltas.people) == 0
        # Event's person reference remapped to committed ID
        assert deltas.events[0].person == 10

    def test_event_spouse_remapped(self):
        diagram_data = _make_diagram_data(
            people=[
                _committed_person(10, "Maria"),
                _committed_person(11, "Carlos"),
            ]
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Maria"),
                Person(id=-2, name="Carlos"),
            ],
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Married,
                    person=-1,
                    spouse=-2,
                    description="Married",
                    dateTime="2015-06-20",
                ),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert deltas.events[0].person == 10
        assert deltas.events[0].spouse == 11

    def test_event_child_remapped(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Sofia")]
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Sofia")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    child=-1,
                    description="Born",
                    dateTime="2018-03-10",
                ),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert deltas.events[0].child == 10

    def test_relationship_targets_remapped(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Bob")]
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Bob"),
                Person(id=-2, name="Alice"),  # novel
            ],
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Shift,
                    person=-2,
                    description="Conflict with Bob",
                    dateTime="2024-03-01",
                    relationshipTargets=[-1],
                ),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert deltas.events[0].relationshipTargets == [10]

    def test_relationship_triangles_remapped(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Carol")]
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Carol"),
                Person(id=-2, name="Alice"),
                Person(id=-3, name="Bob"),
            ],
            events=[
                Event(
                    id=-4,
                    kind=EventKind.Shift,
                    person=-2,
                    description="Triangle move",
                    dateTime="2024-03-15",
                    relationshipTargets=[-3],
                    relationshipTriangles=[-1],
                ),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert deltas.events[0].relationshipTriangles == [10]


# ── Phase 2: PairBond dedup by dyad ────────────────────────────────────────


class TestDedupPairBonds:
    """PairBonds whose remapped dyad matches a committed pair bond are removed."""

    def test_pair_bond_dedup_after_person_remap(self):
        diagram_data = _make_diagram_data(
            people=[
                _committed_person(10, "Maria"),
                _committed_person(11, "Carlos"),
            ],
            pair_bonds=[_committed_pair_bond(20, 10, 11)],
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Maria"),
                Person(id=-2, name="Carlos"),
            ],
            pair_bonds=[
                PairBond(id=-3, person_a=-1, person_b=-2),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        # Both people removed, pair bond also removed (dyad matches)
        assert len(deltas.people) == 0
        assert len(deltas.pair_bonds) == 0

    def test_pair_bond_novel_dyad_preserved(self):
        diagram_data = _make_diagram_data(
            people=[
                _committed_person(10, "Maria"),
                _committed_person(11, "Carlos"),
            ],
            pair_bonds=[_committed_pair_bond(20, 10, 11)],
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Alice"),
                Person(id=-2, name="Bob"),
            ],
            pair_bonds=[
                PairBond(id=-3, person_a=-1, person_b=-2),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        # Novel people and their pair bond survive
        assert len(deltas.people) == 2
        assert len(deltas.pair_bonds) == 1

    def test_person_parents_remapped_to_committed_pair_bond(self):
        """When a pair bond is deduped, Person.parents should point to committed ID."""
        diagram_data = _make_diagram_data(
            people=[
                _committed_person(10, "Maria"),
                _committed_person(11, "Carlos"),
            ],
            pair_bonds=[_committed_pair_bond(20, 10, 11)],
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Maria"),
                Person(id=-2, name="Carlos"),
                Person(id=-4, name="Sofia", parents=-3),  # novel child
            ],
            pair_bonds=[
                PairBond(id=-3, person_a=-1, person_b=-2),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        # Sofia survives; her parents reference remapped to committed pair bond ID
        assert len(deltas.people) == 1
        assert deltas.people[0].name == "Sofia"
        assert deltas.people[0].parents == 20  # committed pair bond ID


# ── Phase 3: Self-describing event dedup ────────────────────────────────────


class TestDedupSelfDescribingEvents:
    """Self-describing events (birth, death, married, etc.) matching committed
    events by kind+person are removed."""

    def test_married_event_deduped(self):
        diagram_data = _make_diagram_data(
            people=[
                _committed_person(10, "Maria"),
                _committed_person(11, "Carlos"),
            ],
            events=[
                _committed_event(30, "married", 10, spouse=11),
            ],
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Maria"),
                Person(id=-2, name="Carlos"),
            ],
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Married,
                    person=-1,
                    spouse=-2,
                    description="Married Carlos",
                    dateTime="2015-06-20",
                ),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        # People removed, event also removed (kind=married, person=10 in committed)
        assert len(deltas.people) == 0
        assert len(deltas.events) == 0

    def test_death_event_deduped(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Grandpa")],
            events=[_committed_event(30, "death", 10)],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Grandpa")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Death,
                    person=-1,
                    description="Died",
                    dateTime="1979-01-01",
                ),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.events) == 0

    def test_birth_event_deduped_by_child(self):
        """Birth events match on child reference as well as person."""
        diagram_data = _make_diagram_data(
            people=[
                _committed_person(10, "Maria"),
                _committed_person(12, "Sofia"),
            ],
            events=[
                _committed_event(30, "birth", 10, child=12),
            ],
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Sofia"),
            ],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    child=-1,
                    description="Sofia born",
                    dateTime="2018-03-10",
                ),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        # Sofia deduped, birth event deduped via child match
        assert len(deltas.events) == 0

    def test_shift_event_not_deduped(self):
        """Shift events are NOT self-describing — they should survive dedup."""
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Alice")],
            events=[
                _committed_event(30, "shift", 10, description="Started new job"),
            ],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Shift,
                    person=-1,
                    description="Started new job",
                    dateTime="2024-01-15",
                ),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        # Person deduped, but shift event survives (not self-describing dedup)
        assert len(deltas.events) == 1
        assert deltas.events[0].person == 10  # remapped


# ── Preservation of novel items ─────────────────────────────────────────────


class TestDedupPreservesNovelItems:
    """Items that don't match committed items must survive untouched."""

    def test_novel_person_preserved(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Maria")]
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Maria"),
                Person(id=-2, name="Sofia"),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 1
        assert deltas.people[0].name == "Sofia"
        assert deltas.people[0].id == -2

    def test_novel_event_preserved(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Maria")],
            events=[_committed_event(30, "married", 10)],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Maria")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Married,
                    person=-1,
                    description="Married again",
                    dateTime="2015-06-20",
                ),
                Event(
                    id=-3,
                    kind=EventKind.Shift,
                    person=-1,
                    description="New symptom",
                    dateTime="2024-06-01",
                    symptom=VariableShift.Up,
                ),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        # Married event is deduped (kind+person match), shift event preserved
        assert len(deltas.events) == 1
        assert deltas.events[0].kind == EventKind.Shift

    def test_novel_pair_bond_preserved(self):
        diagram_data = _make_diagram_data(
            people=[
                _committed_person(10, "Maria"),
                _committed_person(11, "Carlos"),
            ],
            pair_bonds=[_committed_pair_bond(20, 10, 11)],
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Alice"),
                Person(id=-2, name="Bob"),
            ],
            pair_bonds=[PairBond(id=-3, person_a=-1, person_b=-2)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.pair_bonds) == 1


# ── Full family re-extraction scenario ──────────────────────────────────────


class TestDedupFullScenario:
    """End-to-end: LLM re-extracts an entire family that's already committed."""

    def test_full_family_dedup(self):
        """Simulates T7-11: LLM extracts Maria, Carlos, Sofia, their marriage,
        Sofia's birth, and pair bond — all already committed."""
        diagram_data = _make_diagram_data(
            people=[
                _committed_person(10, "Maria", gender="female"),
                _committed_person(11, "Carlos", gender="male"),
                _committed_person(12, "Sofia", gender="female"),
            ],
            events=[
                _committed_event(30, "married", 10, spouse=11),
                _committed_event(31, "birth", 10, spouse=11, child=12),
            ],
            pair_bonds=[_committed_pair_bond(20, 10, 11)],
        )

        # LLM re-extracts the same family
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Maria", gender=PersonKind.Female),
                Person(id=-2, name="Carlos", gender=PersonKind.Male),
                Person(id=-3, name="Sofia", gender=PersonKind.Female, parents=-6),
            ],
            events=[
                Event(
                    id=-4,
                    kind=EventKind.Married,
                    person=-1,
                    spouse=-2,
                    description="Married",
                    dateTime="2015-06-20",
                ),
                Event(
                    id=-5,
                    kind=EventKind.Birth,
                    person=-1,
                    spouse=-2,
                    child=-3,
                    description="Sofia born",
                    dateTime="2018-03-10",
                ),
            ],
            pair_bonds=[
                PairBond(id=-6, person_a=-1, person_b=-2),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        # Everything should be deduped
        assert len(deltas.people) == 0, f"Expected 0 people, got {[p.name for p in deltas.people]}"
        assert len(deltas.events) == 0, f"Expected 0 events, got {[(e.kind, e.id) for e in deltas.events]}"
        assert len(deltas.pair_bonds) == 0, f"Expected 0 pair_bonds, got {deltas.pair_bonds}"

    def test_mixed_committed_and_novel(self):
        """Some items match committed, others are novel. Only novel survive."""
        diagram_data = _make_diagram_data(
            people=[
                _committed_person(10, "Maria", gender="female"),
                _committed_person(11, "Carlos", gender="male"),
            ],
            events=[
                _committed_event(30, "married", 10, spouse=11),
            ],
            pair_bonds=[_committed_pair_bond(20, 10, 11)],
        )

        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Maria"),  # dup
                Person(id=-2, name="Carlos"),  # dup
                Person(id=-3, name="Sofia"),  # novel
            ],
            events=[
                Event(
                    id=-4,
                    kind=EventKind.Married,
                    person=-1,
                    spouse=-2,
                    description="Married",
                    dateTime="2015-06-20",
                ),  # dup
                Event(
                    id=-5,
                    kind=EventKind.Shift,
                    person=-3,
                    description="Sofia started school",
                    dateTime="2023-09-01",
                ),  # novel
            ],
            pair_bonds=[
                PairBond(id=-6, person_a=-1, person_b=-2),  # dup
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        # Only Sofia and her event survive
        assert len(deltas.people) == 1
        assert deltas.people[0].name == "Sofia"
        assert len(deltas.events) == 1
        assert deltas.events[0].description == "Sofia started school"
        assert deltas.events[0].person == -3  # Sofia not remapped (novel)
        assert len(deltas.pair_bonds) == 0


# ── Delete list cleanup ────────────────────────────────────────────────────


class TestDedupDeleteListCleanup:
    """Delete entries referencing remapped IDs are removed."""

    def test_delete_of_remapped_id_removed(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Maria")]
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Maria")],
            delete=[-1],
        )

        dedup_against_committed(deltas, diagram_data)

        # -1 was remapped to 10 (committed), so delete of -1 is meaningless
        assert -1 not in deltas.delete

    def test_delete_of_novel_id_preserved(self):
        diagram_data = _make_diagram_data(
            people=[_committed_person(10, "Maria")]
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Maria")],
            delete=[-5],  # deleting some other item
        )

        dedup_against_committed(deltas, diagram_data)

        assert -5 in deltas.delete
