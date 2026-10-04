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

from btcopilot import diagramjson, playturn
from btcopilot.discussions import open_session
from btcopilot.extensions import db
from btcopilot.case import Case, Snapshot
from btcopilot.models import (
    AccessRight,
    Audience,
    Change,
    Interaction,
    ModelCall,
    Notice,
    NoticeLink,
    Notification,
    NotificationChannel,
    NotificationKind,
    Observation,
    ProductEvent,
    Statement,
    StatementKind,
)
from btcopilot.review.models import Coding, Cut, Item, Note, Vote
from btcopilot.routes import bp
from btcopilot.timeline import build_timeline
from btcopilot.toolbox import said_label
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


def _event(id, date, title, person=1, certainty=CERTAIN, **kwargs):
    return asdict(
        Event(
            id=id,
            kind=EventKind.Shift,
            person=person,
            dateTime=date,
            dateCertainty=certainty,
            title=title,
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
                    title="Nobody sleeps well",
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
                    title="Trouble with the house",
                    description="Something happened with the house",
                )
            ),
        ],
        lastItemId=20,
    )


def one() -> DiagramData:
    return DiagramData(
        people=[_person(1, "Ada", primary=True)],
        events=[_event(10, "2014-03-02", "Moved out", description="Moved out on her own")],
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
                "Stopped calling home",
                description="The winter she stopped calling home",
                relationship="distance",
                relationshipTargets=[2],
            ),
            _event(
                12,
                "2003-09-10",
                "Moved across the country",
                functioning=VariableShift.Down,
            ),
            _event(13, "2021-11-02", "Stopped calling", person=2),
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
        _event(
            10 + i,
            f"200{i}-0{i + 1}-01",
            f"Long story, part {i + 1}",
            description=f"{LONG_LABEL} — part {i + 1}",
        )
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
    ("Reached out", dict(relationship="toward", relationshipTargets=[2])),
    ("Pulled away", dict(relationship="away", relationshipTargets=[2])),
    ("Kept her distance", dict(relationship="distance", relationshipTargets=[2])),
    ("Cut off contact", dict(relationship="cutoff", relationshipTargets=[2])),
    ("Fought it out", dict(relationship="conflict", relationshipTargets=[2])),
    ("Too close to him", dict(relationship="fusion", relationshipTargets=[2])),
    ("Held her ground", dict(relationship="defined-self")),
    (
        "Took a side",
        dict(relationship="inside", relationshipTargets=[2], relationshipTriangles=[3]),
    ),
    (
        "Stayed out of it",
        dict(relationship="outside", relationshipTargets=[2], relationshipTriangles=[3]),
    ),
    ("Did too much", dict(relationship="overfunctioning", relationshipTargets=[2])),
    ("Let her do it", dict(relationship="underfunctioning", relationshipTargets=[2])),
    ("Worried about him", dict(relationship="projection", relationshipTargets=[3])),
    ("Anxiety went up", dict(anxiety=VariableShift.Up)),
    ("Symptoms got worse", dict(symptom=VariableShift.Up)),
    ("Symptoms eased", dict(symptom=VariableShift.Down)),
    ("Functioning slipped", dict(functioning=VariableShift.Down)),
    ("Functioning improved", dict(functioning=VariableShift.Up)),
)


