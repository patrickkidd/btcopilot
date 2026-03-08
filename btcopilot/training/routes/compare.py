import asyncio
import logging

import nest_asyncio
from flask import Blueprint, jsonify, render_template, request, abort, url_for

import btcopilot
from btcopilot import auth, pdp
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.schema import DiagramData, asdict
from btcopilot.training.models import Feedback
from btcopilot.training.litreview import (
    AUDITOR_ID as LITREVIEW_AUDITOR_ID,
    LITREVIEW_PASS2_PROMPT,
    LITREVIEW_SARF_REVIEW_PROMPT,
)
from btcopilot.training.utils import get_discussion_breadcrumbs
from btcopilot.training.f1_metrics import (
    match_people,
    match_events,
    _augment_duplicate_person_id_map,
    normalize_name_for_matching,
    NAME_SIMILARITY_THRESHOLD,
)
from rapidfuzz import fuzz
from btcopilot.training.calibrationutils import (
    SARF_FIELDS,
    _sarf_val,
    _classify_impact,
    _person_name,
)

_log = logging.getLogger(__name__)

bp = Blueprint("compare", __name__, url_prefix="/compare")


def _auditor_options(discussion_id):
    feedbacks = (
        Feedback.query.filter_by(feedback_type="extraction")
        .join(Statement)
        .filter(Statement.discussion_id == discussion_id)
        .all()
    )
    auditor_ids = sorted(set(f.auditor_id for f in feedbacks))

    options = [{"id": "AI", "name": "AI"}]
    for aid in auditor_ids:
        name = aid.split("@")[0] if "@" in aid else aid
        options.append({"id": aid, "name": name})
    return options


def _event_display_person(event):
    from btcopilot.schema import EventKind

    if event.kind in (EventKind.Birth, EventKind.Adopted):
        return event.child or event.person
    return event.person


def _event_display_desc(event):
    desc = event.description or ""
    if not event.kind or not event.kind.isSelfDescribing():
        return desc
    kind_label = event.kind.value.capitalize()
    if not desc or desc.lower() in ("new event", "unknown"):
        return kind_label
    return f"{kind_label}: {desc}"


def _event_sarf(event):
    sarf = []
    for f in SARF_FIELDS:
        val = _sarf_val(event, f)
        if val:
            sarf.append({"field": f, "val": val})
    return sarf


def _dedup_b_people(id_map, b_people):
    """Map duplicate B-side people to their canonical IDs.

    _augment_duplicate_person_id_map handles A-side duplicates. For symmetric
    comparisons we also need B-side: if B has two "Michael" entries and only
    one is in id_map values, map the other to the canonical one so that
    match_events can find it.
    """
    matched_b_ids = set(id_map.values())
    b_name_to_canonical = {}
    for bid in matched_b_ids:
        for p in b_people:
            if p.id == bid:
                norm = normalize_name_for_matching(p.name)
                if norm:
                    b_name_to_canonical[norm] = bid
                break

    dedup = {}
    for p in b_people:
        if p.id in matched_b_ids:
            continue
        norm = normalize_name_for_matching(p.name)
        if not norm:
            continue
        for canon_name, canon_id in b_name_to_canonical.items():
            if (
                fuzz.token_set_ratio(norm, canon_name) / 100.0
                >= NAME_SIMILARITY_THRESHOLD
            ):
                dedup[p.id] = canon_id
                break
    return dedup


def _event_stmt_map(discussion, auditor_id):
    """Map event ID → statement ID for the last statement that introduced each event."""
    sorted_stmts = sorted(
        discussion.statements, key=lambda s: (s.order or 0, s.id or 0)
    )
    feedback_by_stmt = {}
    if auditor_id and auditor_id != "AI":
        feedbacks = Feedback.query.filter(
            Feedback.statement_id.in_([s.id for s in sorted_stmts]),
            Feedback.auditor_id == auditor_id,
            Feedback.feedback_type == "extraction",
        ).all()
        for fb in feedbacks:
            feedback_by_stmt[fb.statement_id] = fb

    result = {}
    for stmt in sorted_stmts:
        if not stmt.speaker or stmt.speaker.type != SpeakerType.Subject:
            continue
        deltas = None
        if auditor_id and auditor_id != "AI":
            fb = feedback_by_stmt.get(stmt.id)
            if fb and fb.edited_extraction:
                deltas = fb.edited_extraction
        elif stmt.pdp_deltas:
            deltas = stmt.pdp_deltas
        if not deltas:
            continue
        for event_data in deltas.get("events", []):
            eid = event_data.get("id")
            if eid:
                result[eid] = stmt.id
    return result


