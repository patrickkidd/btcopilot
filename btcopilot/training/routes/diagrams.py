"""
Diagram management routes for btcopilot training interface.

Handles training-specific diagram operations including PDP workflow,
discussion management, and training data cleanup.
"""

import logging
from flask import Blueprint, request, jsonify, abort

from ...extensions import db
from ..models import Discussion, Statement, Speaker, Feedback
from ..auth import require_auditor_or_admin, get_current_user, require_admin
from ..database import cascade_delete_training_data, get_discussions_for_diagram, create_initial_database

_log = logging.getLogger(__name__)

# Create blueprint
diagrams_bp = Blueprint(
    "diagrams", 
    __name__, 
    url_prefix="/diagrams"
)


@diagrams_bp.route("", methods=["POST"])
@require_auditor_or_admin
def create():
    """Create a new diagram"""
    try:
        from fdserver.auth import current_user
        current_user_obj = current_user()
    except ImportError:
        return jsonify({"error": "Diagram creation requires fdserver integration"}), 400

    data = request.get_json()
    user_id = data.get("user_id")
    name = data.get("name", "").strip()

    if not user_id:
        return jsonify({"error": "user id is required"}), 400

    if not name:
        return jsonify({"error": "Diagram name is required"}), 400

    try:
        from fdserver.models import Diagram
        
        # Create new diagram
        diagram = Diagram(
            user_id=user_id,
            name=name,
            data=b"",  # Empty initial data
        )

        # Initialize with database containing default User and Assistant people
        initial_database = create_initial_database()
        if initial_database:
            diagram.set_database(initial_database)

        db.session.add(diagram)
        db.session.commit()

        _log.info(
            f"User {current_user_obj.username} created diagram '{name}' (ID: {diagram.id})"
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
        
    except ImportError:
        return jsonify({"error": "Diagram creation requires fdserver integration"}), 400


@diagrams_bp.route("/<int:diagram_id>")
def get(diagram_id):
    """Get diagram details"""
    try:
        from fdserver.auth import current_user
        from fdserver.models import Diagram
        
        user = current_user()
        diagram = Diagram.query.get(diagram_id)
        
        if not diagram:
            abort(404)

        if diagram.user_id != user.id and not user.has_role('admin'):
            abort(403)

        ret = diagram.as_dict(exclude="data")
        if diagram.get_database():
            ret["database"] = diagram.get_database().model_dump()

        return jsonify(ret)
        
    except ImportError:
        return jsonify({"error": "Diagram access requires fdserver integration"}), 400


@diagrams_bp.route("/<int:diagram_id>", methods=["DELETE"])
@require_auditor_or_admin
def delete(diagram_id):
    """Delete a diagram (core deletion only - training data handled separately)"""
    try:
        from fdserver.auth import current_user
        from fdserver.models import Diagram
        
        current_user_obj = current_user()
        diagram = Diagram.query.get(diagram_id)

        if not diagram:
            return jsonify({"error": "Diagram not found"}), 404

        # Check permissions: user owns diagram OR user is admin
        is_owner = diagram.user_id == current_user_obj.id
        is_admin = 'admin' in current_user_obj.roles

        if not (is_owner or is_admin):
            return jsonify({"error": "Access denied"}), 403

        # Check if there are discussions (training data)
        discussions_count = Discussion.query.filter_by(diagram_id=diagram_id).count()
        
        if discussions_count > 0 and not is_admin:
            return jsonify({
                "error": f"Diagram has {discussions_count} discussions. Use training interface to clean up training data first, or contact an admin."
            }), 400
        
        if discussions_count > 0:
            return jsonify({
                "error": f"Diagram has {discussions_count} discussions. Please delete training data via /training/diagrams/{diagram_id}/training-data endpoint first."
            }), 400

        diagram_name = diagram.name
        diagram_owner_id = diagram.user_id

        # Delete the diagram (core data only)
        db.session.delete(diagram)
        db.session.commit()

        if is_admin and not is_owner:
            _log.info(
                f"Admin {current_user_obj.username} deleted diagram '{diagram_name}' (ID: {diagram_id}) owned by user ID {diagram_owner_id}"
            )
        else:
            _log.info(
                f"User {current_user_obj.username} deleted their own diagram '{diagram_name}' (ID: {diagram_id})"
            )

        return jsonify({"success": True})
        
    except ImportError:
        return jsonify({"error": "Diagram deletion requires fdserver integration"}), 400


@diagrams_bp.route("/<int:diagram_id>/discussions")
@require_auditor_or_admin
def discussions(diagram_id):
    """Get all discussions for a diagram"""
    user = get_current_user()
    if not user:
        return abort(401)
    
    # Try to check diagram ownership if fdserver is available
    try:
        from fdserver.models import Diagram
        diagram = Diagram.query.get_or_404(diagram_id)
        
        # Check if user has access (owner or admin)
        if hasattr(user, 'id') and hasattr(diagram, 'user_id'):
            if diagram.user_id != user.id:
                # Check if user is admin
                if not (hasattr(user, 'has_role') and user.has_role('admin')):
                    return abort(403)
    except ImportError:
        # fdserver not available, allow access
        pass
    
    discussions_data = get_discussions_for_diagram(diagram_id)
    return jsonify(discussions_data)


@diagrams_bp.route("/<int:diagram_id>/training-data", methods=["DELETE"])
@require_admin  
def delete_training_data(diagram_id):
    """Delete all training data associated with a diagram"""
    user = get_current_user()
    if not user:
        return abort(401)
    
    # Check if there are discussions to delete
    discussions = Discussion.query.filter_by(diagram_id=diagram_id)
    discussion_count = discussions.count()
    
    if discussion_count == 0:
        return jsonify({"message": "No training data found for this diagram"})
    
    # Perform cascade delete
    cascade_delete_training_data(diagram_id)
    db.session.commit()
    
    _log.info(f"Admin {getattr(user, 'username', 'unknown')} deleted training data for diagram {diagram_id}")
    
    return jsonify({
        "success": True,
        "message": f"Deleted {discussion_count} discussions and associated training data"
    })


@diagrams_bp.route("/<int:diagram_id>/pdp/<int:pdp_id>/accept", methods=["POST"])
@require_auditor_or_admin
def pdp_accept(diagram_id: int, pdp_id: int):
    """Accept a PDP (Person Data Point) item"""
    user = get_current_user()
    if not user:
        return abort(401)
    
    try:
        from fdserver.models import Diagram
        
        diagram = Diagram.query.get_or_404(diagram_id)
        
        # Check ownership
        if hasattr(user, 'id') and hasattr(diagram, 'user_id'):
            if diagram.user_id != user.id:
                return jsonify(success=False, message="Unauthorized"), 401

        database = diagram.get_database()
        pdp_id = -pdp_id  # Convert to negative ID for PDP items

        def done():
            diagram.set_database(database)
            db.session.commit()
            return jsonify(success=True)

        for person in database.pdp.people:
            if person.id == pdp_id:
                _log.info(f"Accepting PDP person with id: {pdp_id}")
                database.pdp.people.remove(person)
                database.add_person(person)
                return done()

        for event in database.pdp.events:
            if event.id == pdp_id:
                _log.info(f"Accepting PDP event with id: {pdp_id}")
                database.pdp.events.remove(event)
                database.add_event(event)
                return done()

        return jsonify(success=False, message="PDP item not found"), 404
        
    except ImportError:
        return jsonify(success=False, message="PDP functionality requires fdserver integration"), 400


@diagrams_bp.route("/<int:diagram_id>/pdp/<int:pdp_id>/reject", methods=["POST"])
@require_auditor_or_admin
def pdp_reject(diagram_id: int, pdp_id: int):
    """Reject a PDP (Person Data Point) item"""
    user = get_current_user()
    if not user:
        return abort(401)
    
    try:
        from fdserver.models import Diagram
        
        diagram = Diagram.query.get_or_404(diagram_id)
        
        # Check ownership
        if hasattr(user, 'id') and hasattr(diagram, 'user_id'):
            if diagram.user_id != user.id:
                return jsonify(success=False, message="Unauthorized"), 401

        database = diagram.get_database()
        pdp_id = -pdp_id  # Convert to negative ID for PDP items

        def done():
            diagram.set_database(database)
            db.session.commit()
            return jsonify(success=True)

        for person in database.pdp.people:
            if person.id == pdp_id:
                _log.info(f"Rejecting PDP person with id: {pdp_id}")
                database.pdp.people.remove(person)
                return done()

        for event in database.pdp.events:
            if event.id == pdp_id:
                _log.info(f"Rejecting PDP event with id: {pdp_id}")
                database.pdp.events.remove(event)
                return done()

        return jsonify(success=False, message="PDP item not found"), 404
        
    except ImportError:
        return jsonify(success=False, message="PDP functionality requires fdserver integration"), 400