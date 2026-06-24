from btcopilot.familygraph import components, lcc_percent
from btcopilot.schema import PairBond, Person


def _p(id, name, primary=False, parents=None):
    return {"id": id, "name": name, "primary": primary, "parents": parents}


def _b(id, a, b):
    return {"id": id, "person_a": a, "person_b": b}


def test_components_dict_parents_via_bond():
    people = [_p(10, "Mom"), _p(11, "Dad"), _p(12, "Kid", parents=100), _p(20, "Stray")]
    bonds = [_b(100, 10, 11)]
    assert components(people, bonds) == [{10, 11, 12}, {20}]


def test_components_dataclass_parents_via_bond():
    people = [
        Person(id=1, name="User"),
        Person(id=2, name="Assistant"),
        Person(id=-1, name="Mom"),
        Person(id=-2, name="Kid", parents=-10),
        Person(id=-3, name="Stray"),
    ]
    bonds = [PairBond(id=-10, person_a=1, person_b=-1)]
    assert components(people, bonds) == [{1, -1, -2}, {-3}]


def test_components_mixed_dict_and_dataclass():
    people = [
        _p(1, "User", primary=True),
        _p(10, "Spouse"),
        Person(id=-1, name="Kid", parents=-10),
    ]
    bonds = [_b(100, 1, 10), PairBond(id=-10, person_a=1, person_b=10)]
    assert components(people, bonds) == [{1, 10, -1}]


def test_components_user_connects_assistant_dropped():
    people = [
        _p(1, "User", primary=True),
        _p(2, "Assistant"),
        _p(10, "Spouse"),
        _p(11, "Kid1", parents=100),
        _p(12, "Kid2", parents=100),
    ]
    bonds = [_b(100, 1, 10)]
    assert components(people, bonds) == [{1, 10, 11, 12}]


def test_components_sorted_by_non_default_size():
    # User+Spouse counts 1 non-default member; Mom+Dad count 2 — main tree is
    # Mom+Dad even though raw component sizes tie at 2.
    people = [
        _p(1, "User", primary=True),
        _p(10, "Spouse"),
        _p(20, "Mom"),
        _p(21, "Dad"),
    ]
    bonds = [_b(100, 1, 10), _b(200, 20, 21)]
    assert components(people, bonds) == [{20, 21}, {1, 10}]


def test_user_connects_family_as_hub():
    # User (proband) bonded to spouse and parent of two children — one family via the user.
    people = [
        _p(1, "User", primary=True),
        _p(10, "Spouse"),
        _p(11, "Kid1", parents=100),
        _p(12, "Kid2", parents=100),
    ]
    bonds = [_b(100, 1, 10)]
    s = lcc_percent(people, bonds)
    # User excluded from count; the 3 relatives form one component via the user node.
    assert s["total"] == 3
    assert s["lcc"] == 3
    assert s["lcc_pct"] == 100.0


def test_without_user_links_family_fragments():
    # Same people but the children's parents bond is missing — they fragment.
    people = [
        _p(1, "User", primary=True),
        _p(10, "Spouse"),
        _p(11, "Kid1"),
        _p(12, "Kid2"),
    ]
    bonds = [_b(100, 1, 10)]
    s = lcc_percent(people, bonds)
    assert s["total"] == 3
    assert s["lcc"] == 1  # spouse via user; the two kids are isolated singletons


def test_assistant_dropped_from_graph_and_count():
    people = [
        _p(1, "User", primary=True),
        _p(2, "Assistant"),
        _p(10, "Mom"),
        _p(11, "Kid", parents=100),
    ]
    bonds = [_b(100, 1, 10)]
    s = lcc_percent(people, bonds)
    assert s["total"] == 2  # Mom + Kid only; User and Assistant excluded from count
    assert s["lcc"] == 2  # Kid -> User(hub) -> Mom


def test_empty_returns_zero():
    s = lcc_percent([_p(1, "User", primary=True), _p(2, "Assistant")], [])
    assert s == {"total": 0, "components": 0, "lcc": 0, "lcc_pct": 0.0}
