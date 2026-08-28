"""FD-336 item 4: committed people are stored as camelCase chunks that keep the
family name, and every reader of committed people round-trips them."""

from btcopilot.pdp import _committed_state_for_prompt, fix_committed_person_duplicates
from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    PersonKind,
    committed_person_chunk,
    person_from_committed_chunk,
)

COMMITTED_KEYS = {"id", "name", "lastName", "gender", "parents"}


def test_chunk_has_exactly_the_committed_keys():
    chunk = committed_person_chunk(
        Person(
            id=3,
            name="Connie",
            last_name="Stinson",
            gender=PersonKind.Female,
            confidence=0.9,
        )
    )
    assert set(chunk) == COMMITTED_KEYS


def test_chunk_keeps_first_and_family_name_apart():
    chunk = committed_person_chunk(Person(id=3, name="Connie", last_name="Stinson"))
    assert chunk["name"] == "Connie"
    assert chunk["lastName"] == "Stinson"


def test_chunk_promotes_family_name_when_no_first_name():
    chunk = committed_person_chunk(Person(id=4, last_name="Stinson"))
    assert chunk["name"] == "Stinson"
    assert chunk["lastName"] is None


def test_chunk_leaves_family_name_empty_when_only_first_name():
    chunk = committed_person_chunk(Person(id=5, name="Connie"))
    assert chunk["name"] == "Connie"
    assert chunk["lastName"] is None


def test_person_round_trips_through_chunk():
    person = Person(
        id=6,
        name="Connie",
        last_name="Stinson",
        gender=PersonKind.Female,
        parents=7,
    )
    restored = person_from_committed_chunk(committed_person_chunk(person))
    assert restored.id == 6
    assert restored.name == "Connie"
    assert restored.last_name == "Stinson"
    assert restored.gender == PersonKind.Female
    assert restored.parents == 7


def test_person_accepts_legacy_snake_case_chunk():
    restored = person_from_committed_chunk(
        {"id": 8, "name": "Connie", "last_name": "Stinson"}
    )
    assert restored.last_name == "Stinson"


def test_commit_keeps_family_name_alongside_first_name():
    diagram_data = DiagramData(
        pdp=PDP(people=[Person(id=-1, name="Connie", last_name="Stinson")])
    )
    diagram_data.commit_pdp_items([-1])
    assert diagram_data.people[0]["name"] == "Connie"
    assert diagram_data.people[0]["lastName"] == "Stinson"


def test_commit_promotes_family_name_when_no_first_name():
    diagram_data = DiagramData(pdp=PDP(people=[Person(id=-1, last_name="Stinson")]))
    diagram_data.commit_pdp_items([-1])
    assert diagram_data.people[0]["name"] == "Stinson"
    assert diagram_data.people[0]["lastName"] is None


def test_commit_leaves_family_name_empty_when_only_first_name():
    diagram_data = DiagramData(pdp=PDP(people=[Person(id=-1, name="Connie")]))
    diagram_data.commit_pdp_items([-1])
    assert diagram_data.people[0]["name"] == "Connie"
    assert diagram_data.people[0]["lastName"] is None


def test_prompt_state_carries_the_committed_chunk():
    diagram_data = DiagramData(
        pdp=PDP(people=[Person(id=-1, name="Connie", last_name="Stinson")])
    )
    diagram_data.commit_pdp_items([-1])
    assert _committed_state_for_prompt(diagram_data)["people"] == diagram_data.people


def test_dedup_still_finds_a_person_committed_from_a_family_name_only_row():
    diagram_data = DiagramData(pdp=PDP(people=[Person(id=-1, last_name="Stinson")]))
    committed_id = diagram_data.commit_pdp_items([-1])[-1]

    deltas = PDPDeltas(people=[Person(id=-2, name="Stinson")])
    fix_committed_person_duplicates(deltas, diagram_data)
    assert deltas.people == []
    assert diagram_data.people[0]["id"] == committed_id
