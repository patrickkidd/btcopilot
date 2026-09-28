"""The records the visual goldens are taken against: the sparse and dense shapes
the picture has to survive, one record whose labels are hostile, and one holding
a moment per move the picture can draw.

Every fixture user is a throwaway on the sandbox database. Never run this against
a database holding anyone's real record.

Usage: FLASK_CONFIG=development flask app fixtures [key ...]
"""

import datetime
import traceback

import click

from btcopilot import diagramjson
from btcopilot.case import Case, Snapshot
from btcopilot.models import (
    AccessRight,
    Change,
    Interaction,
    ModelCall,
    Observation,
    ProductEvent,
    StatementKind,
)
from btcopilot.routes import bp
from btcopilot.schema import (
    Cluster,
    DateCertainty,
    DiagramData,
    Event,
    EventKind,
    Person,
    PersonKind,
    TraceKey,
    VariableShift,
    asdict,
)

DIAGRAM_NAME = "FD-362 visual fixture"
DOMAIN = "fd362-fixture.invalid"

CERTAIN = DateCertainty.Certain
APPROX = DateCertainty.Approximate
UNKNOWN = DateCertainty.Unknown

LONG_LABEL = "the cluster when everybody stopped speaking about the house and the money"
LONG_NAME = "Margaret-Anne Fitzgerald-Winterbottom III"
# A professional's client diagram can be named anything. Forty characters is
# past what the title row can hold on a phone, so it has to ellipsise rather
# than push the controls beside it or spill over the picture.
LONG_DIAGRAM_NAME = "The Fitzgerald-Winterbottom Family Files"


def _person(id, name, gender=PersonKind.Female, primary=False):
    chunk = asdict(Person(id=id, name=name, gender=gender))
    chunk["primary"] = primary
    return chunk


def _event(id, date, description, person=1, certainty=CERTAIN, **kwargs):
    return asdict(
        Event(
            id=id,
            kind=EventKind.Shift,
            person=person,
            dateTime=date,
            dateCertainty=certainty,
            description=description,
            **kwargs,
        )
    )


def empty() -> DiagramData:
    """People, and nothing with a date: the picture has only a question mark."""
    return DiagramData(
        people=[_person(1, "Ada", primary=True)],
        events=[
            asdict(
                Event(
                    id=10,
                    kind=EventKind.Shift,
                    person=1,
                    description="Nobody in the family sleeps well",
                )
            ),
            asdict(
                Event(
                    id=11,
                    kind=EventKind.Shift,
                    person=1,
                    dateTime="1990-01-01",
                    dateCertainty=UNKNOWN,
                    description="Something happened with the house",
                )
            ),
        ],
        lastItemId=20,
    )


def one() -> DiagramData:
    return DiagramData(
        people=[_person(1, "Ada", primary=True)],
        events=[_event(10, "2014-03-02", "Moved out on her own")],
        lastItemId=20,
    )


def three_over_forty() -> DiagramData:
    """Moments spread over forty years: three the record holds as one cluster,
    which is the least a cluster may hold, and one it holds on its own, which
    is a dot on the wire with no box."""
    return DiagramData(
        people=[_person(1, "Ada", primary=True), _person(2, "Ben", PersonKind.Male)],
        events=[
            # the three in the cluster are moves the board can draw, so the
            # walk it offers has something to walk through
            _event(
                10,
                "1981-05-01",
                "Grandmother died",
                certainty=APPROX,
                anxiety=VariableShift.Up,
            ),
            _event(
                11,
                "1994-02-14",
                "The winter she stopped calling home",
                relationship="distance",
                relationshipTargets=[2],
            ),
            _event(
                12,
                "2003-09-10",
                "The move across the country",
                functioning=VariableShift.Down,
            ),
            _event(13, "2021-11-02", "Ben stopped calling", person=2),
        ],
        clusters=[
            asdict(
                Cluster(
                    id="cT",
                    reason="Ada lost her grandmother, and then moved away from everyone she knew.",
                    title="Leaving and losing",
                    summary="",
                    eventIds=[10, 11, 12],
                    startDate="1981-05-01",
                    endDate="2003-09-10",
                )
            )
        ],
        lastItemId=20,
    )


