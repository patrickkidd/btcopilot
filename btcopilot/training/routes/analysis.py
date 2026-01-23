"""
Ground Truth Analysis Routes

Provides two analysis views:
1. Discussion-level: Show how ONE discussion contributed to F1 metrics
2. System-wide: Show ALL statements contributing to a specific metric
"""

import logging
from collections import defaultdict

from flask import Blueprint, render_template, request, abort, jsonify, url_for

import btcopilot
from btcopilot import auth
from btcopilot.extensions import db
from btcopilot.training.utils import get_breadcrumbs, get_discussion_view_menu
from btcopilot.auth import minimum_role
from btcopilot.personal.models import Statement
from btcopilot.training.models import Feedback
from btcopilot.training.analysis_utils import calculate_statement_match_breakdown
from btcopilot.training.f1_metrics import calculate_statement_f1

_log = logging.getLogger(__name__)

bp = Blueprint("analysis", __name__, url_prefix="/analysis")

SARF_ORDER = ["symptom", "anxiety", "relationship", "functioning"]


def _calculate_discussion_f1(statement_breakdowns):
    if not statement_breakdowns:
        return None

    result = {
        "aggregate_micro_f1": sum(
            sb["breakdown"].f1_metrics.aggregate_micro_f1 for sb in statement_breakdowns
        )
        / len(statement_breakdowns),
        "people_f1": sum(
            sb["breakdown"].f1_metrics.people_f1 for sb in statement_breakdowns
        )
        / len(statement_breakdowns),
        "events_f1": sum(
            sb["breakdown"].f1_metrics.events_f1 for sb in statement_breakdowns
        )
        / len(statement_breakdowns),
        "pair_bonds_f1": sum(
            sb["breakdown"].f1_metrics.pair_bonds_f1 for sb in statement_breakdowns
        )
        / len(statement_breakdowns),
        "symptom_macro_f1": sum(
            sb["breakdown"].f1_metrics.symptom_macro_f1 for sb in statement_breakdowns
        )
        / len(statement_breakdowns),
        "anxiety_macro_f1": sum(
            sb["breakdown"].f1_metrics.anxiety_macro_f1 for sb in statement_breakdowns
        )
        / len(statement_breakdowns),
        "relationship_macro_f1": sum(
            sb["breakdown"].f1_metrics.relationship_macro_f1
            for sb in statement_breakdowns
        )
        / len(statement_breakdowns),
        "functioning_macro_f1": sum(
            sb["breakdown"].f1_metrics.functioning_macro_f1
            for sb in statement_breakdowns
        )
        / len(statement_breakdowns),
        "symptom_hierarchical": {
            "detection_f1": sum(
                sb["breakdown"].f1_metrics.symptom_hierarchical.detection_f1
                for sb in statement_breakdowns
            )
            / len(statement_breakdowns),
            "value_match_f1": sum(
                sb["breakdown"].f1_metrics.symptom_hierarchical.value_match_f1
                for sb in statement_breakdowns
            )
            / len(statement_breakdowns),
        },
        "anxiety_hierarchical": {
            "detection_f1": sum(
                sb["breakdown"].f1_metrics.anxiety_hierarchical.detection_f1
                for sb in statement_breakdowns
            )
            / len(statement_breakdowns),
            "value_match_f1": sum(
                sb["breakdown"].f1_metrics.anxiety_hierarchical.value_match_f1
                for sb in statement_breakdowns
            )
            / len(statement_breakdowns),
        },
        "relationship_hierarchical": {
            "detection_f1": sum(
                sb["breakdown"].f1_metrics.relationship_hierarchical.detection_f1
                for sb in statement_breakdowns
            )
            / len(statement_breakdowns),
            "value_match_f1": sum(
                sb["breakdown"].f1_metrics.relationship_hierarchical.value_match_f1
                for sb in statement_breakdowns
            )
            / len(statement_breakdowns),
            "people_match_f1": sum(
                sb["breakdown"].f1_metrics.relationship_hierarchical.people_match_f1
                for sb in statement_breakdowns
            )
            / len(statement_breakdowns),
        },
        "functioning_hierarchical": {
            "detection_f1": sum(
                sb["breakdown"].f1_metrics.functioning_hierarchical.detection_f1
                for sb in statement_breakdowns
            )
            / len(statement_breakdowns),
            "value_match_f1": sum(
                sb["breakdown"].f1_metrics.functioning_hierarchical.value_match_f1
                for sb in statement_breakdowns
            )
            / len(statement_breakdowns),
        },
    }
    return result


def _get_person_name_from_people(person_id, people_lists):
    for people in people_lists:
        for person in people:
            if person.id == person_id:
                name = person.name or ""
                if person.last_name:
                    name += f" {person.last_name}"
                return name.strip() or f"Person {person_id}"
    return f"Person {person_id}"


