import logging
import pickle

from flask import Blueprint, jsonify, request, abort
from sqlalchemy import update as sql_update
from sqlalchemy.orm import subqueryload

import asyncio
from btcopilot import auth, pdp
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram
from btcopilot.schema import asdict, get_all_pdp_item_ids, is_parents_edit
from btcopilot.personal import Response, ask
from btcopilot.personal.deepreextract import (
    VALID_K,
    DEFAULT_K,
    mark_rebuild_alive,
    request_rebuild_cancel,
)
from btcopilot.personal.models import Discussion, Speaker, SpeakerType

_log = logging.getLogger(__name__)

bp = Blueprint("discussions", __name__, url_prefix="/discussions")


def _create_discussion(data: dict) -> Discussion:
    user = auth.current_user()

    # Ensure user has a free_diagram
    if not user.free_diagram:
        diagram = Diagram(
            user_id=user.id,
            name=f"{user.username} Personal Case File",
            data=pickle.dumps({}),
        )

        db.session.add(diagram)
        db.session.flush()
        user.free_diagram_id = diagram.id

    discussion = Discussion(
        user_id=user.id,
        diagram_id=user.free_diagram_id,
        summary="New Discussion",
        speakers=[
            Speaker(name="Client", type=SpeakerType.Subject, person_id=1),
            Speaker(name="Coach", type=SpeakerType.Expert, person_id=2),
        ],
    )
    db.session.add(discussion)
    db.session.flush()

    # Update discussion with speaker IDs for chat
    discussion.chat_user_speaker_id = discussion.speakers[0].id
    discussion.chat_ai_speaker_id = discussion.speakers[1].id

    db.session.commit()

    return discussion


@bp.route("", methods=["POST"])
@bp.route("/", methods=["POST"])
def create():
    data = request.get_json(silent=True) or {}
    discussion = _create_discussion(data)
    if "statement" in data:
        response: Response = ask(discussion, data["statement"], model=data.get("model"))
    db.session.commit()
    db.session.merge(discussion)

    ret = discussion.as_dict(include=["speakers", "statements"])
    if "statement" in data:
        ret["statement"] = response.statement

    return jsonify(ret)


@bp.route("")
@bp.route("/")
def index():
    discussions = (
        Discussion.query.options(subqueryload(Discussion.statements))
        .filter_by(user_id=auth.current_user().id)
        .all()
    )
    return jsonify([discussion.as_dict() for discussion in discussions])


@bp.route("/<int:discussion_id>", methods=["GET"])
def get(discussion_id: int):
    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        return abort(404)
    elif discussion.user_id != auth.current_user().id:
        return abort(401)
    return jsonify(discussion.as_dict(include=["speakers", "statements"]))


