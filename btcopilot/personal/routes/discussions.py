from flask import Blueprint, jsonify, request

from btcopilot.extensions import db
from btcopilot.personal import Response, ask
from btcopilot.personal.models import Discussion, Speaker, SpeakerType


bp = Blueprint("discussions", __name__, url_prefix="/discussions")


@bp.route("/<int:discussion_id>/statements", methods=["POST"])
def chat(discussion_id: int):
    if request.headers.get("Content-Type") != "application/json":
        return ("Only 'Content-Type: application/json' is supported", 415)

    discussion = Discussion.query.get(discussion_id)
    statement = request.json["statement"]
    response: Response = ask(discussion, statement)

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

    return jsonify({"statement": response.statement, "pdp": response.pdp.model_dump()})
