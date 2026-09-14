"""Who is who across two codings.

People are paired by the words of their name and by where they stand in the
family — who they are bonded to, and who is born to that bond — never by the
ids two records gave the same person by chance. When the matcher cannot tell,
the room decides who is who (R-0326).
"""

from btcopilot.review import adapter, snapshot
from btcopilot.schema import ItemKind
from btcopilot.tests.chat.review.conftest import coded


def _pdp(people, bonds=()):
    return adapter.pdp_from(
        {"people": list(people), "pair_bonds": list(bonds)}
    )


def _person(person_id, name, gender="male", parents=None):
    return {"id": person_id, "name": name, "gender": gender, "parents": parents}


def _bond(bond_id, a, b):
    return {"id": bond_id, "person_a": a, "person_b": b}


def _match(mine, theirs):
    return snapshot._match(ItemKind.Person, mine, theirs)


def test_the_same_man_named_three_ways_is_one_person():
    """One coder wrote "father", another "Corinne's father", a third his name.
    The bond their daughter hangs on says they are the same man."""
    daughter = _person(3, "Corinne", "female", parents=10)
    theirs = _pdp(
        [_person(1, "Marcus"), _person(2, "Delphine", "female"), daughter],
        [_bond(10, 1, 2)],
    )
    for name in ("father", "Corinne's father", "Marcus"):
        mine = _pdp(
            [
                _person(7, name),
                _person(8, "Delphine", "female"),
                _person(9, "Corinne", "female", parents=20),
            ],
            [_bond(20, 7, 8)],
        )
        matched, unmatched, ambiguous = _match(mine, theirs)
        paired = {one.id: other.id for one, other in matched}
        assert paired[7] == 1, name
        assert unmatched == []
        assert ambiguous == set()


def test_two_people_with_the_same_first_name_are_not_matched():
    """Two men called Marcus standing in different places in the family: one is
    the father, one is a son-in-law, and they are not the same man."""
    theirs = _pdp(
        [_person(1, "Marcus"), _person(2, "Delphine", "female"), _person(3, "Corinne", "female", parents=10)],
        [_bond(10, 1, 2)],
    )
    mine = _pdp(
        [
            _person(7, "Marcus"),
            _person(8, "Corinne", "female"),
            _person(9, "Theo", parents=20),
        ],
        [_bond(20, 7, 8)],
    )
    matched, unmatched, _ = _match(mine, theirs)
    paired = {one.id: other.id for one, other in matched}
    assert paired.get(7) != 1
    assert 7 in [p.id for p in unmatched] or paired.get(7) is None


def test_a_person_who_could_be_two_is_handed_to_the_room():
    """Two sisters both called Lee, with nothing in the family to tell them
    apart: the item carries both versions and the room decides who is who."""
    theirs = _pdp([_person(1, "Lee", "female"), _person(2, "Lee", "female")])
    mine = _pdp([_person(7, "Lee", "female")])
    matched, _, ambiguous = _match(mine, theirs)
    assert len(matched) == 1
    assert ambiguous == {id(mine.people[0])}


def test_an_ambiguous_person_is_never_agreed(coder, patrick, cut):
    """The row the snapshot writes for it is disputed and says it is unsure."""
    record = {"people": [_person(1, "Lee", "female"), _person(2, "Lee", "female")]}
    coded(coder.user, cut, record)
    coded(patrick.user, cut, {"people": [_person(5, "Lee", "female")]})

    rows = snapshot.build(cut)
    unsure = [row for row in rows if row.ambiguous]
    assert len(unsure) == 1
    assert unsure[0].status.value == "disputed"


def test_the_records_say_the_family_each_version_is_drawn_against(patrick, cut):
    """A version of a person is drawn as a fragment, so the ballot is handed the
    people, the bonds and the events of the coding it came from."""
    coded(
        patrick.user,
        cut,
        {
            "people": [
                _person(1, "Marcus"),
                _person(2, "Delphine", "female"),
                _person(3, "Corinne", "female", parents=10),
            ],
            "pair_bonds": [dict(_bond(10, 1, 2), married=True)],
            "events": [
                {
                    "id": 20,
                    "kind": "married",
                    "person": 1,
                    "spouse": 2,
                    "dateTime": "1970-06-01",
                }
            ],
        },
    )
    response = patrick.get(f"/review/records?cut_id={cut.id}")
    assert response.status_code == 200

    record = response.json[0]
    assert [p["name"] for p in record["people"]] == ["Marcus", "Delphine", "Corinne"]
    assert record["people"][2]["parents"] == 10
    assert record["pair_bonds"] == [
        {"id": 10, "person_a": 1, "person_b": 2, "married": True}
    ]
    assert record["events"][0]["dateTime"] == "1970-06-01"
