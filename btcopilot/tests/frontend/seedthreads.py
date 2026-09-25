"""Threads for web/tests/visual/sandboxthreads.spec.ts: one stand-in user per
thread shape, each with its own sign-in link. Prints JSON
{key: {"discussion": id, "link": url}}; save it and name the file in
THREAD_LINKS. Run from the repo root with the sandbox's Flask settings:
uv run python btcopilot/tests/frontend/seedthreads.py [site_url]"""
import json
import sys

from flask import current_app

from btcopilot.app import create_app
from btcopilot.auth.invitation import Invitation
from btcopilot.extensions import db
from btcopilot.models import Discussion, Speaker, Statement, TurnEvent
from btcopilot.routes import fixtures
from btcopilot.routes.fixtures import _event, _person, install, username
from btcopilot.schema import DiagramData
from btcopilot.toolnames import toolcall

SITE = sys.argv[1] if len(sys.argv) > 1 else None
L60 = "Bartholomew Maximilian Worthington-Fairweather the Younger II"[:60]
E60 = "Moved across the country after the long argument about the fa"[:60]


def call(tool, refusal=None, **args):
    return {"type": "tool_call", "name": tool, "args": args, "refusal": refusal}


def record(people, events):
    return lambda: DiagramData(people=people, events=events, lastItemId=100)


LONG = record(
    [_person(1, L60, primary=True), _person(2, L60[::-1].strip())],
    [_event(10, "1994-06-01", E60), _event(11, "1996-01-01", E60[::-1], person=2)],
)
UNI = record(
    [_person(1, "Chloë Ångström-Nguyễn", primary=True), _person(2, "王小明"), _person(3, "Ólafur Þórðarson")],
    [_event(10, "1994-06-01", "Chloë moved to Montréal — für immer", person=1), _event(11, "2001-09-01", "王小明 started school", person=2)],
)
SMALL = record([_person(1, "Ada", primary=True)], [_event(10, "2014-03-02", "Moved out")])

MANY = [call("read_people"), call("read_events", ids=[10, 11], words=True), call("read_notes"), call("read_changes")]
MANY += [call("edit_person", name=f"Cousin {i}") for i in range(1, 11)]
MANY += [call("edit_event", id=10, description="Changed wording"), call("remove", item_kind="event", item_id=11), call("undo"), call("show", refusal="No people were named.", kind="triangle")]
MANY += [call("edit_event", description=f"Event number {i}", date=f"19{70+i}-01-01") for i in range(1, 7)]

THREADS = {
    # key: (record, [(role, text, turn)], {turn: events})
    "v-empty": (SMALL, [], {}),
    "v-one": (SMALL, [("user", "My mother drank.", None)], {}),
    "v-long": (LONG, [
        ("user", f"{L60} moved away. " * 3, "t-long"),
        ("coach", f"What happened when {L60} left? " + "x" * 200, "t-long"),
    ], {"t-long": [call("read_people"), call("edit_person", name=L60), call("edit_event", description=E60, date="1994-06-01"), call("edit_event", id=10, description=E60 + E60)]}),
    "v-uni": (UNI, [
        ("user", "Chloë Ångström-Nguyễn and 王小明 are cousins.", "t-uni"),
        ("coach", "How did Chloë Ångström-Nguyễn and 王小明 meet? 🙂", "t-uni"),
    ], {"t-uni": [call("read_people"), call("edit_person", name="Chloë Ångström-Nguyễn"), call("edit_person", name="王小明"), call("edit_event", description="Chloë moved to Montréal — für immer", date="1994-06-01")]}),
    "v-many": (SMALL, [
        ("user", "Tell me about all my cousins.", "t-many"),
        ("coach", "I've added ten cousins and six events. Which one were you closest to?", "t-many"),
    ], {"t-many": MANY}),
    "v-failmid": (SMALL, [
        ("user", "My father left in 1980.", "t-fm"),
        ("user", "Anyway, and then my mother remarried.", "t-ok"),
        ("coach", "When did she remarry?", "t-ok"),
    ], {"t-fm": [call("read_events"), call("edit_event", description="Father left", date="1980-01-01")],
        "t-ok": [call("read_people")]}),
    "v-failnolines": (SMALL, [("user", "Hello there.", "t-fn")], {"t-fn": []}),
}

app = create_app()
out = {}
with app.app_context():
    for key, (builder, said, turns) in THREADS.items():
        fixtures.FIXTURES[key] = (builder, None)
        user = install(key)
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
        rows = {}
        for order, (who, text, turn) in enumerate(said):
            s = Statement(discussion_id=discussion.id, speaker_id=(coach if who == "coach" else me).id,
                          text=text, order=order, turn_id=turn)
            db.session.add(s)
            db.session.flush()
            if who == "coach":
                rows[turn] = s.id
        for turn, events in turns.items():
            ending = ({"type": "done", "statement_id": rows[turn]} if turn in rows
                      else {"type": "failed", "message": "The coach did not finish that turn."})
            data = diagram.get_diagram_data()
            kept = [dict(toolcall(data, e["name"], e["args"]), refusal=e["refusal"]) for e in events]
            for seq, event in enumerate(kept + [ending], start=1):
                db.session.add(TurnEvent(turn_id=turn, discussion_id=discussion.id, seq=seq,
                                         kind=event["type"], payload=event))
        db.session.commit()
        token = Invitation.issue(username(key), current_app.config["INVITATION_DAYS"]).token
        out[key] = {"discussion": discussion.id, "link": f"{SITE or current_app.config['SITE_URL']}/app/invite/{token}"}
print(json.dumps(out))
