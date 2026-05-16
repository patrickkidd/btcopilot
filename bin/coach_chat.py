#!/usr/bin/env python3
"""Interactive manual test harness for the Personal-app coach.

Chat with the real conversation flow (real fdserver prompts, real ask(),
persisted discussion) to feel how prompt changes land. Optional persona
script reduces tester fatigue: each turn offers a suggested user line you
accept with Enter or override by typing your own.

Usage:
    uv run python btcopilot/bin/coach_chat.py
    uv run python btcopilot/bin/coach_chat.py --diagram returning --model opus
    uv run python btcopilot/bin/coach_chat.py --diagram heavy --persona marcus

  --diagram fresh|returning|heavy
      fresh     : empty diagram (first-ever session)
      returning : parents + 1 sibling known, functioning empty (FD-325/326 core)
      heavy     : full structure, functioning thin (pattern c)
  --model opus|gemini       (default: opus — production chat model)
  --persona none|sarah|marcus  (default: none — fully freeform)

Commands during chat:
    (empty line)  accept the suggested scripted line (if a persona is set)
    /skip         skip the suggested line, type your own
    /judge        run the FD-326 judge on the conversation so far
    /quit         end session (auto-runs judge, saves transcript)
"""
import argparse
import datetime
import json
import logging
import os
import pickle
import sys
import tempfile
import warnings

# fdserver prompts must load before btcopilot.personal.prompts import.
_FD = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "fdserver",
                 "prompts", "private_prompts.py")
)
if os.path.exists(_FD):
    os.environ.setdefault("FDSERVER_PROMPTS_PATH", _FD)

# Load API keys from theapp/.env if not already in env.
_ENV = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
if os.path.exists(_ENV):
    for line in open(_ENV):
        line = line.strip()
        if line.startswith(("GOOGLE_GEMINI_API_KEY=", "ANTHROPIC_API_KEY=")):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

from btcopilot import extensions
from btcopilot.app import create_app
from btcopilot.extensions import db
from btcopilot.personal import ask
from btcopilot.personal.models import Discussion, Speaker, SpeakerType
from btcopilot.pro.models import User
from btcopilot.schema import DiagramData, asdict

try:
    from flask_mail import Mail
except ImportError:
    Mail = None

# Artifact roots. DEFAULT is the private sibling repo (btcopilot-sources/),
# OUTSIDE the open-source tree — same rule as induction reports / GT exports
# (see btcopilot/CLAUDE.md confidential-data table). Freeform sessions draw
# on real personal/family content; that must never sit inside the OSS repo,
# gitignored or not. The in-repo path is opt-in (--out shared) and only for
# synthetic-persona runs safe to share.
_PRIVATE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..",
                 "btcopilot-sources", "coach-sessions")
)
_SHARED_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "doc", "log", "coach-sessions")
)

MODELS = {"opus": "claude-opus-4-6", "gemini": "gemini-2.5-flash"}

DIAGRAMS = {
    "fresh": DiagramData(),
    "returning": DiagramData(
        people=[
            {"id": 1, "name": "Patrick", "primary": True, "parents": 100},
            {"id": 2, "name": "Mary", "gender": "female"},
            {"id": 3, "name": "John", "gender": "male"},
            {"id": 4, "name": "Sarah", "parents": 100},
        ],
        pair_bonds=[{"id": 100, "person_a": 2, "person_b": 3}],
        events=[{"id": 500, "kind": "married", "person": 2, "spouse": 3,
                 "dateTime": "1980-01-01"}],
    ),
    "heavy": DiagramData(
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
    ),
}

KNOWN_NAMES = ["Mary", "John", "Sarah", "Linda", "Tom", "Anne", "Bob", "Lisa", "Emma", "Karen"]

# Persona scripts: realistic returning-user lines to read off when freeform
# improvisation gets tiring. Go off-script anytime with /skip.
PERSONAS = {
    "sarah": [
        "Hey. Haven't been sleeping well again.",
        "I dunno, few weeks maybe. Just lying there.",
        "Work mostly. My boss has been a lot.",
        "It's whatever. Same kind of stuff.",
        "I guess. Mom's been calling more too.",
        "She gets in her head about things. Always has.",
        "I don't really want to get into all that.",
        "It was a long time ago. Doesn't matter now.",
        "Fine, yeah, my brother. We don't really talk.",
        "It is what it is. That's just how the family is.",
    ],
    "marcus": [
        "So I had this whole thing with my girlfriend this weekend, it was a lot.",
        "She said I shut down whenever things get serious, which, maybe.",
        "My sister says I have commitment issues but it's more complicated.",
        "I mean my parents are still together but it was never warm exactly.",
        "Dad was a teacher, very contained. Mom did everything emotional.",
        "I think I do the dad thing honestly. Go quiet.",
        "There was this period in college where I just cut everyone off.",
        "I don't know why I'm telling you all this, sorry, rambling.",
        "It connects though right? Like it's all the same pattern?",
        "Yeah. I guess I never really looked at it that way.",
    ],
}