def sixty_in_five() -> DiagramData:
    people = [_person(1, "Ada", primary=True), _person(2, "Ben", PersonKind.Male)]
    directions = [VariableShift.Up, VariableShift.Down, VariableShift.Same]
    start = datetime.date(2019, 1, 5)
    events = [
        _event(
            100 + i,
            (start + datetime.timedelta(days=30 * i)).isoformat(),
            f"Week {i + 1}: sleep note",
            person=1 if i % 2 else 2,
            anxiety=directions[i % 3],
        )
        for i in range(60)
    ]
    clusters = [
        asdict(
            Cluster(
                id="cA",
                reason="Ada's sleep went first, and the worry spread through the house from there.",
                title="The first hard winter",
                summary="",
                eventIds=[100 + i for i in range(20)],
                startDate="2019-01-05",
                endDate="2020-08-01",
            )
        ),
        asdict(
            Cluster(
                id="cB",
                reason="Everything in this run follows what the doctor said that autumn.",
                title="After the diagnosis",
                summary="",
                eventIds=[100 + i for i in range(20, 60)],
                startDate="2020-09-01",
                endDate="2023-12-01",
            )
        ),
    ]
    return DiagramData(people=people, events=events, clusters=clusters, lastItemId=300)


def hostile() -> DiagramData:
    """Labels and names long enough to break a chip out of its bubble."""
    people = [_person(1, LONG_NAME, primary=True), _person(2, "Bo", PersonKind.Male)]
    events = [
        _event(10 + i, f"200{i}-0{i + 1}-01", f"{LONG_LABEL} — part {i + 1}")
        for i in range(6)
    ]
    clusters = [
        asdict(
            Cluster(
                id="cL",
                reason=LONG_LABEL,
                title=LONG_LABEL,
                summary="",
                eventIds=[10, 11, 12],
                startDate="2000-01-01",
                endDate="2002-03-01",
            )
        )
    ]
    return DiagramData(people=people, events=events, clusters=clusters, lastItemId=40)


PLAY_CLUSTER = "walk"

MOVES = (
    ("toward", dict(relationship="toward", relationshipTargets=[2])),
    ("away", dict(relationship="away", relationshipTargets=[2])),
    ("distance", dict(relationship="distance", relationshipTargets=[2])),
    ("cutoff", dict(relationship="cutoff", relationshipTargets=[2])),
    ("conflict", dict(relationship="conflict", relationshipTargets=[2])),
    ("fusion", dict(relationship="fusion", relationshipTargets=[2])),
    ("defined self", dict(relationship="defined-self")),
    (
        "inside",
        dict(relationship="inside", relationshipTargets=[2], relationshipTriangles=[3]),
    ),
    (
        "outside",
        dict(relationship="outside", relationshipTargets=[2], relationshipTriangles=[3]),
    ),
    ("overfunctioning", dict(relationship="overfunctioning", relationshipTargets=[2])),
    ("underfunctioning", dict(relationship="underfunctioning", relationshipTargets=[2])),
    ("projection", dict(relationship="projection", relationshipTargets=[3])),
    ("anxiety up", dict(anxiety=VariableShift.Up)),
    ("symptom up", dict(symptom=VariableShift.Up)),
    ("symptom down", dict(symptom=VariableShift.Down)),
    ("functioning down", dict(functioning=VariableShift.Down)),
    ("functioning up", dict(functioning=VariableShift.Up)),
)


def moves() -> DiagramData:
    """One moment per move the picture can draw, so each can be looked at."""
    people = [
        _person(1, "Ada", primary=True),
        _person(2, "Ben", PersonKind.Male),
        _person(3, "Cal", PersonKind.Male),
    ]
    events = [
        _event(20 + i, f"{1990 + i}-04-01", words, **kwargs)
        for i, (words, kwargs) in enumerate(MOVES)
    ]
    clusters = [
        asdict(
            Cluster(
                id=PLAY_CLUSTER,
                reason="One move after another between Ada, Ben and Cal, in order.",
                title="The walk",
                summary="Every move in order.",
                eventIds=[event["id"] for event in events],
                name="The walk",
            )
        )
    ]
    return DiagramData(
        people=people, events=events, clusters=clusters, lastItemId=60
    )


# The sparse record has a conversation too, so its moments carry where they
# were said and the row under the picture can offer the way back to it.
# It names no moment, so the picture opens on the whole line the way a record
# with no conversation about it does.
THREE40_CHAT = [
    ("user", "tell me about the year we moved"),
    ("coach", "Tell me what you remember about it."),
]

MOVES_CHAT = [
    ("user", "walk me through it"),
    (
        "coach",
        "The winter of 1993 is where it turned: after a year of "
        "[[event:22|keeping her distance from Ben]], Ada "
        "[[event:23|stopped speaking to him altogether]]. "
        "What do you remember about the winter it started? "
        + " ".join(
            f"[[ask:{offer}]]" for offer in ("winter 1993", "Ben's mother", "Ada, age 9")
        ),
    ),
]

