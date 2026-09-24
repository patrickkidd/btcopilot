"""Pair bonds on the user's own diagram: one bond ever between two people, and
a child born into it."""

import pytest

from btcopilot.extensions import db
from btcopilot.schema import Person, PersonKind, asdict
from btcopilot.tests.conftest import csrf_token


@pytest.fixture
def family(test_user):
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [
        asdict(Person(id=1, name="Marcus", gender=PersonKind.Male)),
        asdict(Person(id=2, name="Delphine", gender=PersonKind.Female)),
        asdict(Person(id=3, name="Corinne", gender=PersonKind.Female)),
    ]
    data.lastItemId = 3
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def _post(web, body):
    return web.post(
        "/app/pair_bonds", json=body, headers={"X-CSRFToken": csrf_token(web)}
    )


def test_adding_a_bond_writes_it(web, family):
    # R-0078
    added = _post(web, {"person_a": 1, "person_b": 2, "married": True})
    assert added.status_code == 201
    assert added.get_json() == {
        "id": 4,
        "person_a": 1,
        "person_b": 2,
        "married": True,
    }


def test_a_bond_of_one_person_with_themselves_is_refused(web, family):
    # R-0326
    refused = _post(web, {"person_a": 1, "person_b": 1})
    assert refused.status_code == 400
    assert "themselves" in refused.get_data(as_text=True)


def test_a_second_bond_between_the_same_two_is_refused(web, family):
    # R-0326
    _post(web, {"person_a": 1, "person_b": 2})
    refused = _post(web, {"person_a": 2, "person_b": 1})
    assert refused.status_code == 400
    assert "already have pair bond" in refused.get_data(as_text=True)


def test_a_child_is_born_to_a_bond_and_never_to_one_they_are_in(web, family):
    # R-0326, R-0345
    bond = _post(web, {"person_a": 1, "person_b": 2}).get_json()
    token = csrf_token(web)

    born = web.patch(
        "/app/people/3",
        json={"parents": bond["id"]},
        headers={"X-CSRFToken": token},
    )
    assert born.get_json()["parents"] == bond["id"]

    refused = web.patch(
        "/app/people/1",
        json={"parents": bond["id"]},
        headers={"X-CSRFToken": token},
    )
    assert refused.status_code == 400
    assert "their own parent" in refused.get_data(as_text=True)


def test_add_parents_makes_a_bond_of_two_generically_named_people(web, family):
    # R-0325
    """"Add parents" on a person with none: the record gains a father and a
    mother named after them, and the person is born to their bond."""
    added = _post(web, {"parent_of": 3})
    assert added.status_code == 201

    db.session.refresh(family)
    data = family.get_diagram_data()
    names = [p["name"] for p in data.people]
    assert names[-2:] == ["Corinne's father", "Corinne's mother"]
    assert [p for p in data.people if p["id"] == 3][0]["parents"] == added.get_json()["id"]


def test_ending_a_bond_leaves_its_children_without_parents(web, family):
    # R-0326
    bond = _post(web, {"person_a": 1, "person_b": 2}).get_json()
    token = csrf_token(web)
    web.patch(
        "/app/people/3",
        json={"parents": bond["id"]},
        headers={"X-CSRFToken": token},
    )

    removed = web.delete(
        f"/app/pair_bonds/{bond['id']}", headers={"X-CSRFToken": token}
    )
    assert removed.status_code == 204

    db.session.refresh(family)
    data = family.get_diagram_data()
    assert data.pair_bonds == []
    assert [p for p in data.people if p["id"] == 3][0]["parents"] is None