def _extract_sarf_from_event(event_dict):
    """Extract SARF variables from an event dict, ordered by SARF_ORDER."""
    if not event_dict:
        return []
    sarf_data = []
    for var_name in SARF_ORDER:
        value = event_dict.get(var_name)
        if value is not None:
            item = {"variable_name": var_name, "value": value}
            if var_name == "relationship":
                item["targets"] = event_dict.get("relationshipTargets", [])
                item["triangles"] = event_dict.get("relationshipTriangles", [])
            sarf_data.append(item)
    return sarf_data


def _preprocess_breakdown_for_display(breakdown):
    """Transform breakdown to match sarf_editor layout: People section then Events section."""
    ai_people = getattr(breakdown, "ai_people", [])
    gt_people = getattr(breakdown, "gt_people", [])

    # Build people section
    people_list = []
    for person_match in breakdown.people_matches:
        person_id = (
            person_match.gt_entity.get("id")
            if person_match.gt_entity
            else person_match.ai_entity.get("id")
        )
        if not person_id:
            continue

        person_name = _get_person_name_from_people(person_id, [gt_people, ai_people])
        people_list.append(
            {
                "person_id": person_id,
                "person_name": person_name,
                "gt_person": person_match.gt_entity,
                "ai_person": person_match.ai_entity,
                "match_type": person_match.match_type,
            }
        )

    # Build events section - each event_match becomes a separate entry
    events_list = []
    for event_match in breakdown.event_matches:
        gt_event = event_match.gt_entity
        ai_event = event_match.ai_entity

        person_id = (
            gt_event.get("person") if gt_event else ai_event.get("person") if ai_event else 0
        )
        if not person_id:
            person_id = 0
            person_name = "(Unassigned)"
        else:
            person_name = _get_person_name_from_people(person_id, [gt_people, ai_people])

        events_list.append(
            {
                "gt_event": gt_event,
                "ai_event": ai_event,
                "match_type": event_match.match_type,
                "person_id": person_id,
                "person_name": person_name,
                "gt_sarf": _extract_sarf_from_event(gt_event),
                "ai_sarf": _extract_sarf_from_event(ai_event),
            }
        )

    # Sort people and events by ID for consistent ordering
    people_list.sort(key=lambda x: x["person_id"])
    events_list.sort(key=lambda x: x["person_id"])

    return {"people": people_list, "events": events_list}


@bp.route("/discussion/<int:discussion_id>")
@minimum_role(btcopilot.ROLE_AUDITOR)
def discussion_analysis(discussion_id):
    """
    URL: /training/analysis/discussion/<id>
    Entry: "View Analysis" button on discussion page
    Purpose: Show all statements in ONE discussion with 4-column layout
    """
    from btcopilot.personal.models import Discussion, Speaker
    from btcopilot.personal.models.speaker import SpeakerType

    discussion = Discussion.query.get_or_404(discussion_id)

    statements = (
        Statement.query.filter(Statement.discussion_id == discussion_id)
        .order_by(Statement.order)
        .all()
    )

    statement_breakdowns = []
    for stmt in statements:
        breakdown = calculate_statement_match_breakdown(stmt.id)
        if breakdown:
            display_blocks = _preprocess_breakdown_for_display(breakdown)
            statement_breakdowns.append(
                {
                    "statement": stmt,
                    "breakdown": breakdown,
                    "display_blocks": display_blocks,
                }
            )

    if not statement_breakdowns:
        abort(404, "This discussion has no approved ground truth")

    discussion_f1 = _calculate_discussion_f1(statement_breakdowns)

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

    menu, active_title = get_discussion_view_menu(discussion_id, "f1")
    breadcrumbs = get_breadcrumbs("thread")
    if discussion.diagram:
        breadcrumbs.append(
            {
                "title": discussion.diagram.name or "Untitled Diagram",
                "url": None,
            }
        )
    breadcrumbs.append(
        {
            "title": discussion.summary or f"Discussion {discussion_id}",
            "url": url_for("training.discussions.audit", discussion_id=discussion_id),
        }
    )
    breadcrumbs.append({"title": active_title, "menu": menu})

    return render_template(
        "training/discussion_analysis.html",
        discussion=discussion,
        statement_breakdowns=statement_breakdowns,
        discussion_f1=discussion_f1,
        subject_speaker_map=subject_speaker_map,
        expert_speaker_map=expert_speaker_map,
        breadcrumbs=breadcrumbs,
        current_user=auth.current_user(),
    )


