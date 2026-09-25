"""The stand-in family the sandbox walks sign in as (INVITE_TURNS): one
finished coach reply with tool lines including reads, then a last turn that
failed after two landed calls. Every call runs through the coach's own
toolbox, so the record holds what the lines say. Run from the repo root with
the sandbox's Flask settings: uv run python btcopilot/tests/frontend/seedturns.py"""
from flask import current_app

from btcopilot.app import create_app
from btcopilot.auth.invitation import Invitation
from btcopilot.extensions import db
from btcopilot.models import Discussion, Speaker, Statement, TurnEvent
from btcopilot.routes.fixtures import install, username
from btcopilot.toolbox import READS, Toolbox
from btcopilot.toolnames import toolcall

KEY = "editable"


def run(box, calls):
    """Each call made for real, kept and named the way a live turn keeps it."""
    events = []
    for name, args in calls:
        event = toolcall(box.data, name, args)
        text, _ = box.call(name, args)
        if name not in READS:
            event["result"] = text
        events.append(event)
    return events


def keep(discussion, turn, events):
    for seq, event in enumerate(events, start=1):
        db.session.add(TurnEvent(turn_id=turn, discussion_id=discussion.id, seq=seq,
                                 kind=event["type"], payload=event))


app = create_app()
with app.app_context():
    user = install(KEY)
    diagram = user.free_diagram
    discussion = Discussion(user_id=user.id, diagram_id=diagram.id)
    db.session.add(discussion)
    db.session.flush()
    me = Speaker(discussion_id=discussion.id, name="You")
    coach = Speaker(discussion_id=discussion.id, name="Coach")
    db.session.add_all([me, coach])
    db.session.flush()
    discussion.chat_user_speaker_id = me.id
    discussion.chat_ai_speaker_id = coach.id
    said = [
        (me, "My sister Nell moved to Denver in 1994, the year after Dad's heart attack.", "t-done"),
        (coach, "Nell moving out the year after your father's heart attack is worth sitting with. Who did she stay closest to after she left?", "t-done"),
        (me, "Mostly Mom. She called her every Sunday, and Mom's drinking got worse in 1996.", "t-failed"),
    ]
    rows = []
    for order, (who, text, turn) in enumerate(said):
        s = Statement(discussion_id=discussion.id, speaker_id=who.id, text=text, order=order, turn_id=turn)
        db.session.add(s)
        rows.append(s)
    db.session.flush()
    db.session.commit()
    ada = next(p["id"] for p in diagram.get_diagram_data().people if p["name"] == "Ada")
    ben = next(p["id"] for p in diagram.get_diagram_data().people if p["name"] == "Ben")
    done = Toolbox(diagram.id, "t-done", user_id=user.id, session_id=str(discussion.id),
                   statement_id=rows[1].id)
    events = run(done, [("read_people", {}), ("read_events", {}),
                        ("edit_person", {"name": "Nell", "gender": "female"})])
    nell = int(events[-1]["result"].split()[-1].rstrip("."))
    events += run(done, [
        ("edit_event", {"kind": "noted", "description": "Moved to Denver", "date": "1994-06-01", "date_certainty": "certain", "person": nell}),
        ("show", {"kind": "triangle", "persons": [ada, nell, ben]}),
    ])
    keep(discussion, "t-done", events + [{"type": "done", "statement_id": rows[1].id}])
    failed = Toolbox(diagram.id, "t-failed", user_id=user.id, session_id=str(discussion.id),
                     statement_id=rows[2].id)
    events = run(failed, [
        ("read_notes", {}),
        ("edit_event", {"kind": "noted", "description": "Drinking got worse", "date": "1996-01-01", "date_certainty": "certain"}),
    ])
    keep(discussion, "t-failed", events + [{"type": "failed", "message": "The coach did not finish that turn."}])
    db.session.commit()
    token = Invitation.issue(username(KEY), current_app.config["INVITATION_DAYS"]).token
    print(f"discussion {discussion.id}")
    print(f"{current_app.config['SITE_URL']}/app/invite/{token}")
