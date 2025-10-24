import logging
import pickle

from flask import Blueprint, jsonify, request, abort
from sqlalchemy.orm import subqueryload

from btcopilot import auth
from btcopilot.extensions import db
from btcopilot.schema import DiagramData, Person
from btcopilot.pro.models import Diagram
from btcopilot.personal import Response, ask
from btcopilot.personal.models import Discussion, Speaker, SpeakerType

_log = logging.getLogger(__name__)

bp = Blueprint("discussions", __name__, url_prefix="/discussions")


def _create_initial_database() -> DiagramData:
    """Create initial database with User and Assistant people."""
    initial_database = DiagramData()

    # Add User person (ID will be 1)
    user_person = Person(
        name="User", spouses=[], offspring=[], parents=[], confidence=1.0
    )
    initial_database.add_person(user_person)

    # Add Assistant person (ID will be 2)
    assistant_person = Person(
        name="Assistant", spouses=[], offspring=[], parents=[], confidence=1.0
    )
    initial_database.add_person(assistant_person)

    return initial_database


def _create_discussion(data: dict) -> Discussion:
    user = auth.current_user()

    # Ensure user has a free_diagram
    if not user.free_diagram:
        # Create initial database with User and Assistant people
        initial_database = _create_initial_database()

        diagram = Diagram(
            user_id=user.id,
            name=f"{user.username} Personal Case File",
            data=pickle.dumps({"database": initial_database.model_dump()}),
        )

        db.session.add(diagram)
        db.session.flush()
        user.free_diagram_id = diagram.id

    discussion = Discussion(
        user_id=user.id,
        diagram_id=user.free_diagram_id,
        summary="New Discussion",
        speakers=[
            Speaker(name="User", type=SpeakerType.Subject, person_id=1),
            Speaker(name="Assistant", type=SpeakerType.Expert, person_id=2),
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
        response: Response = ask(discussion, data["statement"])
    db.session.commit()
    db.session.merge(discussion)

    ret = discussion.as_dict(include=["speakers", "statements"])
    if "statement" in data:
        ret["pdp"] = response.pdp.model_dump()
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


# @bp.route("/<int:discussion_id>/statements", methods=["GET"])
# def statements(discussion_id: int):
#     discussion = Discussion.query.get(discussion_id)
#     if discussion.user_id != auth.current_user().id:
#         return abort(401)
#     _log.debug(f"Discussion: {discussion} with {len(discussion.statements)} statements")
#     return jsonify([stmt.as_dict() for stmt in discussion.statements])
