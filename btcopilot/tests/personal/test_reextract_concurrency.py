"""FD-331: re-extraction / accept concurrency safety.

These exercise the interleavings deterministically (no threads): the
SQLite test DB ignores SELECT FOR UPDATE, so the row-lock fix for
next_order() is only enforced on PostgreSQL in production and is covered
here by the contiguous-allocation regression guard plus a documented
limitation. The version-check and cursor-binding fixes ARE fully
exercisable on SQLite and are tested here by injecting a concurrent
writer mid-extract / between commit-pdp's read and write.
"""

from unittest.mock import patch, AsyncMock

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Statement
from btcopilot.schema import PDP, PDPDeltas, Person


def _pdp(*ids):
    people = [
        Person(id=i, name=f"P{abs(i)}", gender="male", confidence=0.8) for i in ids
    ]
    return PDP(people=people), PDPDeltas(people=people)


def _extract(subscriber, discussion, ret=None, side_effect=None):
    ret = ret or _pdp(-1, -2)
    mock = AsyncMock(return_value=ret)
    if side_effect is not None:
        mock.side_effect = side_effect
    with patch("btcopilot.pdp.extract_full", mock):
        return subscriber.post(f"/personal/discussions/{discussion.id}/extract")


# --- Defect 1: /extract overlap guard + version-checked write ---


def test_overlapping_extract_rejected_409(subscriber, discussion):
    discussion.extracting = True
    db.session.commit()
    r = _extract(subscriber, discussion)
    assert r.status_code == 409


def test_extract_clears_extracting_flag_on_success(subscriber, discussion):
    r = _extract(subscriber, discussion)
    assert r.status_code == 200
    db.session.refresh(discussion)
    assert discussion.extracting is False
    # A second extract is now admitted.
    assert _extract(subscriber, discussion).status_code == 200


def test_extract_clears_extracting_flag_on_conflict(subscriber, discussion):
    """A commit-pdp landing during the LLM call bumps the diagram version;
    the staged result is stale -> 409, items from the concurrent writer
    preserved, pending NOT advanced, and the flag is released."""

    def concurrent_commit(*a, **k):
        d = Discussion.query.get(discussion.id)
        dd = d.diagram.get_diagram_data()
        dd.pdp, _ = _pdp(-9)
        d.diagram.update_with_version_check(d.diagram.version, diagram_data=dd)
        db.session.commit()
        return _pdp(-1, -2)

    r = _extract(subscriber, discussion, side_effect=concurrent_commit)
    assert r.status_code == 409
    db.session.refresh(discussion)
    assert discussion.extracting is False
    assert discussion.pending_extracted_through_order is None
    staged = {p.id for p in discussion.diagram.get_diagram_data().pdp.people}
    assert staged == {-9}  # concurrent writer's item not clobbered


# --- Defect 2: commit-pdp cursor bound to the accepted extraction ---


def test_cursor_advances_to_accepted_not_current_pending(subscriber, discussion):
    """extract#1 (pending=1) -> new chat (order 2) -> extract#2 (pending=2).
    Client accepts extraction #1 (accepted_through_order=1). Cursor must
    advance to 1, NOT 2 — order-2 conversation was never in extraction #1
    and must remain windowed for the next extract."""
    _extract(subscriber, discussion)  # pending -> 1
    db.session.refresh(discussion)
    assert discussion.pending_extracted_through_order == 1

    spk = discussion.statements[0].speaker_id
    db.session.add(
        Statement(
            discussion_id=discussion.id,
            speaker_id=spk,
            text="Later: about my brother",
            order=2,
        )
    )
    db.session.commit()
    _extract(subscriber, discussion)  # pending -> 2 (concurrent re-extract)
    db.session.refresh(discussion)
    assert discussion.pending_extracted_through_order == 2

    r = subscriber.post(
        f"/personal/discussions/{discussion.id}/commit-pdp",
        json={"item_ids": [-1, -2], "full_accept": True, "accepted_through_order": 1},
    )
    assert r.status_code == 200
    db.session.refresh(discussion)
    assert discussion.extracted_through_order == 1  # bound to accepted, not 2
    assert discussion.pending_extracted_through_order == 2  # newer kept


def test_cursor_falls_back_to_pending_without_accepted(subscriber, discussion):
    """Legacy / standalone client (no accepted_through_order) keeps the old
    behaviour: full accept advances to current pending."""
    _extract(subscriber, discussion)
    r = subscriber.post(
        f"/personal/discussions/{discussion.id}/commit-pdp",
        json={"item_ids": [-1, -2], "full_accept": True},
    )
    assert r.status_code == 200
    db.session.refresh(discussion)
    assert discussion.extracted_through_order == 1
    assert discussion.pending_extracted_through_order is None


def test_commit_pdp_survives_concurrent_version_bump(subscriber, discussion):
    """A writer bumps the diagram version between commit-pdp's read and
    write; the bounded retry re-reads and still commits without error."""
    _extract(subscriber, discussion)

    real = Discussion.query.get(discussion.id).diagram.update_with_version_check
    state = {"bumped": False}

    def bump_once(self, expected_version, **kw):
        if not state["bumped"]:
            state["bumped"] = True
            d = Discussion.query.get(discussion.id).diagram
            dd = d.get_diagram_data()
            real_self_update = type(d).update_with_version_check
            real_self_update(d, d.version, diagram_data=dd)  # version++
            db.session.commit()
        return real(expected_version, **kw)

    with patch.object(type(discussion.diagram), "update_with_version_check", bump_once):
        r = subscriber.post(
            f"/personal/discussions/{discussion.id}/commit-pdp",
            json={
                "item_ids": [-1, -2],
                "full_accept": True,
                "accepted_through_order": 1,
            },
        )
    assert r.status_code == 200
    db.session.refresh(discussion)
    committed = {p.id for p in discussion.diagram.get_diagram_data().pdp.people}
    # staged negative ids were committed (remapped to positive) — none left
    assert all(i > 0 for i in committed) or committed == set()
    assert discussion.extracted_through_order == 1


# --- Defect 3: Statement.order allocation (regression guard) ---


def test_sequential_chat_orders_are_distinct_and_contiguous(discussion):
    """Row-lock concurrency is PostgreSQL-only (SQLite ignores FOR UPDATE);
    this guards the non-concurrent invariant the lock must preserve."""
    base = max(s.order for s in discussion.statements)
    a = discussion.next_order()
    db.session.add(
        Statement(
            discussion_id=discussion.id,
            speaker_id=discussion.statements[0].speaker_id,
            text="a",
            order=a,
        )
    )
    db.session.flush()
    b = discussion.next_order()
    assert a == base + 1
    assert b == base + 2
    assert a != b