def play() -> DiagramData:
    """The moves record, whose whole walk is one stored cluster, so a
    play-by-play about it has a cluster id that resolves."""
    data = moves()
    data.clusters = [
        asdict(
            Cluster(
                id=PLAY_CLUSTER,
                reason="One move after another between Ada, Ben and Cal, in order.",
                title="The walk",
                summary="Every move in order.",
                eventIds=[event["id"] for event in data.events],
                name="The walk",
            )
        )
    ]
    return data


# Seventy characters of a person's own words, which is what the board's summary
# has to survive without changing the board's height.
LONG_WORDS = "her back pain eased after the winter she stopped calling her mother now"


def long_move() -> DiagramData:
    """The moves record with one move carrying a description long enough to
    wrap the summary under the board, and one person the record knows both the
    birth and the death of."""
    data = moves()
    for event in data.events:
        if event["symptom"]:
            event["description"] = LONG_WORDS
    data.events.extend(
        [
            asdict(
                Event(id=70, kind=EventKind.Birth, child=1, dateTime="1961-02-03")
            ),
            asdict(
                Event(id=71, kind=EventKind.Death, person=1, dateTime="2019-08-09")
            ),
        ]
    )
    data.lastItemId = 80
    data.clusters = [
        asdict(
            Cluster(
                id=PLAY_CLUSTER,
                reason="One move after another between Ada, Ben and Cal, in order.",
                title="The walk",
                summary="Every move in order.",
                eventIds=[event["id"] for event in data.events],
                name="The walk",
            )
        )
    ]
    return data


# The case the coach tells about the walk, in its snapshots (R-0563): four of the
# moves between Ada and Ben, one picture per year.
PLAY_CASE = Case(
    cluster_id=PLAY_CLUSTER,
    point="Ada moved toward Ben in 1990; by 1994 they were in open conflict.",
    snapshots=[
        Snapshot("1990-04-01", [20], "In April 1990 Ada moved toward Ben.", None),
        Snapshot("1992-04-01", [22], "By 1992 she kept her distance from him.", None),
        Snapshot(
            "1993-04-01",
            [23],
            "In 1993 she stopped speaking to him.",
            "My guess: the distance came before the silence, not after it.",
        ),
        Snapshot("1994-04-01", [24], "When they spoke again in 1994 it was open conflict.", None),
    ],
    question="Where was Cal in the year Ada stopped speaking to Ben?",
)

# A walk told the old way, in prose with chips, as production sessions still
# hold them: its chips are chips like any other now (R-0501, R-0570).
OLD_WALK = (
    "In 1990 Ada [[event:20|moved toward Ben]], and a year later she"
    " [[event:21|pulled away from him]] again."
)

PLAY_CHAT = [
    ("user", "walk me through it"),
    ("coach", OLD_WALK, {"kind": StatementKind.Play, "cluster_id": PLAY_CLUSTER}),
    ("user", "and again, in pictures"),
    (
        "coach",
        PLAY_CASE.point,
        {
            "kind": StatementKind.Play,
            "cluster_id": PLAY_CLUSTER,
            "told_case": PLAY_CASE.asdict(),
        },
    ),
]

LONG_REPLY = "Here is the long version. " + ("This is a sentence about the family. " * 100)

HOSTILE_CHAT = [
    ("user", "tell me about [[cluster:cL]] and [[person:1]]"),
    (
        "coach",
        f"One chip with a very long label: [[cluster:cL|{LONG_LABEL}]] "
        f"and a person [[person:1|{LONG_NAME}]].",
    ),
    (
        "coach",
        "Twelve of them: "
        + " ".join(f"[[event:{10 + (i % 6)}|moment number {i + 1}]]" for i in range(12)),
    ),
    ("coach", LONG_REPLY),
    ("user", "🙂🎉😀🔥🌍💡🥲🫠🧠🌱🕰️🪞 " * 12),
]

