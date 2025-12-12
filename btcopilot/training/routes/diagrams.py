import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram, AccessRight, User
from btcopilot.schema import DiagramData
from btcopilot.personal.models import Discussion, Statement
from btcopilot.personal.models.speaker import Speaker

import logging
from flask import Blueprint, request, jsonify


_log = logging.getLogger(__name__)

bp = Blueprint(
    "diagrams",
    __name__,
    url_prefix="/diagrams",
    template_folder="../templates",
)
bp = minimum_role(btcopilot.ROLE_AUDITOR)(bp)


@bp.route("", methods=["POST"])
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
    database_with_defaults = DiagramData.create_with_defaults()
    diagram.set_diagram_data(database_with_defaults)

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


@bp.route("/<int:diagram_id>", methods=["DELETE"])
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
    is_admin = btcopilot.ROLE_ADMIN in current_user.roles

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


@bp.route("/<int:diagram_id>/access-rights", methods=["GET"])
def get_access_rights(diagram_id):
    """Get access rights for a diagram"""
    current_user = auth.current_user()

    diagram = Diagram.query.get_or_404(diagram_id)

    is_owner = diagram.user_id == current_user.id
    is_admin = current_user.has_role(btcopilot.ROLE_ADMIN)

    if not (is_owner or is_admin):
        return jsonify({"error": "Access denied"}), 403

    access_rights = AccessRight.query.filter_by(diagram_id=diagram_id).all()

    rights_data = [
        ar.as_dict(include={"user": {"only": ["username", "first_name", "last_name"]}})
        for ar in access_rights
    ]

    return jsonify({"success": True, "access_rights": rights_data})


@bp.route("/<int:diagram_id>/access-rights", methods=["POST"])
def grant_access_right(diagram_id):
    """Grant or update access right to a diagram"""
    current_user = auth.current_user()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    target_user_id = data.get("user_id")
    right = data.get("right")

    if not target_user_id:
        return jsonify({"error": "user_id required"}), 400

    if right not in [btcopilot.ACCESS_READ_ONLY, btcopilot.ACCESS_READ_WRITE]:
        return (
            jsonify(
                {
                    "error": f"Invalid right. Must be '{btcopilot.ACCESS_READ_ONLY}' or '{btcopilot.ACCESS_READ_WRITE}'"
                }
            ),
            400,
        )

    diagram = Diagram.query.get_or_404(diagram_id)
    target_user = User.query.get(target_user_id)

    if not target_user:
        return jsonify({"error": "User not found"}), 404

    is_owner = diagram.user_id == current_user.id
    is_admin = current_user.has_role(btcopilot.ROLE_ADMIN)

    if not (is_owner or is_admin):
        return jsonify({"error": "Access denied"}), 403

    if target_user_id == diagram.user_id:
        return (
            jsonify({"error": "Cannot grant access rights to diagram owner"}),
            400,
        )

    existing_right = AccessRight.query.filter_by(
        diagram_id=diagram_id, user_id=target_user_id
    ).first()

    if existing_right:
        old_right = existing_right.right
        existing_right.right = right
        db.session.commit()

        _log.info(
            f"User {current_user.username} updated access right for user {target_user.username} "
            f"on diagram {diagram_id} from {old_right} to {right}"
        )

        return jsonify(
            {
                "success": True,
                "message": f"Updated access to {right}",
                "access_right": existing_right.as_dict(
                    include={"user": {"only": ["username", "first_name", "last_name"]}}
                ),
            }
        )
    else:
        diagram.grant_access(target_user, right, _commit=True)

        new_right = AccessRight.query.filter_by(
            diagram_id=diagram_id, user_id=target_user_id
        ).first()

        _log.info(
            f"User {current_user.username} granted {right} access to user {target_user.username} "
            f"on diagram {diagram_id}"
        )

        return (
            jsonify(
                {
                    "success": True,
                    "message": f"Granted {right} access",
                    "access_right": new_right.as_dict(
                        include={
                            "user": {"only": ["username", "first_name", "last_name"]}
                        }
                    ),
                }
            ),
            201,
        )


@bp.route("/<int:diagram_id>/access-rights/<int:access_right_id>", methods=["DELETE"])
def revoke_access_right(diagram_id, access_right_id):
    """Revoke access right from a diagram"""
    current_user = auth.current_user()

    diagram = Diagram.query.get_or_404(diagram_id)

    is_owner = diagram.user_id == current_user.id
    is_admin = current_user.has_role(btcopilot.ROLE_ADMIN)

    if not (is_owner or is_admin):
        return jsonify({"error": "Access denied"}), 403

    access_right = AccessRight.query.get_or_404(access_right_id)

    if access_right.diagram_id != diagram_id:
        return jsonify({"error": "Access right does not belong to this diagram"}), 400

    target_user = User.query.get(access_right.user_id)
    target_username = (
        target_user.username if target_user else f"User {access_right.user_id}"
    )

    db.session.delete(access_right)
    db.session.commit()

    _log.info(
        f"User {current_user.username} revoked access from user {target_username} on diagram {diagram_id}"
    )

    return jsonify({"success": True, "message": "Access revoked"})
