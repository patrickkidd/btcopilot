"""
Discussion routes for btcopilot training interface.

Handles discussion management for training data collection including
audit interface, extraction progress tracking, and export functionality.
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, abort, render_template, session

from ...extensions import db
from ..models import Discussion, Statement, Speaker, SpeakerType, Feedback
from ..auth import require_auditor_or_admin, get_current_user, require_admin
from ..utils import get_breadcrumbs, get_auditor_id

_log = logging.getLogger(__name__)

# Create blueprint
discussions_bp = Blueprint(
    "discussions", 
    __name__, 
    url_prefix="/discussions"
)

def _get_current_user():
    """Get current user"""
    return get_current_user()

@discussions_bp.route("/import", methods=["POST"])
@require_auditor_or_admin
def import_discussion():
    """Import discussion from JSON data"""
    json_data = request.get_json()
    if not json_data:
        return jsonify({"error": "No JSON data provided"}), 400
    
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    # Create discussion from JSON
    discussion = Discussion(
        user_id=getattr(user, 'id', 1),  # Default to 1 for standalone mode
        summary=json_data.get("summary", "Imported Discussion"),
    )
    db.session.add(discussion)
    db.session.commit()
    
    # Import speakers and statements from JSON
    speakers_map = {}
    for speaker_data in json_data.get("speakers", []):
        speaker = Speaker(
            discussion_id=discussion.id,
            name=speaker_data.get("name"),
            type=SpeakerType(speaker_data.get("type", "subject")),
        )
        db.session.add(speaker)
        speakers_map[speaker_data.get("id")] = speaker
    
    db.session.commit()
    
    for stmt_data in json_data.get("statements", []):
        speaker = speakers_map.get(stmt_data.get("speaker_id"))
        statement = Statement(
            discussion_id=discussion.id,
            speaker_id=speaker.id if speaker else None,
            text=stmt_data.get("text"),
            order=stmt_data.get("order", 0),
            pdp_deltas=stmt_data.get("pdp_deltas"),
        )
        db.session.add(statement)
    
    db.session.commit()
    return jsonify(discussion.as_dict(include=["speakers", "statements"]))

@discussions_bp.route("/transcript", methods=["POST"])
@require_auditor_or_admin
def create_from_transcript():
    """Create discussion from transcript data"""
    transcript_data = request.get_json()
    if not transcript_data:
        return jsonify({"error": "No transcript data provided"}), 400
    
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    title = request.args.get("title", "Transcript Import")
    
    # Create discussion
    discussion = Discussion(
        user_id=getattr(user, 'id', 1),  # Default to 1 for standalone mode
        summary=title,
    )
    db.session.add(discussion)
    db.session.commit()
    
    # Create speakers
    speakers = {}
    for utterance in transcript_data.get("utterances", []):
        speaker_label = utterance.get("speaker")
        if speaker_label not in speakers:
            speaker = Speaker(
                discussion_id=discussion.id,
                name=f"Speaker {speaker_label}",
                type=SpeakerType.Subject if speaker_label == "A" else SpeakerType.Expert,
            )
            db.session.add(speaker)
            speakers[speaker_label] = speaker
    
    db.session.commit()
    
    # Create statements
    for i, utterance in enumerate(transcript_data.get("utterances", [])):
        speaker = speakers[utterance.get("speaker")]
        statement = Statement(
            discussion_id=discussion.id,
            speaker_id=speaker.id,
            text=utterance.get("text"),
            order=i + 1,
        )
        db.session.add(statement)
    
    db.session.commit()
    return jsonify(discussion.as_dict(include=["speakers", "statements"]))

@discussions_bp.route("/<int:discussion_id>/statements", methods=["GET"])
@require_auditor_or_admin
def statements(discussion_id: int):
    """Get statements for a discussion"""
    discussion = Discussion.query.get_or_404(discussion_id)
    user = _get_current_user()
    
    # Basic authorization check
    if hasattr(user, 'id') and hasattr(discussion, 'user_id'):
        if discussion.user_id != user.id:
            return abort(401)
    
    _log.debug(f"Discussion: {discussion} with {len(discussion.statements)} statements")
    return jsonify([stmt.as_dict() for stmt in discussion.statements])

@discussions_bp.route("/upload_token")
@require_auditor_or_admin
def upload_token():
    """Get upload token for file uploads"""
    return jsonify({"upload_token": "placeholder_token"})

@discussions_bp.route("/<int:discussion_id>/audit")
@require_auditor_or_admin
def audit(discussion_id):
    """Audit interface for discussion review"""
    discussion = Discussion.query.get_or_404(discussion_id)
    auditor_id = get_auditor_id(request, session)
    
    statements_with_feedback = []
    for statement in discussion.statements:
        stmt_dict = statement.as_dict()
        existing_feedback = Feedback.query.filter_by(
            statement_id=statement.id,
            auditor_id=auditor_id
        ).first()
        
        stmt_dict["existing_feedback"] = (
            existing_feedback.as_dict() if existing_feedback else None
        )
        statements_with_feedback.append(stmt_dict)
    
    breadcrumbs = get_breadcrumbs("thread")
    current_user = get_current_user()
    
    return render_template(
        "discussion_audit.html",
        discussion=discussion.as_dict(include=["speakers"]),
        statements=statements_with_feedback,
        breadcrumbs=breadcrumbs,
        current_user=current_user,
    )

@discussions_bp.route("/<int:discussion_id>/extract", methods=["POST"])
@require_admin
def extract(discussion_id: int):
    """Trigger extraction for discussion"""
    discussion = Discussion.query.get_or_404(discussion_id)
    discussion.extracting = True
    db.session.commit()
    
    # Note: Actual extraction would be handled by background tasks
    # This is just marking the discussion for extraction
    _log.info(f"Discussion {discussion_id} marked for extraction")
    
    return jsonify({"status": "extraction_started"})

@discussions_bp.route("/<int:discussion_id>/progress", methods=["GET"])
@require_auditor_or_admin
def progress(discussion_id: int):
    """Get extraction progress for discussion"""
    discussion = Discussion.query.get_or_404(discussion_id)
    
    statements = discussion.statements
    total_statements = len(statements)
    
    if total_statements == 0:
        return jsonify({
            "total": 0,
            "processed": 0,
            "percentage": 100,
            "extracting": discussion.extracting
        })
    
    processed_statements = sum(
        1 for stmt in statements
        if stmt.pdp_deltas is not None and stmt.pdp_deltas != {}
    )
    
    percentage = int((processed_statements / total_statements) * 100)
    
    return jsonify({
        "total": total_statements,
        "processed": processed_statements,
        "percentage": percentage,
        "extracting": discussion.extracting
    })

@discussions_bp.route("/<int:discussion_id>/export", methods=["GET"])
@require_admin
def export(discussion_id: int):
    """Export discussion data"""
    discussion = Discussion.query.get_or_404(discussion_id)
    
    export_data = {
        "discussion": discussion.as_dict(include=["speakers", "statements"]),
        "export_timestamp": datetime.now().isoformat(),
        "exported_by": get_current_user().username if get_current_user() else "unknown"
    }
    
    response = jsonify(export_data)
    response.headers["Content-Disposition"] = f'attachment; filename="discussion_{discussion_id}_export.json"'
    return response

@discussions_bp.route("/<int:discussion_id>/clear-extracted", methods=["POST"])
@require_admin
def clear_extracted_data(discussion_id):
    """Clear extracted data from discussion"""
    discussion = Discussion.query.get_or_404(discussion_id)
    
    for statement in discussion.statements:
        statement.pdp_deltas = None
        statement.custom_prompts = None
    
    discussion.extracting = False
    db.session.commit()
    
    return jsonify({"message": "Extracted data cleared successfully"})

@discussions_bp.route("/<int:discussion_id>", methods=["DELETE"])
@require_admin
def delete(discussion_id):
    """Delete discussion and all associated data"""
    discussion = Discussion.query.get_or_404(discussion_id)
    
    # Delete all associated statements and speakers
    Statement.query.filter_by(discussion_id=discussion_id).delete()
    Speaker.query.filter_by(discussion_id=discussion_id).delete()
    Feedback.query.filter(
        Feedback.statement_id.in_(
            db.session.query(Statement.id).filter_by(discussion_id=discussion_id)
        )
    ).delete(synchronize_session=False)
    
    db.session.delete(discussion)
    db.session.commit()
    
    return jsonify({"message": "Discussion deleted successfully"})