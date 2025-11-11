import os
import logging
import json
import asyncio
import nest_asyncio
import pickle
from datetime import datetime

from flask import (
    Blueprint,
    jsonify,
    request,
    abort,
    render_template,
    session,
    current_app,
    make_response,
)
from sqlalchemy import create_engine


import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram, User
from btcopilot import pdp
from btcopilot.personal import Response, ask
from btcopilot.schema import DiagramData, PDP, PDPDeltas, Person, Event, asdict
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.training.models import Feedback
from btcopilot.training.utils import get_breadcrumbs, get_auditor_id


# from btcopilot.training.sse import sse_manager
import btcopilot

_log = logging.getLogger(__name__)


def _next_statement() -> Statement:
    # Get all subject statements from discussions marked for extraction
    candidates = (
        Statement.query.join(Speaker)
        .join(Discussion, Statement.discussion_id == Discussion.id)
        .filter(
            Speaker.type == SpeakerType.Subject,
            Statement.text.isnot(None),
            Statement.text != "",
            Discussion.extracting == True,
        )
        .order_by(
            Statement.discussion_id.asc(),
            Statement.order.asc(),
            Statement.id.asc(),  # Tiebreaker for statements with same order
        )
        .all()
    )

    # Find the first one that actually needs processing
    # Check for None or empty dict since SQLAlchemy JSON column filters are unreliable
    for stmt in candidates:
        if stmt.pdp_deltas is None or stmt.pdp_deltas == {}:
            return stmt

    return None


def extract_next_statement(*args, **kwargs):
    """
    Background job to extract data from the oldest pending Subject statement.
    Returns True if a statement was processed, False if no statements are pending.
    """
    _log.info(f"extract_next_statement() called with: args: {args}, kwargs: {kwargs}")

    try:

        try:
            db.session.get_bind()
        except:
            engine = create_engine(current_app.config["SQLALCHEMY_DATABASE_URI"])
            db.session.bind = engine

        # Query for the oldest unprocessed Subject statement from discussions with extracting=True
        # Order by discussion_id first, then by order column for reliable sorting
        statement = _next_statement()

        if not statement:
            _log.debug("No pending statements found")
            return False

        discussion = statement.discussion
        if not discussion or not discussion.user:
            _log.warning(
                f"Skipping statement {statement.id} - missing discussion or user"
            )
            return False

        _log.info(
            f"Data extraction started - "
            f"statement_id: {statement.id}, "
            f"discussion_id: {statement.discussion_id}, "
            f"speaker_type: {statement.speaker.type}, "
            f"text_length: {len(statement.text)}"
        )

        # Get or create diagram database
        if discussion.diagram:
            database = discussion.diagram.get_diagram_data()
        else:
            database = DiagramData()

        try:
            # Apply nest_asyncio to allow nested event loops in Celery workers
            nest_asyncio.apply()

            # Run pdp.update for this statement
            new_pdp, pdp_deltas = asyncio.run(
                pdp.update(discussion, database, statement.text)
            )

            # Update database and statement
            database.pdp = new_pdp
            if discussion.diagram:
                discussion.diagram.set_diagram_data(database)
            if pdp_deltas:
                statement.pdp_deltas = asdict(pdp_deltas)
                event_count = len(pdp_deltas.events)
                people_count = len(pdp_deltas.people)
                _log.info(
                    f"Data extraction completed - "
                    f"statement_id: {statement.id}, "
                    f"discussion_id: {discussion.id}, "
                    f"events_extracted: {event_count}, "
                    f"people_extracted: {people_count}"
                )
            else:
                statement.pdp_deltas = None
                _log.info(
                    f"Data extraction completed - "
                    f"statement_id: {statement.id}, "
                    f"discussion_id: {discussion.id}, "
                    f"events_extracted: 0, "
                    f"people_extracted: 0"
                )

            # Check if there are any more unprocessed statements in this discussion
            # We need to check manually because JSON column filters are unreliable
            remaining_candidates = (
                Statement.query.join(Speaker)
                .filter(
                    Speaker.type == SpeakerType.Subject,
                    Statement.text.isnot(None),
                    Statement.text != "",
                    Statement.discussion_id == discussion.id,
                    Statement.id != statement.id,  # Exclude the current statement
                )
                .all()
            )

            # Count how many actually need processing
            remaining_statements = sum(
                1
                for s in remaining_candidates
                if s.pdp_deltas is None or s.pdp_deltas == {}
            )

            # If no more statements to process in this discussion, set extracting to False
            if remaining_statements == 0:
                discussion.extracting = False
                total_statements = Statement.query.filter_by(
                    discussion_id=discussion.id
                ).count()
                _log.info(
                    f"Discussion extraction complete - "
                    f"discussion_id: {discussion.id}, "
                    f"total_statements: {total_statements}"
                )
            else:
                _log.info(
                    f"Discussion extraction continuing - "
                    f"discussion_id: {discussion.id}, "
                    f"remaining_statements: {remaining_statements}"
                )
                # There are more statements in this discussion, schedule another task
                from btcopilot.extensions import celery

                celery.send_task("extract_next_statement", countdown=1)

            # Commit this statement's updates
            db.session.commit()
            return True

        except Exception as e:
            _log.error(
                f"Error processing statement {statement.id if statement else None}: {e}",
                exc_info=True,
            )
            db.session.rollback()
            return False

    except Exception as e:
        _log.error(f"Unexpected error in extract_next_statement: {e}", exc_info=True)
        return False


