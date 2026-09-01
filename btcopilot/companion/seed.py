"""Seed a throwaway companion-test diagram for a user: 6-person family, 2
couples, 26 dated events with mixed certainty, exercising every DRAWABILITY
rule (3-point line, dots-only lane, gap, explicit same, touching approximate
ranges, undated shelf). Never touches any diagram it did not create.

Usage: FLASK_CONFIG=development python -m btcopilot.companion.seed [username]
"""

import pickle
import sys

from btcopilot.schema import (
    DateCertainty,
    DiagramData,
    Event,
    EventKind,
    PairBond,
    Person,
    VariableShift,
    asdict,
)

SEED_DIAGRAM_NAME = "FD-360 Companion Seed"


def _person(id, name, last_name=None, primary=False):
    chunk = asdict(Person(id=id, name=name, last_name=last_name))
    if primary:
        chunk["primary"] = True
    return chunk


def _event(id, kind, **kwargs):
    return asdict(Event(id=id, kind=kind, **kwargs))


def seed_diagram_data() -> DiagramData:
    C, A, U = DateCertainty.Certain, DateCertainty.Approximate, DateCertainty.Unknown
    up, down, same = VariableShift.Up, VariableShift.Down, VariableShift.Same
    shift = EventKind.Shift

    people = [
        _person(1, "Alex", "Harmon", primary=True),
        _person(2, "Assistant"),
        _person(3, "Sam", "Harmon"),
        _person(4, "Diane", "Voss"),
        _person(5, "Robert", "Voss"),
        _person(6, "Kate", "Voss"),
        _person(7, "Earl", "Voss"),
    ]
    pair_bonds = [
        asdict(PairBond(id=8, person_a=1, person_b=3, married=True)),
        asdict(PairBond(id=9, person_a=4, person_b=5, married=True)),
    ]
    events = [
        # Alex symptoms: 3 directed + explicit same; 2005->2015 is the gap
        _event(10, shift, person=1, dateTime="1995-06-15", dateCertainty=A,
               symptom=up, description="Sleep got worse"),
        _event(11, shift, person=1, dateTime="2005-03-10", dateCertainty=C,
               symptom=up, description="Sleep problems deepened"),
        _event(12, shift, person=1, dateTime="2015-09-01", dateCertainty=A,
               symptom=down, description="Sleep began to ease"),
        _event(13, shift, person=1, dateTime="2020-01-10", dateCertainty=C,
               symptom=same, description="Sleep unchanged at check-in"),
        # Alex anxiety: only 2 directed -> dots only
        _event(14, shift, person=1, dateTime="2018-02-01", dateCertainty=C,
               anxiety=up, description="Worry spiked at work"),
        _event(15, shift, person=1, dateTime="2019-07-01", dateCertainty=A,
               anxiety=down, description="Settled down after the move"),
        # Sam functioning: 4 directed -> line
        _event(16, shift, person=3, dateTime="2010-05-01", dateCertainty=A,
               functioning=down, description="Dropped out of school"),
        _event(17, shift, person=3, dateTime="2012-08-15", dateCertainty=C,
               functioning=up, description="Started the new job"),
        _event(18, shift, person=3, dateTime="2016-04-01", dateCertainty=C,
               functioning=up, description="Promoted to manager"),
        _event(19, shift, person=3, dateTime="2021-11-05", dateCertainty=C,
               functioning=down, description="Burned out and cut hours"),
        # Diane symptoms: 2 directed -> dots only
        _event(20, shift, person=4, dateTime="1988-03-01", dateCertainty=A,
               symptom=up, description="Headaches began"),
        _event(21, shift, person=4, dateTime="1992-06-01", dateCertainty=A,
               symptom=down, description="Headaches let up"),
        # Robert anxiety: 3 directed -> line
        _event(22, shift, person=5, dateTime="1985-09-01", dateCertainty=A,
               anxiety=up, description="Money pressure started"),
        _event(23, shift, person=5, dateTime="1990-01-15", dateCertainty=A,
               anxiety=up, description="Laid off from the mill"),
        _event(24, shift, person=5, dateTime="1993-04-01", dateCertainty=A,
               anxiety=down, description="Found steady work again"),
        # Kate functioning: 2 directed -> dots only
        _event(25, shift, person=6, dateTime="2008-09-01", dateCertainty=C,
               functioning=up, description="Moved out on her own"),
        _event(26, shift, person=6, dateTime="2014-02-01", dateCertainty=C,
               functioning=down, description="Came back home for a while"),
        # Earl symptoms: 1 point
        _event(27, shift, person=7, dateTime="2000-01-01", dateCertainty=A,
               symptom=up, description="Health started failing"),
        # Structural events
        _event(28, EventKind.Married, person=1, spouse=3, dateTime="2018-05-20",
               dateCertainty=C),
        _event(29, EventKind.Moved, person=1, spouse=3, dateTime="2019-03-01",
               dateCertainty=A, description="Moved across town"),
        # Touching approximate pair: this 1994 move vs Alex's 1995 sleep onset
        _event(30, EventKind.Moved, person=1, dateTime="1994-08-01",
               dateCertainty=A, description="The family moved"),
        _event(31, EventKind.Married, person=4, spouse=5, dateTime="1985-06-15",
               dateCertainty=A),
        _event(32, EventKind.Birth, person=4, spouse=5, child=1,
               dateTime="1980-04-12", dateCertainty=C),
        _event(33, EventKind.Birth, person=4, spouse=5, child=6,
               dateTime="1983-09-30", dateCertainty=C),
        # Also touches Alex's 1995 sleep onset range
        _event(34, EventKind.Separated, person=4, spouse=5, dateTime="1996-10-01",
               dateCertainty=A),
        _event(35, EventKind.Death, person=7, dateTime="2009-05-01",
               dateCertainty=A),
        # Undated shelf
        _event(36, shift, person=7, dateCertainty=U,
               description="Family never talked about Earl's drinking"),
        _event(37, shift, person=1, dateTime="2003-01-01", dateCertainty=U,
               symptom=up, description="A rough patch no one can place"),
        _event(38, shift, person=4, anxiety=up, dateCertainty=U),
    ]
    return DiagramData(
        people=people, events=events, pair_bonds=pair_bonds, lastItemId=40
    )


def seed(username: str):
    from btcopilot.extensions import db
    from btcopilot.pro.models import Diagram, User

    user = User.query.filter_by(username=username).first()
    if user is None:
        raise SystemExit(f"No user {username}")
    for old in Diagram.query.filter_by(user_id=user.id, name=SEED_DIAGRAM_NAME):
        for discussion in old.discussions:
            db.session.delete(discussion)
        if user.free_diagram_id == old.id:
            user.free_diagram_id = None
        db.session.delete(old)
    db.session.flush()

    diagram = Diagram(user_id=user.id, name=SEED_DIAGRAM_NAME, data=pickle.dumps({}))
    diagram.set_diagram_data(seed_diagram_data())
    db.session.add(diagram)
    db.session.flush()
    user.free_diagram_id = diagram.id
    db.session.commit()
    return diagram


if __name__ == "__main__":
    from btcopilot.app import create_app

    username = sys.argv[1] if len(sys.argv) > 1 else "patrickkidd+unittest@gmail.com"
    app = create_app()
    with app.app_context():
        diagram = seed(username)
        print(f"Seeded diagram {diagram.id} ({SEED_DIAGRAM_NAME}) for {username}")
