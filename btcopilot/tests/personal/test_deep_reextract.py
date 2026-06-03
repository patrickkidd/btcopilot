"""
Unit tests for deep_reextract merge/reconcile core.
extract_full is mocked to return canned PDPs across K runs.

Family: 3 runs each missing a different bridge bond.
  Committed: User (id=1), Alice (id=10), Bob (id=11), Carol (id=12)
             Bond: Alice--Bob (id=100)
  Run 1: adds Dave (neg id) + Dave--Carol bond — links Carol to Alice/Bob cluster
  Run 2: adds Eve (neg id) + Eve--Carol bond — different bridge person
  Run 3: adds Dave again (same name) + Dave--Bob bond — duplicate Dave, same bond
"""
import copy
import pytest

from btcopilot.schema import DiagramData, PDP, Person, PairBond, PersonKind


def _dd(people: list[dict], pair_bonds: list[dict]) -> DiagramData:
    dd = DiagramData()
    dd.people = copy.deepcopy(people)
    dd.pair_bonds = copy.deepcopy(pair_bonds)
    dd.lastItemId = max((p["id"] for p in people if p.get("id") is not None), default=0)
    return dd


COMMITTED_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None, "primary": True},
    {"id": 10, "name": "Alice", "gender": "female", "parents": None},
    {"id": 11, "name": "Bob", "gender": "male", "parents": None},
    {"id": 12, "name": "Carol", "gender": "female", "parents": None},
]
COMMITTED_BONDS = [
    {"id": 100, "person_a": 10, "person_b": 11},
]

# Run 1: Dave links Carol to the Alice-Bob cluster via Dave--Carol bond
RUN1_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None},
    {"id": 10, "name": "Alice", "gender": "female", "parents": None},
    {"id": 11, "name": "Bob", "gender": "male", "parents": None},
    {"id": 12, "name": "Carol", "gender": "female", "parents": None},
    {"id": 201, "name": "Dave", "gender": "male", "parents": None},
]
RUN1_BONDS = [
    {"id": 100, "person_a": 10, "person_b": 11},
    {"id": 201, "person_a": 201, "person_b": 12},
]

# Run 2: Eve provides a different bridge Carol → Alice/Bob cluster
RUN2_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None},
    {"id": 10, "name": "Alice", "gender": "female", "parents": None},
    {"id": 11, "name": "Bob", "gender": "male", "parents": None},
    {"id": 12, "name": "Carol", "gender": "female", "parents": None},
    {"id": 301, "name": "Eve", "gender": "female", "parents": None},
]
RUN2_BONDS = [
    {"id": 100, "person_a": 10, "person_b": 11},
    {"id": 301, "person_a": 301, "person_b": 12},
]

# Run 3: Dave again (same name) — should match Dave from run1 and not create a dupe
RUN3_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None},
    {"id": 10, "name": "Alice", "gender": "female", "parents": None},
    {"id": 11, "name": "Bob", "gender": "male", "parents": None},
    {"id": 12, "name": "Carol", "gender": "female", "parents": None},
    {"id": 401, "name": "Dave", "gender": "male", "parents": None},
]
RUN3_BONDS = [
    {"id": 100, "person_a": 10, "person_b": 11},
    {"id": 401, "person_a": 401, "person_b": 11},
]


def test_merge_adds_new_people_from_runs():
    """New people from runs end up in the delta with negative IDs."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    runs = [_dd(RUN1_PEOPLE, RUN1_BONDS), _dd(RUN2_PEOPLE, RUN2_BONDS)]
    delta_pdp, _ = merge_runs(runs, committed)

    names = {p.name for p in delta_pdp.people if p.id is not None and p.id < 0}
    # Dave and Eve are both new
    assert "Dave" in names
    assert "Eve" in names


def test_merge_deduplicates_same_person_across_runs():
    """Dave appearing in run1 and run3 should produce only one Dave in the delta."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    runs = [_dd(RUN1_PEOPLE, RUN1_BONDS), _dd(RUN3_PEOPLE, RUN3_BONDS)]
    delta_pdp, _ = merge_runs(runs, committed)

    dave_entries = [p for p in delta_pdp.people if p.name == "Dave" and p.id is not None and p.id < 0]
    assert len(dave_entries) == 1


