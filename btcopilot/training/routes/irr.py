import json
import logging
from dataclasses import asdict

from flask import Blueprint, abort, jsonify, render_template, request, url_for

import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.llmutil import gemini_calibration_sync
from btcopilot.personal.models import Discussion, Speaker, SpeakerType, Statement
from btcopilot.training.irr_metrics import (
    calculate_discussion_irr,
    calculate_statement_irr,
    get_multi_coder_discussions,
    get_statement_extractions,
    safe_avg,
)
from btcopilot.training.models import Feedback, ReconciliationNote
from btcopilot.training.utils import get_discussion_breadcrumbs
from btcopilot.training.calibrationutils import SARF_FIELDS
from btcopilot.training.calibrationprompts import (
    STATEMENT_REVIEW_SYSTEM,
    STATEMENT_REVIEW_USER,
)

_log = logging.getLogger(__name__)

bp = Blueprint("irr", __name__, url_prefix="/irr")
EVENT_FIELDS = ("description", "dateTime", "dateCertainty")
PERSON_FIELDS = ("gender", "last_name", "parents")


def _field_coded(obj: dict, field: str) -> bool:
    val = obj.get(field)
    if hasattr(val, "value"):
        val = val.value
    return val not in (None, "-", "")


def _compute_sarf_disagreements(extractions: dict) -> dict:
    if len(extractions) < 2:
        return {}

    compared_fields = ("kind", "person") + SARF_FIELDS + EVENT_FIELDS
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

    breadcrumbs = get_discussion_breadcrumbs(disc, "irr")

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


@bp.route("/discussion/<int:discussion_id>/review")
@minimum_role(btcopilot.ROLE_AUDITOR)
def review(discussion_id: int):
    disc = Discussion.query.get_or_404(discussion_id)

    irr = calculate_discussion_irr(discussion_id)
    if not irr:
        abort(404, "No multi-coder data available for this discussion")

    coders = sorted(irr.coders, key=lambda c: (c.startswith("ai-"), c))
    statements = (
        Statement.query.filter_by(discussion_id=discussion_id)
        .join(Speaker)
        .order_by(Statement.order)
        .all()
    )

    # Build cumulative people per coder across statements in order so that
    # person IDs introduced in earlier statements resolve correctly in later ones.
    cumulative_people: dict[str, dict[int, dict]] = {c: {} for c in coders}

    statement_data = []
    for stmt in statements:
        if stmt.speaker.type != SpeakerType.Subject:
            statement_data.append({"statement": stmt, "extractions": None})
            continue

        feedbacks = Feedback.query.filter(
            Feedback.statement_id == stmt.id,
            Feedback.feedback_type == "extraction",
            Feedback.edited_extraction.isnot(None),
        ).all()
        raw_extractions = {fb.auditor_id: fb.edited_extraction for fb in feedbacks}

        extractions_dict = {}
        for coder in coders:
            ext = raw_extractions.get(coder)
            if not ext:
                continue
            # Merge this statement's new people into the cumulative dict (id → person).
            for p in ext.get("people") or []:
                cumulative_people[coder][p["id"]] = p
            # Attach a snapshot of all known people so the template can pass it
            # as cumulative_pdp for correct name resolution in the sarf_editor.
            ext = dict(ext)
            ext["_cumulative_people"] = list(cumulative_people[coder].values())
            extractions_dict[coder] = ext

        statement_data.append({"statement": stmt, "extractions": extractions_dict})

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

    breadcrumbs = get_discussion_breadcrumbs(disc, "review")

    return render_template(
        "training/irr_review.html",
        discussion=disc,
        statement_data=statement_data,
        coders=coders,
        subject_speaker_map=subject_speaker_map,
        expert_speaker_map=expert_speaker_map,
        breadcrumbs=breadcrumbs,
        current_user=auth.current_user(),
    )


@bp.route(
    "/discussion/<int:discussion_id>/statement/<int:statement_id>/review",
    methods=["GET"],
)
@minimum_role(btcopilot.ROLE_AUDITOR)
def get_statement_review(discussion_id: int, statement_id: int):
    disc = Discussion.query.get_or_404(discussion_id)
    reviews = disc.statement_reviews or {}
    cached = reviews.get(str(statement_id))
    if cached:
        return jsonify(cached)
    return jsonify({}), 404


def _resolve_people(ext: dict, cumulative: dict) -> dict:
    """Return id→name map for one coder at one statement, merged with cumulative."""
    m = dict(cumulative)
    for p in ext.get("people") or []:
        m[p["id"]] = p.get("name") or p.get("last_name") or f"Person {p['id']}"
    return m


def _short(coder_id: str) -> str:
    return coder_id.split("@")[0]


def _event_label(ev: dict, person_map: dict) -> str:
    kind = ev.get("kind") or "shift"
    pid = ev.get("person") or ev.get("child")
    name = person_map.get(pid, "") if pid else ""
    return f"{kind}({name})" if name else kind