# One-paragraph SARF read of each persona, printed at startup so the tester
# knows the clinical picture they're walking into (symptom, anxiety,
# relationship, functioning).
PERSONA_SARF = {
    "sarah": (
        "Sarah presents with recurrent insomnia (symptom) that flares with "
        "work pressure and increased contact from her mother, who is a "
        "chronic worrier — the family's anxiety runs through Sarah as the one "
        "who absorbs it. The key relationships are an enmeshed, draining tie "
        "with her mother and an emotional cutoff with her brother that she "
        "won't discuss. Functioning is holding but brittle: she copes by "
        "minimizing and deflecting ('it is what it is, that's just how the "
        "family is'), which keeps the pattern intact and the symptom cycling."
    ),
    "marcus": (
        "Marcus presents with relationship distress (symptom): he shuts down "
        "and goes quiet when intimacy intensifies, just flagged by his "
        "girlfriend and his sister. The anxiety is around commitment and "
        "closeness. Relationally his parents stayed together but emotionally "
        "cold — a contained, distancing father and an over-functioning "
        "emotional mother — and Marcus reproduces the father's withdrawal, "
        "including a college period of total cutoff. Functioning is "
        "reasonable and his insight is rising: he is starting to see the "
        "distancing as a multigenerational pattern rather than a personal flaw."
    ),
}


def _load_real_diagram_bytes(diagram_id):
    """Read-only SELECT of one real Diagram's pickled data. No app init, no
    writes, connection disposed immediately."""
    from sqlalchemy import create_engine, text as _sql

    uri = os.environ.get(
        "SQLALCHEMY_DATABASE_URI",
        "postgresql://familydiagram:pks@localhost:5432/familydiagram",
    )
    eng = create_engine(uri)
    try:
        with eng.connect() as c:
            row = c.execute(
                _sql("SELECT data FROM diagrams WHERE id = :i"),
                {"i": diagram_id},
            ).fetchone()
    finally:
        eng.dispose()
    if row is None or row[0] is None:
        sys.exit(f"Diagram {diagram_id} not found / has no data.")
    return bytes(row[0])


def build(diagram_key, model_key, persona_key, from_diagram=None):
    """Fully sandboxed: in-memory sqlite, fresh synthetic user. Never writes
    to the postgres dev DB. With from_diagram, the real diagram's committed
    state is read once (SELECT only) and injected into the sandbox."""
    real_bytes = _load_real_diagram_bytes(from_diagram) if from_diagram else None
    tmp = tempfile.mkdtemp(prefix="coach_chat_")
    app = create_app(config={
        "ENV": "unittest",
        "CONFIG": "testing",
        "TESTING": True,
        "SECRET_KEY": "coach_chat",
        "FD_DIR": tmp,
        "DATABASE": tmp,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "CELERY_BROKER_URL": "memory://",
        "CELERY_RESULT_BACKEND": "cache+memory://",
        "SCHEDULER_API_ENABLED": False,
    })
    app.instance_path = tmp
    if Mail is not None:
        extensions.mail = Mail()
        extensions.mail.init_app(app)
    app.app_context().push()
    db.create_all()

    user = User(
        status="confirmed", username="coach_chat@example.com",
        password="x", first_name="Coach", last_name="Chat",
    )
    user._plaintext_password = "x"
    db.session.add(user)
    db.session.merge(user)
    if real_bytes is not None:
        user.set_free_diagram(real_bytes)
    else:
        user.set_free_diagram(pickle.dumps(asdict(DIAGRAMS[diagram_key])))
    db.session.commit()
    diagram = user.free_diagram

    disc = Discussion(
        user_id=user.id, diagram_id=diagram.id,
        summary=f"coach_chat {diagram_key}/{model_key}/{persona_key}",
    )
    db.session.add(disc)
    db.session.flush()
    us = Speaker(discussion_id=disc.id, name="Tester", type=SpeakerType.Subject, person_id=1)
    es = Speaker(discussion_id=disc.id, name="Coach", type=SpeakerType.Expert)
    db.session.add_all([us, es])
    db.session.flush()
    disc.chat_user_speaker_id = us.id
    disc.chat_ai_speaker_id = es.id
    db.session.commit()
    return disc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diagram", choices=DIAGRAMS, default="returning")
    ap.add_argument("--model", choices=MODELS, default="opus")
    ap.add_argument("--persona", choices=["none", *PERSONAS], default="none")
    ap.add_argument(
        "--out", choices=["private", "shared"], default="private",
        help="private = btcopilot-sources/ (default, never in OSS repo); "
        "shared = in-repo doc/log (synthetic personas only, no real data)",
    )
    ap.add_argument(
        "--from-diagram", type=int, default=None,
        help="Read a real diagram's committed state (SELECT only) and run "
        "the chat against it in the sandbox. Forces --out private.",
    )
    args = ap.parse_args()
    if args.from_diagram is not None:
        args.out = "private"  # real personal content — never sharable
    if args.out == "shared" and args.persona == "none":
        sys.exit("Refusing --out shared with --persona none: freeform "
                 "sessions may contain personal content. Use --out private.")

    disc = build(args.diagram, args.model, args.persona,
                 from_diagram=args.from_diagram)
    model_id = MODELS[args.model]
    script = PERSONAS.get(args.persona, [])
    transcript = []

    # Interactive feel-test: keep the console to persona/coach turns only.
    # Framework INFO logs and deprecation warnings go to a side log, not the
    # REPL. ERROR+ still surfaces so real failures aren't hidden.
    logging.disable(logging.WARNING)
    warnings.filterwarnings("ignore")

    print(f"\ncoach_chat | diagram={args.diagram} model={args.model} "
          f"persona={args.persona}")
    sarf = PERSONA_SARF.get(args.persona)
    if sarf:
        print(f"\n[persona SARF] {sarf}\n")
    print("Enter=accept suggested line | /skip | /judge | /quit\n")

    i = 0
    while True:
        # Suggested line is an icebreaker only — show it before the first
        # user turn, then get out of the way.
        suggested = script[i] if i < len(script) else None
        if suggested and not transcript:
            print(f"  [suggested] {suggested}")
        try:
            raw = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            raw = "/quit"

        if raw == "/quit":
            break
        if raw == "/judge":
            _run_judge(transcript)
            continue
        if raw == "/skip":
            i += 1
            continue
        user_text = raw if raw else (suggested or "")
        if not user_text:
            continue
        if not raw and suggested:
            i += 1

        resp = ask(disc, user_text, model=model_id)
        db.session.commit()  # persist turn so next ask() sees the history
        transcript.append(("user", user_text))
        transcript.append(("ai", resp.statement))
        print(f"\ncoach> {resp.statement}\n")

    if transcript:
        scores = _run_judge(transcript)
        _write_artifact(args, transcript, scores)


