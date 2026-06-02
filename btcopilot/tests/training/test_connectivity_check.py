from btcopilot.training.connectivity_check import lcc_percent


def _p(id, name, primary=False, parents=None):
    return {"id": id, "name": name, "primary": primary, "parents": parents}


def _b(id, a, b):
    return {"id": id, "person_a": a, "person_b": b}


def test_user_connects_family_as_hub():
    # User (proband) bonded to spouse and parent of two children — one family via the user.
    people = [_p(1, "User", primary=True), _p(10, "Spouse"), _p(11, "Kid1", parents=100), _p(12, "Kid2", parents=100)]
    bonds = [_b(100, 1, 10)]
    s = lcc_percent(people, bonds)
    # User excluded from count; the 3 relatives form one component via the user node.
    assert s["total"] == 3
    assert s["lcc"] == 3
    assert s["lcc_pct"] == 100.0


def test_without_user_links_family_fragments():
    # Same people but the children's parents bond is missing — they fragment.
    people = [_p(1, "User", primary=True), _p(10, "Spouse"), _p(11, "Kid1"), _p(12, "Kid2")]
    bonds = [_b(100, 1, 10)]
    s = lcc_percent(people, bonds)
    assert s["total"] == 3
    assert s["lcc"] == 1  # spouse via user; the two kids are isolated singletons


def test_assistant_dropped_from_graph_and_count():
    people = [_p(1, "User", primary=True), _p(2, "Assistant"), _p(10, "Mom"), _p(11, "Kid", parents=100)]
    bonds = [_b(100, 1, 10)]
    s = lcc_percent(people, bonds)
    assert s["total"] == 2  # Mom + Kid only; User and Assistant excluded from count
    assert s["lcc"] == 2  # Kid -> User(hub) -> Mom


def test_empty_returns_zero():
    s = lcc_percent([_p(1, "User", primary=True), _p(2, "Assistant")], [])
    assert s == {"total": 0, "components": 0, "lcc": 0, "lcc_pct": 0.0}
