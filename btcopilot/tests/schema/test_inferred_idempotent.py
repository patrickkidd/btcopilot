"""
Verify that _create_inferred_birth_items / _create_inferred_pair_bond_items /
_repair_dangling_parents do not produce duplicates on a 409-retry replay.

Each retry of commit_pdp_items runs on the SERVER's fresh state (the prior
attempt's mutations aren't visible because the server rejected them with
409). So the inferred items should appear exactly once in the final blob,
not twice.

Plan: familydiagram/doc/plans/2026-05-01--mvp-merge-fix/README.md (latent fix 3b)
"""

from btcopilot.schema import (
    DiagramData,
    PDP,
    Person,
    PairBond,
    Event,
    EventKind,
    asdict,
)


def _build_pdp_with_birth_unknown_parents():
    """Build a DiagramData where pdp has a Birth event for a child with no parents."""
    dd = DiagramData()
    child = Person(id=-1, name="Alice")
    birth = Event(
        id=-2, kind=EventKind.Birth, child=child.id,
    )
    dd.pdp = PDP(people=[child], events=[birth], pair_bonds=[])
    return dd, child.id, birth.id


def test_commit_then_replay_on_fresh_pdp_no_duplicates():
    """
    Simulate the 409-retry semantic: each attempt runs commit_pdp_items on a
    fresh DiagramData (because server rejects and returns its untouched
    state). The final saved blob should have inferred parents exactly once.
    """
    # First attempt
    dd1, child_id, birth_id = _build_pdp_with_birth_unknown_parents()
    dd1.commit_pdp_items([birth_id])

    # Now simulate 409: server doesn't accept dd1. Second attempt starts
    # from a fresh PDP (server's state, which still has the original PDP
    # items because the first commit was rejected).
    dd2, _, _ = _build_pdp_with_birth_unknown_parents()
    dd2.commit_pdp_items([birth_id])

    # Final blob is dd2's. Should have exactly one inferred mother + father
    # + pair_bond, just like a single attempt would.
    inferred_parents = [
        p for p in dd2.people if p.get("name", "").endswith("'s mother")
        or p.get("name", "").endswith("'s father")
    ]
    assert len(inferred_parents) == 2
    assert len(dd2.pair_bonds) == 1


def test_double_commit_on_same_diagramData_fails_fast():
    """
    If commit_pdp_items is called twice on the SAME DiagramData with the
    same item_ids, the second call raises ValueError because the item is
    no longer in pdp. Fail-fast is the correct behavior — it surfaces
    duplicate-commit attempts rather than silently duplicating items.
    """
    import pytest

    dd, child_id, birth_id = _build_pdp_with_birth_unknown_parents()
    dd.commit_pdp_items([birth_id])

    # Second commit on the same item_id should fail loudly.
    with pytest.raises(ValueError, match="not found in PDP"):
        dd.commit_pdp_items([birth_id])