def _neighbor_coding(neighbor_ids: list[int], coder_ids: list[str]) -> dict[str, dict[int, list]]:
    """Return {coder_id: {stmt_id: [event_dicts]}} for neighbor statements."""
    if not neighbor_ids:
        return {}
    nfbs = Feedback.query.filter(
        Feedback.statement_id.in_(neighbor_ids),
        Feedback.feedback_type == "extraction",
        Feedback.auditor_id.in_(coder_ids),
        Feedback.edited_extraction.isnot(None),
    ).all()
    result: dict[str, dict[int, list]] = {}
    for nfb in nfbs:
        result.setdefault(nfb.auditor_id, {})
        result[nfb.auditor_id][nfb.statement_id] = nfb.edited_extraction.get("events") or []
    return result


def _compute_review(
    feedbacks: list,
    cumulative_people: dict[str, dict],
    neighbor_coding: dict[str, dict[int, list]],
    statement_id: int,
) -> tuple[list[str], list[str]]:
    """
    Returns (conflicts, gaps).

    conflicts: events where 2+ coders coded the same person+kind but assigned different field values.
    gaps: events coded by only some coders (others skipped or shifted to a neighbor statement).
    """
    coder_ids = [fb.auditor_id for fb in feedbacks]
    person_maps: dict[str, dict] = {}
    coder_events: dict[str, list[dict]] = {}
    for fb in feedbacks:
        pm = _resolve_people(fb.edited_extraction, cumulative_people.get(fb.auditor_id, {}))
        person_maps[fb.auditor_id] = pm
        coder_events[fb.auditor_id] = fb.edited_extraction.get("events") or []

    # Build {label: {coder: {field: value}}} — one entry per (person, kind) label per coder.
    # Multiple events with the same label from one coder → union their field values.
    label_coder_fields: dict[str, dict[str, dict[str, str]]] = {}
    for coder, events in coder_events.items():
        pm = person_maps[coder]
        for ev in events:
            label = _event_label(ev, pm)
            label_coder_fields.setdefault(label, {}).setdefault(coder, {})
            for field in SARF_FIELDS:
                val = ev.get(field)
                if val and val not in (None, "-", ""):
                    label_coder_fields[label][coder][field] = str(val)

    conflicts: list[str] = []
    gaps: list[str] = []

    for label in sorted(label_coder_fields):
        raw = label_coder_fields[label]
        # Only count coders who actually set at least one SARF field value.
        coders_with_event = {c: f for c, f in raw.items() if f}
        if not coders_with_event:
            continue
        coders_absent = [c for c in coder_ids if c not in coders_with_event]

        # Resolve neighbor codings for absent coders.
        neighbor_note: dict[str, str] = {}  # coder -> "s{sid}"
        for coder in coders_absent:
            pm = person_maps[coder]
            for sid, nevents in (neighbor_coding.get(coder) or {}).items():
                for nev in nevents:
                    if _event_label(nev, pm) == label:
                        neighbor_note[coder] = f"s{sid}"
                        break
                if coder in neighbor_note:
                    break

        truly_absent = [c for c in coders_absent if c not in neighbor_note]

        # Value conflicts: coders who coded this event disagree on field values.
        conflict_fields: list[str] = []
        for field in SARF_FIELDS:
            vals = {c: cf.get(field) for c, cf in coders_with_event.items() if cf.get(field)}
            if len(set(vals.values())) > 1:
                conflict_fields.append(
                    f"{field}: " + ", ".join(f"{_short(c)}={v}" for c, v in sorted(vals.items()))
                )
        if conflict_fields:
            conflicts.append(f"{label} — " + "; ".join(conflict_fields))

        # Coverage gaps: event coded by some but not all (accounting for neighbor shifts).
        if truly_absent or neighbor_note:
            coder_summaries: list[str] = []
            for coder, fields in sorted(coders_with_event.items()):
                field_str = ", ".join(f"{f}={v}" for f, v in sorted(fields.items()))
                coder_summaries.append(f"{_short(coder)}: {field_str}")
            for coder, sid_note in sorted(neighbor_note.items()):
                coder_summaries.append(f"{_short(coder)}: coded at {sid_note}")
            if truly_absent:
                coder_summaries.append("skipped: " + ", ".join(_short(c) for c in sorted(truly_absent)))
            gaps.append(f"{label} — " + "; ".join(coder_summaries))

    return conflicts, gaps