def _build_timeline(pdp_a, pdp_b, coder_a, coder_b, stmt_map_a=None, stmt_map_b=None):
    people_result, id_map = match_people(
        pdp_a.people, pdp_b.people, pdp_a.pair_bonds, pdp_b.pair_bonds
    )
    _augment_duplicate_person_id_map(id_map, pdp_a.people, pdp_b.people)

    # Normalize B-side duplicate person IDs so match_events can find them
    b_dedup = _dedup_b_people(id_map, pdp_b.people)
    if b_dedup:
        for event in pdp_b.events:
            if event.person in b_dedup:
                event.person = b_dedup[event.person]

    events_result = match_events(pdp_a.events, pdp_b.events, id_map)

    rows = []
    n_disagreements = 0
    sma = stmt_map_a or {}
    smb = stmt_map_b or {}

    for event_a, event_b in events_result.matched_pairs:
        person_id = _event_display_person(event_a) or _event_display_person(event_b)
        pname = _person_name(person_id, pdp_a.people, pdp_b.people)
        diffs = []
        for f in SARF_FIELDS:
            val_a = _sarf_val(event_a, f)
            val_b = _sarf_val(event_b, f)
            differs = val_a != val_b
            if val_a or val_b:
                diffs.append(
                    {
                        "field": f,
                        "val_a": val_a,
                        "val_b": val_b,
                        "differs": differs,
                        "impact": (
                            _classify_impact(f, val_a, val_b).value if differs else None
                        ),
                    }
                )
        has_disagreement = any(d["differs"] for d in diffs)
        if has_disagreement:
            n_disagreements += 1
        rows.append(
            {
                "date": event_a.dateTime or event_b.dateTime or "",
                "person_name": pname,
                "kind": event_a.kind.value if event_a.kind else "",
                "a": {
                    "description": _event_display_desc(event_a),
                    "sarf": _event_sarf(event_a),
                },
                "b": {
                    "description": _event_display_desc(event_b),
                    "sarf": _event_sarf(event_b),
                },
                "status": "matched",
                "has_disagreement": has_disagreement,
                "sarf_diffs": diffs,
                "stmt_a": sma.get(event_a.id),
                "stmt_b": smb.get(event_b.id),
            }
        )

    for event in events_result.ai_unmatched:
        rows.append(
            {
                "date": event.dateTime or "",
                "person_name": _person_name(_event_display_person(event), pdp_a.people),
                "kind": event.kind.value if event.kind else "",
                "a": {
                    "description": _event_display_desc(event),
                    "sarf": _event_sarf(event),
                },
                "b": None,
                "status": "a_only",
                "has_disagreement": False,
                "sarf_diffs": [],
                "stmt_a": sma.get(event.id),
                "stmt_b": None,
            }
        )

    for event in events_result.gt_unmatched:
        rows.append(
            {
                "date": event.dateTime or "",
                "person_name": _person_name(_event_display_person(event), pdp_b.people),
                "kind": event.kind.value if event.kind else "",
                "a": None,
                "b": {
                    "description": _event_display_desc(event),
                    "sarf": _event_sarf(event),
                },
                "status": "b_only",
                "has_disagreement": False,
                "sarf_diffs": [],
                "stmt_a": None,
                "stmt_b": smb.get(event.id),
            }
        )

    rows.sort(key=lambda r: r["date"] or "zzzz")

    people_a_only = [{"name": p.name} for p in people_result.ai_unmatched]
    people_b_only = [{"name": p.name} for p in people_result.gt_unmatched]

    return {
        "rows": rows,
        "people_a_only": people_a_only,
        "people_b_only": people_b_only,
        "counts": {
            "matched": len(events_result.matched_pairs),
            "disagreements": n_disagreements,
            "a_only": len(events_result.ai_unmatched),
            "b_only": len(events_result.gt_unmatched),
        },
    }


