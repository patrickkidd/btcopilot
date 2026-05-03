"""
Tests for DiagramData.apply_local_changes — snapshot-diff merge.

Plan: familydiagram/doc/plans/2026-05-01--mvp-merge-fix/README.md
"""

from PyQt5.QtCore import QPointF, QDateTime, QDate

from btcopilot.schema import DiagramData


def test_clean_item_takes_server_state():
    """User didn't touch the item → server's concurrent edit survives."""
    snapshot = [{"id": 1, "name": "A", "cutoff": False}]
    local = [{"id": 1, "name": "A", "cutoff": False}]  # same as snapshot
    server = [{"id": 1, "name": "A", "cutoff": True}]  # other client edited

    result = DiagramData.apply_local_changes(server, snapshot, local)

    assert result == [{"id": 1, "name": "A", "cutoff": True}]


def test_dirty_item_takes_local_state():
    """User edited the item → local wins (item-level last-write-wins)."""
    snapshot = [{"id": 1, "name": "A", "cutoff": False}]
    local = [{"id": 1, "name": "A_new", "cutoff": False}]  # user changed name
    server = [{"id": 1, "name": "A", "cutoff": False}]  # server unchanged

    result = DiagramData.apply_local_changes(server, snapshot, local)

    assert result == [{"id": 1, "name": "A_new", "cutoff": False}]


def test_same_item_both_sides_edited_local_wins():
    """Both sides edited the same item different fields → local item wins whole."""
    snapshot = [{"id": 1, "name": "A", "cutoff": False}]
    local = [{"id": 1, "name": "A_local", "cutoff": False}]
    server = [{"id": 1, "name": "A", "cutoff": True}]

    result = DiagramData.apply_local_changes(server, snapshot, local)

    # Local wins entire item; server's cutoff edit lost (documented MVP behavior).
    assert result == [{"id": 1, "name": "A_local", "cutoff": False}]


def test_local_deletion_survives_server_unchanged():
    """User deleted the item locally → it stays deleted, even if server still has it."""
    snapshot = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
    local = [{"id": 2, "name": "B"}]  # deleted 1
    server = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]

    result = DiagramData.apply_local_changes(server, snapshot, local)

    assert result == [{"id": 2, "name": "B"}]


def test_local_addition_preserved():
    """User added a new item → it appears in result."""
    snapshot = [{"id": 1, "name": "A"}]
    local = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
    server = [{"id": 1, "name": "A"}]

    result = DiagramData.apply_local_changes(server, snapshot, local)

    by_id = {item["id"]: item for item in result}
    assert by_id == {1: {"id": 1, "name": "A"}, 2: {"id": 2, "name": "B"}}


def test_server_addition_preserved():
    """Other client added an item → it appears in result alongside local additions."""
    snapshot = [{"id": 1, "name": "A"}]
    local = [{"id": 1, "name": "A"}, {"id": 2, "name": "Local2"}]
    server = [{"id": 1, "name": "A"}, {"id": 3, "name": "Server3"}]

    result = DiagramData.apply_local_changes(server, snapshot, local)

    by_id = {item["id"]: item for item in result}
    assert by_id == {
        1: {"id": 1, "name": "A"},
        2: {"id": 2, "name": "Local2"},
        3: {"id": 3, "name": "Server3"},
    }


def test_simultaneous_delete_both_sides():
    """Both sides deleted the same item → it stays deleted (idempotent)."""
    snapshot = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
    local = [{"id": 2, "name": "B"}]  # deleted 1 locally
    server = [{"id": 2, "name": "B"}]  # other side also deleted 1

    result = DiagramData.apply_local_changes(server, snapshot, local)

    assert result == [{"id": 2, "name": "B"}]


def test_empty_snapshot_treats_all_as_added():
    snapshot = []
    local = [{"id": 1, "name": "A"}]
    server = []

    result = DiagramData.apply_local_changes(server, snapshot, local)

    assert result == [{"id": 1, "name": "A"}]


def test_qpointf_field_unchanged_not_marked_dirty():
    """QtCore types in dicts compare correctly via pickle bytes (regression guard)."""
    pos = QPointF(10.5, 20.5)
    snapshot = [{"id": 1, "name": "A", "itemPos": pos}]
    # Same logical position, different QPointF instance — should not be dirty.
    local = [{"id": 1, "name": "A", "itemPos": QPointF(10.5, 20.5)}]
    server = [{"id": 1, "name": "A", "itemPos": pos, "cutoff": True}]

    result = DiagramData.apply_local_changes(server, snapshot, local)

    # Server's cutoff edit must survive — local is NOT dirty.
    assert result == [{"id": 1, "name": "A", "itemPos": pos, "cutoff": True}]


def test_qdatetime_field_unchanged_not_marked_dirty():
    dt = QDateTime(QDate(2026, 5, 1))
    snapshot = [{"id": 1, "dateTime": dt}]
    local = [{"id": 1, "dateTime": QDateTime(QDate(2026, 5, 1))}]
    server = [{"id": 1, "dateTime": dt, "description": "added by other"}]

    result = DiagramData.apply_local_changes(server, snapshot, local)

    assert result == [{"id": 1, "dateTime": dt, "description": "added by other"}]


