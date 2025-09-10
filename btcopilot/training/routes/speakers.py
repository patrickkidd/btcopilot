import logging
from flask import Blueprint, request, jsonify

from ..auth import require_auditor_or_admin, get_current_user
from ...extensions import db
from ..models import Speaker, SpeakerType

_log = logging.getLogger(__name__)

# Create the speakers blueprint
speakers_bp = Blueprint(
    "speakers",
    __name__,
    url_prefix="/speakers",
)


@speakers_bp.route("/<int:speaker_id>", methods=["PUT"])
@require_auditor_or_admin
def update(speaker_id):
    """Update a speaker's properties, optionally creating a new person"""

    data = request.json
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    speaker = Speaker.query.get(speaker_id)
    if not speaker:
        return jsonify({"error": "Speaker not found"}), 404

    updated_fields = []
    created_person = None

    # Handle person creation/mapping
    if "person_id" in data:
        # If creating new person (when name is also provided)
        if "name" in data and data.get("person_id") == -1:
            # Get the diagram from the speaker's discussion
            if not speaker.discussion or not speaker.discussion.diagram_id:
                return (
                    jsonify(
                        {"error": "Speaker's discussion has no associated diagram"}
                    ),
                    400,
                )

            try:
                from fdserver.models import Diagram
                from fdserver.therapist.database import Person
                
                diagram = Diagram.query.get(speaker.discussion.diagram_id)
                if not diagram:
                    return jsonify({"error": "Associated diagram not found"}), 404
                    
                database = diagram.get_database()

                person = Person(
                    name=data["name"],
                    birthDate="",
                    spouses=[],
                    offspring=[],
                    parents=[],
                    confidence=1.0,
                )
                database.add_person(person)
                diagram.set_database(database)
                db.session.add(diagram)
                speaker.person_id = person.id
                created_person = person
                updated_fields.append(f"person_id to {person.id} (created '{person.name}')")

                _log.info(
                    f"Created person '{person.name}' with ID {person.id} in diagram {diagram.id}"
                )
                
            except ImportError:
                return jsonify({"error": "Person creation requires fdserver integration"}), 400
        else:
            # Just mapping to existing person
            speaker.person_id = data["person_id"]
            updated_fields.append(f"person_id to {data['person_id']}")

    # Update speaker name if provided (and not used for person creation)
    if "name" in data and not ("person_id" in data and data.get("person_id") == -1):
        speaker.name = data["name"]
        updated_fields.append(f"name to {data['name']}")

    # Update speaker type if provided
    if "type" in data:
        speaker_type = data["type"]
        if speaker_type not in ["expert", "subject"]:
            return (
                jsonify(
                    {"error": "Invalid speaker type. Must be 'expert' or 'subject'"}
                ),
                400,
            )

        speaker.type = (
            SpeakerType.Expert if speaker_type == "expert" else SpeakerType.Subject
        )
        updated_fields.append(f"type to {speaker_type}")

    if not updated_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    db.session.commit()

    _log.info(f"Updated speaker {speaker_id}: {', '.join(updated_fields)}")

    response = {
        "success": True,
        "speaker_id": speaker_id,
        "updated_fields": updated_fields,
        "message": f"Speaker updated: {', '.join(updated_fields)}",
    }

    if created_person:
        response["person_id"] = created_person.id
        response["message"] = (
            f"Person '{created_person.name}' created and speaker mapped"
        )

    return jsonify(response)