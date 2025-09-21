import vedana
from btcopilot import auth
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram, AccessRight
from btcopilot.personal.database import Database
from btcopilot.personal.models import Discussion, Statement
from btcopilot.personal.models.speaker import Speaker

import logging
from flask import Blueprint, request, jsonify


_log = logging.getLogger(__name__)

diagrams_bp = Blueprint(
    "diagrams",
    __name__,
    url_prefix="/diagrams",
    template_folder="../templates",
)


@diagrams_bp.route("", methods=["POST"])
def create():
    """Create a new diagram for the auditor"""
    current_user = auth.current_user()

    data = request.get_json()
    user_id = data.get("user_id")
    name = data.get("name", "").strip()

    if not user_id:
        return jsonify({"error": "user id is required"}), 400

    if not name:
        return jsonify({"error": "Diagram name is required"}), 400

    # Create new diagram
    diagram = Diagram(
        user_id=user_id,
        name=name,
        data=b"",  # Empty initial data
    )

    # Initialize with database containing default User and Assistant people
    database_with_defaults = Database.create_with_defaults()
    diagram.set_database(database_with_defaults)

    db.session.add(diagram)
    db.session.commit()

    _log.info(
        f"Auditor {current_user.username} created diagram '{name}' (ID: {diagram.id})"
    )

    return jsonify(
        {
            "success": True,
            "diagram": {
                "id": diagram.id,
                "name": diagram.name,
                "created_at": (
                    diagram.created_at.isoformat() if diagram.created_at else None
                ),
            },
        }
    )


@diagrams_bp.route("/<int:diagram_id>", methods=["DELETE"])
def delete(diagram_id):
    """Delete a diagram - auditors can delete their own, admins can delete any"""
    from btcopilot.training.models import Feedback

    current_user = auth.current_user()

    # Find the diagram
    diagram = Diagram.query.get(diagram_id)

    if not diagram:
        return jsonify({"error": "Diagram not found"}), 404

    # Check permissions: user owns diagram OR user is admin
    is_owner = diagram.user_id == current_user.id
    is_admin = vedana.ROLE_ADMIN in current_user.roles

    if not (is_owner or is_admin):
        return jsonify({"error": "Access denied"}), 403

    discussions = Discussion.query.filter_by(diagram_id=diagram_id)
    if discussions.count() > 0 and not is_admin:
        return (
            jsonify({"error": "Only admins can delete diagrams with discussions"}),
            400,
        )

    diagram_name = diagram.name
    diagram_owner_id = diagram.user_id

    # Manually cascade delete related records
    # 1. Delete feedbacks for statements in discussions of this diagram
    Feedback.query.filter(
        Feedback.statement_id.in_(
            db.session.query(Statement.id).filter(
                Statement.discussion_id.in_(
                    db.session.query(Discussion.id).filter(
                        Discussion.diagram_id == diagram_id
                    )
                )
            )
        )
    ).delete(synchronize_session=False)

    # 2. Delete statements in discussions of this diagram
    Statement.query.filter(
        Statement.discussion_id.in_(
            db.session.query(Discussion.id).filter(Discussion.diagram_id == diagram_id)
        )
    ).delete(synchronize_session=False)

    # 3. Delete speakers in discussions of this diagram
    Speaker.query.filter(
        Speaker.discussion_id.in_(
            db.session.query(Discussion.id).filter(Discussion.diagram_id == diagram_id)
        )
    ).delete(synchronize_session=False)

    # 4. Delete discussions for this diagram
    Discussion.query.filter(Discussion.diagram_id == diagram_id).delete(
        synchronize_session=False
    )

    # 5. Delete access rights for this diagram
    access_rights = AccessRight.query.filter_by(diagram_id=diagram_id)
    access_rights.delete(synchronize_session=False)

    # 6. Finally delete the diagram itself
    db.session.delete(diagram)
    db.session.commit()

    if is_admin and not is_owner:
        _log.info(
            f"Admin {current_user.username} deleted diagram '{diagram_name}' (ID: {diagram_id}) owned by user ID {diagram_owner_id}"
        )
    else:
        _log.info(
            f"User {current_user.username} deleted their own diagram '{diagram_name}' (ID: {diagram_id})"
        )

    return jsonify({"success": True})