@bp.route("/discussion/<int:discussion_id>")
@minimum_role(btcopilot.ROLE_AUDITOR)
def timeline(discussion_id):
    disc = Discussion.query.get_or_404(discussion_id)

    options = _auditor_options(discussion_id)
    if len(options) < 2:
        abort(404, "Need at least 2 sources to compare")

    # Default: first two non-AI sources, falling back to AI
    non_ai = [o for o in options if o["id"] != "AI"]
    default_a = non_ai[0]["id"] if len(non_ai) > 0 else "AI"
    default_b = non_ai[1]["id"] if len(non_ai) > 1 else "AI"
    coder_a = request.args.get("a", default_a)
    coder_b = request.args.get("b", default_b)

    # Build cumulative PDPs
    last_stmt = (
        Statement.query.filter_by(discussion_id=discussion_id)
        .join(Speaker)
        .filter(Speaker.type == SpeakerType.Subject)
        .order_by(Statement.order.desc())
        .first()
    )
    if not last_stmt:
        abort(404, "No subject statements")

    pdp_a = pdp.cumulative(disc, last_stmt, auditor_id=coder_a)
    pdp_b = pdp.cumulative(disc, last_stmt, auditor_id=coder_b)
    stmt_map_a = _event_stmt_map(disc, coder_a)
    stmt_map_b = _event_stmt_map(disc, coder_b)

    timeline_data = _build_timeline(
        pdp_a, pdp_b, coder_a, coder_b, stmt_map_a, stmt_map_b
    )

    breadcrumbs = get_discussion_breadcrumbs(disc, "timeline")

    # Check if litreview-ai has data for this discussion
    litreview_fb = (
        Feedback.query.filter_by(
            auditor_id=LITREVIEW_AUDITOR_ID, feedback_type="extraction"
        )
        .join(Statement)
        .filter(Statement.discussion_id == discussion_id)
        .first()
    )

    return render_template(
        "training/timeline.html",
        discussion=disc,
        auditor_options=options,
        coder_a=coder_a,
        coder_b=coder_b,
        timeline=timeline_data,
        breadcrumbs=breadcrumbs,
        current_user=auth.current_user(),
        litreview_exists=litreview_fb is not None,
        litreview_auditor_id=LITREVIEW_AUDITOR_ID,
    )


@bp.route("/litreview/<int:discussion_id>", methods=["POST"])
@minimum_role(btcopilot.ROLE_ADMIN)
def run_litreview(discussion_id):
    disc = Discussion.query.get_or_404(discussion_id)

    last_stmt = (
        Statement.query.filter_by(discussion_id=discussion_id)
        .join(Speaker)
        .filter(Speaker.type == SpeakerType.Subject)
        .order_by(Statement.order.desc())
        .first()
    )
    if not last_stmt:
        abort(404, "No subject statements")

    # Clear existing litreview feedback for this discussion
    stmt_ids = [s.id for s in disc.statements]
    Feedback.query.filter(
        Feedback.auditor_id == LITREVIEW_AUDITOR_ID,
        Feedback.feedback_type == "extraction",
        Feedback.statement_id.in_(stmt_ids),
    ).delete(synchronize_session=False)
    db.session.flush()

    if LITREVIEW_PASS2_PROMPT is None:
        abort(503, "Litreview unavailable: production prompts not found")

    nest_asyncio.apply()
    diagram_data = DiagramData()
    ai_pdp, _ = asyncio.run(
        pdp.extract_full(
            disc,
            diagram_data,
            pass2_prompt=LITREVIEW_PASS2_PROMPT,
            sarf_review_prompt=LITREVIEW_SARF_REVIEW_PROMPT,
        )
    )

    fb = Feedback(
        statement_id=last_stmt.id,
        auditor_id=LITREVIEW_AUDITOR_ID,
        feedback_type="extraction",
        edited_extraction=asdict(ai_pdp),
        meta={"prompt": LITREVIEW_PASS2_PROMPT},
    )
    db.session.add(fb)
    db.session.commit()

    return jsonify(
        {
            "people": len(ai_pdp.people),
            "events": len(ai_pdp.events),
        }
    )


@bp.route("/litreview/<int:discussion_id>/prompt")
@minimum_role(btcopilot.ROLE_AUDITOR)
def litreview_prompt(discussion_id):
    fb = (
        Feedback.query.filter_by(
            auditor_id=LITREVIEW_AUDITOR_ID, feedback_type="extraction"
        )
        .join(Statement)
        .filter(Statement.discussion_id == discussion_id)
        .first()
    )
    if not fb or not fb.meta or not fb.meta.get("prompt"):
        abort(404, "No litreview prompt stored for this discussion")

    return render_template(
        "training/litreview_prompt.html",
        discussion_id=discussion_id,
        prompt=fb.meta["prompt"],
        breadcrumbs=[
            {"title": "Coding", "url": url_for("training.audit.index")},
            {
                "title": f"Discussion {discussion_id}",
                "url": url_for(
                    "training.discussions.audit", discussion_id=discussion_id
                ),
            },
            {"title": "Litreview Prompt"},
        ],
        current_user=auth.current_user(),
    )