def test_merge_bond_endpoints_resolve_to_valid_ids():
    """All delta bond endpoints must reference a person that exists (committed or new)."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    runs = [_dd(RUN1_PEOPLE, RUN1_BONDS), _dd(RUN2_PEOPLE, RUN2_BONDS), _dd(RUN3_PEOPLE, RUN3_BONDS)]
    delta_pdp, _ = merge_runs(runs, committed)

    all_person_ids = (
        {p["id"] for p in COMMITTED_PEOPLE if p.get("id") is not None}
        | {p.id for p in delta_pdp.people if p.id is not None}
    )
    for pb in delta_pdp.pair_bonds:
        assert pb.person_a in all_person_ids, f"bond {pb.id} person_a={pb.person_a} not found"
        assert pb.person_b in all_person_ids, f"bond {pb.id} person_b={pb.person_b} not found"


def test_merge_produces_only_negative_id_new_entities():
    """Delta must not contain positive-ID new people or bonds (only positive-ID edits)."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    runs = [_dd(RUN1_PEOPLE, RUN1_BONDS), _dd(RUN2_PEOPLE, RUN2_BONDS)]
    delta_pdp, _ = merge_runs(runs, committed)

    committed_person_ids = {p["id"] for p in COMMITTED_PEOPLE}
    for p in delta_pdp.people:
        if p.id is not None and p.id > 0:
            # Positive-ID people in delta are parent edits — must be committed
            assert p.id in committed_person_ids, f"positive-ID person {p.id} not in committed"
    for pb in delta_pdp.pair_bonds:
        assert pb.id is not None and pb.id < 0, f"bond {pb.id} in delta is not negative"


def test_delta_commits_cleanly_onto_committed_diagram():
    """Committing the delta PDP onto a copy of the committed diagram must not raise."""
    from btcopilot.personal.deepreextract import merge_runs
    from btcopilot.schema import get_all_pdp_item_ids

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    runs = [_dd(RUN1_PEOPLE, RUN1_BONDS), _dd(RUN2_PEOPLE, RUN2_BONDS)]
    delta_pdp, _ = merge_runs(runs, committed)

    # Apply delta onto a fresh copy of committed
    target = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    target.pdp = delta_pdp

    neg_ids = [p.id for p in delta_pdp.people if p.id is not None and p.id < 0]
    neg_ids += [pb.id for pb in delta_pdp.pair_bonds if pb.id is not None and pb.id < 0]
    if neg_ids:
        id_mapping = target.commit_pdp_items(neg_ids)
        assert len(id_mapping) == len(neg_ids)

    # After commit, all previously negative ids are now positive
    all_ids = {p["id"] for p in target.people} | {pb["id"] for pb in target.pair_bonds}
    for old_neg in neg_ids:
        assert old_neg not in all_ids  # original neg id gone
        assert id_mapping[old_neg] in all_ids  # new positive id present


def test_delta_raises_lcc_vs_committed():
    """Post-commit LCC should not decrease vs. the committed baseline."""
    from btcopilot.personal.deepreextract import merge_runs
    from btcopilot.training.connectivity_check import lcc_percent
    from btcopilot.schema import get_all_pdp_item_ids

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    baseline = lcc_percent(committed.people, committed.pair_bonds)

    runs = [_dd(RUN1_PEOPLE, RUN1_BONDS), _dd(RUN2_PEOPLE, RUN2_BONDS), _dd(RUN3_PEOPLE, RUN3_BONDS)]
    delta_pdp, _ = merge_runs(runs, committed)

    target = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    target.pdp = delta_pdp
    neg_ids = [p.id for p in delta_pdp.people if p.id is not None and p.id < 0]
    neg_ids += [pb.id for pb in delta_pdp.pair_bonds if pb.id is not None and pb.id < 0]
    if neg_ids:
        target.commit_pdp_items(neg_ids)

    after = lcc_percent(target.people, target.pair_bonds)
    assert after["lcc_pct"] >= baseline["lcc_pct"], (
        f"LCC dropped after delta commit: {baseline['lcc_pct']} → {after['lcc_pct']}"
    )
