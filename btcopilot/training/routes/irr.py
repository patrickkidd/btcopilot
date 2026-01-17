from dataclasses import asdict

from flask import Blueprint, abort, jsonify, render_template, request, url_for

import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Speaker, SpeakerType, Statement
from btcopilot.training.irr_metrics import (
    calculate_discussion_irr,
    calculate_statement_irr,
    get_multi_coder_discussions,
    get_statement_extractions,
    safe_avg,
)
from btcopilot.training.models import ReconciliationNote
from btcopilot.training.utils import get_discussion_view_menu

bp = Blueprint("irr", __name__, url_prefix="/irr")

SARF_FIELDS = ["symptom", "anxiety", "relationship", "functioning"]
EVENT_FIELDS = ["description", "dateTime", "dateCertainty"]
PERSON_FIELDS = ["gender", "last_name", "parents"]


def _field_coded(obj: dict, field: str) -> bool:
    """Check if a field has a coded value."""
    val = obj.get(field)
    if hasattr(val, "value"):
        val = val.value
    return val not in (None, "-", "")


def _compute_sarf_disagreements(extractions: dict) -> dict:
    """Compute which event field values disagree across coders for a statement.

    Returns dict mapping "coder|event_idx|field" -> 'disagree' (only disagreements stored)
    """
    if len(extractions) < 2:
        return {}

    compared_fields = ["kind", "person"] + SARF_FIELDS + EVENT_FIELDS
    disagreements = {}

    # Get max events across all coders
    max_events = max(
        (len(ext.get("events", []) or []) for ext in extractions.values()), default=0
    )

    for event_idx in range(max_events):
        for field in compared_fields:
            # Collect values from all coders for this event/field combination
            values = {}
            for coder, ext in extractions.items():
                events = ext.get("events", []) or []
                if event_idx < len(events):
                    event = events[event_idx]
                    val = event.get(field)
                    # Normalize: extract .value if it's an enum-like object
                    if hasattr(val, "value"):
                        val = val.value
                    # Treat None, '-', and '' as equivalent
                    if val is None or val == "-" or val == "":
                        val = None
                    values[coder] = val
                else:
                    values[coder] = None

            # Check if all values agree
            unique_vals = set(values.values())
            has_disagreement = len(unique_vals) > 1

            if has_disagreement:
                for coder in values:
                    # Use string key for Jinja2 compatibility
                    key = f"{coder}|{event_idx}|{field}"
                    disagreements[key] = "disagree"

    return disagreements


def _compute_person_disagreements(extractions: dict) -> dict:
    """Compute which person field values disagree across coders for a statement.

    Returns dict mapping "coder|person_idx|field" -> 'disagree' (only disagreements stored)
    """
    if len(extractions) < 2:
        return {}

    disagreements = {}

    max_people = max(
        (len(ext.get("people", []) or []) for ext in extractions.values()), default=0
    )

    for person_idx in range(max_people):
        for field in PERSON_FIELDS:
            values = {}
            for coder, ext in extractions.items():
                people = ext.get("people", []) or []
                if person_idx < len(people):
                    person = people[person_idx]
                    val = person.get(field)
                    if hasattr(val, "value"):
                        val = val.value
                    if val is None or val == "-" or val == "":
                        val = None
                    values[coder] = val
                else:
                    values[coder] = None

            unique_vals = set(values.values())
            has_disagreement = len(unique_vals) > 1

            if has_disagreement:
                for coder in values:
                    key = f"{coder}|{person_idx}|{field}"
                    disagreements[key] = "disagree"

    return disagreements


@bp.route("/")
@minimum_role(btcopilot.ROLE_AUDITOR)
def index():
    multi_coder = get_multi_coder_discussions()

    discussions_data = []
    for discussion_id, coder_count, coder_ids in multi_coder:
        discussion = Discussion.query.get(discussion_id)
        if not discussion:
            continue

        irr = calculate_discussion_irr(discussion_id)
        discussions_data.append(
            {
                "discussion": discussion,
                "coder_count": coder_count,
                "coders": irr.coders if irr else coder_ids,
                "statement_count": irr.coded_statement_count if irr else 0,
                "avg_events_f1": irr.avg_events_f1 if irr else None,
                "avg_aggregate_f1": irr.avg_aggregate_f1 if irr else None,
                "avg_symptom_kappa": irr.avg_symptom_kappa if irr else None,
                "avg_anxiety_kappa": irr.avg_anxiety_kappa if irr else None,
                "avg_relationship_kappa": irr.avg_relationship_kappa if irr else None,
                "avg_functioning_kappa": irr.avg_functioning_kappa if irr else None,
            }
        )

    breadcrumbs = [
        {"title": "Coding", "url": url_for("training.audit.index")},
        {"title": "Inter-Rater Reliability", "url": None},
    ]

    return render_template(
        "training/irr_index.html",
        discussions=discussions_data,
        breadcrumbs=breadcrumbs,
        current_user=auth.current_user(),
    )