@bp.route("/<int:discussion_id>/statements", methods=["POST"])
def chat(discussion_id: int):
    if request.headers.get("Content-Type") != "application/json":
        return ("Only 'Content-Type: application/json' is supported", 415)

    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        return abort(404)

    # Ensure User and Assistant people exist in the diagram (if diagram exists)
    if discussion.diagram:
        diagram_data = discussion.diagram.get_diagram_data()
        user_person_id, _, changed = diagram_data.ensure_chat_defaults()
        if changed:
            discussion.diagram.set_diagram_data(diagram_data)

        # Update speaker person_ids if primary person differs from default
        user_speaker = Speaker.query.filter_by(
            discussion_id=discussion.id, type=SpeakerType.Subject
        ).first()
        if user_speaker and user_speaker.person_id != user_person_id:
            user_speaker.person_id = user_person_id

    statement = request.json["statement"]
    model = request.json.get("model")
    response: Response = ask(discussion, statement, model=model)

    # Notify audit system of new statements (both user and AI)
    # from btcopilot.training.sse import sse_manager
    # import json

    # Get both statements that were just created
    db.session.flush()  # Ensure statements get IDs
    # Get subject and expert speakers for this discussion
    subject_speaker = Speaker.query.filter_by(
        discussion_id=discussion.id, type=SpeakerType.Subject
    ).first()
    expert_speaker = Speaker.query.filter_by(
        discussion_id=discussion.id, type=SpeakerType.Expert
    ).first()

    # subject_statement = None
    # expert_statement = None

    # if subject_speaker:
    #     subject_statement = (
    #         Statement.query.filter_by(
    #             discussion_id=discussion.id, speaker_id=subject_speaker.id
    #         )
    #         .order_by(Statement.id.desc())
    #         .first()
    #     )

    # if expert_speaker:
    #     expert_statement = (
    #         Statement.query.filter_by(
    #             discussion_id=discussion.id, speaker_id=expert_speaker.id
    #         )
    #         .order_by(Statement.id.desc())
    #         .first()
    #     )

    # # Prepare extracted data for expert statement
    # extracted_data = None
    # if expert_statement and expert_statement.pdp_deltas:
    #     extracted_data = {
    #         "people": expert_statement.pdp_deltas.get("people", []),
    #         "events": expert_statement.pdp_deltas.get("events", []),
    #         "deletes": expert_statement.pdp_deltas.get("delete", []),
    #     }

    # # Send both statements in one notification
    # sse_manager.publish(
    #     json.dumps(
    #         {
    #             "type": "new_statement_pair",
    #             "discussion_id": discussion.id,
    #             "subject_statement": {
    #                 "id": subject_statement.id if subject_statement else None,
    #                 "text": (
    #                     subject_statement.text if subject_statement else statement
    #                 ),
    #                 "origin": "subject",
    #                 "created_at": (
    #                     subject_statement.created_at.isoformat()
    #                     if subject_statement and subject_statement.created_at
    #                     else None
    #                 ),
    #             },
    #             "expert_statement": {
    #                 "id": expert_statement.id if expert_statement else None,
    #                 "text": response.statement,
    #                 "origin": "expert",
    #                 "created_at": (
    #                     expert_statement.created_at.isoformat()
    #                     if expert_statement and expert_statement.created_at
    #                     else None
    #                 ),
    #                 "extracted_data": extracted_data,
    #             },
    #         }
    #     )
    # )

    db.session.commit()

    return jsonify({"statement": response.statement})


@bp.route("/<int:discussion_id>/extract", methods=["POST"])
def extract(discussion_id: int):
    user = auth.current_user()

    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        abort(404)
    if discussion.user_id != user.id:
        abort(401)
    if not discussion.diagram:
        abort(400, description="Discussion has no diagram attached")

    # Atomically claim the extraction. Overlapping extracts each run the
    # expensive LLM pass and then race the single staged PDP and pending
    # cursor; this conditional UPDATE admits exactly one at a time. Committed
    # immediately so the flag is visible to the other request and no row lock
    # is held across the multi-second LLM call.
    claimed = db.session.execute(
        sql_update(Discussion)
        .where(Discussion.id == discussion_id, Discussion.extracting.is_(False))
        .values(extracting=True)
    ).rowcount
    db.session.commit()
    if not claimed:
        abort(409, description="An extraction is already in progress")

    try:
        diagram_data = discussion.diagram.get_diagram_data()
        expected_version = discussion.diagram.version
        # Bind the pending cursor to THIS extraction's input window, captured
        # before the LLM call, so a concurrent chat turn cannot retroactively
        # widen what this extraction is credited with having covered.
        orders = [s.order for s in discussion.statements if s.order is not None]
        pending_through = max(orders) if orders else None

        new_pdp, _ = asyncio.run(pdp.extract_full(discussion, diagram_data))
        diagram_data.pdp = new_pdp

        ok, _ = discussion.diagram.update_with_version_check(
            expected_version, diagram_data=diagram_data
        )
        if not ok:
            db.session.rollback()
            abort(409, description="Diagram changed during extraction; re-extract")
        discussion.pending_extracted_through_order = pending_through
        db.session.commit()
    finally:
        db.session.rollback()
        db.session.execute(
            sql_update(Discussion)
            .where(Discussion.id == discussion_id)
            .values(extracting=False)
        )
        db.session.commit()

    return jsonify(
        success=True,
        people_count=len(new_pdp.people),
        events_count=len(new_pdp.events),
        pair_bonds_count=len(new_pdp.pair_bonds),
        pending_extracted_through_order=pending_through,
        pdp=asdict(new_pdp),
    )


