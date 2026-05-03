"""
Tests for the Pro app's id-block reservation endpoint and Diagram.reserve_id_block.

Plan: familydiagram/doc/plans/2026-05-01--mvp-merge-fix/README.md
"""

import pickle

import pytest

import PyQt5.sip  # required for unpickling QtCore types in diagram blobs

from btcopilot.extensions import db
from btcopilot.pro.models import Diagram


def test_reserve_id_block_basic(flask_app, test_user):
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"lastItemId": 10})
    db.session.commit()
    starting_version = diagram.version

    start, end, new_version = diagram.reserve_id_block(100)

    assert start == 11
    assert end == 110
    assert new_version == starting_version + 1
    pickled = pickle.loads(diagram.data)
    assert pickled["lastItemId"] == 110


def test_reserve_id_block_two_consecutive_returns_distinct_ranges(flask_app, test_user):
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"lastItemId": 10})
    db.session.commit()

    start1, end1, _ = diagram.reserve_id_block(50)
    start2, end2, _ = diagram.reserve_id_block(50)

    assert start1 == 11
    assert end1 == 60
    assert start2 == 61
    assert end2 == 110


def test_reserve_id_block_persists_across_reads(flask_app, test_user):
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"lastItemId": 0})
    db.session.commit()

    diagram.reserve_id_block(25)
    db.session.commit()

    refreshed = Diagram.query.get(diagram.id)
    assert pickle.loads(refreshed.data)["lastItemId"] == 25


def test_reserve_id_block_zero_count_rejected(flask_app, test_user):
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"lastItemId": 5})
    db.session.commit()

    with pytest.raises(ValueError):
        diagram.reserve_id_block(0)


def test_reserve_id_block_empty_data_starts_from_zero(flask_app, test_user):
    diagram = test_user.free_diagram
    diagram.data = None
    db.session.commit()

    start, end, _ = diagram.reserve_id_block(10)

    assert start == 1
    assert end == 10


def test_reserve_ids_endpoint_anonymous_rejected(flask_app):
    with flask_app.test_client() as client:
        response = client.post(
            "/v1/diagrams/1/reserve_ids",
            data=pickle.dumps({"count": 100}),
        )
    assert response.status_code == 401


def test_reserve_ids_endpoint_unknown_diagram_404(flask_app, test_user):
    with flask_app.test_client(user=test_user) as client:
        response = client.post(
            "/v1/diagrams/9999999/reserve_ids",
            data=pickle.dumps({"count": 100}),
        )
    assert response.status_code == 404


def test_reserve_ids_endpoint_basic(flask_app, test_user):
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"lastItemId": 50})
    db.session.commit()
    starting_version = diagram.version

    with flask_app.test_client(user=test_user) as client:
        response = client.post(
            f"/v1/diagrams/{diagram.id}/reserve_ids",
            data=pickle.dumps({"count": 100}),
        )

    assert response.status_code == 200
    body = pickle.loads(response.data)
    assert body["start"] == 51
    assert body["end"] == 150
    assert body["version"] == starting_version + 1


def test_reserve_ids_endpoint_two_clients_distinct_blocks(flask_app, test_user):
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"lastItemId": 0})
    db.session.commit()

    with flask_app.test_client(user=test_user) as client:
        r1 = client.post(
            f"/v1/diagrams/{diagram.id}/reserve_ids",
            data=pickle.dumps({"count": 100}),
        )
        r2 = client.post(
            f"/v1/diagrams/{diagram.id}/reserve_ids",
            data=pickle.dumps({"count": 100}),
        )

    body1 = pickle.loads(r1.data)
    body2 = pickle.loads(r2.data)
    assert body1["start"] == 1 and body1["end"] == 100
    assert body2["start"] == 101 and body2["end"] == 200
    assert body2["version"] > body1["version"]