# Create the discussions blueprint
bp = Blueprint(
    "discussions",
    __name__,
    url_prefix="/discussions",
    template_folder="../templates",
    static_folder="../static",
)
bp = minimum_role(btcopilot.ROLE_SUBSCRIBER)(bp)


def _create_assembly_ai_transcript(data: dict):
    # Require auditor role for transcript creation
    current_user = auth.current_user()
    if not current_user.has_role(btcopilot.ROLE_AUDITOR):
        return jsonify({"error": "Unauthorized"}), 403

    transcript_data = data["transcript_data"]
    title = data.get("title", "")
    diagram_id = data.get("diagram_id")

    utterance_count = len(transcript_data.get("utterances", []))
    transcript_length = len(transcript_data.get("text", ""))
    _log.info(
        f"Audio transcript upload - "
        f"title: '{title}', "
        f"diagram_id: {diagram_id}, "
        f"utterances: {utterance_count}, "
        f"transcript_length: {transcript_length}"
    )

    if diagram_id:
        # Create in specific diagram
        diagram = Diagram.query.filter_by(id=diagram_id).first()
        if not diagram:
            return jsonify({"error": "Diagram not found"}), 404

        target_user = diagram.user
        target_diagram_id = diagram_id
        target_user_id = diagram.user_id

    else:
        # Create in current user's free diagram
        target_user = current_user

        # Ensure user has a free_diagram
        if not target_user.free_diagram:
            # Create initial database with User and Assistant people
            initial_database = _create_initial_database()

            diagram = Diagram(
                user_id=target_user.id,
                name=f"{target_user.username} Personal Case File",
            )
            diagram.set_diagram_data(initial_database)
            db.session.add(diagram)
            db.session.flush()
            target_user.free_diagram_id = diagram.id
        target_diagram_id = target_user.free_diagram_id
        target_user_id = target_user.id

    discussion = Discussion(
        user_id=target_user_id,
        diagram_id=target_diagram_id,
        summary=title
        or f"Audio discussion - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        last_topic=(
            transcript_data.get("text", "")[:100]
            if transcript_data.get("text")
            else "Audio transcript"
        ),
    )
    db.session.add(discussion)
    db.session.flush()

    speakers_map = {}

    if transcript_data.get("utterances"):
        # Create speakers and statements from utterances
        for order, utterance in enumerate(transcript_data["utterances"]):
            speaker_label = utterance.get("speaker", "Unknown")
            if speaker_label not in speakers_map:
                speaker = Speaker(
                    discussion_id=discussion.id,
                    name=speaker_label,
                    type=SpeakerType.Subject,  # Default to Subject
                )
                db.session.add(speaker)
                db.session.flush()
                speakers_map[speaker_label] = speaker

            statement = Statement(
                discussion_id=discussion.id,
                speaker_id=speakers_map[speaker_label].id,
                text=utterance.get("text", ""),
                order=order,  # Use enumerate order for reliable sorting
            )
            db.session.add(statement)
    else:
        # No speaker diarization, create single speaker with full text
        speaker = Speaker(
            discussion_id=discussion.id,
            name="Speaker",
            type=SpeakerType.Subject,
        )
        db.session.add(speaker)
        db.session.flush()

        # Create single statement with full transcript
        statement = Statement(
            discussion_id=discussion.id,
            speaker_id=speaker.id,
            text=transcript_data.get("text", ""),
            order=0,  # Single statement gets order 0
        )
        db.session.add(statement)

    db.session.commit()

    speaker_count = len(speakers_map) if speakers_map else 1
    statement_count = len(transcript_data.get("utterances", [])) or 1

    _log.info(
        f"Audio transcript discussion created - "
        f"discussion_id: {discussion.id}, "
        f"diagram_id: {target_diagram_id}, "
        f"speakers: {speaker_count}, "
        f"statements: {statement_count}"
    )

    # Return format compatible with both use cases
    return jsonify(
        {
            "success": True,
            "id": discussion.id,
            "discussion_id": discussion.id,  # For backwards compatibility
            "user_id": target_user_id,
            "message": "Discussion created successfully",
            **discussion.as_dict(include=["statements", "speakers"]),
        }
    )


