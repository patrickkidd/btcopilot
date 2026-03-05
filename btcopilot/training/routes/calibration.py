import json
import asyncio
import logging

from flask import Blueprint, abort, jsonify, request

import btcopilot
from btcopilot import pdp as pdp_module
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, SpeakerType, Statement
from btcopilot.schema import asdict as schema_asdict
from btcopilot.llmutil import gemini_calibration
from btcopilot.training.models import Feedback
from btcopilot.training.sarfdefinitions import definitions_for_event, linkify_passages
from btcopilot.training.calibrationprompts import (
    CODING_ADVISOR_SYSTEM,
    CODING_ADVISOR_USER,
    IRR_REVIEW_SYSTEM,
    IRR_REVIEW_USER,
)
from btcopilot.training.calibrationutils import (
    compare_cumulative_pdps,
    prioritize_disagreements,
    trace_to_statements,
)

_log = logging.getLogger(__name__)

LLM_BATCH_SIZE = 24  # Gemini quota: 25 requests/min/model
LLM_BATCH_DELAY = 60  # seconds between batches

bp = Blueprint("calibration", __name__, url_prefix="/calibration")


async def batch_llm_calls(prompts, system_instruction):
    """Run LLM calls in rate-limited batches to stay under Gemini's 25 req/min quota."""
    results = []
    for batch_start in range(0, len(prompts), LLM_BATCH_SIZE):
        batch = prompts[batch_start:batch_start + LLM_BATCH_SIZE]
        batch_num = batch_start // LLM_BATCH_SIZE + 1
        total_batches = (len(prompts) + LLM_BATCH_SIZE - 1) // LLM_BATCH_SIZE
        _log.info(f"  Batch {batch_num}/{total_batches}: {len(batch)} calls...")
        batch_results = await asyncio.gather(
            *[gemini_calibration(p, system_instruction=system_instruction) for p in batch]
        )
        results.extend(batch_results)
        if batch_start + LLM_BATCH_SIZE < len(prompts):
            _log.info(f"  Waiting {LLM_BATCH_DELAY}s for rate limit reset...")
            await asyncio.sleep(LLM_BATCH_DELAY)
    return results


def _get_statement_context(discussion, target_stmt, n_prior=3):
    """Get target statement text plus n_prior preceding statements for context."""
    sorted_stmts = sorted(
        discussion.statements, key=lambda s: (s.order or 0, s.id or 0)
    )
    target_idx = None
    for i, s in enumerate(sorted_stmts):
        if s.id == target_stmt.id:
            target_idx = i
            break
    if target_idx is None:
        return target_stmt.text or ""

    start = max(0, target_idx - n_prior)
    context_stmts = sorted_stmts[start : target_idx + 1]
    lines = []
    for s in context_stmts:
        speaker = s.speaker.name if s.speaker else "Unknown"
        marker = " [CURRENT]" if s.id == target_stmt.id else ""
        lines.append(f"{speaker}: {s.text}{marker}")
    return "\n\n".join(lines)


def _build_definitions_text(event_dict):
    """Build combined definition text for all SARF fields coded on an event."""
    defs = definitions_for_event(event_dict)
    if not defs:
        return "(No SARF variables coded on this event)"
    parts = []
    for label, text in defs.items():
        parts.append(f"### Definition: {label}\n\n{text}")
    return "\n\n---\n\n".join(parts)


def _advice_key(statement_id, auditor_id, event_index):
    return f"{statement_id}:{auditor_id}:{event_index}"


