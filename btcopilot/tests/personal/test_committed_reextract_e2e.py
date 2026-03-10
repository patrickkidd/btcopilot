"""
E2E test: re-extraction with committed diagram items references them
by positive ID instead of recreating duplicates.

Requires GOOGLE_GEMINI_API_KEY.
"""

import asyncio

import pytest

from btcopilot.schema import DiagramData, PDP, EventKind
from btcopilot.pdp import import_text


# --- Shared assertion helpers ---


def _new_people_names(deltas):
    return {p.name.lower() for p in deltas.people}


def _assert_no_duplicate_people(deltas, committed_names):
    """Assert none of the committed names appear as new people in deltas."""
    new_names = _new_people_names(deltas)
    for name in committed_names:
        assert name.lower() not in new_names, (
            f"{name} was recreated instead of referenced by committed ID. "
            f"New people: {[(p.id, p.name) for p in deltas.people]}"
        )


def _assert_no_duplicate_events(deltas, committed_kinds):
    """Assert no events of the given kinds were recreated."""
    for kind in committed_kinds:
        dupes = [e for e in deltas.events if e.kind == kind]
        assert len(dupes) == 0, (
            f"{kind.value} event was recreated. "
            f"Duplicates: {[(e.id, e.person, e.spouse) for e in dupes]}"
        )


# --- Simple tests ---


@pytest.mark.e2e
def test_reextract_references_committed_people():
    """LLM should reference committed people by positive ID, not recreate them."""
    dd = DiagramData()
    dd.people = [
        {"id": 1, "name": "Mary", "last_name": "Smith", "gender": "female"},
        {"id": 2, "name": "John", "last_name": "Smith", "gender": "male"},
    ]
    dd.pair_bonds = [{"id": 10, "person_a": 1, "person_b": 2}]
    dd.events = [
        {"id": 20, "kind": "married", "person": 1, "spouse": 2, "dateTime": "1990-06-15"},
    ]

    text = (
        "My parents are Mary and John Smith. They got married in 1990. "
        "My sister Sarah was born in 1995."
    )
    pdp, deltas = asyncio.run(import_text(dd, text))

    _assert_no_duplicate_people(deltas, ["Mary", "John"])

    # Sarah should be new (negative ID)
    sarah = [p for p in deltas.people if p.name.lower() == "sarah"]
    assert len(sarah) == 1, (
        f"Sarah should be extracted as new person. Got: {[(p.id, p.name) for p in deltas.people]}"
    )
    assert sarah[0].id < 0


@pytest.mark.e2e
def test_reextract_does_not_duplicate_marriage():
    """Committed marriage event should not be recreated."""
    dd = DiagramData()
    dd.people = [
        {"id": 1, "name": "Mary", "gender": "female"},
        {"id": 2, "name": "John", "gender": "male"},
    ]
    dd.pair_bonds = [{"id": 10, "person_a": 1, "person_b": 2}]
    dd.events = [
        {"id": 20, "kind": "married", "person": 1, "spouse": 2, "dateTime": "1990-06-15"},
    ]

    text = "Mary and John got married in June 1990. They have been together ever since."
    pdp, deltas = asyncio.run(import_text(dd, text))

    _assert_no_duplicate_events(deltas, [EventKind.Married])


# --- Complex 3-generation family ---


COMPLEX_CONVERSATION = """\
My name is David Chen. My wife is Lisa Chen, we got married in 2010. We have \
two kids: Emma, born 2012, and Jake, born 2015.

My parents are Robert and Margaret Chen. Dad is 72, mom is 70. They married in \
1978. Dad had a heart attack in 2020 and has been on medication since. Mom has \
been taking care of him — she stopped working after his heart attack.

My mom's parents were William and Dorothy Hayes. Grandpa William died in 2015 \
of lung cancer. Grandma Dorothy is 92, lives in a nursing home now — she moved \
there in 2021.

My dad's parents were Henry and Rose Chen. They both passed — Grandpa Henry \
died in 2005 from a stroke, Grandma Rose died in 2018.

I have a brother, Michael Chen, he's 38. He got divorced from his wife Karen \
in 2022. They have a daughter, Sophie, born 2017. Michael has been drinking \
more since the divorce.

Lisa's parents are Tom and Susan Park. They're both healthy, still together. \
Tom is 68, Susan is 65.

After Dad's heart attack I started having trouble sleeping. My anxiety went up \
around that time. When Grandpa William died the same year, things got worse — \
I was barely functioning at work for a few months.
"""