@bp.route("/<int:discussion_id>/commit-pdp", methods=["POST"])
def commit_pdp(discussion_id: int):
    """Accept staged PDP items into the committed diagram. On a FULL accept
    the re-extraction cursor advances to the extraction the client is
    accepting (accepted_through_order) so the next extract treats that
    conversation as captured, and staged parents-edit rows (positive ids) are
    applied server-side to the committed people. The diagram write is guarded
    by an optimistic version check with bounded retry, so a concurrent extract
    or commit cannot silently overwrite committed items. All in one
    transaction."""
    user = auth.current_user()

    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        abort(404)
    if discussion.user_id != user.id:
        abort(401)
    if not discussion.diagram:
        abort(400, description="Discussion has no diagram attached")

    body = request.get_json(silent=True) or {}
    item_ids = body.get("item_ids")
    # Empty item_ids is valid when full_accept is asserted: re-extracting an
    # already-covered conversation yields an empty PDP; "Accept all" on it is
    # still a full accept and must advance the re-extraction cursor.
    if not isinstance(item_ids, list) or (
        not item_ids and body.get("full_accept") is not True
    ):
        abort(400, description="item_ids list required (empty only if full_accept)")

    # The Personal client commits items locally then saves the diagram, so by
    # the time this runs the server-side staged pool may already be drained —
    # the server can't re-derive full-vs-partial. The client passes whether the
    # staged pool is now fully drained; trust it for the cursor advance. When
    # called standalone (no flag) fall back to the server-side comparison.
    client_full = body.get("full_accept")
    accepted_through = body.get("accepted_through_order")

    diagram = discussion.diagram
    committed = 0
    full_accept = False
    for _ in range(32):
        db.session.refresh(diagram)
        expected_version = diagram.version
        diagram_data = diagram.get_diagram_data()
        # The acceptance contract covers only NEW (negative-id) items.
        # Positive ids in the staged pool are committed-entity edit rows;
        # clients that echo them back are acknowledged as no-ops —
        # commit_pdp_items raises on them by design.
        staged_new = {i for i in get_all_pdp_item_ids(diagram_data.pdp) if i < 0}
        present = [i for i in item_ids if i in staged_new]
        if isinstance(client_full, bool):
            full_accept = client_full
        else:
            full_accept = bool(staged_new) and set(item_ids) >= staged_new

        parent_edits = full_accept and any(
            is_parents_edit(p) for p in diagram_data.pdp.people
        )
        if not present and not parent_edits:
            committed = 0
            break
        if present:
            # Must run before apply_parent_edits: its trailing remap rewrites
            # negative bond refs on staged parents rows to committed ids.
            diagram_data.commit_pdp_items(present)
        if parent_edits:
            diagram_data.apply_parent_edits()
        ok, _ = diagram.update_with_version_check(
            expected_version, diagram_data=diagram_data
        )
        if not ok:
            # Another writer bumped the version between our read and write.
            # Re-read the now-current committed state and retry —
            # commit_pdp_items is idempotent on item ids, so re-applying
            # against fresh data never double-commits.
            db.session.rollback()
            continue
        committed = len(present)
        break
    else:
        abort(409, description="Diagram write contention; retry commit-pdp")

    # Bind the cursor advance to the exact extraction the client accepted, NOT
    # to whatever pending currently holds. A concurrent extract may have
    # advanced pending past conversation this accept never covered; advancing
    # to that value would skip that conversation from every future extract.
    # Fall back to pending only when the client did not specify the value
    # (older client / standalone call).
    if full_accept:
        target = (
            accepted_through
            if isinstance(accepted_through, int)
            else discussion.pending_extracted_through_order
        )
        if target is not None and (
            discussion.extracted_through_order is None
            or target > discussion.extracted_through_order
        ):
            discussion.extracted_through_order = target
        if discussion.pending_extracted_through_order == target:
            discussion.pending_extracted_through_order = None

    db.session.commit()

    return jsonify(
        success=True,
        committed=committed,
        full_accept=full_accept,
        extracted_through_order=discussion.extracted_through_order,
    )