def test_id_collision_between_local_add_and_server_add_local_wins():
    """If both sides somehow allocated the same id (shouldn't happen with block
    allocation, but verify behavior is item-level LWW = local wins)."""
    snapshot = []
    local = [{"id": 5, "name": "Local5"}]
    server = [{"id": 5, "name": "Server5"}]

    result = DiagramData.apply_local_changes(server, snapshot, local)

    # Local addition takes precedence (added_ids loop runs after server loop).
    assert result == [{"id": 5, "name": "Local5"}]


def test_items_without_ids_skipped():
    """Items missing an id are silently skipped (defensive)."""
    snapshot = [{"id": 1, "name": "A"}]
    local = [{"id": 1, "name": "A"}, {"name": "no-id"}]
    server = [{"id": 1, "name": "A"}]

    result = DiagramData.apply_local_changes(server, snapshot, local)

    assert result == [{"id": 1, "name": "A"}]


def test_local_edit_beats_server_delete():
    """Item-level last-write-wins: if user edited an item locally and another
    client deleted it server-side, the user's edit wins (item resurrects with
    the user's edit). Per docstring: "Take local (the user's edit wins;
    item-level last-write-wins)."
    """
    snapshot = [{"id": 1, "name": "A", "cutoff": False}]
    local = [{"id": 1, "name": "A_local_edit", "cutoff": False}]
    server = []  # other client deleted

    result = DiagramData.apply_local_changes(server, snapshot, local)

    assert result == [{"id": 1, "name": "A_local_edit", "cutoff": False}]


def test_local_add_with_server_unchanged_no_other_items():
    """Edge case: local has new id, server is empty (or has unrelated items).
    The local add must appear in result even when server has nothing.
    """
    snapshot = []
    local = [{"id": 5, "name": "Local5"}]
    server = []

    result = DiagramData.apply_local_changes(server, snapshot, local)

    assert result == [{"id": 5, "name": "Local5"}]


def test_regression_snapshot_must_reflect_local_view_not_canonical():
    """
    Regression for the bug discovered by e2e harness 2026-05-02:

    Prior bug: client's snapshot was set from `_diagram.data` (canonical),
    which after a merge contained items the local Scene never loaded
    (other-client adds). On the next save, those items were "in snapshot,
    not in local" and silently dropped.

    Fix: client captures snapshot from its local Scene view, NOT from
    the post-merge canonical bytes.

    This test reproduces the scenario at the merge layer: snapshot=local
    (Pro never loaded the other-client item into its Scene), server has
    the other-client item. The merge MUST preserve the server's item.
    """
    # Pro's snapshot and local Scene both have only [Person 2, Person 4]
    # (Pro's Scene was never refreshed with other-client adds).
    snapshot = [{"id": 2, "name": "Pro2"}, {"id": 4, "name": "Pro4"}]
    local = [{"id": 2, "name": "Pro2"}, {"id": 4, "name": "Pro4"}]
    # Server has Pro's items + Person 99 added by another client.
    server = [
        {"id": 2, "name": "Pro2"},
        {"id": 4, "name": "Pro4"},
        {"id": 99, "name": "OtherClient99"},
    ]

    result = DiagramData.apply_local_changes(server, snapshot, local)

    by_id = {item["id"]: item for item in result}
    assert 99 in by_id, (
        "Other-client's Person 99 must survive Pro's save. The pre-fix "
        "bug would have set snapshot to include 99 (from canonical) "
        "while local lacked 99, causing apply_local_changes to drop it "
        "as a 'delete'. Verifies that snapshot=local (Pro's Scene view) "
        "preserves 99."
    )
    assert by_id[99]["name"] == "OtherClient99"


def test_regression_subsequent_save_preserves_other_client_items_after_delete():
    """
    Regression for the bug's second-half scenario:

    After Pro's first save brought Person 99 into the merged result,
    the next save's snapshot must NOT include 99 (because Pro's Scene
    doesn't have it). Otherwise a subsequent server-side delete
    operation would cause apply_local_changes to drop 99 as well
    (snapshot has 99, local doesn't → DELETE → drop from result).

    Setup: Pro's local has [2, 4]. Snapshot has [2, 4] (Scene's view,
    no 99). Server now has [2, 99] (Person 4 deleted by other client).
    Expected: result preserves Pro's lack-of-edits, takes server's
    state for both 2 and 99 (4 not in server, not in dirty/added,
    naturally dropped).
    """
    snapshot = [{"id": 2, "name": "P"}, {"id": 4, "name": "Q"}]
    local = [{"id": 2, "name": "P"}, {"id": 4, "name": "Q"}]
    # Server: another client deleted Person 4 AND added Person 99.
    server = [{"id": 2, "name": "P"}, {"id": 99, "name": "OtherClient"}]

    result = DiagramData.apply_local_changes(server, snapshot, local)
    by_id = {item["id"]: item for item in result}

    # Person 4 should not be in result (server doesn't have it; not added by Pro).
    assert 4 not in by_id, "Other client's delete of Person 4 must survive"
    # Person 99 should be in result (server has it; Pro didn't touch).
    assert 99 in by_id, "Other client's add of Person 99 must survive"
    # Person 2 should be in result (both have it, Pro didn't change).
    assert 2 in by_id
