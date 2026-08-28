import pytest

from btcopilot.testing import fixtures
from btcopilot.testing.fixtures import Case

ALL_PROFILES = "minimal+family+hostile+random"


def test_every_case_is_named_in_a_manifest():
    manifest = fixtures.spec(ALL_PROFILES)["manifest"]
    assert set(manifest) == {case.value for case in Case}


def test_every_manifest_entry_says_what_it_exemplifies():
    manifest = fixtures.spec(ALL_PROFILES)["manifest"]
    assert all(entry["what"] for entry in manifest.values())


def test_hostile_names_carry_every_degenerate_shape():
    diagram = next(
        d for d in fixtures.hostile()["diagrams"] if d["name"] == "Hostile Names"
    )
    people = {p["id"]: p for p in diagram["data"]["people"]}
    assert people[1]["name"] == ""
    assert people[2]["name"] == "Mom"
    assert people[3]["name"] is None and people[3]["last_name"]
    assert len(people[5]["name"]) == 200
    assert people[6]["name"] == people[7]["name"]

    bonds = {b["id"]: b for b in diagram["data"]["pair_bonds"]}
    assert bonds[22]["person_a"] == bonds[22]["person_b"]

    events = {e["id"]: e for e in diagram["data"]["events"]}
    assert events[32]["person"] not in people
    assert [e["child"] for e in (events[30], events[31])] == [8, 8]

    staged = diagram["data"]["pdp"]
    assert staged["people"][0]["parents"] not in {p["id"] for p in staged["people"]}


def test_hostile_sizes_and_licenses():
    spec = fixtures.hostile()
    huge = next(d for d in spec["diagrams"] if d["name"] == "Huge Diagram")
    assert (len(huge["data"]["people"]), len(huge["data"]["events"])) == (
        fixtures.HUGE_PEOPLE,
        fixtures.HUGE_EVENTS,
    )
    licenses = {u["username"]: u.get("license", "active") for u in spec["users"]}
    assert set(licenses.values()) == {"active", "expired", "none"}
    assert any(u.get("free_diagram") is False for u in spec["users"])


def test_family_is_a_connected_three_generation_case():
    diagram = fixtures.family()["diagrams"][0]
    people = diagram["data"]["people"]
    bond_ids = {b["id"] for b in diagram["data"]["pair_bonds"]}
    assert len(people) == 7
    assert all(p["parents"] in bond_ids for p in people if p["parents"] is not None)
    assert any(e["kind"] == "shift" and e["anxiety"] for e in diagram["data"]["events"])
    assert len(fixtures.family()["discussions"]) == 2


def test_random_is_deterministic_for_a_seed():
    assert fixtures.spec("random:5:8") == fixtures.spec("random:5:8")
    assert fixtures.spec("random:5:8") != fixtures.spec("random:6:8")


def test_random_produces_structurally_valid_references():
    diagram = fixtures.random_family(seed=3, people=20)["diagrams"][0]
    person_ids = {p["id"] for p in diagram["data"]["people"]}
    bond_ids = {b["id"] for b in diagram["data"]["pair_bonds"]}
    assert all(
        {b["person_a"], b["person_b"]} <= person_ids for b in diagram["data"]["pair_bonds"]
    )
    assert all(
        p["parents"] in bond_ids for p in diagram["data"]["people"] if p["parents"] is not None
    )
    for event in diagram["data"]["events"]:
        assert {event[k] for k in ("person", "spouse", "child") if event[k]} <= person_ids


def test_profiles_compose_and_unknown_names_fail_early():
    composed = fixtures.spec("family+hostile")
    assert len(composed["users"]) == len(fixtures.family()["users"]) + len(
        fixtures.hostile()["users"]
    )
    with pytest.raises(ValueError):
        fixtures.spec("nope")
