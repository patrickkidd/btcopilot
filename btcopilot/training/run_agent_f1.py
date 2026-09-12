"""F1 for the agent loop — replays a discussion's user statements through the
coach and scores the record the coach leaves behind.

The batch harness (run_extract_full_f1) hands a whole transcript to extraction
in one call. This one feeds the same user statements one at a time through
`CoachTurn`, so the coach's own replies are in the history the next turn sees,
and the record is built by tool calls rather than by one extraction. Ground
truth loading and scoring are the batch harness's own functions, so the two
numbers are comparable.

The GT discussion and its diagram are never written to: each replay gets a
fresh diagram and a fresh discussion copy.

Usage:
    uv run python -m btcopilot.training.run_agent_f1
    uv run python -m btcopilot.training.run_agent_f1 --discussion 50
    uv run python -m btcopilot.training.run_agent_f1 --model claude-sonnet-5
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from flask import current_app

from btcopilot import diagramjson
from btcopilot.app import create_app
from btcopilot.extensions import db
from btcopilot.personal.coachmodel import CoachModel
from btcopilot.personal.coachturn import CoachTurn, EventKind
from btcopilot.personal.models import Discussion, Speaker, SpeakerType
from btcopilot.personal.recordtext import date_text
from btcopilot.pro.models import Diagram
from btcopilot.schema import PDP, DiagramData, Event, PairBond, Person, from_dict
from btcopilot.training.run_extract_full_f1 import (
    gt_discussion_ids,
    gt_pdp_for,
    report,
    score,
)

_log = logging.getLogger(__name__)

HARNESS = "agent"
RESULTS_DIR = "f1_runs"


def record_pdp(data: DiagramData) -> PDP:
    """The record as a PDP, so the batch harness's scorer can read it.

    The record holds plain chunks and the scorer matches typed items.
    """
    return PDP(
        people=[from_dict(Person, p) for p in data.people],
        events=[from_dict(Event, _dated(e)) for e in data.events],
        pair_bonds=[from_dict(PairBond, b) for b in data.pair_bonds],
    )


def _dated(event: dict) -> dict:
    return dict(
        event,
        dateTime=date_text(event.get("dateTime")),
        endDateTime=date_text(event.get("endDateTime")),
    )


def user_statements(discussion) -> list[str]:
    """What the person said, in order. The coach's own replies are not replayed
    — the coach writes new ones as it goes."""
    ordered = sorted(discussion.statements, key=lambda s: (s.order or 0, s.id or 0))
    return [
        s.text
        for s in ordered
        if s.text and s.speaker and s.speaker.type == SpeakerType.Subject
    ]


def replay_copy(discussion) -> Discussion:
    """A fresh diagram and a fresh session for one replay."""
    diagram = Diagram(
        user_id=discussion.user_id,
        name=f"agent-f1 replay of discussion {discussion.id}",
        data=diagramjson.dumps({}),
    )
    db.session.add(diagram)
    db.session.flush()

    copy = Discussion(
        user_id=discussion.user_id,
        diagram_id=diagram.id,
        # A title already set keeps the turn from spending a model call naming
        # the session, which this harness does not measure.
        title=f"agent-f1 replay of discussion {discussion.id}",
        title_set_by_user=True,
        summary=discussion.summary,
        discussion_date=discussion.discussion_date,
        speakers=[
            Speaker(name="Client", type=SpeakerType.Subject, person_id=1),
            Speaker(name="Coach", type=SpeakerType.Expert),
        ],
    )
    db.session.add(copy)
    db.session.flush()
    copy.chat_user_speaker_id = copy.speakers[0].id
    copy.chat_ai_speaker_id = copy.speakers[1].id
    db.session.commit()
    return copy


def replay(discussion, model=None) -> tuple[Discussion, dict]:
    """Feed every user statement through the loop. A turn that raises is
    counted and the replay carries on: the record refusing an edit comes back
    as a tool result, so an exception here is the loop itself failing."""
    copy = replay_copy(discussion)
    counts = {"turns": 0, "tool_calls": 0, "failed_turns": 0}

    for text in user_statements(discussion):
        counts["turns"] += 1
        try:
            reply = CoachTurn(
                copy, text, model=model, session_id=f"agent-f1-{discussion.id}"
            ).run()
        except Exception as e:
            db.session.rollback()
            counts["failed_turns"] += 1
            _log.warning(f"Discussion {discussion.id} turn {counts['turns']} failed: {e}")
            continue
        counts["tool_calls"] += sum(
            1 for event in reply["events"] if event["type"] == EventKind.ToolCall.value
        )

    return copy, counts


def write_result(payload: dict) -> Path:
    """The batch harness prints and returns but writes nothing, so this run
    lands under the instance folder rather than beside a file that is not
    there."""
    folder = Path(current_app.instance_path) / RESULTS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{HARNESS}-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def run_agent_f1(discussion_id=None, model=None):
    # A name names the real coach; anything else is a model a caller already
    # built, which is how a test drives the loop without the wire.
    coach = CoachModel(model=model) if isinstance(model, str) else model
    if isinstance(model, str):
        print(f"Using coach model: {model}\n")

    disc_ids = gt_discussion_ids(discussion_id)
    if not disc_ids:
        print("No discussions with approved GT found.")
        return None

    print(f"Replaying the agent loop on {len(disc_ids)} discussion(s)...\n")

    results = []
    errors = []
    run_start = time.time()

    for disc_id in disc_ids:
        discussion = db.session.get(Discussion, disc_id)
        print(f"Disc {disc_id} ({discussion.summary})...", end=" ", flush=True)
        disc_start = time.time()

        try:
            copy, counts = replay(discussion, model=coach)
        except Exception as e:
            elapsed = time.time() - disc_start
            print(f"REPLAY FAILED ({elapsed:.1f}s): {e}")
            errors.append((disc_id, str(e)))
            continue

        ai_pdp = record_pdp(copy.diagram.get_diagram_data())
        gt_pdp = gt_pdp_for(discussion)

        elapsed = time.time() - disc_start
        result = {
            "discussion_id": disc_id,
            "summary": discussion.summary,
            **score(ai_pdp, gt_pdp, dump_id=disc_id),
            **counts,
            "replay_discussion_id": copy.id,
            "elapsed": elapsed,
        }
        results.append(result)

        print(
            f"People={result['people_f1']:.3f} Events={result['events_f1']:.3f} "
            f"Bonds={result['pair_bonds_f1']:.3f} Agg={result['aggregate_f1']:.3f} "
            f"turns={counts['turns']} calls={counts['tool_calls']} ({elapsed:.1f}s)"
        )

    if not results:
        print("\nNo discussions could be evaluated.")
        if errors:
            print(f"Errors: {errors}")
        return None

    totals = report(results, errors, time.time() - run_start, HARNESS)
    totals["model"] = model if isinstance(model, str) else None
    print(f"\nWrote {write_result(totals)}")
    return totals


def main():
    parser = argparse.ArgumentParser(
        description="Score the agent loop's record against GT"
    )
    parser.add_argument("--discussion", type=int, help="Only replay this discussion ID")
    parser.add_argument("--model", type=str, help="Override the coach model")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        result = run_agent_f1(discussion_id=args.discussion, model=args.model)
        sys.exit(0 if result and result["count"] > 0 else 1)


if __name__ == "__main__":
    main()