def _create_import(data: dict):
    user = auth.current_user()

    # Require auditor role for JSON import
    if not user.has_role(btcopilot.ROLE_AUDITOR):
        return jsonify({"error": "Unauthorized"}), 403

    json_data = data["json_data"]

    # Get current user (auditor)
    current_user = auth.current_user()
    diagram_id = data.get("diagram_id")

    if diagram_id:
        # Import to specific diagram
        diagram = Diagram.query.filter_by(id=diagram_id).first()
        if not diagram:
            return jsonify({"error": "Diagram not found"}), 404

        target_user = diagram.user
        target_diagram_id = diagram_id
        target_user_id = diagram.user_id

    else:
        # Import to current user's free diagram
        target_user = current_user

        # Ensure user has a free_diagram
        if not target_user.free_diagram:
            # Create initial database with User and Assistant people
            initial_database = _create_initial_database()

            diagram = Diagram(
                user_id=target_user.id,
                name=f"{target_user.username} Personal Case File",
            )
            diagram.set_diagram_data(initial_database)
            db.session.add(diagram)
            db.session.flush()
            target_user.free_diagram_id = diagram.id
        target_diagram_id = target_user.free_diagram_id
        target_user_id = target_user.id

    # Create new discussion from imported data
    discussion = Discussion(
        user_id=target_user_id,
        diagram_id=target_diagram_id,
        summary=json_data.get("summary", "Imported discussion"),
        last_topic=json_data.get("last_topic"),
        extracting=json_data.get("extracting", False),
    )

    if json_data.get("created_at"):
        created_at_str = json_data.get("created_at")
        if isinstance(created_at_str, str):
            discussion.created_at = datetime.fromisoformat(
                created_at_str.replace("Z", "+00:00")
            )
        else:
            discussion.created_at = created_at_str

    if json_data.get("updated_at"):
        updated_at_str = json_data.get("updated_at")
        if isinstance(updated_at_str, str):
            discussion.updated_at = datetime.fromisoformat(
                updated_at_str.replace("Z", "+00:00")
            )
        else:
            discussion.updated_at = updated_at_str

    db.session.add(discussion)
    db.session.flush()

    # Map old speaker IDs to new ones
    speaker_id_map = {}

    if "speakers" in json_data:
        for speaker_data in json_data["speakers"]:
            speaker = Speaker(
                discussion_id=discussion.id,
                name=speaker_data.get("name", "Unknown"),
                type=SpeakerType(speaker_data.get("type", "subject")),
                person_id=speaker_data.get("person_id"),
            )

            if speaker_data.get("created_at"):
                created_at_str = speaker_data.get("created_at")
                if isinstance(created_at_str, str):
                    speaker.created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                else:
                    speaker.created_at = created_at_str

            if speaker_data.get("updated_at"):
                updated_at_str = speaker_data.get("updated_at")
                if isinstance(updated_at_str, str):
                    speaker.updated_at = datetime.fromisoformat(
                        updated_at_str.replace("Z", "+00:00")
                    )
                else:
                    speaker.updated_at = updated_at_str

            db.session.add(speaker)
            db.session.flush()

            # Map old ID to new ID
            speaker_id_map[speaker_data["id"]] = speaker.id

            # Update discussion chat speaker IDs if they match
            if json_data.get("chat_user_speaker_id") == speaker_data["id"]:
                discussion.chat_user_speaker_id = speaker.id
            if json_data.get("chat_ai_speaker_id") == speaker_data["id"]:
                discussion.chat_ai_speaker_id = speaker.id

    if "statements" in json_data:
        for idx, stmt_data in enumerate(json_data["statements"]):
            # Map speaker ID to new speaker
            new_speaker_id = speaker_id_map.get(stmt_data.get("speaker_id"))

            # Create statement without JSON fields first
            statement = Statement(
                discussion_id=discussion.id,
                speaker_id=new_speaker_id,
                text=stmt_data.get("text", ""),
                order=stmt_data.get("order", idx),
                approved=stmt_data.get("approved", False),
                approved_by=stmt_data.get("approved_by"),
            )

            if stmt_data.get("approved_at"):
                approved_at_str = stmt_data.get("approved_at")
                if isinstance(approved_at_str, str):
                    statement.approved_at = datetime.fromisoformat(
                        approved_at_str.replace("Z", "+00:00")
                    )
                else:
                    statement.approved_at = approved_at_str

            if stmt_data.get("exported_at"):
                exported_at_str = stmt_data.get("exported_at")
                if isinstance(exported_at_str, str):
                    statement.exported_at = datetime.fromisoformat(
                        exported_at_str.replace("Z", "+00:00")
                    )
                else:
                    statement.exported_at = exported_at_str

            if stmt_data.get("created_at"):
                created_at_str = stmt_data.get("created_at")
                if isinstance(created_at_str, str):
                    statement.created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                else:
                    statement.created_at = created_at_str

            if stmt_data.get("updated_at"):
                updated_at_str = stmt_data.get("updated_at")
                if isinstance(updated_at_str, str):
                    statement.updated_at = datetime.fromisoformat(
                        updated_at_str.replace("Z", "+00:00")
                    )
                else:
                    statement.updated_at = updated_at_str

            # Only set JSON fields if they have actual values (not None/null)
            pdp_deltas = stmt_data.get("pdp_deltas")
            if pdp_deltas is not None:
                statement.pdp_deltas = pdp_deltas

            custom_prompts = stmt_data.get("custom_prompts")
            if custom_prompts is not None:
                statement.custom_prompts = custom_prompts

            db.session.add(statement)
            db.session.flush()

            # Import feedback if present
            feedbacks_data = stmt_data.get("feedbacks")
            if feedbacks_data:
                for feedback_data in feedbacks_data:
                    feedback = Feedback(
                        statement_id=statement.id,
                        auditor_id=feedback_data.get(
                            "auditor_id", current_user.username
                        ),
                        feedback_type=feedback_data.get("feedback_type", "extraction"),
                        thumbs_down=feedback_data.get("thumbs_down", False),
                        comment=feedback_data.get("comment"),
                        edited_extraction=feedback_data.get("edited_extraction"),
                        approved=feedback_data.get("approved", False),
                        approved_by=feedback_data.get("approved_by"),
                        rejection_reason=feedback_data.get("rejection_reason"),
                    )

                    if feedback_data.get("approved_at"):
                        approved_at_str = feedback_data.get("approved_at")
                        if isinstance(approved_at_str, str):
                            feedback.approved_at = datetime.fromisoformat(
                                approved_at_str.replace("Z", "+00:00")
                            )
                        else:
                            feedback.approved_at = approved_at_str

                    if feedback_data.get("exported_at"):
                        exported_at_str = feedback_data.get("exported_at")
                        if isinstance(exported_at_str, str):
                            feedback.exported_at = datetime.fromisoformat(
                                exported_at_str.replace("Z", "+00:00")
                            )
                        else:
                            feedback.exported_at = exported_at_str

                    if feedback_data.get("created_at"):
                        created_at_str = feedback_data.get("created_at")
                        if isinstance(created_at_str, str):
                            feedback.created_at = datetime.fromisoformat(
                                created_at_str.replace("Z", "+00:00")
                            )
                        else:
                            feedback.created_at = created_at_str

                    if feedback_data.get("updated_at"):
                        updated_at_str = feedback_data.get("updated_at")
                        if isinstance(updated_at_str, str):
                            feedback.updated_at = datetime.fromisoformat(
                                updated_at_str.replace("Z", "+00:00")
                            )
                        else:
                            feedback.updated_at = updated_at_str

                    db.session.add(feedback)

    db.session.commit()

    needs_processing = any(
        stmt.get("speaker_id") in speaker_id_map
        and not stmt.get("pdp_deltas")
        and stmt.get("text")
        for stmt in json_data.get("statements", [])
    )

    # Note: Extraction is not automatically started for imported discussions
    # Users must manually trigger extraction via the audit interface
    if needs_processing:
        # Count statements that need processing (no pdp_deltas and has text)
        statements_to_process = [
            s
            for s in json_data.get("statements", [])
            if not s.get("pdp_deltas") and s.get("text")
        ]
        num_statements_to_process = len(statements_to_process)
        _log.info(
            f"Discussion {discussion.id} has "
            f"{num_statements_to_process} statements that need processing - extraction can be triggered manually"
        )

    _log.info(
        f"Imported discussion {discussion.id} from JSON for user {target_user_id}"
    )

    return jsonify(
        {
            "success": True,
            "id": discussion.id,
            "discussion_id": discussion.id,
            "user_id": target_user_id,
            "message": "Discussion imported successfully",
            **discussion.as_dict(include=["statements", "speakers"]),
        }
    )


