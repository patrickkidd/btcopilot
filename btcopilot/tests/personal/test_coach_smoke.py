"""Single-turn smoke for FD-325/326: returning-user ask() with pre-populated
diagram + blank conversation history. Verifies the new committed_state
plumbing produces coherent coach output and (qualitatively) that the prompt
is steering toward outstanding categories.

Run: uv run pytest btcopilot/btcopilot/tests/personal/test_coach_smoke.py -v -m e2e -s
"""
import pickle

import pytest

from btcopilot.extensions import db
from btcopilot.personal import ask
from btcopilot.personal.models import Discussion, Speaker, SpeakerType
from btcopilot.schema import DiagramData, asdict


@pytest.fixture
def returning_user_setup(test_user):
    """Pre-populate the user's free_diagram with structure-only intake from a
    prior session: parents and one sibling known; grandparents/spouse/children
    not yet covered; no SARF/functioning data at all."""
    diagram = test_user.free_diagram
    dd = DiagramData(
        people=[
            {"id": 1, "name": "Patrick", "primary": True, "parents": 100},
            {"id": 2, "name": "Mary", "gender": "female"},
            {"id": 3, "name": "John", "gender": "male"},
            {"id": 4, "name": "Sarah", "parents": 100},
        ],
        pair_bonds=[{"id": 100, "person_a": 2, "person_b": 3}],
        events=[
            {"id": 500, "kind": "married", "person": 2, "spouse": 3,
             "dateTime": "1980-01-01"},
        ],
    )
    dd.lastItemId = 500
    diagram.data = pickle.dumps(asdict(dd))
    db.session.commit()

    discussion = Discussion(
        user_id=test_user.id,
        diagram_id=diagram.id,
        summary="FD-326 smoke: returning user, structure partial, functioning empty",
    )
    db.session.add(discussion)
    db.session.flush()
    user_speaker = Speaker(
        discussion_id=discussion.id, name="Patrick",
        type=SpeakerType.Subject, person_id=1,
    )
    ai_speaker = Speaker(
        discussion_id=discussion.id, name="Coach", type=SpeakerType.Expert,
    )
    db.session.add_all([user_speaker, ai_speaker])
    db.session.flush()
    discussion.chat_user_speaker_id = user_speaker.id
    discussion.chat_ai_speaker_id = ai_speaker.id
    db.session.commit()
    return discussion


@pytest.mark.e2e
def test_smoke_opus_returning_user(returning_user_setup):
    discussion = returning_user_setup
    user_msg = "Hey, I've been having a rough week. My boss has been on my case and I haven't been sleeping well."
    response = ask(discussion, user_msg, model="claude-opus-4-6")
    tr = [("user", user_msg), ("ai", response.statement)]
    _judge("(a) opening-current-events Opus", tr)
    assert response.statement and len(response.statement) > 20


@pytest.mark.e2e
def test_smoke_gemini_returning_user(returning_user_setup):
    discussion = returning_user_setup
    user_msg = "Hey, I've been having a rough week. My boss has been on my case and I haven't been sleeping well."
    response = ask(discussion, user_msg, model="gemini-2.5-flash")
    tr = [("user", user_msg), ("ai", response.statement)]
    _judge("(a) opening-current-events Gemini", tr)
    assert response.statement and len(response.statement) > 20


def _multi_turn(discussion, user_turns, model):
    transcript = []
    for u in user_turns:
        r = ask(discussion, u, model=model)
        db.session.commit()  # persist turn so next ask() sees the history
        transcript.append(("user", u))
        transcript.append(("ai", r.statement))
    return transcript


_KNOWN = ["Mary", "John", "Sarah"]


def _judge(label, transcript, known=None):
    from btcopilot.personal.coacheval import evaluate_coach

    s = evaluate_coach(transcript, known if known is not None else _KNOWN)
    verdict = "PASS" if s.passed else "FAIL"
    print(
        f"\n[FD326 {verdict}] {label} | "
        f"returns={s.returns_to_collection} "
        f"engage={s.current_events_engagement} "
        f"names={s.name_usage} "
        f"no_pivot={s.no_premature_pivot} "
        f"no_pitch={s.no_theory_pitch} | {s.notes}"
    )
    return s


def _print_transcript(label, transcript):
    print(f"\n=== {label} ===")
    for role, text in transcript:
        print(f"\n[{role}] {text}")


# AC pattern (b): user cycles on the same complaint without adding new info.
# By turn 4-5 the coach should bridge gracefully rather than continue probing.
@pytest.mark.e2e
def test_pattern_b_shallow_cycling_opus(returning_user_setup):
    user_turns = [
        "Hey, I've been having a rough week. My boss has been on my case and I haven't been sleeping well.",
        "I dunno, just stuff piling up.",
        "It's whatever. Just been a bad stretch.",
        "Yeah, I guess. Same kind of stuff.",
        "It is what it is.",
    ]
    transcript = _multi_turn(returning_user_setup, user_turns, model="claude-opus-4-6")
    _print_transcript("Pattern (b) Opus", transcript)
    _judge("(b) shallow-cycling Opus", transcript)
    assert transcript[-1][1]