def moves() -> DiagramData:
    """One moment per move the picture can draw, so each can be looked at."""
    people = [
        _person(1, "Ada", primary=True),
        _person(2, "Ben", PersonKind.Male),
        _person(3, "Cal", PersonKind.Male),
    ]
    events = [
        _event(20 + i, f"{1990 + i}-04-01", title, **kwargs)
        for i, (title, kwargs) in enumerate(MOVES)
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
        playturn.worded({"id": PLAY_CLUSTER, "name": "The walk"}, PLAY_CASE.point),
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
        event(202, EventKind.Noted, "1980-09-15", person=3, title="Moved out", description="Took a room over the hardware store"),
        event(203, EventKind.Shift, "1981-01-15", person=3, symptom=VariableShift.Up, title="Drinking most nights", description="Drinking most nights after the separation"),
        event(204, EventKind.Divorced, "1981-06-15", person=3, spouse=4),
        event(205, EventKind.Noted, "1981-09-15", person=6, title="Started day care", description="Started at the church day care"),
        event(206, EventKind.Shift, "1982-04-15", person=3, symptom=VariableShift.Down, title="Stopped drinking", description="Stopped drinking for good"),
        event(207, EventKind.Noted, "1982-09-15", person=5, title="Started school", description="Started first grade"),
        event(208, EventKind.Shift, "1982-11-15", person=5, symptom=VariableShift.Up, title="Trouble at school", description="Her teacher called Delphine"),
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


def every_mark() -> DiagramData:
    """The Pemberton stand-in family, wholly invented, whose one stored cluster
    holds one event for every mark the play-by-play can draw, in date order, so
    each can be looked at on its own step."""

    def kin(id, name, gender, primary=False, **fields):
        return dict(_person(id, name, gender, primary=primary), **fields)

    def event(id, kind, date, **fields):
        return asdict(Event(id=id, kind=kind, dateTime=date, dateCertainty=CERTAIN, **fields))

    def shift(id, date, person, title, description, **fields):
        return event(id, EventKind.Shift, date, person=person, title=title, description=description, **fields)

    male, female = PersonKind.Male, PersonKind.Female
    up, down = VariableShift.Up, VariableShift.Down
    people = [
        kin(1, "Harold", male, last_name="Pemberton"),
        kin(2, "June", female, last_name="Pemberton"),
        kin(3, "Walter", male, last_name="Pemberton", parents=20),
        kin(4, "Rosa", female, last_name="Quint"),
        kin(5, "Ivy", female, primary=True, last_name="Pemberton", parents=21),
        kin(6, "Leo", male, last_name="Pemberton", parents=21),
        kin(7, "Sam", male, last_name="Okoro"),
    ]
    born = [
        event(101, EventKind.Birth, "1922-02-01", child=1),
        event(102, EventKind.Birth, "1925-07-01", child=2),
        event(103, EventKind.Married, "1946-06-01", person=1, spouse=2),
        event(104, EventKind.Birth, "1948-04-01", person=1, spouse=2, child=3),
        event(105, EventKind.Birth, "1950-10-01", child=4),
        event(106, EventKind.Birth, "1973-01-01", child=7),
        event(107, EventKind.Birth, "1977-05-01", child=6),
    ]
    marks = [
        event(301, EventKind.Married, "1972-06-10", person=3, spouse=4),
        event(302, EventKind.Birth, "1975-03-02", person=3, spouse=4, child=5),
        event(303, EventKind.Adopted, "1978-09-20", person=3, spouse=4, child=6),
        shift(304, "1979-05-01", 4, "Kept her close", "Kept Ivy close", relationship="toward", relationshipTargets=[5]),
        shift(305, "1980-02-01", 3, "Took long road trips", "Took long road trips alone", relationship="away", relationshipTargets=[4]),
        shift(306, "1980-11-01", 3, "Fought about money", "Fought about money most weekends", relationship="conflict", relationshipTargets=[4]),
        shift(307, "1981-06-01", 4, "Went quiet at dinner", "Stopped talking at dinner", relationship="distance", relationshipTargets=[3]),
        event(308, EventKind.Separated, "1982-01-15", person=3, spouse=4),
        shift(309, "1982-04-01", 3, "Drinking most nights", "Drinking most nights after the separation", symptom=up),
        shift(310, "1982-09-01", 4, "Could not sleep", "Could not sleep through the night", anxiety=up),
        shift(311, "1983-03-01", 4, "Slept again", "Slept through the night again", anxiety=down),
        event(312, EventKind.Divorced, "1983-08-01", person=3, spouse=4),
        shift(313, "1984-02-01", 3, "Stopped calling home", "Stopped calling his father", relationship="cutoff", relationshipTargets=[1]),
        shift(314, "1985-05-01", 4, "Worried over grades", "Worried over Leo's grades", relationship="projection", relationshipTargets=[6]),
        shift(315, "1986-01-01", 4, "Told her everything", "Told Ivy everything", relationship="fusion", relationshipTargets=[5]),
        shift(316, "1987-03-01", 5, "Did his homework", "Did Leo's homework", relationship="overfunctioning", relationshipTargets=[6]),
        shift(317, "1987-09-01", 6, "Let her handle school", "Let Ivy handle school", relationship="underfunctioning", relationshipTargets=[5]),
        shift(318, "1988-04-01", 3, "Lost his job", "Lost his job at the plant", functioning=down),
        shift(319, "1989-06-01", 3, "Opened his own shop", "Opened his own repair shop", functioning=up),
        shift(320, "1990-01-01", 3, "Stopped drinking", "Stopped drinking for good", symptom=down),
        shift(321, "1991-05-01", 5, "Held her ground", "Held her ground with Rosa", relationship="defined-self", relationshipTargets=[4]),
        shift(322, "1992-08-01", 6, "Sided with his mother", "Sided with Rosa", relationship="inside", relationshipTargets=[4], relationshipTriangles=[5]),
        shift(323, "1993-02-01", 6, "Stayed out of it", "Stayed out of their fight", relationship="outside", relationshipTargets=[4], relationshipTriangles=[5]),
        event(324, EventKind.Noted, "1994-07-01", person=5, title="Moved to Chicago", description="Moved to Chicago for work"),
        event(325, EventKind.Death, "1996-11-01", person=1),
        event(326, EventKind.Bonded, "1998-06-01", person=5, spouse=7),
        shift(327, "1999-09-01", None, "Sold the farm", "The family sold the farm"),
    ]
    return DiagramData(
        people=people,
        pair_bonds=[
            {"id": 20, "person_a": 1, "person_b": 2, "married": True},
            {"id": 21, "person_a": 3, "person_b": 4, "married": True},
            {"id": 22, "person_a": 5, "person_b": 7, "married": False},
        ],
        events=born + marks,
        clusters=[
            asdict(
                Cluster(
                    id=EVERY_MARK_CLUSTER,
                    reason="Every mark the play-by-play draws, one event at a time.",
                    title="Every mark",
                    summary="One event for each mark.",
                    eventIds=[e["id"] for e in marks],
                    name="Every mark",
                )
            )
        ],
        lastItemId=400,
    )


EVERY_MARK_CLUSTER = "everymark"
# each step's words name the mark it shows first, so a reader can check the drawing
EVERY_MARK_FACTS = {
    301: "Married: Walter and Rosa married.",
    302: "Birth: Ivy was born.",
    303: "Adopted: Walter and Rosa adopted Leo.",
    304: "Toward: Rosa kept Ivy close.",
    305: "Away: Walter took long road trips away from Rosa.",
    306: "Conflict: Walter and Rosa fought about money.",
    307: "Distance: Rosa stopped talking to Walter at dinner.",
    308: "Separated: Walter and Rosa separated.",
    309: "Symptom up: Walter was drinking most nights.",
    310: "Anxiety up: Rosa could not sleep.",
    311: "Anxiety down: Rosa slept again.",
    312: "Divorced: Walter and Rosa divorced.",
    313: "Cutoff: Walter stopped calling his father.",
    314: "Projection: Rosa worried over Leo's grades.",
    315: "Fusion: Rosa told Ivy everything.",
    316: "Overfunctioning: Ivy did Leo's homework.",
    317: "Underfunctioning: Leo let Ivy handle school.",
    318: "Functioning down: Walter lost his job.",
    319: "Functioning up: Walter opened his own shop.",
    320: "Symptom down: Walter stopped drinking.",
    321: "Defined self: Ivy held her ground with Rosa.",
    322: "Inside: Leo sided with Rosa, leaving Ivy out.",
    323: "Outside: Leo stayed out of it.",
    324: "An event with no drawing of its own: Ivy moved to Chicago.",
    325: "Death: Harold died.",
    326: "Bonded: Ivy and Sam got together.",
    327: "An event about the whole family: they sold the farm.",
}
EVERY_MARK_CASE = Case(
    cluster_id=EVERY_MARK_CLUSTER,
    point="Every mark the play-by-play draws, one step each.",
    snapshots=[
        Snapshot(e["dateTime"], [e["id"]], EVERY_MARK_FACTS[e["id"]], None)
        for e in every_mark().events
        if e["id"] in EVERY_MARK_FACTS
    ],
    question="Which of these marks is hard to read?",
)
EVERY_MARK_CHAT = [
    ("user", "show me every mark"),
    (
        "coach",
        EVERY_MARK_CASE.point,
        {
            "kind": StatementKind.Play,
            "cluster_id": EVERY_MARK_CLUSTER,
            "told_case": EVERY_MARK_CASE.asdict(),
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


# A family's thread over its sittings: (how long ago it ended, summary, what was
# said). The summaries are the hostile ones a divider has to hold: none, empty, sixty
# characters, and unicode.
SIXTY = "Why the Sunday calls to Mum stopped after the funeral in May"
UNICODE = "Zoë, 祖母 and the move to Łódź 🏠"


DAY = datetime.timedelta(days=1)


def _at(days: int, hour: int, minute: int, lines: int) -> datetime.timedelta:
    """How long ago a sitting of `lines` lines ends so that it starts at this
    clock time `days` ago, in the zone the fixtures are installed in, which is
    the zone the browser reading them runs in."""
    now = datetime.datetime.now().astimezone()
    start = (now - days * DAY).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    return now - start - datetime.timedelta(seconds=lines)


def _sitting(topic: str, lines: int = 6) -> list[tuple[str, str]]:
    return [
        ("user", f"I keep coming back to {topic}."),
        ("coach", f"What happened first, with {topic}?"),
        ("user", "It started before anyone said anything about it."),
        ("coach", "Who noticed first?"),
        ("user", "My sister, I think. She always does."),
        ("coach", "And what did she do then?"),
    ][:lines]


SITTINGS = {
    "sitting": [(0 * DAY, "Talking about Mum's move to the coast", _sitting("Mum's move"))],
    "sittings": [
        (240 * DAY, "How the house sale started the arguments", _sitting("the house sale")),
        (218 * DAY, "Dad's drinking after he retired", _sitting("Dad's drinking")),
        (190 * DAY, None, _sitting("the wedding")),
        (163 * DAY, SIXTY, _sitting("the Sunday calls")),
        (131 * DAY, "", _sitting("my brother's job")),
        (104 * DAY, UNICODE, _sitting("Zoë and 祖母's move to Łódź")),
        (80 * DAY, "The summer at the lake house", _sitting("the lake house")),
        (55 * DAY, "Mum's diagnosis and who was told", _sitting("the diagnosis")),
        (33 * DAY, "Christmas without Dad", _sitting("Christmas")),
        (14 * DAY, "My sister taking over the care", _sitting("the care")),
        (1 * DAY, "What changed after the hospital", _sitting("the hospital", 2)),
        (0 * DAY, "Planning the visit home", _sitting("the visit home", 2)),
    ],
    # two sittings on one day, far from midnight either side
    "sameday": [
        (_at(3, 9, 40, 2), "The morning call", _sitting("the morning call", 2)),
        (_at(3, 21, 40, 2), "The evening call", _sitting("the evening call", 2)),
    ],
}

NOTICE_CHAT = [
    ("user", "my mother called on Sunday"),
    ("coach", "What did she want when she called?"),
]

# (title, body, link, days ago, opened)
NOTICES = (
    ("Welcome to the app", "Your family's record is in the list.", None, 4, True),
    (
        "Coach messages can now come weekly",
        "Choose how often under Coach messages on your account page.",
        NoticeLink.CoachSettings,
        0,
        False,
    ),
)

def _case_report_family(names=None) -> DiagramData:
    """The Halloran stand-in family, wholly invented: Nora, her husband and
    daughter, her parents and both her parents' families, the events that
    brought her, and the coach's guesses and questions on every case report
    card that takes one (R-0709, R-0708). `names` renames anyone by id."""
    names = names or {}
    male, female = PersonKind.Male, PersonKind.Female

    def kin(id, name, last, gender, parents=None, primary=False):
        return dict(
            _person(id, names.get(id, name), gender, primary=primary),
            last_name=last,
            parents=parents,
        )

    def bond(id, a, b):
        return {"id": id, "person_a": a, "person_b": b, "married": True}

    def event(id, kind, date, **fields):
        return asdict(Event(id=id, kind=kind, dateTime=date, dateCertainty=CERTAIN, **fields))

    def shift(id, date, person, title, **fields):
        return event(id, EventKind.Shift, date, person=person, title=title, description=title, **fields)

    up, down = VariableShift.Up, VariableShift.Down
    people = [
        kin(1, "Nora", "Halloran", female, parents=30, primary=True),
        kin(2, "Frank", "Halloran", male, parents=31),
        kin(3, "Elaine", "Halloran", female, parents=32),
        kin(4, "Walter", "Halloran", male),
        kin(5, "June", "Halloran", female),
        kin(6, "Harold", "Price", male),
        kin(7, "Ruth", "Price", female),
        kin(8, "Sean", "Halloran", male, parents=30),
        kin(9, "Kate", "Halloran", female, parents=30),
        kin(10, "Daniel", "Moreau", male),
        kin(11, "Lily", "Moreau", female, parents=33),
        kin(12, "Peter", "Halloran", male, parents=31),
        kin(13, "Carol", "Price", female, parents=32),
    ]
    structure = [
        event(100, EventKind.Married, "1945-06-01", person=6, spouse=7),
        event(101, EventKind.Married, "1947-05-01", person=4, spouse=5),
        event(102, EventKind.Birth, "1948-03-01", person=4, spouse=5, child=12),
        event(103, EventKind.Birth, "1950-08-01", person=4, spouse=5, child=2),
        event(104, EventKind.Birth, "1953-01-01", person=6, spouse=7, child=3),
        event(105, EventKind.Birth, "1956-11-01", person=6, spouse=7, child=13),
        event(106, EventKind.Married, "1976-09-01", person=2, spouse=3),
        event(107, EventKind.Birth, "1979-04-01", person=2, spouse=3, child=8),
        event(108, EventKind.Birth, "1982-02-01", person=2, spouse=3, child=1),
        event(109, EventKind.Birth, "1986-07-01", person=2, spouse=3, child=9),
        event(110, EventKind.Death, "1990-03-01", person=4),
        event(111, EventKind.Married, "2009-06-01", person=1, spouse=10),
        event(112, EventKind.Birth, "2012-05-01", person=1, spouse=10, child=11),
    ]
    told = [
        shift(200, "1991-02-01", 2, "Drinking heavily", symptom=up),
        shift(201, "1992-09-01", 3, "Ran the whole household", functioning=up),
        shift(202, "2004-09-01", 1, "Stopped sleeping well", symptom=up),
        shift(203, "2005-02-01", 1, "Stopped calling her mother", relationship="distance", relationshipTargets=[3]),
        shift(204, "2005-06-01", 1, "Left graduate school", functioning=down),
        shift(205, "2011-06-01", 1, "Fights over money", relationship="conflict", relationshipTargets=[10]),
        shift(206, "2014-02-01", 10, "Lost his job", functioning=down),
        shift(207, "2018-04-01", 3, "Hospitalized with pneumonia", symptom=up),
        shift(208, "2018-05-01", 1, "Worried every night", anxiety=up),
        shift(209, "2019-01-01", 1, "Stopped visiting her mother", relationship="distance", relationshipTargets=[3]),
        shift(210, "2021-10-01", 1, "Panic attacks at work", symptom=up),
        event(211, EventKind.Noted, "2022-03-01", person=1, title="Started seeing a counselor", description="Started seeing a counselor"),
    ]

    def note(id, text, kind, state, card=None, evidence=(), outcome=None):
        return {
            "id": id,
            "text": text,
            "kind": kind,
            "state": state,
            "outcome": outcome,
            "session_id": None,
            "asked_at": None if state == "held" else "2026-09-20",
            "evidence": [{"kind": "event", "id": str(e)} for e in evidence],
            "pushback": None,
            "case_report_card": card,
        }

    questions = [
        note("i1", "My guess is that when your mother is unwell you keep your distance from her, and your sleep goes first.", "impression", "raised", "main_guess", (202, 207, 209)),
        note("i2", "It looks to me as if your part has been to stop visiting when things with your mother get tense.", "impression", "raised", "own_part", (203, 209)),
        note("i3", "Twice you stopped being in touch with your mother within months of a worry about her.", "impression", "raised", "choice", (203, 209)),
        note("i4", "Staying in touch with your mother the next time she is unwell, and expecting her to push back at first.", "impression", "raised", "work_on", (207, 209)),
        note("i5", "Noticing when your sleep slips, as an early sign that things are tense at home.", "impression", "raised", "work_on", (202, 210)),
        note("i6", "Your father started drinking heavily the year after his own father died.", "impression", "raised", None, (110, 200)),
        note("i7", "Your mother ran the household much as her own mother did.", "impression", "held", None, (201,)),
        note("q1", "What do you think your own part was?", "thought", "resolved", "own_part", outcome="answered"),
        note("q2", "What would it look like to visit her the next time she is unwell?", "thought", "asked", "choice"),
        note("q3", "When did your grandmother June die?", "fact", "asked"),
    ]
    return DiagramData(
        people=people,
        pair_bonds=[bond(30, 2, 3), bond(31, 4, 5), bond(32, 6, 7), bond(33, 1, 10)],
        events=structure + told,
        clusters=[
            asdict(
                Cluster(
                    id="mother-ill",
                    reason="Elaine was in hospital, Nora worried and stayed away, and then the panic attacks began.",
                    title="Her mother's illness",
                    summary="Hospital to panic attacks.",
                    eventIds=[207, 208, 209, 210],
                    name="Her mother's illness",
                )
            )
        ],
        questions=questions,
        lastItemId=400,
    )


def case_report() -> DiagramData:
    return _case_report_family()


def case_report_thin() -> DiagramData:
    """A record the coach has barely begun: no card has anything on it."""
    return DiagramData(
        people=[dict(_person(1, "Ines", primary=True), last_name="Varga")],
        events=[_event(100, "2024-01-01", "Trouble sleeping", symptom=VariableShift.Up)],
        lastItemId=200,
    )


def case_report_dense() -> DiagramData:
    """The Halloran family ten times over: every aunt and uncle with a partner
    and children, long names, events with no date, and thirty open guesses."""
    data = _case_report_family({1: LONG_NAME, 2: "Francis-Xavier Halloran-Montgomery"})
    next_id = iter(range(1000, 10000))

    def event(kind, date, **fields):
        certainty = CERTAIN if date else UNKNOWN
        return asdict(Event(id=next(next_id), kind=kind, dateTime=date, dateCertainty=certainty, **fields))

    for parent_bond in (31, 32):
        for n in range(8):
            aunt = next(next_id)
            partner = next(next_id)
            couple = next(next_id)
            data.people += [
                dict(_person(aunt, f"Bartholomew-Alexander {n} Fitzgerald-Winterbottom", PersonKind.Male), parents=parent_bond),
                dict(_person(partner, f"Anastasia-Josephine {n} Montgomery-Whitfield", PersonKind.Female)),
            ]
            data.pair_bonds.append({"id": couple, "person_a": aunt, "person_b": partner, "married": True})
            data.events.append(event(EventKind.Married, f"19{70 + n}-06-01", person=aunt, spouse=partner))
            for k in range(5):
                cousin = next(next_id)
                data.people.append(dict(_person(cousin, f"Maximiliana-Theodora {n}{k} Fitzgerald-Winterbottom"), parents=couple))
                moved = "Moved across the country without telling anyone"
                gone = "Stopped speaking to the family for years"
                data.events += [
                    event(EventKind.Birth, f"19{80 + k}-0{1 + n % 9}-15", person=aunt, spouse=partner, child=cousin),
                    event(EventKind.Noted, None, person=cousin, title=moved, description=moved),
                    event(EventKind.Shift, f"20{10 + k}-0{1 + n % 9}-01", person=cousin, title=gone, description=gone, relationship="cutoff", relationshipTargets=[aunt]),
                ]
    for n in range(30):
        data.questions.append(
            {
                "id": f"i{100 + n}",
                "text": f"Guess {n + 1}: around the year your cousins moved away, your mother and her sister stopped speaking for a while.",
                "kind": "impression",
                "state": "raised",
                "outcome": None,
                "session_id": None,
                "asked_at": "2026-09-21",
                "evidence": [{"kind": "event", "id": "207"}],
                "pushback": None,
                "case_report_card": None,
            }
        )
    data.lastItemId = 10000
    return data


CASE_REPORT_CHAT = [
    ("user", "My mother was in hospital again and I could not face going."),
    ("coach", "That sounds hard. What do you think your own part was, when you stayed away?"),
    ("user", "I think I go quiet and stay away instead of telling her what I need."),
    ("coach", "Thank you. That is your own view, and it will stand on your case report beside mine."),
]
# the question each fixture's person answered, by the line of the chat that answers it
CASE_REPORT_ANSWERS = {"case-report": ("q1", 2), "case-report-dense": ("q1", 2)}


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
    "everymark": (every_mark, EVERY_MARK_CHAT),
    "sitting": (one, None),
    "sittings": (one, None),
    "sameday": (one, None),
    "notice": (one, NOTICE_CHAT),
    "case-report": (case_report, CASE_REPORT_CHAT),
    "case-report-thin": (case_report_thin, None),
    "case-report-dense": (case_report_dense, CASE_REPORT_CHAT),
}

# the diagram name each fixture's record carries, when it is not the default
DIAGRAM_NAMES = {"longname": LONG_DIAGRAM_NAME}
# the account's own name, for the fixtures whose screen shows it
OWNER_NAMES = {
    "case-report": ("Nora", "Halloran"),
    "case-report-thin": ("Ines", "Varga"),
    "case-report-dense": ("Margaret-Anne", "Fitzgerald-Winterbottom"),
}


DIAGRAM_ROWS = (AccessRight, Change, Interaction, ModelCall, Observation, ProductEvent)


def username(key: str) -> str:
    return f"{key}@{DOMAIN}"


def drop_cuts(diagram_id: int):
    """A family's thread on the agenda is held by its cuts, and each cut by what
    was coded and voted on it; they go before its lines, children first."""
    cuts = [c.id for c in Cut.query.filter_by(diagram_id=diagram_id)]
    items = [i.id for i in Item.query.filter(Item.cut_id.in_(cuts))]
    codings = [c.id for c in Coding.query.filter(Coding.cut_id.in_(cuts))]
    Vote.query.filter(Vote.review_item_id.in_(items)).delete()
    Note.query.filter(Note.coding_id.in_(codings)).delete()
    Item.query.filter(Item.id.in_(items)).delete()
    Coding.query.filter(Coding.id.in_(codings)).delete()
    Cut.query.filter(Cut.id.in_(cuts)).delete()


def install(key: str):
    """Make the fixture user, replace their diagram, and replay their chat."""
    from btcopilot.models import Diagram, User

    builder, chat = FIXTURES[key]
    name = username(key)
    user = User.query.filter_by(username=name).first()
    if user is None:
        user = User(username=name, status="confirmed", password="x")
        db.session.add(user)
        db.session.flush()
    user.first_name, user.last_name = OWNER_NAMES.get(key, ("", ""))
    Notification.query.filter_by(user_id=user.id).delete()
    for notice in Notice.query.filter_by(audience=Audience.People):
        if notice.user_ids == [user.id]:
            db.session.delete(notice)
    for old in Diagram.query.filter_by(user_id=user.id).all():
        drop_cuts(old.id)
        for discussion in old.discussions:
            discussion.chat_user_speaker_id = None
            discussion.chat_ai_speaker_id = None
            db.session.flush()
            db.session.delete(discussion)
        if user.free_diagram_id == old.id:
            user.free_diagram_id = None
        # an admin who opened this record holds it as theirs too
        User.query.filter_by(current_diagram_id=old.id).update({"current_diagram_id": None})
        # what was done to the old record goes with it; the database will not
        # delete a diagram while rows still point at it
        for kept in DIAGRAM_ROWS:
            kept.query.filter_by(diagram_id=old.id).delete()
        db.session.flush()
        db.session.delete(old)
    db.session.flush()

    data = builder()
    # the coach's questions and guesses are kept in the record but not by
    # set_diagram_data, which writes only what the Pro app edits
    diagram = Diagram(
        user_id=user.id,
        name=DIAGRAM_NAMES.get(key, DIAGRAM_NAME),
        data=diagramjson.dumps({"questions": data.questions}),
    )
    diagram.set_diagram_data(data)
    db.session.add(diagram)
    db.session.flush()
    user.free_diagram_id = diagram.id
    db.session.commit()

    if chat:
        discussion = _replay(user, diagram, data, chat)
        _stamp_coded_in(diagram, discussion)
        if key == "notice":
            _notify(user, discussion)
        if key in CASE_REPORT_ANSWERS:
            _answered(diagram, discussion, *CASE_REPORT_ANSWERS[key])
    for ago, summary, said in SITTINGS.get(key, []):
        _replay(user, diagram, data, said, ago, summary)
    return user


def _notify(user, discussion):
    """Notices meant for this one person, one opened days ago and one not,
    and an unread push to the coach's reply, which is no notice."""
    now = datetime.datetime.utcnow()
    for title, body, link, ago, opened in NOTICES:
        sent = now - ago * DAY - datetime.timedelta(minutes=5)
        notice = Notice(
            title=title,
            body=body,
            link=link,
            audience=Audience.People,
            user_ids=[user.id],
            created_at=sent,
        )
        db.session.add(notice)
        db.session.flush()
        db.session.add(
            Notification(
                user_id=user.id,
                kind=NotificationKind.Notice,
                notice_id=notice.id,
                channel=NotificationChannel.App,
                created_at=sent,
                opened_at=sent + datetime.timedelta(minutes=1) if opened else None,
            )
        )
    reply = next(
        s for s in discussion.statements if s.speaker_id == discussion.chat_ai_speaker_id
    )
    db.session.add(
        Notification(
            user_id=user.id,
            kind=NotificationKind.Coach,
            statement_id=reply.id,
            channel=NotificationChannel.Push,
        )
    )
    db.session.commit()


def _replay(user, diagram, data, chat, ago=datetime.timedelta(0), summary=None):
    """One sitting of the fixture's thread, said `ago`, a second a line."""
    discussion = open_session(user, diagram)
    discussion.summary = summary
    ended = datetime.datetime.utcnow() - ago
    discussion.created_at = ended - datetime.timedelta(seconds=len(chat))
    # a kept play is marked as told from the record as it stands, so it
    # opens with no call; worked out here, not at import, as it reads the
    # private play prompt
    kept = any(extra and "told_case" in extra[0] for _, _, *extra in chat)
    told = playturn.digests(data, build_timeline(data)) if kept else {}
    for order, (role, text, *extra) in enumerate(chat):
        said = extra[0] if extra else {}
        db.session.add(
            Statement(
                discussion_id=discussion.id,
                speaker_id=(
                    discussion.chat_ai_speaker_id
                    if role == "coach"
                    else discussion.chat_user_speaker_id
                ),
                text=text,
                order=order,
                created_at=ended - datetime.timedelta(seconds=len(chat) - order),
                digest=told[said["cluster_id"]] if "told_case" in said else None,
                **said,
            )
        )
    db.session.commit()
    return discussion


def _answered(diagram, discussion, question_id: str, line: int):
    """The person's own message that answered a question, kept on it the way
    the coach keeps it (R-0708)."""
    said = next(s for s in discussion.statements if s.order == line)
    data = diagramjson.loads(diagram.data)
    question = next(q for q in data["questions"] if q["id"] == question_id)
    question["answer"] = {"kind": "statement", "id": said.id, "label": said_label(said)}
    diagram.data = diagramjson.dumps(data)
    db.session.commit()


def _stamp_coded_in(diagram, discussion):
    """A real record remembers which words coded each moment, so the fixtures
    do too: every event is stamped against this discussion's first coach
    statement. Without it there is nothing for traceability to point at."""
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