def test_reserve_id_block_serial_calls_distinct_blocks(flask_app, test_user):
    """
    Serial concurrency check: many sequential calls within one session. No
    overlap. This is the strongest concurrency test that's reliable under
    SQLite :memory: (which doesn't honor SELECT FOR UPDATE and gives each
    thread its own private DB, breaking true thread-based concurrency
    testing).

    Under PostgreSQL in production, `with_for_update()` acquires the row
    lock, plus the `WHERE version=N` optimistic check is the backstop. See
    `Diagram.reserve_id_block` docstring. A future test under
    file-based SQLite or a dedicated PostgreSQL test fixture would
    exercise true thread-based concurrency.
    """
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"lastItemId": 0})
    db.session.commit()
    diagram_id = diagram.id

    N = 16
    BLOCK = 50
    blocks = []

    with flask_app.test_client(user=test_user) as client:
        for _ in range(N):
            r = client.post(
                f"/v1/diagrams/{diagram_id}/reserve_ids",
                data=pickle.dumps({"count": BLOCK}),
            )
            assert r.status_code == 200
            body = pickle.loads(r.data)
            blocks.append((body["start"], body["end"]))

    # Distinct, contiguous, non-overlapping.
    for i, (start, end) in enumerate(blocks):
        if i > 0:
            prev_end = blocks[i - 1][1]
            assert start == prev_end + 1, (
                f"Block {i} starts at {start} but previous ended at "
                f"{prev_end} — overlap or gap"
            )
        assert end - start + 1 == BLOCK

    # Final lastItemId on disk matches the cumulative reservation.
    refreshed = Diagram.query.get(diagram_id)
    assert pickle.loads(refreshed.data)["lastItemId"] == N * BLOCK


def test_reserve_id_block_optimistic_locking_retries_on_conflict(
    flask_app, test_user
):
    """
    Simulate concurrent contention by manually bumping `version` between
    a refresh and the UPDATE inside `reserve_id_block`. Verifies the
    retry loop catches stale-version writes and produces a valid block
    after a conflict.
    """
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"lastItemId": 0})
    db.session.commit()
    diagram_id = diagram.id

    # Bump version externally to simulate another writer winning.
    diagram.version = diagram.version + 1
    db.session.commit()

    # The next reserve_id_block must NOT crash — its retry loop reads
    # the new version and proceeds.
    start, end, new_version = diagram.reserve_id_block(50)

    assert start == 1
    assert end == 50
    assert new_version > 1


def test_reserve_id_block_retry_branch_actually_executes(
    flask_app, test_user, monkeypatch
):
    """
    Force the retry branch to execute by monkeypatching `db.session.execute`
    so the FIRST call returns rowcount=0 (simulating a concurrent writer
    winning the race). Verifies the retry loop's recover-and-succeed path.
    Without this test, a regression that broke the retry branch would not be
    caught by the other tests (which only exercise the no-conflict path).
    """
    from sqlalchemy.engine import CursorResult

    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"lastItemId": 0})
    db.session.commit()

    real_execute = db.session.execute
    call_count = {"n": 0}

    class _ZeroRowResult:
        rowcount = 0

    def fake_execute(stmt, *args, **kwargs):
        # Only intercept the UPDATE inside reserve_id_block (rowcount-aware).
        # The first UPDATE returns rowcount=0; the second goes through.
        sql = str(stmt).lower()
        if "update diagrams" in sql and call_count["n"] == 0:
            call_count["n"] += 1
            return _ZeroRowResult()
        return real_execute(stmt, *args, **kwargs)

    monkeypatch.setattr(db.session, "execute", fake_execute)

    start, end, _ = diagram.reserve_id_block(50)

    # Retry branch ran exactly once (the first UPDATE was 0-row, second was real).
    assert call_count["n"] == 1, (
        f"Expected the retry branch to fire once, got {call_count['n']}"
    )
    assert start == 1
    assert end == 50


def test_put_diagram_response_includes_canonical_data(flask_app, test_user):
    """
    Latent fix 3a: PUT /v1/diagrams/{id} 200 response must include the
    canonical post-write blob so the client can refresh its snapshot.
    """
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"people": [], "lastItemId": 0})
    db.session.commit()

    new_blob = pickle.dumps({"people": [{"id": 1, "name": "test"}], "lastItemId": 1})

    with flask_app.test_client(user=test_user) as client:
        response = client.put(
            f"/v1/diagrams/{diagram.id}",
            data=pickle.dumps(
                {
                    "data": new_blob,
                    "updated_at": diagram.updated_at,
                    "expected_version": diagram.version,
                }
            ),
        )

    assert response.status_code == 200
    body = pickle.loads(response.data)
    assert "data" in body, "200 response must include canonical data field (fix 3a)"
    assert "version" in body
    canonical = pickle.loads(body["data"])
    assert canonical["people"][0]["name"] == "test"