@pytest.mark.e2e
def test_pattern_b_shallow_cycling_gemini(returning_user_setup):
    user_turns = [
        "Hey, I've been having a rough week. My boss has been on my case and I haven't been sleeping well.",
        "I dunno, just stuff piling up.",
        "It's whatever. Just been a bad stretch.",
        "Yeah, I guess. Same kind of stuff.",
        "It is what it is.",
    ]
    transcript = _multi_turn(returning_user_setup, user_turns, model="gemini-2.5-flash")
    _print_transcript("Pattern (b) Gemini", transcript)
    _judge("(b) shallow-cycling Gemini", transcript)
    assert transcript[-1][1]


# AC pattern (c): structurally complete returning user with functioning thin.
# Coach should engage with present, then over time draw out functioning data
# (relationship patterns, symptom-event connections) rather than re-asking
# for names or dates that are already known.
@pytest.fixture
def heavy_structure_thin_functioning(test_user):
    diagram = test_user.free_diagram
    dd = DiagramData(
        people=[
            {"id": 1, "name": "Patrick", "primary": True, "parents": 100},
            {"id": 2, "name": "Mary", "gender": "female", "parents": 200},
            {"id": 3, "name": "John", "gender": "male", "parents": 300},
            {"id": 4, "name": "Sarah", "parents": 100},
            {"id": 5, "name": "Linda", "gender": "female"},
            {"id": 6, "name": "Tom", "gender": "male"},
            {"id": 7, "name": "Anne", "gender": "female"},
            {"id": 8, "name": "Bob", "gender": "male"},
            {"id": 9, "name": "Lisa", "gender": "female"},
            {"id": 10, "name": "Emma", "parents": 400},
            {"id": 11, "name": "Karen", "parents": 200},
        ],
        pair_bonds=[
            {"id": 100, "person_a": 2, "person_b": 3},
            {"id": 200, "person_a": 5, "person_b": 6},
            {"id": 300, "person_a": 7, "person_b": 8},
            {"id": 400, "person_a": 1, "person_b": 9},
        ],
        events=[
            {"id": 500, "kind": "married", "person": 2, "spouse": 3, "dateTime": "1980-01-01"},
            {"id": 501, "kind": "death", "person": 6, "dateTime": "2010-01-01"},
            {"id": 502, "kind": "moved", "person": 1, "dateTime": "2018-01-01"},
        ],
    )
    dd.lastItemId = 502
    diagram.data = pickle.dumps(asdict(dd))
    db.session.commit()

    discussion = Discussion(
        user_id=test_user.id, diagram_id=diagram.id,
        summary="Pattern (c): structure heavy, functioning thin",
    )
    db.session.add(discussion)
    db.session.flush()
    user_speaker = Speaker(
        discussion_id=discussion.id, name="Patrick",
        type=SpeakerType.Subject, person_id=1,
    )
    ai_speaker = Speaker(
        discussion_id=discussion.id, name="Coach", type=SpeakerType.Expert,
    )
    db.session.add_all([user_speaker, ai_speaker])
    db.session.flush()
    discussion.chat_user_speaker_id = user_speaker.id
    discussion.chat_ai_speaker_id = ai_speaker.id
    db.session.commit()
    return discussion


@pytest.mark.e2e
def test_pattern_c_long_session_opus(heavy_structure_thin_functioning):
    user_turns = [
        "Sleep has been bad again. Started a couple weeks back.",
        "Yeah, just lying there. Mind racing about work.",
        "Boss thing has been stressful. Been like that on and off for a while.",
        "I guess. Mary has been calling more lately too. That doesn't help.",
        "She gets in her head about things. Always has.",
    ]
    transcript = _multi_turn(heavy_structure_thin_functioning, user_turns, model="claude-opus-4-6")
    _print_transcript("Pattern (c) Opus", transcript)
    _judge("(c) long-session Opus", transcript)
    assert transcript[-1][1]


@pytest.mark.e2e
def test_pattern_c_long_session_gemini(heavy_structure_thin_functioning):
    user_turns = [
        "Sleep has been bad again. Started a couple weeks back.",
        "Yeah, just lying there. Mind racing about work.",
        "Boss thing has been stressful. Been like that on and off for a while.",
        "I guess. Mary has been calling more lately too. That doesn't help.",
        "She gets in her head about things. Always has.",
    ]
    transcript = _multi_turn(heavy_structure_thin_functioning, user_turns, model="gemini-2.5-flash")
    _print_transcript("Pattern (c) Gemini", transcript)
    _judge("(c) long-session Gemini", transcript)
    assert transcript[-1][1]