def _run_judge(transcript):
    if not transcript:
        print("(nothing to judge yet)")
        return None
    from btcopilot.personal.fd326_eval import evaluate_fd326

    s = evaluate_fd326(transcript, KNOWN_NAMES)
    v = "PASS" if s.passed else "FAIL"
    print(f"\n[FD326 {v}] engage={s.current_events_engagement} "
          f"names={s.name_usage} no_pivot={s.no_premature_pivot} "
          f"no_pitch={s.no_theory_pitch} returns={s.returns_to_collection}"
          f"\n  {s.notes}")
    return s


def _write_artifact(args, transcript, scores):
    artifact_dir = _SHARED_DIR if args.out == "shared" else _PRIVATE_DIR
    os.makedirs(artifact_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{ts}_{args.diagram}_{args.model}_{args.persona}"
    verdict = "PASS" if (scores and scores.passed) else "FAIL"

    md = [
        f"# Coach session {ts}",
        "",
        f"- diagram: `{args.diagram}` | model: `{args.model}` | "
        f"persona: `{args.persona}`",
        f"- FD-326 judge: **{verdict}**"
        + (f" — engage={scores.current_events_engagement} "
           f"names={scores.name_usage} no_pivot={scores.no_premature_pivot} "
           f"no_pitch={scores.no_theory_pitch} "
           f"returns={scores.returns_to_collection}" if scores else ""),
        f"- judge notes: {scores.notes if scores else '(none)'}",
        "",
        "## Transcript",
        "",
    ]
    for role, text in transcript:
        who = "**You**" if role == "user" else "**Coach**"
        md.append(f"{who}: {text}\n")
    md += [
        "## Reviewer notes (Patrick)",
        "",
        "_Human read is the final gate. Note where it felt off, where it "
        "felt human, and any pattern the judge missed._",
        "",
        "- ",
        "",
    ]
    md_path = os.path.join(artifact_dir, stem + ".md")
    json_path = os.path.join(artifact_dir, stem + ".json")
    with open(md_path, "w") as f:
        f.write("\n".join(md))
    with open(json_path, "w") as f:
        json.dump({
            "timestamp": ts,
            "diagram": args.diagram,
            "model": args.model,
            "persona": args.persona,
            "judge": (None if not scores else {
                "passed": scores.passed,
                "current_events_engagement": scores.current_events_engagement,
                "name_usage": scores.name_usage,
                "no_premature_pivot": scores.no_premature_pivot,
                "no_theory_pitch": scores.no_theory_pitch,
                "returns_to_collection": scores.returns_to_collection,
                "notes": scores.notes,
            }),
            "transcript": [{"role": r, "text": t} for r, t in transcript],
        }, f, indent=2)
    print(f"\nArtifact: {md_path}")
    print("Add your read under 'Reviewer notes' — that's the final gate.")


if __name__ == "__main__":
    main()