@bp.route("/discussion/<int:discussion_id>")
@minimum_role(btcopilot.ROLE_AUDITOR)
def discussion(discussion_id: int):
    disc = Discussion.query.get_or_404(discussion_id)

    irr = calculate_discussion_irr(discussion_id)
    if not irr:
        abort(404, "No multi-coder data available for this discussion")

    statements = (
        Statement.query.filter_by(discussion_id=discussion_id)
        .join(Speaker)
        .filter(Speaker.type == SpeakerType.Subject)
        .order_by(Statement.order)
        .all()
    )
    statement_irrs = []

    # Build cumulative people per coder across all statements
    cumulative_people_by_coder: dict[str, dict[int, dict]] = {}

    for stmt in statements:
        stmt_irr = calculate_statement_irr(stmt.id)
        extractions = get_statement_extractions(stmt.id)
        extractions_dict = {coder: asdict(pdp) for coder, pdp in extractions.items()}
        disagreements = _compute_sarf_disagreements(extractions_dict)
        person_disagreements = _compute_person_disagreements(extractions_dict)
        disagreements.update(person_disagreements)
        note = ReconciliationNote.query.filter_by(statement_id=stmt.id).first()

        # Accumulate people per coder (like coding page does for single auditor)
        for coder, ext in extractions_dict.items():
            if coder not in cumulative_people_by_coder:
                cumulative_people_by_coder[coder] = {}
            for person in ext.get("people", []) or []:
                pid = person.get("id")
                if pid:
                    cumulative_people_by_coder[coder][pid] = person

        # Build all_people from cumulative data across all coders
        all_people = {}
        for coder_people in cumulative_people_by_coder.values():
            for pid, person in coder_people.items():
                if pid not in all_people:
                    all_people[pid] = person

        # Compute which fields are coded by ANY coder for each event index
        # Key: "event_idx|field" -> True if any coder coded it
        any_coded = {}
        max_events = max(
            (len(ext.get("events", []) or []) for ext in extractions_dict.values()),
            default=0,
        )
        for event_idx in range(max_events):
            for field in SARF_FIELDS + EVENT_FIELDS:
                if any(
                    _field_coded(events[event_idx], field)
                    for ext in extractions_dict.values()
                    if (events := ext.get("events", []) or [])
                    and event_idx < len(events)
                ):
                    any_coded[f"{event_idx}|{field}"] = True

        # Compute which person fields are coded by ANY coder
        # Key: "person_idx|field" -> True if any coder coded it
        person_any_coded = {}
        max_people = max(
            (len(ext.get("people", []) or []) for ext in extractions_dict.values()),
            default=0,
        )
        for person_idx in range(max_people):
            for field in PERSON_FIELDS:
                if any(
                    _field_coded(people[person_idx], field)
                    for ext in extractions_dict.values()
                    if (people := ext.get("people", []) or [])
                    and person_idx < len(people)
                ):
                    person_any_coded[f"{person_idx}|{field}"] = True

        statement_irrs.append(
            {
                "statement": stmt,
                "irr": stmt_irr,
                "extractions": extractions_dict,
                "disagreements": disagreements,
                "note": note,
                "all_people": all_people,
                "any_coded": any_coded,
                "person_any_coded": person_any_coded,
            }
        )

    unique_speakers = (
        Speaker.query.filter(Speaker.discussion_id == discussion_id)
        .order_by(Speaker.id)
        .all()
    )
    subject_speakers = [s for s in unique_speakers if s.type == SpeakerType.Subject]
    expert_speakers = [s for s in unique_speakers if s.type == SpeakerType.Expert]
    subject_speaker_map = {
        speaker.id: idx + 1 for idx, speaker in enumerate(subject_speakers)
    }
    expert_speaker_map = {
        speaker.id: idx + 1 for idx, speaker in enumerate(expert_speakers)
    }

    menu, active_title = get_discussion_view_menu(discussion_id, "irr")
    breadcrumbs = [
        {"title": "Coding", "url": url_for("training.audit.index")},
        {"title": "IRR", "url": url_for("training.irr.index")},
        {
            "title": disc.summary or f"Discussion {discussion_id}",
            "url": url_for("training.discussions.audit", discussion_id=discussion_id),
        },
        {"title": active_title, "menu": menu},
    ]

    return render_template(
        "training/irr_discussion.html",
        discussion=disc,
        discussion_irr=irr,
        statement_irrs=statement_irrs,
        coders=sorted(irr.coders),
        subject_speaker_map=subject_speaker_map,
        expert_speaker_map=expert_speaker_map,
        breadcrumbs=breadcrumbs,
        current_user=auth.current_user(),
    )