# 3-generation committed state: grandparents, parents, siblings, spouses, children
COMPLEX_COMMITTED = {
    "people": [
        {"id": 1, "name": "David", "last_name": "Chen", "gender": "male"},
        {"id": 2, "name": "Lisa", "last_name": "Chen", "gender": "female"},
        {"id": 3, "name": "Emma", "last_name": "Chen", "gender": "female"},
        {"id": 4, "name": "Jake", "last_name": "Chen", "gender": "male"},
        {"id": 5, "name": "Robert", "last_name": "Chen", "gender": "male"},
        {"id": 6, "name": "Margaret", "last_name": "Chen", "gender": "female"},
        {"id": 7, "name": "Michael", "last_name": "Chen", "gender": "male"},
        {"id": 8, "name": "Karen", "gender": "female"},
        {"id": 9, "name": "Sophie", "last_name": "Chen", "gender": "female"},
        {"id": 10, "name": "William", "last_name": "Hayes", "gender": "male"},
        {"id": 11, "name": "Dorothy", "last_name": "Hayes", "gender": "female"},
        {"id": 12, "name": "Henry", "last_name": "Chen", "gender": "male"},
        {"id": 13, "name": "Rose", "last_name": "Chen", "gender": "female"},
        {"id": 14, "name": "Tom", "last_name": "Park", "gender": "male"},
        {"id": 15, "name": "Susan", "last_name": "Park", "gender": "female"},
    ],
    "pair_bonds": [
        {"id": 100, "person_a": 1, "person_b": 2},      # David-Lisa
        {"id": 101, "person_a": 5, "person_b": 6},      # Robert-Margaret
        {"id": 102, "person_a": 7, "person_b": 8},      # Michael-Karen
        {"id": 103, "person_a": 10, "person_b": 11},    # William-Dorothy
        {"id": 104, "person_a": 12, "person_b": 13},    # Henry-Rose
        {"id": 105, "person_a": 14, "person_b": 15},    # Tom-Susan
    ],
    "events": [
        {"id": 200, "kind": "married", "person": 1, "spouse": 2, "dateTime": "2010-01-01"},
        {"id": 201, "kind": "married", "person": 5, "spouse": 6, "dateTime": "1978-01-01"},
        {"id": 202, "kind": "birth", "person": 1, "spouse": 2, "child": 3, "dateTime": "2012-01-01"},
        {"id": 203, "kind": "birth", "person": 1, "spouse": 2, "child": 4, "dateTime": "2015-01-01"},
        {"id": 204, "kind": "death", "person": 10, "dateTime": "2015-01-01"},
        {"id": 205, "kind": "death", "person": 12, "dateTime": "2005-01-01"},
        {"id": 206, "kind": "death", "person": 13, "dateTime": "2018-01-01"},
        {"id": 207, "kind": "divorced", "person": 7, "spouse": 8, "dateTime": "2022-01-01"},
        {"id": 208, "kind": "birth", "person": 7, "spouse": 8, "child": 9, "dateTime": "2017-01-01"},
    ],
}

COMMITTED_NAMES = [
    "David", "Lisa", "Emma", "Jake", "Robert", "Margaret",
    "Michael", "Karen", "Sophie", "William", "Dorothy",
    "Henry", "Rose", "Tom", "Susan",
]


@pytest.mark.e2e
def test_complex_reextract_no_duplicate_people():
    """15-person committed family: re-extraction should not recreate any of them."""
    dd = DiagramData()
    dd.people = list(COMPLEX_COMMITTED["people"])
    dd.pair_bonds = list(COMPLEX_COMMITTED["pair_bonds"])
    dd.events = list(COMPLEX_COMMITTED["events"])

    pdp, deltas = asyncio.run(import_text(dd, COMPLEX_CONVERSATION))

    _assert_no_duplicate_people(deltas, COMMITTED_NAMES)


@pytest.mark.e2e
def test_complex_reextract_no_duplicate_structural_events():
    """Committed structural events (marriages, deaths, births, divorce) should not be recreated."""
    dd = DiagramData()
    dd.people = list(COMPLEX_COMMITTED["people"])
    dd.pair_bonds = list(COMPLEX_COMMITTED["pair_bonds"])
    dd.events = list(COMPLEX_COMMITTED["events"])

    pdp, deltas = asyncio.run(import_text(dd, COMPLEX_CONVERSATION))

    _assert_no_duplicate_events(deltas, [
        EventKind.Married,
        EventKind.Death,
        EventKind.Divorced,
    ])

    # Birth events: should not duplicate committed births (Emma, Jake, Sophie)
    new_births = [e for e in deltas.events if e.kind == EventKind.Birth]
    committed_children = {3, 4, 9}  # Emma, Jake, Sophie
    for birth in new_births:
        assert birth.child not in committed_children, (
            f"Birth event for committed child {birth.child} was recreated. "
            f"New births: {[(e.id, e.child) for e in new_births]}"
        )


@pytest.mark.e2e
def test_complex_reextract_no_duplicate_pair_bonds():
    """Committed pair bonds should not be recreated."""
    dd = DiagramData()
    dd.people = list(COMPLEX_COMMITTED["people"])
    dd.pair_bonds = list(COMPLEX_COMMITTED["pair_bonds"])
    dd.events = list(COMPLEX_COMMITTED["events"])

    pdp, deltas = asyncio.run(import_text(dd, COMPLEX_CONVERSATION))

    committed_dyads = {
        frozenset((b["person_a"], b["person_b"]))
        for b in COMPLEX_COMMITTED["pair_bonds"]
    }
    for bond in deltas.pair_bonds:
        dyad = frozenset((bond.person_a, bond.person_b))
        assert dyad not in committed_dyads, (
            f"Pair bond {bond.person_a}-{bond.person_b} duplicates committed bond. "
            f"New bonds: {[(b.id, b.person_a, b.person_b) for b in deltas.pair_bonds]}"
        )


@pytest.mark.e2e
def test_complex_reextract_shift_events_reference_committed_people():
    """Shift events (anxiety, functioning changes) should reference committed person IDs."""
    dd = DiagramData()
    dd.people = list(COMPLEX_COMMITTED["people"])
    dd.pair_bonds = list(COMPLEX_COMMITTED["pair_bonds"])
    dd.events = list(COMPLEX_COMMITTED["events"])

    pdp, deltas = asyncio.run(import_text(dd, COMPLEX_CONVERSATION))

    committed_ids = {p["id"] for p in COMPLEX_COMMITTED["people"]}
    new_ids = {p.id for p in deltas.people}
    valid_ids = committed_ids | new_ids

    shifts = [e for e in deltas.events if e.kind == EventKind.Shift]
    for shift in shifts:
        assert shift.person in valid_ids, (
            f"Shift event references person {shift.person} which is neither "
            f"committed nor a new PDP person. Valid: {valid_ids}"
        )