@bp.route("/discussion/<int:discussion_id>/filter", methods=["POST"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def filter_discussion_analysis(discussion_id):
    """
    AJAX endpoint for hierarchical filtering (hybrid approach):
    - entity_type: Single-select - "people"/"events"/"pair_bonds"/"all"
    - match_types: Multi-select array - ["TP", "FP", "FN", "TN"] or empty for all
    - sarf_variable: Single-select - "symptom"/"anxiety"/"relationship"/"functioning"/"all"
    - sarf_level: Single-select - "detection"/"value_match"/"people_match"/"all"

    Returns: {statement_ids: [...], count: N}
    """
    filters = request.get_json()

    statements = (
        Statement.query.filter(Statement.discussion_id == discussion_id)
        .order_by(Statement.order)
        .all()
    )

    matching_statement_ids = []

    for stmt in statements:
        breakdown = calculate_statement_match_breakdown(stmt.id)
        if not breakdown:
            continue

        if _statement_matches_filters(breakdown, filters):
            matching_statement_ids.append(stmt.id)

    return jsonify(
        {"statement_ids": matching_statement_ids, "count": len(matching_statement_ids)}
    )


def _statement_matches_filters(breakdown, filters):
    entity_type = filters.get("entity_type", "all")
    match_types = filters.get("match_types", [])
    sarf_variable = filters.get("sarf_variable", "all")
    sarf_level = filters.get("sarf_level", "all")

    if entity_type == "people":
        matches = breakdown.people_matches
    elif entity_type == "events":
        matches = breakdown.event_matches
    elif entity_type == "pair_bonds":
        matches = breakdown.pair_bond_matches
    else:
        matches = (
            breakdown.people_matches
            + breakdown.event_matches
            + breakdown.pair_bond_matches
        )

    if match_types:
        entity_match = any(m.match_type in match_types for m in matches)
    else:
        entity_match = True

    if sarf_variable != "all":
        sarf_matches = [
            m for m in breakdown.sarf_matches if m.variable_name == sarf_variable
        ]

        if sarf_level == "detection":
            sarf_match = any(
                m.detection_match in (match_types or ["TP", "FP", "FN"])
                for m in sarf_matches
            )
        elif sarf_level == "value_match":
            sarf_match = any(m.value_match == "mismatch" for m in sarf_matches)
        elif sarf_level == "people_match":
            sarf_match = any(m.people_match == "mismatch" for m in sarf_matches)
        else:
            sarf_match = bool(sarf_matches)
    else:
        sarf_match = True

    return entity_match and sarf_match


def _parse_metric_to_filters(metric_name):
    if metric_name == "perfect_matches":
        return {"perfect_only": True}
    elif metric_name == "aggregate_micro_f1":
        return {"entity_type": "all", "match_types": ["FP", "FN"]}
    elif metric_name == "people_f1":
        return {"entity_type": "people", "match_types": ["FP", "FN"]}
    elif metric_name == "events_f1":
        return {"entity_type": "events", "match_types": ["FP", "FN"]}
    elif metric_name == "pair_bonds_f1":
        return {"entity_type": "pair_bonds", "match_types": ["FP", "FN"]}
    elif "_" in metric_name:
        parts = metric_name.split("_")
        variable = parts[0]
        level = "_".join(parts[1:])
        return {
            "entity_type": "all",
            "sarf_variable": variable,
            "sarf_level": level,
            "match_types": ["FP", "FN"],
        }
    return {}


def _get_metric_display_name(metric_name):
    names = {
        "perfect_matches": "Perfect Matches (F1 = 1.00)",
        "aggregate_micro_f1": "Overall F1",
        "people_f1": "People Detection F1",
        "events_f1": "Events Detection F1",
        "pair_bonds_f1": "Pair Bonds F1",
        "symptom_detection": "Symptom Detection F1",
        "symptom_value_match": "Symptom Value Match F1",
        "anxiety_detection": "Anxiety Detection F1",
        "anxiety_value_match": "Anxiety Value Match F1",
        "relationship_detection": "Relationship Detection F1",
        "relationship_value_match": "Relationship Value Match F1",
        "relationship_people_match": "Relationship People Match F1",
        "functioning_detection": "Functioning Detection F1",
        "functioning_value_match": "Functioning Value Match F1",
    }
    return names.get(metric_name, metric_name.replace("_", " ").title())


def _get_metric_breadcrumb_name(metric_name):
    """Get short name for breadcrumb (e.g., 'events_f1' -> 'Events')"""
    names = {
        "perfect_matches": "Perfect Matches",
        "aggregate_micro_f1": "Overall",
        "people_f1": "People",
        "events_f1": "Events",
        "pair_bonds_f1": "Pair Bonds",
        "symptom_detection": "Symptom Detection",
        "symptom_value_match": "Symptom Value",
        "anxiety_detection": "Anxiety Detection",
        "anxiety_value_match": "Anxiety Value",
        "relationship_detection": "Relationship Detection",
        "relationship_value_match": "Relationship Value",
        "relationship_people_match": "Relationship People",
        "functioning_detection": "Functioning Detection",
        "functioning_value_match": "Functioning Value",
    }
    return names.get(metric_name, metric_name.replace("_", " ").title())


def _statement_matches_metric_filter(breakdown, filters):
    if filters.get("perfect_only"):
        return breakdown.f1_metrics.aggregate_micro_f1 == 1.0

    entity_type = filters.get("entity_type", "all")
    match_types = filters.get("match_types", [])
    sarf_variable = filters.get("sarf_variable")
    sarf_level = filters.get("sarf_level")

    if sarf_variable:
        sarf_matches = [
            m for m in breakdown.sarf_matches if m.variable_name == sarf_variable
        ]

        if sarf_level == "detection":
            return any(m.detection_match in ["FP", "FN"] for m in sarf_matches)
        elif sarf_level == "value_match":
            return any(m.value_match == "mismatch" for m in sarf_matches)
        elif sarf_level == "people_match":
            return any(m.people_match == "mismatch" for m in sarf_matches)

    if entity_type == "people":
        return any(m.match_type in match_types for m in breakdown.people_matches)
    elif entity_type == "events":
        return any(m.match_type in match_types for m in breakdown.event_matches)
    elif entity_type == "pair_bonds":
        return any(m.match_type in match_types for m in breakdown.pair_bond_matches)
    else:
        all_matches = (
            breakdown.people_matches
            + breakdown.event_matches
            + breakdown.pair_bond_matches
        )
        return any(m.match_type in match_types for m in all_matches)


@bp.route("/")
@minimum_role(btcopilot.ROLE_AUDITOR)
def system_analysis():
    """
    URL: /training/analysis?metric=<metric_name>
    Entry: Clickable metrics in F1 dashboard card

    Supported metrics:
    - aggregate_micro_f1, people_f1, events_f1, pair_bonds_f1
    - symptom_detection, symptom_value_match
    - anxiety_detection, anxiety_value_match
    - relationship_detection, relationship_value_match, relationship_people_match
    - functioning_detection, functioning_value_match
    """
    metric_name = request.args.get("metric")
    if not metric_name:
        abort(400, "metric parameter required")

    filters = _parse_metric_to_filters(metric_name)

    approved_feedbacks = (
        Feedback.query.filter(
            Feedback.approved == True, Feedback.feedback_type == "extraction"
        )
        .join(Statement)
        .all()
    )

    matching_statements = []
    for feedback in approved_feedbacks:
        breakdown = calculate_statement_match_breakdown(feedback.statement_id)
        if breakdown and _statement_matches_metric_filter(breakdown, filters):
            statement = Statement.query.get(feedback.statement_id)
            display_blocks = _preprocess_breakdown_for_display(breakdown)
            matching_statements.append(
                {
                    "statement": statement,
                    "breakdown": breakdown,
                    "discussion": statement.discussion,
                    "display_blocks": display_blocks,
                }
            )

    from btcopilot.personal.models import Speaker
    from btcopilot.personal.models.speaker import SpeakerType

    discussions_map = defaultdict(list)
    for item in matching_statements:
        discussions_map[item["discussion"].id].append(item)

    speaker_maps = {}
    for discussion_id in discussions_map.keys():
        unique_speakers = (
            Speaker.query.filter(Speaker.discussion_id == discussion_id)
            .order_by(Speaker.id)
            .all()
        )
        subject_speakers = [s for s in unique_speakers if s.type == SpeakerType.Subject]
        expert_speakers = [s for s in unique_speakers if s.type == SpeakerType.Expert]

        subject_map = {
            speaker.id: idx + 1 for idx, speaker in enumerate(subject_speakers)
        }
        expert_map = {
            speaker.id: idx + 1 for idx, speaker in enumerate(expert_speakers)
        }

        speaker_maps[discussion_id] = {
            "subject": subject_map,
            "expert": expert_map,
        }

    breadcrumbs = get_breadcrumbs("audit")
    breadcrumbs.append(
        {"title": "System-Wide F1", "url": url_for("training.audit.index")}
    )
    breadcrumbs.append({"title": _get_metric_breadcrumb_name(metric_name), "url": None})

    return render_template(
        "training/system_analysis.html",
        metric_name=metric_name,
        metric_display=_get_metric_display_name(metric_name),
        discussions_map=discussions_map,
        total_statements=len(matching_statements),
        speaker_maps=speaker_maps,
        breadcrumbs=breadcrumbs,
        current_user=auth.current_user(),
    )
