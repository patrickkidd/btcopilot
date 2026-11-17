"""Children of one parent named together share one generically named other
parent, named for the known parent; a child added later is given the same
one; a second generic parent is made only when the coder says the children
have different mothers or fathers (R-0971, R-0325). A case passes when 2 of 3
runs leave the copy as stated.

Run on the coach's Claude model through the subscription, not on the scribe's
Gemini, so it spends nothing: it proves the prompt and the tools, not the
Gemini model's reading of them.

Fails on the old prompt: given only the known parent for each child, the
record names a new mother for each child, one per sibling.

The family is invented.
"""

import pytest

from btcopilot.coachmodel import CoachModel
from btcopilot.review import adapter
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.live.test_scribe_evals import ANN, BORN, coding_of, told

BOB = {"id": 3, "name": "Bob", "gender": "male"}
KIDS = ("Amy", "Ben", "Cal")
THREE = f"Ann's stepfather Bob had three kids, {KIDS[0]}, {KIDS[1]}, and {KIDS[2]} in that order"
PARTNER = {"id": 4, "name": "Bob's partner"}
BOND = {"id": 5, "person_a": 3, "person_b": 4}
GIVEN = {"people": [ANN, BOB], "events": [BORN], "lastItemId": 3}
RAISED = {
    "people": [
        ANN,
        BOB,
        PARTNER,
        *({"id": 6 + i, "name": name, "parents": BOND["id"]} for i, name in enumerate(KIDS)),
    ],
    "events": [BORN],
    "pair_bonds": [BOND],
    "lastItemId": 8,
}


@pytest.fixture(autouse=True)
def claude(monkeypatch):
    monkeypatch.setattr(adapter, "scribe_model", lambda name: CoachModel())


def diagram(coding) -> dict:
    return adapter.record_of(adapter.diagram_of(coding.diagram_id))


def kids(data: dict, names) -> dict:
    return {p["name"]: p for p in data["people"] if p["name"] in names}


def bonds(data: dict) -> dict:
    return {b["id"]: b for b in data.get("pair_bonds") or []}


def others(data: dict, named) -> list[dict]:
    return [p for p in data["people"] if p["name"] not in named]


@passes(2, of=3)
def test_children_named_together_share_one_other_parent_named_for_the_known_one(test_user):
    # R-0971, R-0325
    coding, statement = coding_of(test_user, GIVEN)
    told(coding, statement, THREE)
    data = diagram(coding)
    found = kids(data, KIDS)
    assert sorted(found) == sorted(KIDS), data
    shared = {p.get("parents") for p in found.values()}
    assert len(shared) == 1 and shared <= set(bonds(data)), data
    bond = bonds(data)[shared.pop()]
    added = others(data, {"Ann", "Bob", *KIDS})
    assert len(added) == 1, data
    assert {bond["person_a"], bond["person_b"]} == {BOB["id"], added[0]["id"]}, data
    assert added[0]["name"].lower().startswith("bob"), added


@passes(2, of=3)
def test_a_child_added_later_is_given_the_same_other_parent(test_user):
    # R-0971, R-0325
    coding, statement = coding_of(test_user, RAISED)
    told(coding, statement, "Bob also had a fourth kid, Dan")
    data = diagram(coding)
    assert [p.get("parents") for p in kids(data, {"Dan"}).values()] == [BOND["id"]], data
    assert not others(data, {"Ann", "Bob", "Bob's partner", "Dan", *KIDS}), data


@passes(2, of=3)
def test_children_with_different_mothers_get_two_other_parents(test_user):
    # R-0971, R-0325
    coding, statement = coding_of(test_user, GIVEN)
    told(coding, statement, "Ann's stepfather Bob had two kids by different mothers, Amy and Ben")
    data = diagram(coding)
    found = kids(data, {"Amy", "Ben"})
    held = bonds(data)
    sides = [
        {held[p["parents"]]["person_a"], held[p["parents"]]["person_b"]}
        for p in found.values()
        if p.get("parents") in held
    ]
    assert len(sides) == 2 and all(BOB["id"] in s for s in sides), data
    assert len(set.union(*sides) - {BOB["id"]}) == 2, data
    assert len(others(data, {"Ann", "Bob", "Amy", "Ben"})) == 2, data
