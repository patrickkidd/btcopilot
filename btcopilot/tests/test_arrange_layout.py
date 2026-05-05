"""Tests for btcopilot.arrange.layout — focused on the parent-aware compact (D-28).

The layout pipeline is: placement -> _sweep -> _compact -> _sweep. The
parent-aware cap inside `_compact` prevents children that were correctly placed
under their parents from being yanked into adjacent whitespace by a wider sibling
cluster on the same row. This is the D-28 fix that resolved the Belgards-style
multi-cluster bug. We verify the integrated behavior via `layout()` rather than
poking at the closure inside `_compact`.
"""

from btcopilot.arrange.layout import layout


def _person(pid, gender="male", partners=None, parent_a=None, parent_b=None):
    return {
        "id": pid,
        "name": f"p{pid}",
        "gender": gender,
        "size": 5,
        "partners": partners or [],
        "parent_a": parent_a,
        "parent_b": parent_b,
    }


def test_children_stay_under_parents_when_sibling_cluster_to_left():
    """Topology that previously triggered the Belgards bug:
    root couple A on the right, root couple B on the left, A's children
    must stay under A — not get pulled left into B's whitespace.
    """
    people = [
        # Couple A (right side); couple has children (4 and 5)
        _person(1, gender="male", partners=[2]),
        _person(2, gender="female", partners=[1]),
        _person(4, parent_a=1, parent_b=2),
        _person(5, parent_a=1, parent_b=2),
        # Couple B (left side); childless, just creates a root cluster
        _person(6, gender="male", partners=[7]),
        _person(7, gender="female", partners=[6]),
    ]

    pos = layout(people)

    couple_a_center = (pos[1][0] + pos[2][0]) / 2
    children_center = (pos[4][0] + pos[5][0]) / 2

    # Children must stay aligned-or-right of their parents' midpoint.
    # Pre-D-28 behavior would pull children center far to the left
    # (toward couple B's whitespace) — this assertion catches that regression.
    assert children_center >= couple_a_center - 50, (
        f"children pulled left of parents: couple_a_center={couple_a_center:.0f} "
        f"children_center={children_center:.0f}"
    )


def test_single_child_stays_under_parents():
    """Single child under a single couple — must remain centered."""
    people = [
        _person(1, gender="male", partners=[2]),
        _person(2, gender="female", partners=[1]),
        _person(3, parent_a=1, parent_b=2),
    ]
    pos = layout(people)
    couple_center = (pos[1][0] + pos[2][0]) / 2
    assert abs(pos[3][0] - couple_center) < 30


def test_compact_still_pulls_when_no_parent_constraint():
    """Compact must still close whitespace gaps for items with no parent anchor
    (otherwise the cap would be too restrictive). Two adjacent root persons
    should end up close together, not arbitrarily far apart."""
    people = [
        _person(1),
        _person(2),
    ]
    pos = layout(people)
    gap = abs(pos[1][0] - pos[2][0])
    # Two solo size-5 root persons (125 px symbols) should sit within ~250 px
    # of each other after compact (sibling-gap factor + label allowance).
    assert gap < 350, f"two solo roots too far apart after compact: gap={gap}"