@bp.route("/discussion/<int:discussion_id>/matrix")
@minimum_role(btcopilot.ROLE_AUDITOR)
def pairwise_matrix(discussion_id: int):
    disc = Discussion.query.get_or_404(discussion_id)

    irr = calculate_discussion_irr(discussion_id)
    if not irr:
        abort(404, "No multi-coder data available")

    coders = sorted(irr.coders)
    matrix = {}
    for pair in irr.pairwise_metrics:
        matrix[(pair.coder_a, pair.coder_b)] = pair
        matrix[(pair.coder_b, pair.coder_a)] = pair

    menu, active_title = get_discussion_view_menu(discussion_id, "matrix")
    breadcrumbs = [
        {"title": "Coding", "url": url_for("training.audit.index")},
        {"title": "IRR", "url": url_for("training.irr.index")},
        {
            "title": disc.summary or f"Discussion {discussion_id}",
            "url": url_for("training.discussions.audit", discussion_id=discussion_id),
        },
        {"title": active_title, "menu": menu},
    ]

    return render_template(
        "training/irr_matrix.html",
        discussion=disc,
        coders=coders,
        matrix=matrix,
        discussion_irr=irr,
        breadcrumbs=breadcrumbs,
        current_user=auth.current_user(),
    )


@bp.route("/system")
@minimum_role(btcopilot.ROLE_AUDITOR)
def system():
    multi_coder = get_multi_coder_discussions()
    discussion_ids = [row[0] for row in multi_coder]

    all_irrs = []
    for did in discussion_ids:
        irr = calculate_discussion_irr(did)
        if irr:
            all_irrs.append(irr)

    if not all_irrs:
        abort(404, "No multi-coder discussions available")

    system_metrics = {
        "discussion_count": len(all_irrs),
        "total_statements": sum(irr.coded_statement_count for irr in all_irrs),
        "avg_events_f1": safe_avg([irr.avg_events_f1 for irr in all_irrs]),
        "avg_aggregate_f1": safe_avg([irr.avg_aggregate_f1 for irr in all_irrs]),
        "avg_symptom_kappa": safe_avg([irr.avg_symptom_kappa for irr in all_irrs]),
        "avg_anxiety_kappa": safe_avg([irr.avg_anxiety_kappa for irr in all_irrs]),
        "avg_relationship_kappa": safe_avg(
            [irr.avg_relationship_kappa for irr in all_irrs]
        ),
        "avg_functioning_kappa": safe_avg(
            [irr.avg_functioning_kappa for irr in all_irrs]
        ),
    }

    breadcrumbs = [
        {"title": "Coding", "url": url_for("training.audit.index")},
        {"title": "IRR", "url": url_for("training.irr.index")},
        {"title": "System-Wide", "url": None},
    ]

    return render_template(
        "training/irr_system.html",
        system_metrics=system_metrics,
        discussion_irrs=all_irrs,
        breadcrumbs=breadcrumbs,
        current_user=auth.current_user(),
    )


@bp.route("/statement/<int:statement_id>/note", methods=["POST"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def save_note(statement_id: int):
    data = request.get_json()
    note_text = data.get("note", "").strip()
    current = auth.current_user()

    note = ReconciliationNote.query.filter_by(statement_id=statement_id).first()

    if not note_text:
        if note:
            db.session.delete(note)
            db.session.commit()
        return jsonify({"success": True, "note": None})

    if note:
        note.note = note_text
    else:
        note = ReconciliationNote(
            statement_id=statement_id,
            note=note_text,
            created_by=current.email,
        )
        db.session.add(note)

    db.session.commit()
    return jsonify(
        {
            "success": True,
            "note": {"id": note.id, "note": note.note, "resolved": note.resolved},
        }
    )


@bp.route("/statement/<int:statement_id>/resolve", methods=["POST"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def toggle_resolved(statement_id: int):
    note = ReconciliationNote.query.filter_by(statement_id=statement_id).first()
    if not note:
        return jsonify({"error": "No note exists for this statement"}), 400

    note.resolved = not note.resolved
    db.session.commit()
    return jsonify({"success": True, "resolved": note.resolved})