def whitlock() -> DiagramData:
    """The Whitlock stand-in family (doc/mockups/family.md), wholly invented,
    with the years Marcus and Delphine came apart as one stored cluster: what
    the play-by-play drawer tells."""

    def kin(id, name, gender, primary=False, **fields):
        return dict(_person(id, name, gender, primary=primary), **fields)

    def bond(id, a, b):
        return {"id": id, "person_a": a, "person_b": b, "married": True}

    def event(id, kind, date, **fields):
        return asdict(Event(id=id, kind=kind, dateTime=date, dateCertainty=CERTAIN, **fields))

    male, female = PersonKind.Male, PersonKind.Female
    people = [
        kin(1, "Errol", male, last_name="Whitlock"),
        kin(2, "Odile", female, last_name="Whitlock"),
        kin(3, "Marcus", male, last_name="Whitlock", parents=20),
        kin(4, "Delphine", female, last_name="Reyes"),
        kin(5, "Corinne", female, primary=True, last_name="Whitlock", parents=21),
        kin(6, "Theo", male, last_name="Whitlock", parents=21),
    ]
    born = [
        event(101, EventKind.Birth, "1924-06-01", child=1),
        event(102, EventKind.Birth, "1926-06-01", child=2),
        event(103, EventKind.Married, "1948-06-01", person=1, spouse=2),
        event(104, EventKind.Birth, "1951-10-01", person=1, spouse=2, child=3),
        event(105, EventKind.Birth, "1953-06-01", child=4),
        event(106, EventKind.Married, "1970-06-01", person=3, spouse=4),
        event(107, EventKind.Birth, "1975-06-01", person=3, spouse=4, child=5),
        event(108, EventKind.Birth, "1979-06-01", person=3, spouse=4, child=6),
    ]
    apart = [
        event(201, EventKind.Separated, "1980-09-15", person=3, spouse=4),
        event(202, EventKind.Noted, "1980-09-15", person=3, description="Took a room over the hardware store"),
        event(203, EventKind.Shift, "1981-01-15", person=3, symptom=VariableShift.Up, description="Drinking most nights"),
        event(204, EventKind.Divorced, "1981-06-15", person=3, spouse=4),
        event(205, EventKind.Noted, "1981-09-15", person=6, description="Started at the church day care"),
        event(206, EventKind.Shift, "1982-04-15", person=3, symptom=VariableShift.Down, description="Stopped drinking"),
        event(207, EventKind.Noted, "1982-09-15", person=5, description="Started school"),
        event(208, EventKind.Shift, "1982-11-15", person=5, symptom=VariableShift.Up, description="Her teacher called Delphine"),
    ]
    return DiagramData(
        people=people,
        pair_bonds=[bond(20, 1, 2), bond(21, 3, 4)],
        events=born + apart,
        clusters=[
            asdict(
                Cluster(
                    id=WHITLOCK_CLUSTER,
                    reason="Marcus and Delphine came apart, and the trouble moved.",
                    title="The years apart",
                    summary="Separation to the teacher's call.",
                    eventIds=[e["id"] for e in apart],
                    name="The years apart",
                )
            )
        ],
        lastItemId=300,
    )


WHITLOCK_CLUSTER = "apart"
WHITLOCK_CASE = Case(
    cluster_id=WHITLOCK_CLUSTER,
    point="As Marcus drank less, school got hard for you.",
    snapshots=[
        Snapshot(
            "1980-09-15",
            [201, 202],
            "Marcus and Delphine separated, and Marcus took a room over the hardware store. You were five; Theo was one.",
            None,
        ),
        Snapshot("1981-01-15", [203], "Marcus was drinking “most nights,” as Delphine put it later.", None),
        Snapshot("1981-06-15", [204], "The divorce went through in June.", None),
        Snapshot("1982-04-15", [206], "Marcus “hadn’t had a drink since Easter.”", None),
        Snapshot(
            "1982-11-15",
            [208],
            "Your teacher called Delphine: you had stopped talking in class.",
            "My guess: the trouble moved from Marcus to you as his drinking eased.",
        ),
    ],
    question="Theo started day care that autumn. Who was looking after the two of you?",
)
WHITLOCK_CHAT = [
    ("user", "explain those years"),
    (
        "coach",
        WHITLOCK_CASE.point,
        {
            "kind": StatementKind.Play,
            "cluster_id": WHITLOCK_CLUSTER,
            "told_case": WHITLOCK_CASE.asdict(),
        },
    ),
]


def editable() -> DiagramData:
    """A copy of the sparse record for the tests that write through the editor.
    They change what they open, so they need a record of their own or every
    picture taken after them is of a record they altered. A third person lets a
    move name two people besides its mover, and Ada and Ben's bond lets an event
    be made a couple's."""
    data = three_over_forty()
    data.people.append(_person(3, "Cy"))
    data.pair_bonds.append({"id": 20, "person_a": 1, "person_b": 2})
    return data


def long_name() -> DiagramData:
    """An ordinary small record; what is under test is its diagram's name."""
    return three_over_forty()