@bp.route(
    "/discussion/<int:discussion_id>/statement/<int:statement_id>/review",
    methods=["POST"],
)
@minimum_role(btcopilot.ROLE_AUDITOR)
def generate_statement_review(discussion_id: int, statement_id: int):
    disc = Discussion.query.get_or_404(discussion_id)
    stmt = Statement.query.get_or_404(statement_id)

    feedbacks = Feedback.query.filter(
        Feedback.statement_id == statement_id,
        Feedback.feedback_type == "extraction",
        Feedback.edited_extraction.isnot(None),
    ).all()
    if not feedbacks:
        abort(400, "No extractions for this statement")

    all_subject_stmts = (
        Statement.query.filter_by(discussion_id=discussion_id)
        .join(Speaker)
        .filter(Speaker.type == SpeakerType.Subject)
        .order_by(Statement.order)
        .all()
    )
    stmt_ids = [s.id for s in all_subject_stmts]
    try:
        focal_idx = stmt_ids.index(statement_id)
    except ValueError:
        focal_idx = -1

    WINDOW = 2
    neighbor_ids = [
        all_subject_stmts[i].id
        for i in range(
            max(0, focal_idx - WINDOW),
            min(len(all_subject_stmts), focal_idx + WINDOW + 1),
        )
        if i != focal_idx
    ]

    coder_ids = [fb.auditor_id for fb in feedbacks]
    cumulative_people: dict[str, dict] = {c: {} for c in coder_ids}
    for sid in stmt_ids[: focal_idx + 1]:
        prior_fbs = Feedback.query.filter(
            Feedback.statement_id == sid,
            Feedback.feedback_type == "extraction",
            Feedback.auditor_id.in_(coder_ids),
            Feedback.edited_extraction.isnot(None),
        ).all()
        for pfb in prior_fbs:
            for p in pfb.edited_extraction.get("people") or []:
                cumulative_people[pfb.auditor_id][p["id"]] = (
                    p.get("name") or p.get("last_name") or f"Person {p['id']}"
                )

    neighbor_coding = _neighbor_coding(neighbor_ids, coder_ids)

    coder_lines: list[str] = []
    for fb in feedbacks:
        pm = _resolve_people(fb.edited_extraction, cumulative_people.get(fb.auditor_id, {}))
        events = fb.edited_extraction.get("events") or []
        event_parts: list[str] = []
        for ev in events:
            label = _event_label(ev, pm)
            fields = {f: ev[f] for f in SARF_FIELDS if ev.get(f) and ev[f] not in (None, "-", "")}
            field_str = ", ".join(f"{k}={v}" for k, v in fields.items())
            event_parts.append(f"{label}({field_str})" if field_str else label)
        # Append any neighbor codings for context.
        for sid, nevents in (neighbor_coding.get(fb.auditor_id) or {}).items():
            for nev in nevents:
                label = _event_label(nev, pm)
                fields = {f: nev[f] for f in SARF_FIELDS if nev.get(f) and nev[f] not in (None, "-", "")}
                field_str = ", ".join(f"{k}={v}" for k, v in fields.items())
                event_parts.append(f"{label}({field_str}) [placed on s{sid}]" if field_str else f"{label} [placed on s{sid}]")
        coder_lines.append(f"{_short(fb.auditor_id)}: {'; '.join(event_parts) if event_parts else '(nothing coded)'}")

    prompt = STATEMENT_REVIEW_USER.format(
        statement_text=stmt.text or "",
        coder_extractions="\n".join(coder_lines),
    )

    _log.info(
        f"Statement review: discussion={discussion_id} statement={statement_id} coders={len(feedbacks)}"
    )
    raw = gemini_calibration_sync(prompt, STATEMENT_REVIEW_SYSTEM, max_output_tokens=1024).strip()

    triage = "DISCUSS"
    questions: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("**Triage:**"):
            val = line.split("**Triage:**", 1)[1].strip()
            triage = "SKIP" if "SKIP" in val.upper() else "DISCUSS"
        elif line.startswith("**Questions:**"):
            text = line.split("**Questions:**", 1)[1].strip()
            if text and not text.startswith("["):
                questions.append(text.lstrip("- ").strip())
        elif line.startswith("- "):
            questions.append(line[2:].strip())

    result = {"summary": raw, "triage": triage, "questions": questions}
    reviews = dict(disc.statement_reviews or {})
    reviews[str(statement_id)] = result
    disc.statement_reviews = reviews
    db.session.commit()

    return jsonify(result)


@bp.route("/discussion/<int:discussion_id>/matrix")
@minimum_role(btcopilot.ROLE_AUDITOR)
def pairwise_matrix(discussion_id: int):
    disc = Discussion.query.get_or_404(discussion_id)

    irr = calculate_discussion_irr(discussion_id)
    if not irr:
        abort(404, "No multi-coder data available")

    coders = sorted(irr.coders, key=lambda c: (c.startswith("ai-"), c))
    matrix = {}
    for pair in irr.pairwise_metrics:
        matrix[(pair.coder_a, pair.coder_b)] = pair
        matrix[(pair.coder_b, pair.coder_a)] = pair

    breadcrumbs = get_discussion_breadcrumbs(disc, "matrix")

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
