"""Tests for btcopilot.arrange.refine alignment-penalty quality term (D-27).

Positions use ample x/y separation so size-5 (125 px) symbols don't trigger
spurious symbol-overlap rejections in `_quality`.
"""

from btcopilot.arrange import refine


def _person(pid, partners=None, parent_a=None, parent_b=None):
    return {
        "id": pid,
        "name": f"p{pid}",
        "gender": "",
        "size": 5,
        "partners": partners or [],
        "parent_a": parent_a,
        "parent_b": parent_b,
    }


def test_alignment_penalty_zero_when_children_centered_under_couple():
    by_id = {
        1: _person(1, partners=[2]),
        2: _person(2, partners=[1]),
        3: _person(3, parent_a=1, parent_b=2),
    }
    pos = {1: (0, 0), 2: (500, 0), 3: (250, 500)}
    assert refine._alignment_penalty(by_id, pos) == 0.0


def test_alignment_penalty_equals_offset_for_single_couple():
    by_id = {
        1: _person(1, partners=[2]),
        2: _person(2, partners=[1]),
        3: _person(3, parent_a=1, parent_b=2),
    }
    # couple_center=250, child_center=1500, penalty=1250
    pos = {1: (0, 0), 2: (500, 0), 3: (1500, 500)}
    assert refine._alignment_penalty(by_id, pos) == 1250.0


def test_alignment_penalty_counts_each_couple_once():
    by_id = {
        1: _person(1, partners=[2]),
        2: _person(2, partners=[1]),
        3: _person(3, parent_a=1, parent_b=2),
    }
    pos = {1: (0, 0), 2: (500, 0), 3: (1500, 500)}
    assert refine._alignment_penalty(by_id, pos) == 1250.0


def test_quality_includes_alignment_term():
    by_id = {
        1: _person(1, partners=[2]),
        2: _person(2, partners=[1]),
        3: _person(3, parent_a=1, parent_b=2),
        4: _person(4),
    }
    pos_centered = {1: (0, 0), 2: (500, 0), 3: (250, 500), 4: (5000, 0)}
    pos_offaxis = {1: (0, 0), 2: (500, 0), 3: (750, 500), 4: (5000, 0)}
    q_centered = refine._quality(by_id, pos_centered, label_buffer=20)
    q_offaxis = refine._quality(by_id, pos_offaxis, label_buffer=20)
    assert q_centered < q_offaxis
    assert q_offaxis - q_centered == 500.0 * refine.ALIGNMENT_WEIGHT


def test_quality_recenter_move_accepted_when_bbox_unchanged():
    """The D-27 bug: a recenter move that keeps bbox identical was rejected by
    strict-< on bbox-only quality. With alignment term, accepted."""
    by_id = {
        1: _person(1, partners=[2]),
        2: _person(2, partners=[1]),
        3: _person(3, parent_a=1, parent_b=2),
        4: _person(4),
    }
    pos_before = {1: (0, 0), 2: (500, 0), 3: (750, 500), 4: (5000, 0)}
    pos_after = {1: (0, 0), 2: (500, 0), 3: (250, 500), 4: (5000, 0)}
    assert refine._bbox_width(pos_before) == refine._bbox_width(pos_after)
    q_before = refine._quality(by_id, pos_before, label_buffer=20)
    q_after = refine._quality(by_id, pos_after, label_buffer=20)
    assert q_after < q_before


def test_alignment_penalty_skips_couples_without_shared_children():
    by_id = {
        1: _person(1, partners=[2]),
        2: _person(2, partners=[1]),
        3: _person(3, parent_a=1, parent_b=None),
    }
    pos = {1: (0, 0), 2: (500, 0), 3: (3000, 500)}
    assert refine._alignment_penalty(by_id, pos) == 0.0