@bp.route("/import", methods=["POST"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def import_discussion():
    request_data = request.get_json()
    discussion_data = request_data["discussion"]
    diagram_id = request_data.get("diagram_id")

    return _create_import({"diagram_id": diagram_id, "json_data": discussion_data})


@bp.route("/transcript", methods=["POST"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def create_from_transcript():
    diagram_id = request.args.get("diagram_id", type=int)
    title = request.args.get("title")
    transcript_data = request.get_json()

    return _create_assembly_ai_transcript(
        {"diagram_id": diagram_id, "title": title, "transcript_data": transcript_data}
    )


@bp.route("/upload_token")
@minimum_role(btcopilot.ROLE_AUDITOR)
def upload_token():
    """Get AssemblyAI API key for client-side upload"""
    api_key = os.getenv("ASSEMBLYAI_API_KEY")

    if not api_key:
        return (
            jsonify({"success": False, "error": "AssemblyAI API key not configured"}),
            500,
        )

    return jsonify({"success": True, "api_key": api_key})


@bp.route("/<int:discussion_id>")
@minimum_role(btcopilot.ROLE_AUDITOR)
def audit(discussion_id):
    """View a specific discussion for audit (from audit system)"""
    from sqlalchemy.orm import joinedload, subqueryload

    current_user = auth.current_user()

    discussion = (
        Discussion.query
        .options(
            subqueryload(Discussion.statements).joinedload(Statement.speaker)
        )
        .get_or_404(discussion_id)
    )
    auditor_id = get_auditor_id(request, session)

    selected_auditor = request.args.get("selected_auditor")

    statements_with_feedback = []
    # Sort statements by order for proper display
    sorted_statements = sorted(
        discussion.statements, key=lambda s: (s.order or 0, s.id)
    )

    from collections import defaultdict
    all_feedback = (
        Feedback.query
        .join(Statement)
        .filter(Statement.discussion_id == discussion_id)
        .all()
    )
    feedback_by_statement = defaultdict(lambda: {"conversation": [], "extraction": []})
    for fb in all_feedback:
        feedback_by_statement[fb.statement_id][fb.feedback_type].append(fb)

    cumulative_people_by_id = {}
    cumulative_events_by_id = {}

    for stmt in sorted_statements:
        stmt_feedback = feedback_by_statement[stmt.id]

        if current_user.has_role(btcopilot.ROLE_ADMIN):
            if selected_auditor and selected_auditor != "AI":
                # Admin filtering to specific auditor
                conv_feedback = next(
                    (fb for fb in stmt_feedback["conversation"] if fb.auditor_id == selected_auditor),
                    None
                )
                ext_feedback = next(
                    (fb for fb in stmt_feedback["extraction"] if fb.auditor_id == selected_auditor),
                    None
                )
            elif selected_auditor == "AI":
                # AI selected - don't show any feedback, only AI extraction
                conv_feedback = []
                ext_feedback = []
            else:
                # Admin sees all feedback (no auditor selected)
                conv_feedback = sorted(
                    stmt_feedback["conversation"],
                    key=lambda fb: (fb.auditor_id or "", fb.created_at)
                )
                ext_feedback = sorted(
                    stmt_feedback["extraction"],
                    key=lambda fb: (fb.auditor_id or "", fb.created_at)
                )
        else:
            # Auditor sees only their own feedback
            conv_feedback = next(
                (fb for fb in stmt_feedback["conversation"] if fb.auditor_id == auditor_id),
                None
            )
            ext_feedback = next(
                (fb for fb in stmt_feedback["extraction"] if fb.auditor_id == auditor_id),
                None
            )

        # Get stored PDP deltas - ONLY show for Subject statements (where extraction data is stored)
        pdp_deltas = None
        pdp_deltas_model = None
        deltas_source = None

        if stmt.speaker and stmt.speaker.type == SpeakerType.Subject:
            # Determine which deltas to use: AI or selected auditor's
            if selected_auditor and selected_auditor != "AI":
                # Use selected human auditor's corrections
                if (
                    ext_feedback
                    and hasattr(ext_feedback, "edited_extraction")
                    and ext_feedback.edited_extraction
                ):
                    deltas_source = ext_feedback.edited_extraction
                elif stmt.pdp_deltas:
                    # Fallback to AI deltas if auditor has no edited_extraction yet
                    deltas_source = stmt.pdp_deltas
            elif stmt.pdp_deltas:
                # Use AI deltas (default)
                deltas_source = stmt.pdp_deltas

            if deltas_source:
                try:
                    pdp_deltas = {
                        "people": deltas_source.get("people", []),
                        "events": deltas_source.get("events", []),
                        "deletes": deltas_source.get("delete", []),
                    }

                    def filter_person_fields(person_data):
                        valid_fields = {'id', 'name', 'last_name', 'spouses', 'parent_a', 'parent_b', 'confidence'}
                        return {k: v for k, v in person_data.items() if k in valid_fields}

                    def filter_event_fields(event_data):
                        valid_fields = {'id', 'kind', 'person', 'spouse', 'child', 'description',
                                       'dateTime', 'endDateTime', 'symptom', 'anxiety', 'relationship',
                                       'relationshipTargets', 'relationshipTriangles', 'confidence'}
                        return {k: v for k, v in event_data.items() if k in valid_fields}

                    pdp_deltas_model = PDPDeltas(
                        people=[
                            Person(**filter_person_fields(person_data))
                            for person_data in pdp_deltas.get("people", [])
                        ],
                        events=[
                            Event(**filter_event_fields(event_data))
                            for event_data in pdp_deltas.get("events", [])
                        ],
                        delete=pdp_deltas.get("deletes", []),
                    )
                except (ValueError, KeyError, TypeError) as e:
                    _log.warning(f"Error parsing deltas for statement {stmt.id}: {e}")

        # Get person name if speaker is mapped to a person
        person_name = None
        if stmt.speaker and stmt.speaker.person_id and discussion.diagram:
            database = discussion.diagram.get_diagram_data()
            if database.people:
                for person in database.people:
                    if person["id"] == stmt.speaker.person_id:
                        person_name = person["name"]
                        break

        if pdp_deltas_model:
            for person in pdp_deltas_model.people:
                cumulative_people_by_id[person.id] = person

            for event in pdp_deltas_model.events:
                cumulative_events_by_id[event.id] = event

            for delete_id in pdp_deltas_model.delete:
                cumulative_people_by_id.pop(delete_id, None)
                cumulative_events_by_id.pop(delete_id, None)

        cumulative_pdp = {
            "people": [asdict(p) for p in cumulative_people_by_id.values()],
            "events": [asdict(e) for e in cumulative_events_by_id.values()],
        } if cumulative_people_by_id or cumulative_events_by_id else None

        if 633 <= stmt.id <= 637:
            _log.debug(f"Stmt {stmt.id}: speaker_type={stmt.speaker.type if stmt.speaker else None}, "
                      f"has_pdp_deltas_model={pdp_deltas_model is not None}, "
                      f"deltas={pdp_deltas if pdp_deltas_model else None}, "
                      f"cumulative_people={len(cumulative_people_by_id)}, "
                      f"cumulative_events={len(cumulative_events_by_id)}, "
                      f"cumulative_pdp={'set' if cumulative_pdp else 'None'}")

        # Handle different feedback data structures for admin vs auditor
        if current_user.has_role(btcopilot.ROLE_ADMIN):
            # When specific auditor selected, feedback is single object; otherwise it's a list
            if selected_auditor and selected_auditor != "AI":
                # Single auditor selected - feedback is single object
                all_conv_feedback = [conv_feedback] if conv_feedback else []
                all_ext_feedback = [ext_feedback] if ext_feedback else []
            else:
                # All auditors or AI - feedback is already a list
                all_conv_feedback = conv_feedback if conv_feedback else []
                all_ext_feedback = ext_feedback if ext_feedback else []

            # Convert feedback objects to dictionaries using as_dict() method
            all_conv_feedback_dict = [
                feedback.as_dict(exclude=["statement", "updated_at"])
                for feedback in all_conv_feedback
            ]

            all_ext_feedback_dict = [
                feedback.as_dict(exclude=["statement", "updated_at"])
                for feedback in all_ext_feedback
            ]

            # Find admin's own feedback for reset button logic
            admin_ext_feedback = next(
                (f for f in all_ext_feedback if f.auditor_id == auditor_id), None
            )

            # Admin gets arrays of all feedback
            statements_with_feedback.append(
                {
                    "statement": stmt,
                    "has_conv_feedback": len(all_conv_feedback) > 0,
                    "has_ext_feedback": len(all_ext_feedback) > 0,
                    "conv_feedback": (
                        all_conv_feedback[0] if all_conv_feedback else None
                    ),
                    "ext_feedback": (all_ext_feedback[0] if all_ext_feedback else None),
                    "all_conv_feedback": all_conv_feedback,
                    "all_ext_feedback": all_ext_feedback,
                    "all_conv_feedback_dict": all_conv_feedback_dict,
                    "all_ext_feedback_dict": all_ext_feedback_dict,
                    "admin_ext_feedback": admin_ext_feedback,
                    "pdp_deltas": pdp_deltas,
                    "person_name": person_name,
                    "cumulative_pdp": cumulative_pdp,
                    "approved": stmt.approved,
                    "approved_by": stmt.approved_by,
                    "approved_at": (
                        stmt.approved_at.isoformat() if stmt.approved_at else None
                    ),
                }
            )
        else:
            # Auditor gets single feedback objects (existing behavior)
            statements_with_feedback.append(
                {
                    "statement": stmt,
                    "has_conv_feedback": conv_feedback is not None,
                    "has_ext_feedback": ext_feedback is not None,
                    "conv_feedback": conv_feedback,
                    "ext_feedback": ext_feedback,
                    "pdp_deltas": pdp_deltas,
                    "person_name": person_name,
                    "cumulative_pdp": cumulative_pdp,
                    "approved": stmt.approved,
                    "approved_by": stmt.approved_by,
                    "approved_at": (
                        stmt.approved_at.isoformat() if stmt.approved_at else None
                    ),
                }
            )

    # Mark the last expert statement for prompt editing
    expert_statements = [
        item
        for item in statements_with_feedback
        if item["statement"].speaker
        and item["statement"].speaker.type == SpeakerType.Expert
    ]
    if expert_statements:
        expert_statements[-1]["is_last_expert"] = True

    breadcrumbs = get_breadcrumbs("thread")
    breadcrumbs.append(
        {
            "title": f"{discussion.user.username if discussion.user else 'Unknown User'} - Discussion #{discussion.id}",
            "url": None,
        }
    )

    # Get current user for navigation
    current_user = auth.current_user()

    # Create speaker mappings for CSS class assignment
    # Sort speakers by ID to maintain consistent ordering regardless of type changes
    unique_speakers = sorted(
        {stmt.speaker for stmt in sorted_statements if stmt.speaker}, key=lambda s: s.id
    )
    subject_speakers = [s for s in unique_speakers if s.type == SpeakerType.Subject]
    expert_speakers = [s for s in unique_speakers if s.type == SpeakerType.Expert]

    # Create ordered mappings: speaker_id -> order (1-based)
    subject_speaker_map = {
        speaker.id: idx + 1 for idx, speaker in enumerate(subject_speakers)
    }
    expert_speaker_map = {
        speaker.id: idx + 1 for idx, speaker in enumerate(expert_speakers)
    }

    # Create user mapping for admin display and auditor dropdown
    auditor_user_map = {}
    auditor_options = []

    if current_user.has_role(btcopilot.ROLE_ADMIN):
        # Query ALL extraction feedback for this discussion to get complete auditor list
        all_discussion_feedback = (
            Feedback.query.filter_by(feedback_type="extraction")
            .join(Statement)
            .filter(Statement.discussion_id == discussion_id)
            .all()
        )

        # Collect all unique auditor IDs
        all_auditor_ids = set(f.auditor_id for f in all_discussion_feedback)

        # Fetch user info for each auditor ID
        for auditor_id_str in all_auditor_ids:
            try:
                # Skip test auditor IDs that aren't user IDs
                if (
                    auditor_id_str.startswith("auditor")
                    or auditor_id_str == "anonymous"
                ):
                    auditor_user_map[auditor_id_str] = auditor_id_str
                    continue

                user_id = int(auditor_id_str)
                user = User.query.get(user_id)
                if user:
                    auditor_user_map[auditor_id_str] = user.username
                else:
                    auditor_user_map[auditor_id_str] = f"User {auditor_id_str}"
            except (ValueError, TypeError):
                # Handle non-integer auditor IDs (test cases)
                auditor_user_map[auditor_id_str] = auditor_id_str

        # Build dropdown options: AI + all human auditors
        auditor_options.append({"id": "AI", "name": "AI"})
        for auditor_id_str in sorted(auditor_user_map.keys()):
            auditor_options.append(
                {"id": auditor_id_str, "name": auditor_user_map[auditor_id_str]}
            )

    return render_template(
        "discussion_audit.html",
        discussion=discussion,
        statements=statements_with_feedback,
        current_auditor=auditor_id,
        breadcrumbs=breadcrumbs,
        current_user=current_user,
        btcopilot=btcopilot,
        unique_speakers=unique_speakers,
        subject_speaker_map=subject_speaker_map,
        expert_speaker_map=expert_speaker_map,
        auditor_user_map=auditor_user_map,
        auditor_options=auditor_options,
        selected_auditor=selected_auditor,
    )


@bp.route("/<int:discussion_id>/extract", methods=["POST"])
@minimum_role(btcopilot.ROLE_ADMIN)
def extract(discussion_id: int):
    """Trigger background extraction for a specific discussion"""

    # Get the discussion
    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        return jsonify({"error": "Discussion not found"}), 404

    statement_count = Statement.query.filter_by(discussion_id=discussion_id).count()

    # Set extracting to True
    discussion.extracting = True
    db.session.commit()

    from btcopilot.extensions import celery

    celery.send_task("extract_discussion_statements", args=[discussion_id])

    _log.info(
        f"Extraction triggered - "
        f"discussion_id: {discussion_id}, "
        f"total_statements: {statement_count}"
    )

    return jsonify({"success": True, "message": "Extraction triggered successfully"})


@bp.route("/<int:discussion_id>/progress", methods=["GET"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def progress(discussion_id: int):
    """Get extraction progress for statements in a discussion"""
    current_user = auth.current_user()

    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        return abort(404)

    # Check permissions - user can only see their own discussions or auditors can see any
    if discussion.user_id != current_user.id and not current_user.has_role(
        btcopilot.ROLE_AUDITOR
    ):
        return abort(403)

    # Count Subject statements that need processing
    total_subject_statements = (
        Statement.query.join(Speaker)
        .filter(
            Statement.discussion_id == discussion_id,
            Speaker.type == SpeakerType.Subject,
            Statement.text.isnot(None),
            Statement.text != "",
        )
        .count()
    )

    # Count processed Subject statements (those with pdp_deltas)
    # Note: We need to check for both not None AND not empty dict/list
    # because SQLAlchemy's JSON column comparison can be unreliable
    all_subject_statements = (
        Statement.query.join(Speaker)
        .filter(
            Statement.discussion_id == discussion_id,
            Speaker.type == SpeakerType.Subject,
            Statement.text.isnot(None),
            Statement.text != "",
        )
        .all()
    )

    # Count statements that actually have pdp_deltas content
    processed_statements = sum(
        1
        for stmt in all_subject_statements
        if stmt.pdp_deltas is not None and stmt.pdp_deltas != {}
    )

    # Calculate pending statements
    pending_statements = total_subject_statements - processed_statements

    # Check if there's a statement currently being processed
    # (This is a simple check - in production you might want to track this more explicitly)
    is_processing = pending_statements > 0

    return jsonify(
        {
            "total": total_subject_statements,
            "processed": processed_statements,
            "pending": pending_statements,
            "is_processing": is_processing,
            "extracting": discussion.extracting,
            "percent_complete": (
                round((processed_statements / total_subject_statements) * 100, 1)
                if total_subject_statements > 0
                else 100
            ),
        }
    )


@bp.route("/<int:discussion_id>/export", methods=["GET"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def export(discussion_id: int):
    """Export a discussion as JSON file

    Query parameters:
    - mode: 'statements' or 'full' (default: 'full')
        - statements: Export only discussion metadata and statements (no extracted data)
        - full: Export everything including AI extractions and user corrections
    """
    from flask import request

    current_user = auth.current_user()
    mode = request.args.get("mode", "full")

    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        return abort(404)

    # Check permissions - user can only export their own discussions or auditors can export any
    if discussion.user_id != current_user.id and not current_user.has_role(
        btcopilot.ROLE_AUDITOR
    ):
        return abort(403)

    # Get discussion data with statements, speakers, and feedbacks
    discussion_data = discussion.as_dict(include=["statements", "speakers"])

    # Include feedbacks for each statement in full mode
    if mode == "full":
        if "statements" in discussion_data:
            for statement_dict in discussion_data["statements"]:
                statement_id = statement_dict.get("id")
                if statement_id:
                    statement_obj = Statement.query.get(statement_id)
                    if statement_obj and statement_obj.feedbacks:
                        statement_dict["feedbacks"] = [
                            fb.as_dict() for fb in statement_obj.feedbacks
                        ]
    elif mode == "statements":
        # Remove pdp_deltas and other extracted data from all statements
        if "statements" in discussion_data:
            for statement in discussion_data["statements"]:
                if "pdp_deltas" in statement:
                    del statement["pdp_deltas"]
                if "approved" in statement:
                    del statement["approved"]
                if "approved_by" in statement:
                    del statement["approved_by"]
                if "approved_at" in statement:
                    del statement["approved_at"]
                if "exported_at" in statement:
                    del statement["exported_at"]

    # Create JSON response with custom encoder for datetime objects
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            return super().default(obj)

    json_data = json.dumps(
        discussion_data, cls=DateTimeEncoder, indent=2, ensure_ascii=False
    )
    response = make_response(json_data)
    response.headers["Content-Type"] = "application/json"

    # Update filename based on mode
    filename_suffix = "_statements" if mode == "statements" else "_full"
    response.headers["Content-Disposition"] = (
        f"attachment; filename=discussion_{discussion_id}{filename_suffix}.json"
    )

    return response


@bp.route("/<int:discussion_id>/clear-extracted", methods=["POST"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def clear_extracted_data(discussion_id):
    """Clear all extracted PDP data from a discussion"""
    current_user = auth.current_user()

    discussion = Discussion.query.get_or_404(discussion_id)
    discussion_owner = discussion.user.username if discussion.user else "Unknown"

    # Count statements with extracted data before clearing
    statements_with_data = (
        Statement.query.filter_by(discussion_id=discussion_id)
        .filter(Statement.pdp_deltas.isnot(None))
        .count()
    )

    # Clear PDP deltas from all statements in the discussion
    # Use synchronize_session='fetch' to ensure SQLAlchemy updates its cache
    Statement.query.filter_by(discussion_id=discussion_id).update(
        {"pdp_deltas": None}, synchronize_session=False
    )

    # Reset extraction progress by setting extracting to False
    # This ensures UI doesn't show extraction in progress
    discussion.extracting = False

    # Note: Celery tasks are automatically managed and don't need manual cancellation
    _log.info(f"Cleared extraction state for discussion {discussion_id}")

    # Clear PDP data from the diagram if it exists
    if discussion.diagram:
        database = discussion.diagram.get_diagram_data()
        database.pdp.people = []
        database.pdp.events = []

        # Ensure default User and Assistant people always exist for speaker mapping
        user_exists = any(person["id"] == 1 for person in database.people)
        assistant_exists = any(person["id"] == 2 for person in database.people)

        if not user_exists:
            user_person = Person(id=1, name="User")
            database.people.append(asdict(user_person))

        if not assistant_exists:
            assistant_person = Person(id=2, name="Assistant")
            database.people.append(asdict(assistant_person))

        # Ensure last_id accounts for default people
        database.last_id = max(database.last_id, 2)

        discussion.diagram.set_diagram_data(database)

    db.session.commit()

    # Expire all statements to force fresh load from DB on next access
    # This ensures cached JSON column values are refreshed
    for stmt in discussion.statements:
        db.session.expire(stmt)

    _log.info(
        f"Admin {current_user.username} cleared extracted data from discussion {discussion_id} owned by {discussion_owner} "
        f"- {statements_with_data} statements had extracted data"
    )

    return jsonify(
        {
            "success": True,
            "message": f"Cleared extracted data from {statements_with_data} statements",
        }
    )


@bp.route("/<int:discussion_id>", methods=["PATCH"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def update_discussion(discussion_id):
    """Update discussion attributes"""
    from datetime import date

    current_user = auth.current_user()
    data = request.json

    discussion = Discussion.query.get_or_404(discussion_id)

    updatable_fields = {
        "discussion_date": lambda v: date.fromisoformat(v) if v else None,
        "summary": lambda v: v,
        "last_topic": lambda v: v,
        "extracting": lambda v: bool(v) if v is not None else None,
    }

    updated_fields = []
    errors = []

    for field, value in data.items():
        if field not in updatable_fields:
            errors.append(f"Field '{field}' is not updatable")
            continue

        try:
            converted_value = updatable_fields[field](value)
            setattr(discussion, field, converted_value)
            updated_fields.append(field)
        except (ValueError, TypeError) as e:
            errors.append(f"Invalid value for '{field}': {str(e)}")

    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    if not updated_fields:
        return jsonify({"success": False, "error": "No valid fields to update"}), 400

    db.session.commit()

    _log.info(
        f"User {current_user.username} updated discussion {discussion_id}: {', '.join(updated_fields)}"
    )

    return jsonify({"success": True, "updated_fields": updated_fields})


@bp.route("/<int:discussion_id>", methods=["DELETE"])
def delete(discussion_id):
    """Delete a specific discussion and all its messages"""
    current_user = auth.current_user()

    discussion = Discussion.query.get_or_404(discussion_id)
    discussion_owner = discussion.user.username if discussion.user else "Unknown"

    if current_user.id != discussion.user_id and not current_user.has_role(
        btcopilot.ROLE_ADMIN
    ):
        return abort(403)

    statement_count = len(discussion.statements)
    speaker_count = len(discussion.speakers)

    # Manual cascade delete
    statement_ids = [stmt.id for stmt in discussion.statements]

    # Delete all audit feedback for statements in this discussion
    feedback_count = 0
    if statement_ids:
        feedback_count = Feedback.query.filter(
            Feedback.statement_id.in_(statement_ids)
        ).count()
        Feedback.query.filter(Feedback.statement_id.in_(statement_ids)).delete(
            synchronize_session=False
        )

    # Delete all statements in the discussion
    Statement.query.filter_by(discussion_id=discussion_id).delete(
        synchronize_session=False
    )

    # Delete all speakers in the discussion
    Speaker.query.filter_by(discussion_id=discussion_id).delete(
        synchronize_session=False
    )

    # Delete the discussion
    db.session.expunge(discussion)
    Discussion.query.filter_by(id=discussion_id).delete(synchronize_session=False)

    db.session.commit()

    _log.info(
        f"Admin {current_user.username} deleted discussion {discussion_id} owned by {discussion_owner} "
        f"with {statement_count} statements, {speaker_count} speakers, and {feedback_count} feedback records"
    )

    return jsonify(
        {
            "success": True,
            "message": f"Discussion {discussion_id} deleted: {statement_count} statements, "
            f"{speaker_count} speakers, and {feedback_count} feedback records removed",
        }
    )