@bp.route("/<int:discussion_id>/deep-reextract", methods=["POST"])
def deep_reextract(discussion_id: int):
    from btcopilot.extensions import celery

    user = auth.current_user()
    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        abort(404)
    if discussion.user_id != user.id:
        abort(401)
    if not discussion.diagram:
        abort(400, description="Discussion has no diagram attached")
    if celery is None:
        abort(503, description="Celery not available")

    body = request.get_json(silent=True) or {}
    k = int(body.get("k", DEFAULT_K))
    if k not in VALID_K:
        abort(400, description=f"k must be one of {sorted(VALID_K)}")

    claimed = db.session.execute(
        sql_update(Discussion)
        .where(Discussion.id == discussion_id, Discussion.extracting.is_(False))
        .values(extracting=True)
    ).rowcount
    db.session.commit()
    if not claimed:
        abort(409, description="An extraction is already in progress")

    task = celery.send_task("deep_reextract", args=[discussion_id, k])
    _log.info(
        f"User {user.username} started deep_reextract task {task.id} "
        f"for discussion {discussion_id} k={k}"
    )
    return jsonify({"task_id": task.id})


@bp.route("/<int:discussion_id>/deep-reextract-status/<task_id>", methods=["GET"])
def deep_reextract_status(discussion_id: int, task_id: str):
    from btcopilot.extensions import celery
    from celery.result import AsyncResult

    user = auth.current_user()
    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        abort(404)
    if discussion.user_id != user.id:
        abort(401)
    if celery is None:
        return jsonify({"status": "error", "error": "Celery not available"}), 503

    # This poll is the client's liveness heartbeat: refresh the key the worker
    # watches so it knows someone is still waiting. If polling stops (cancel or
    # app quit), the key expires and the task aborts itself.
    mark_rebuild_alive(task_id)

    result = AsyncResult(task_id, app=celery)

    if result.failed():
        return jsonify({"status": "error", "error": str(result.result)})
    if result.ready():
        task_result = result.get()
        if task_result.get("cancelled"):
            return jsonify({"status": "error", "error": "Rebuild cancelled"})
        return jsonify({"status": "complete", **task_result})
    if result.state == "PROGRESS":
        meta = result.info or {}
        return jsonify(
            {
                "status": "progress",
                "current": meta.get("current", 0),
                "total": meta.get("total", 0),
                "label": meta.get("label", ""),
            }
        )
    return jsonify({"status": "pending"})


@bp.route("/<int:discussion_id>/deep-reextract/<task_id>/cancel", methods=["POST"])
def deep_reextract_cancel(discussion_id: int, task_id: str):
    """Cancel a running rebuild: flag it so the worker aborts on its next window,
    and release the lock immediately so the user can re-trigger right away."""
    user = auth.current_user()
    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        abort(404)
    if discussion.user_id != user.id:
        abort(401)

    request_rebuild_cancel(task_id)
    db.session.execute(
        sql_update(Discussion)
        .where(Discussion.id == discussion_id)
        .values(extracting=False)
    )
    db.session.commit()
    return jsonify({"success": True})


# @bp.route("/<int:discussion_id>/statements", methods=["GET"])
# def statements(discussion_id: int):
#     discussion = Discussion.query.get(discussion_id)
#     if discussion.user_id != auth.current_user().id:
#         return abort(401)
#     _log.debug(f"Discussion: {discussion} with {len(discussion.statements)} statements")
#     return jsonify([stmt.as_dict() for stmt in discussion.statements])
