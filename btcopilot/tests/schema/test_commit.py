import pytest

from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    PairBond,
    Person,
    Event,
    EventKind,
    VariableShift,
    RelationshipKind,
)


def test_commit_birth_event_creates_inferred_parents():
    # R-0325
    data = DiagramData(
        pdp=PDP(
            people=[Person(id=-1, name="Baby")],
            events=[
                Event(id=-2, kind=EventKind.Birth, child=-1, dateTime="2020-01-01")
            ],
        )
    )
    data.commit_pdp_items([-2])

    # Should have created: Baby, Mother, Father + PairBond
    assert len(data.people) == 3
    assert len(data.pair_bonds) == 1

    baby = [p for p in data.people if p["name"] == "Baby"][0]
    mother = [p for p in data.people if "mother" in p["name"]][0]
    father = [p for p in data.people if "father" in p["name"]][0]

    assert mother["name"] == "Baby's mother"
    assert father["name"] == "Baby's father"

    # Birth event should have person, spouse, child all set
    event = data.events[0]
    assert event["child"] == baby["id"]
    assert event["person"] == mother["id"]
    assert event["spouse"] == father["id"]

    # Child's parents should point to the pair bond
    pair_bond = data.pair_bonds[0]
    assert baby["parents"] == pair_bond["id"]


def test_commit_birth_event_creates_inferred_spouse():
    # R-0325
    data = DiagramData(
        pdp=PDP(
            people=[Person(id=-1, name="Alice"), Person(id=-2, name="Baby")],
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Birth,
                    person=-1,
                    child=-2,
                    dateTime="2020-01-01",
                )
            ],
        )
    )
    data.commit_pdp_items([-3])

    # Should have created: Alice, Baby, inferred spouse
    assert len(data.people) == 3

    alice = [p for p in data.people if p["name"] == "Alice"][0]
    spouse = [p for p in data.people if "spouse" in p["name"]][0]

    assert spouse["name"] == "Alice's spouse"

    event = data.events[0]
    assert event["person"] == alice["id"]
    assert event["spouse"] == spouse["id"]

    # Should have created a pair bond between Alice and inferred spouse
    assert len(data.pair_bonds) == 1
    pb = data.pair_bonds[0]
    assert {pb["person_a"], pb["person_b"]} == {alice["id"], spouse["id"]}

    # Baby's parents should reference the pair bond
    baby = [p for p in data.people if p["name"] == "Baby"][0]
    assert baby["parents"] == pb["id"]