# key -> (builder, chat, diagram name)
FIXTURES = {
    "empty": (empty, None),
    "one": (one, None),
    "three40": (three_over_forty, THREE40_CHAT),
    "dense60": (sixty_in_five, None),
    "hostile": (hostile, HOSTILE_CHAT),
    "moves": (moves, MOVES_CHAT),
    "play": (play, PLAY_CHAT),
    "longmove": (long_move, None),
    "longname": (long_name, None),
    "editable": (editable, None),
    "whitlock": (whitlock, WHITLOCK_CHAT),
}

# the diagram name each fixture's record carries, when it is not the default
DIAGRAM_NAMES = {"longname": LONG_DIAGRAM_NAME}


DIAGRAM_ROWS = (AccessRight, Change, Interaction, ModelCall, Observation, ProductEvent)


def username(key: str) -> str:
    return f"{key}@{DOMAIN}"


def install(key: str):
    """Make the fixture user, replace their diagram, and replay their chat."""
    from btcopilot.extensions import db
    from btcopilot.models import Discussion, Speaker, Statement
    from btcopilot.models import Diagram, User

    builder, chat = FIXTURES[key]
    name = username(key)
    user = User.query.filter_by(username=name).first()
    if user is None:
        user = User(username=name, status="confirmed", password="x")
        db.session.add(user)
        db.session.flush()
    for old in Diagram.query.filter_by(user_id=user.id).all():
        for discussion in old.discussions:
            discussion.chat_user_speaker_id = None
            discussion.chat_ai_speaker_id = None
            db.session.flush()
            db.session.delete(discussion)
        if user.free_diagram_id == old.id:
            user.free_diagram_id = None
        if user.current_diagram_id == old.id:
            user.current_diagram_id = None
        # what was done to the old record goes with it; the database will not
        # delete a diagram while rows still point at it
        for kept in DIAGRAM_ROWS:
            kept.query.filter_by(diagram_id=old.id).delete()
        db.session.flush()
        db.session.delete(old)
    db.session.flush()

    diagram = Diagram(
        user_id=user.id,
        name=DIAGRAM_NAMES.get(key, DIAGRAM_NAME),
        data=diagramjson.dumps({}),
    )
    diagram.set_diagram_data(builder())
    db.session.add(diagram)
    db.session.flush()
    user.free_diagram_id = diagram.id
    db.session.commit()

    if chat:
        discussion = Discussion(user_id=user.id, diagram_id=diagram.id)
        db.session.add(discussion)
        db.session.flush()
        me = Speaker(discussion_id=discussion.id, name="You")
        coach = Speaker(discussion_id=discussion.id, name="Coach")
        db.session.add_all([me, coach])
        db.session.flush()
        discussion.chat_user_speaker_id = me.id
        discussion.chat_ai_speaker_id = coach.id
        for order, (role, text, *extra) in enumerate(chat):
            db.session.add(
                Statement(
                    discussion_id=discussion.id,
                    speaker_id=coach.id if role == "coach" else me.id,
                    text=text,
                    order=order,
                    **(extra[0] if extra else {}),
                )
            )
        db.session.commit()
        _stamp_coded_in(diagram, discussion)
    return user


def _stamp_coded_in(diagram, discussion):
    """A real record remembers which words coded each moment, so the fixtures
    do too: every event is stamped against this discussion's first coach
    statement. Without it there is nothing for traceability to point at."""
    from btcopilot.extensions import db

    coach_said = next(
        (s for s in discussion.statements if s.speaker_id == discussion.chat_ai_speaker_id),
        None,
    )
    if coach_said is None:
        return
    data = diagram.get_diagram_data()
    for event in data.events:
        event[TraceKey.Discussion.value] = discussion.id
        event[TraceKey.Statement.value] = coach_said.id
    diagram.set_diagram_data(data)
    db.session.commit()


@bp.cli.command("fixtures")
@click.argument("keys", nargs=-1)
def fixtures_command(keys):
    """Install the visual-golden fixtures and print a sign-in link for each."""
    from flask import current_app

    from btcopilot.auth.invitation import Invitation

    for key in keys or list(FIXTURES):
        if key not in FIXTURES:
            raise click.BadParameter(f"no fixture named {key}")
        try:
            install(key)
            token = Invitation.issue(
                username(key), current_app.config["INVITATION_DAYS"]
            ).token
        except Exception:
            # A caller that silences stderr must still see this fail: say what
            # broke on both streams and leave a non-zero status behind.
            trace = traceback.format_exc()
            click.echo(trace, err=True)
            click.echo(f"{key} FAILED: {trace.strip().splitlines()[-1]}")
            raise SystemExit(1)
        click.echo(f"{key} {token}")