@bp.route("/event", methods=["GET"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def get_cached_advice():
    statement_id = request.args.get("statement_id", type=int)
    event_index = request.args.get("event_index", type=int)
    auditor_id = request.args.get("auditor_id")
    if statement_id is None or event_index is None or not auditor_id:
        abort(400, "statement_id, event_index, and auditor_id required")

    stmt = Statement.query.get_or_404(statement_id)
    discussion = Discussion.query.get_or_404(stmt.discussion_id)
    cache = discussion.calibration_advice or {}
    key = _advice_key(statement_id, auditor_id, event_index)
    cached = cache.get(key)
    if cached:
        return jsonify(cached)
    return jsonify(None)


@bp.route("/event", methods=["POST"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def calibrate_event():
    data = request.get_json()
    statement_id = data.get("statement_id")
    event_index = data.get("event_index")
    auditor_id = data.get("auditor_id")

    if statement_id is None or event_index is None or not auditor_id:
        abort(400, "statement_id, event_index, and auditor_id required")

    _log.info(f"Calibrate event: stmt={statement_id} event_idx={event_index} auditor={auditor_id}")

    stmt = Statement.query.get_or_404(statement_id)
    discussion = Discussion.query.get_or_404(stmt.discussion_id)

    feedback = Feedback.query.filter_by(
        statement_id=statement_id,
        auditor_id=auditor_id,
        feedback_type="extraction",
    ).first()
    if not feedback or not feedback.edited_extraction:
        abort(404, "No extraction found for this auditor/statement")

    events = feedback.edited_extraction.get("events", [])
    if event_index < 0 or event_index >= len(events):
        abort(400, f"event_index {event_index} out of range")

    event_dict = events[event_index]

    _log.info(f"  Event: {event_dict.get('description', '?')} | S={event_dict.get('symptom')} A={event_dict.get('anxiety')} R={event_dict.get('relationship')} F={event_dict.get('functioning')}")

    _log.info(f"  Building cumulative PDP up to stmt {statement_id}...")
    cum_pdp = pdp_module.cumulative(discussion, stmt, auditor_id=auditor_id)
    cum_pdp_dict = schema_asdict(cum_pdp)

    statement_context = _get_statement_context(discussion, stmt)
    defs = definitions_for_event(event_dict)
    definitions_text = _build_definitions_text(event_dict)
    event_json = json.dumps(event_dict, indent=2, default=str)
    cumulative_pdp_json = json.dumps(cum_pdp_dict, indent=2, default=str)

    prompt = CODING_ADVISOR_USER.format(
        statement_context=statement_context,
        cumulative_pdp_json=cumulative_pdp_json,
        event_json=event_json,
        definitions_text=definitions_text,
    )

    _log.info(f"  Cumulative PDP: {len(cum_pdp.people)} people, {len(cum_pdp.events)} events")
    _log.info(f"  Definitions: {list(defs.keys())}")
    _log.info(f"  Calling LLM ({len(prompt)} chars)...")
    analysis = asyncio.run(
        gemini_calibration(prompt, system_instruction=CODING_ADVISOR_SYSTEM)
    )
    _log.info(f"  LLM response: {len(analysis)} chars")

    analysis = linkify_passages(analysis)
    result = {"analysis": analysis, "event": event_dict}

    # Cache in discussion
    cache = dict(discussion.calibration_advice or {})
    cache[_advice_key(statement_id, auditor_id, event_index)] = result
    discussion.calibration_advice = cache
    db.session.commit()

    return jsonify(result)


@bp.route("/irr/<int:discussion_id>", methods=["GET"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def get_cached_irr_report(discussion_id: int):
    discussion = Discussion.query.get_or_404(discussion_id)
    if discussion.calibration_report:
        return jsonify(discussion.calibration_report)
    return jsonify({"disagreements": []})


@bp.route("/irr/<int:discussion_id>", methods=["POST"])
@minimum_role(btcopilot.ROLE_AUDITOR)
def irr_report(discussion_id: int):
    discussion = Discussion.query.get_or_404(discussion_id)

    sorted_stmts = sorted(
        discussion.statements, key=lambda s: (s.order or 0, s.id or 0)
    )
    subject_stmts = [
        s for s in sorted_stmts
        if s.speaker and s.speaker.type == SpeakerType.Subject
    ]
    if not subject_stmts:
        abort(404, "No subject statements in discussion")

    last_stmt = subject_stmts[-1]

    stmt_ids = [s.id for s in sorted_stmts]
    feedbacks = Feedback.query.filter(
        Feedback.statement_id.in_(stmt_ids),
        Feedback.feedback_type == "extraction",
        Feedback.edited_extraction.isnot(None),
    ).all()
    coder_ids = list({fb.auditor_id for fb in feedbacks})

    if len(coder_ids) < 2:
        abort(400, "Need at least 2 coders for IRR calibration")

    _log.info(f"IRR calibration: discussion={discussion_id} coders={coder_ids} stmts={len(sorted_stmts)}")

    cumulative_pdps = {}
    for coder_id in coder_ids:
        cumulative_pdps[coder_id] = pdp_module.cumulative(
            discussion, last_stmt, auditor_id=coder_id
        )
        _log.info(f"  {coder_id}: {len(cumulative_pdps[coder_id].people)} people, {len(cumulative_pdps[coder_id].events)} events")

    fb_lookup = {(f.statement_id, f.auditor_id): f for f in feedbacks}
    coder_feedbacks = {}
    for coder_id in coder_ids:
        stmts_data = []
        for stmt in sorted_stmts:
            fb = fb_lookup.get((stmt.id, coder_id))
            if fb and fb.edited_extraction:
                stmts_data.append({
                    "statement_id": stmt.id,
                    "statement_text": stmt.text or "",
                    "events": fb.edited_extraction.get("events", []),
                })
        coder_feedbacks[coder_id] = stmts_data

    pending = []

    for i, coder_a in enumerate(coder_ids):
        for coder_b in coder_ids[i + 1:]:
            comparison = compare_cumulative_pdps(
                cumulative_pdps[coder_a],
                cumulative_pdps[coder_b],
                coder_a,
                coder_b,
            )
            prioritized = prioritize_disagreements(comparison)
            _log.info(f"  Pair {coder_a} vs {coder_b}: {len(prioritized)} disagreements")

            for idx, disagreement in enumerate(prioritized):
                evidence = trace_to_statements(disagreement, coder_feedbacks)

                event_for_defs = {}
                source_event = disagreement.event_a or disagreement.event_b
                if source_event:
                    event_for_defs = schema_asdict(source_event)
                definitions_text = _build_definitions_text(event_for_defs)

                coder_values_text = "\n".join(
                    f"- {fd.field}: {json.dumps(fd.values)}"
                    for fd in disagreement.field_disagreements
                )
                source_statements_text = "\n".join(
                    f"- [{ev.coder_id}] Statement {ev.statement_id}: "
                    f"{ev.statement_text[:200]}"
                    for ev in evidence
                ) or "(No source statements traced)"

                prompt = IRR_REVIEW_USER.format(
                    discussion_summary=discussion.summary or f"Discussion {discussion_id}",
                    index=idx + 1,
                    description=disagreement.description,
                    person_name=disagreement.person_name,
                    impact=disagreement.max_impact.value,
                    coder_values_text=coder_values_text,
                    source_statements_text=source_statements_text,
                    definitions_text=definitions_text,
                )

                metadata = {
                    "description": disagreement.description,
                    "person_name": disagreement.person_name,
                    "impact": disagreement.max_impact.value,
                    "coder_a": disagreement.coder_a,
                    "coder_b": disagreement.coder_b,
                    "field_disagreements": [
                        {"field": fd.field, "values": fd.values, "impact": fd.impact.value}
                        for fd in disagreement.field_disagreements
                    ],
                    "source_statements": [
                        {
                            "statement_id": ev.statement_id,
                            "statement_text": ev.statement_text[:300],
                            "coder_id": ev.coder_id,
                        }
                        for ev in evidence
                    ],
                }
                pending.append((metadata, prompt))

    _log.info(f"  Total disagreements across all pairs: {len(pending)}. Calling LLM in batches of {LLM_BATCH_SIZE}...")
    for i, (meta, prompt) in enumerate(pending):
        _log.info(f"    [{i+1}/{len(pending)}] {meta['impact']} | {meta['person_name']}: {meta['description'][:60]} ({len(prompt)} chars)")

    prompts = [p for _, p in pending]
    analyses = asyncio.run(batch_llm_calls(prompts, IRR_REVIEW_SYSTEM))
    _log.info(f"  All {len(analyses)} LLM calls complete")

    all_analyses = []
    for (metadata, _), analysis in zip(pending, analyses):
        metadata["analysis"] = linkify_passages(analysis)
        all_analyses.append(metadata)

    report = {"disagreements": all_analyses}

    # Cache in discussion
    discussion.calibration_report = report
    db.session.commit()

    return jsonify(report)
