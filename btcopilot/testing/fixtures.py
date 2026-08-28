"""Seed profiles for the sandbox harness.

LLM-authored journeys under-generate non-happy-path data, so the hostile
profile enumerates each degenerate shape as a named case a journey can select
by name from the returned manifest.
"""

import enum
import random as _random

from btcopilot import ACCESS_READ_ONLY, ACCESS_READ_WRITE
from btcopilot.schema import (
    DateCertainty,
    Event,
    EventKind,
    PairBond,
    Person,
    PersonKind,
    RelationshipKind,
    VariableShift,
    asdict,
    committed_bond_chunk,
    committed_person_chunk,
)


class Case(enum.StrEnum):
    MinimalUser = "minimal_user"
    FamilyCase = "family_case"
    FamilyFirstDiscussion = "family_first_discussion"
    FamilyReturnDiscussion = "family_return_discussion"
    EmptyName = "empty_name"
    SingleTokenName = "single_token_name"
    LastNameOnly = "last_name_only"
    UnicodeName = "unicode_name"
    LongName = "long_name"
    DuplicateNames = "duplicate_names"
    SelfReferentialBond = "self_referential_bond"
    DanglingEventPerson = "dangling_event_person"
    ChildOfTwoBonds = "child_of_two_bonds"
    StagedDanglingPdp = "staged_dangling_pdp"
    EmptyDiagram = "empty_diagram"
    HugeDiagram = "huge_diagram"
    StaleVersion = "stale_version"
    SharedReadOnly = "shared_read_only"
    SharedReadWrite = "shared_read_write"
    NoAccess = "no_access"
    ExpiredLicense = "expired_license"
    NoLicense = "no_license"
    NoFreeDiagram = "no_free_diagram"
    OrphanDiscussion = "orphan_discussion"
    ForeignDiagramDiscussion = "foreign_diagram_discussion"
    EmojiStatement = "emoji_statement"
    HugeStatement = "huge_statement"
    RandomFamily = "random_family"


class LicenseState(enum.StrEnum):
    Active = "active"
    Expired = "expired"
    None_ = "none"


class SpeakerRole(enum.StrEnum):
    User = "user"
    Ai = "ai"


FREE_DIAGRAM_NAME = "Free Diagram"

HUGE_PEOPLE = 500
HUGE_EVENTS = 2000
# The row is ahead of the client, which is the direction the regression runs:
# a client holding an older snapshot must be refused, not silently win.
STALE_VERSION = 7
STALE_CLIENT_VERSION = 3
LONG_NAME = "Ⅷ" + "a" * 199
UNICODE_NAME = "Ñoño 🧬 Þórsdóttir"
EMOJI_TEXT = "🧬 My mother 👩‍👧 said 🙃 nothing 🌊"
HUGE_STATEMENT_LEN = 5000


def _ref(username: str, name: str) -> str:
    return f"{username}/{name}"


def _person(**kwargs) -> dict:
    return committed_person_chunk(Person(**kwargs))


def _bond(**kwargs) -> dict:
    return committed_bond_chunk(PairBond(**kwargs))


def _event(**kwargs) -> dict:
    return asdict(Event(**kwargs))


def _data(
    people: list[dict],
    events: list[dict],
    pair_bonds: list[dict],
    pdp: dict | None = None,
    last_item_id: int | None = None,
    name: str = "",
) -> dict:
    ids = [x["id"] for x in people + events + pair_bonds if x.get("id") is not None]
    return {
        "name": name,
        "people": people,
        "events": events,
        "pair_bonds": pair_bonds,
        "pdp": pdp or {"people": [], "events": [], "pair_bonds": [], "delete": []},
        "lastItemId": last_item_id if last_item_id is not None else max(ids, default=0),
    }


def minimal() -> dict:
    username = "minimal@test"
    return {
        "users": [{"username": username, "first_name": "Min", "last_name": "Imal"}],
        "diagrams": [],
        "discussions": [],
        "access_rights": [],
        "manifest": {
            Case.MinimalUser.value: {
                "what": "one licensed user whose only diagram is the empty free diagram",
                "user": username,
                "diagram": _ref(username, FREE_DIAGRAM_NAME),
            }
        },
    }


def family() -> dict:
    """Three coherent generations: grandparents, their two children, and the
    children of one of them, with births, a marriage, and SARF shifts."""
    username = "family@test"
    case_name = "Three Generations"

    people = [
        _person(id=1, name="Ada", last_name="Whitfield", gender=PersonKind.Female),
        _person(id=2, name="Bernard", last_name="Whitfield", gender=PersonKind.Male),
        _person(
            id=3,
            name="Clara",
            last_name="Whitfield",
            gender=PersonKind.Female,
            parents=10,
        ),
        _person(
            id=4,
            name="Dennis",
            last_name="Whitfield",
            gender=PersonKind.Male,
            parents=10,
        ),
        _person(id=5, name="Elena", last_name="Marsh", gender=PersonKind.Female),
        _person(
            id=6,
            name="Felix",
            last_name="Whitfield",
            gender=PersonKind.Male,
            parents=11,
        ),
        _person(
            id=7,
            name="Greta",
            last_name="Whitfield",
            gender=PersonKind.Female,
            parents=11,
        ),
    ]
    pair_bonds = [
        _bond(id=10, person_a=1, person_b=2, married=True),
        _bond(id=11, person_a=4, person_b=5, married=True),
    ]
    events = [
        _event(
            id=20, kind=EventKind.Married, person=1, spouse=2, dateTime="1958-06-14"
        ),
        _event(
            id=21,
            kind=EventKind.Birth,
            person=1,
            spouse=2,
            child=3,
            dateTime="1961-03-02",
        ),
        _event(
            id=22,
            kind=EventKind.Birth,
            person=1,
            spouse=2,
            child=4,
            dateTime="1964-11-19",
        ),
        _event(
            id=23, kind=EventKind.Married, person=4, spouse=5, dateTime="1992-08-01"
        ),
        _event(
            id=24,
            kind=EventKind.Birth,
            person=4,
            spouse=5,
            child=6,
            dateTime="1995-01-27",
        ),
        _event(
            id=25,
            kind=EventKind.Birth,
            person=4,
            spouse=5,
            child=7,
            dateTime="1998-05-05",
        ),
        _event(id=26, kind=EventKind.Death, person=2, dateTime="2014-02-09"),
        _event(
            id=27,
            kind=EventKind.Shift,
            person=3,
            description="Sleepless after the funeral",
            dateTime="2014-03-01",
            dateCertainty=DateCertainty.Approximate,
            symptom=VariableShift.Up,
            anxiety=VariableShift.Up,
            functioning=VariableShift.Down,
        ),
        _event(
            id=28,
            kind=EventKind.Shift,
            person=4,
            description="Took over the family business",
            dateTime="2014-06-15",
            functioning=VariableShift.Up,
            anxiety=VariableShift.Down,
            relationship=RelationshipKind.Overfunctioning,
            relationshipTargets=[3],
        ),
        _event(
            id=29,
            kind=EventKind.Shift,
            person=6,
            description="Stopped calling home",
            dateTime="2021-09-10",
            relationship=RelationshipKind.Distance,
            relationshipTargets=[4],
            relationshipTriangles=[5],
            anxiety=VariableShift.Up,
        ),
    ]

    first = {
        "summary": "First session: the funeral",
        "user": username,
        "diagram": _ref(username, case_name),
        "discussion_date": "2026-01-12",
        "speakers": [
            {
                "name": "Clara",
                "type": "subject",
                "role": SpeakerRole.User.value,
                "person_id": 3,
            },
            {"name": "Coach", "type": "expert", "role": SpeakerRole.Ai.value},
        ],
        "statements": [
            {
                "speaker": "Clara",
                "text": "My father Bernard died in 2014 and I stopped sleeping.",
            },
            {"speaker": "Coach", "text": "Who else in the family noticed that change?"},
            {
                "speaker": "Clara",
                "text": "My brother Dennis took over everything after that.",
            },
            {
                "speaker": "Coach",
                "text": "What did your mother Ada do while that was happening?",
            },
        ],
    }
    second = {
        "summary": "Return session: the next generation",
        "user": username,
        "diagram": _ref(username, case_name),
        "discussion_date": "2026-02-20",
        "speakers": [
            {
                "name": "Clara",
                "type": "subject",
                "role": SpeakerRole.User.value,
                "person_id": 3,
            },
            {"name": "Coach", "type": "expert", "role": SpeakerRole.Ai.value},
        ],
        "statements": [
            {
                "speaker": "Clara",
                "text": "Dennis married Elena and their son Felix went quiet.",
            },
            {"speaker": "Coach", "text": "When did Felix stop calling?"},
            {"speaker": "Clara", "text": "Around 2021, after Greta moved out."},
        ],
        "extracted_through_order": 2,
    }

    return {
        "users": [
            {"username": username, "first_name": "Clara", "last_name": "Whitfield"}
        ],
        "diagrams": [
            {
                "user": username,
                "name": case_name,
                "data": _data(people, events, pair_bonds, name=case_name),
            }
        ],
        "discussions": [first, second],
        "access_rights": [],
        "manifest": {
            Case.FamilyCase.value: {
                "what": "coherent three-generation family: 7 people, 2 pair bonds, births, a death, SARF shifts",
                "user": username,
                "diagram": _ref(username, case_name),
            },
            Case.FamilyFirstDiscussion.value: {
                "what": "prior discussion, never extracted",
                "user": username,
                "discussion": first["summary"],
            },
            Case.FamilyReturnDiscussion.value: {
                "what": "returning discussion whose re-extraction cursor is already advanced",
                "user": username,
                "discussion": second["summary"],
            },
        },
    }


def _hostile_names_data() -> dict:
    people = [
        # committed_person_chunk() folds an empty name to None, so the
        # empty-string shape has to be written literally.
        {
            "id": 1,
            "name": "",
            "lastName": None,
            "gender": PersonKind.Unknown.value,
            "parents": None,
        },
        _person(id=2, name="Mom"),
        {
            "id": 3,
            "name": None,
            "last_name": "Okonkwo",
            "gender": None,
            "parents": None,
        },
        _person(id=4, name=UNICODE_NAME, gender=PersonKind.Female),
        _person(id=5, name=LONG_NAME, gender=PersonKind.Male),
        _person(id=6, name="Sam", last_name="Reyes", gender=PersonKind.Male),
        _person(id=7, name="Sam", last_name="Reyes", gender=PersonKind.Male),
        _person(id=8, name="Twice", gender=PersonKind.Female, parents=20),
        _person(id=9, name="Loop", gender=PersonKind.Unknown),
    ]
    pair_bonds = [
        _bond(id=20, person_a=2, person_b=4, married=True),
        _bond(id=21, person_a=6, person_b=7, married=False),
        _bond(id=22, person_a=9, person_b=9, married=True),
    ]
    events = [
        _event(
            id=30,
            kind=EventKind.Birth,
            person=2,
            spouse=4,
            child=8,
            dateTime="1990-04-04",
        ),
        _event(
            id=31,
            kind=EventKind.Birth,
            person=6,
            spouse=7,
            child=8,
            dateTime="1990-04-04",
        ),
        _event(
            id=32,
            kind=EventKind.Shift,
            person=9999,
            description="Shift on a person who is not here",
            dateTime="2001-01-01",
        ),
    ]
    pdp = {
        "people": [asdict(Person(id=-1, name="Ghost", parents=-99))],
        "events": [
            asdict(
                Event(
                    id=-2,
                    kind=EventKind.Shift,
                    person=-77,
                    description="Staged shift on a missing person",
                    dateTime="2002-02-02",
                )
            )
        ],
        "pair_bonds": [asdict(PairBond(id=-3, person_a=-1, person_b=-88))],
        "delete": [],
    }
    return _data(people, events, pair_bonds, pdp=pdp, name="Hostile Names")


def _huge_data() -> dict:
    people = [
        _person(id=i, name=f"Person{i}", gender=PersonKind.Unknown)
        for i in range(1, HUGE_PEOPLE + 1)
    ]
    pair_bonds = [
        _bond(id=HUGE_PEOPLE + i, person_a=2 * i - 1, person_b=2 * i, married=True)
        for i in range(1, HUGE_PEOPLE // 2 + 1)
    ]
    first_event_id = HUGE_PEOPLE * 2 + 1
    events = [
        _event(
            id=first_event_id + i,
            kind=EventKind.Shift,
            person=(i % HUGE_PEOPLE) + 1,
            description=f"Shift {i}",
            dateTime=f"{1950 + (i % 70)}-01-01",
            anxiety=VariableShift.Up if i % 2 else VariableShift.Down,
        )
        for i in range(HUGE_EVENTS)
    ]
    return _data(people, events, pair_bonds, name="Huge Diagram")


def hostile() -> dict:
    owner = "hostile@test"
    peer = "hostile+peer@test"
    expired = "hostile+expired@test"
    unlicensed = "hostile+nolicense@test"
    nofree = "hostile+nofree@test"

    names_case = "Hostile Names"
    empty_case = "Empty Diagram"
    huge_case = "Huge Diagram"
    stale_case = "Stale Version"
    ro_case = "Shared Read Only"
    rw_case = "Shared Read Write"
    private_case = "Peer Private"

    orphan = {
        "summary": "Discussion with no owner",
        "user": None,
        "diagram": _ref(owner, names_case),
        "speakers": [
            {"name": "Nobody", "type": "subject", "role": SpeakerRole.User.value},
            {"name": "Coach", "type": "expert", "role": SpeakerRole.Ai.value},
        ],
        "statements": [{"speaker": "Nobody", "text": "Who owns this conversation?"}],
    }
    foreign = {
        "summary": "Discussion bound to someone else's diagram",
        "user": owner,
        "diagram": _ref(peer, private_case),
        "speakers": [
            {"name": "Intruder", "type": "subject", "role": SpeakerRole.User.value},
            {"name": "Coach", "type": "expert", "role": SpeakerRole.Ai.value},
        ],
        "statements": [{"speaker": "Intruder", "text": "This case is not mine."}],
    }
    extremes = {
        "summary": "Statements at the size and encoding extremes",
        "user": owner,
        "diagram": _ref(owner, names_case),
        "speakers": [
            {"name": "Extremes", "type": "subject", "role": SpeakerRole.User.value},
            {"name": "Coach", "type": "expert", "role": SpeakerRole.Ai.value},
        ],
        "statements": [
            {"speaker": "Extremes", "text": EMOJI_TEXT},
            {"speaker": "Coach", "text": "Say more."},
            {"speaker": "Extremes", "text": "x" * HUGE_STATEMENT_LEN},
        ],
    }

    def named(case, what, **kwargs):
        return {case.value: {"what": what, **kwargs}}

    manifest = {}
    for case, what, locator in (
        (
            Case.EmptyName,
            "committed person whose name is the empty string",
            {"person_id": 1},
        ),
        (
            Case.SingleTokenName,
            "committed person with a single-token name",
            {"person_id": 2},
        ),
        (
            Case.LastNameOnly,
            "old-writer chunk carrying last_name and no name",
            {"person_id": 3},
        ),
        (
            Case.UnicodeName,
            "committed person with combining unicode and emoji in the name",
            {"person_id": 4},
        ),
        (Case.LongName, "committed person with a 200-character name", {"person_id": 5}),
        (
            Case.DuplicateNames,
            "two committed people with identical names",
            {"person_id": 6, "person_ids": [6, 7]},
        ),
        (
            Case.SelfReferentialBond,
            "pair bond whose two endpoints are the same person",
            {"pair_bond_id": 22, "person_id": 9},
        ),
        (
            Case.DanglingEventPerson,
            "event referencing a person id that does not exist",
            {"event_id": 32, "person_id": 9999},
        ),
        (
            Case.ChildOfTwoBonds,
            "person listed as the child of two different bonds",
            {"person_id": 8, "pair_bond_ids": [20, 21], "event_ids": [30, 31]},
        ),
        (
            Case.StagedDanglingPdp,
            "staged pdp with negative ids referencing people that are not staged",
            {"person_id": -1, "event_id": -2, "pair_bond_id": -3},
        ),
    ):
        manifest.update(
            named(case, what, user=owner, diagram=_ref(owner, names_case), **locator)
        )

    manifest.update(
        named(
            Case.EmptyDiagram,
            "diagram with zero people",
            user=owner,
            diagram=_ref(owner, empty_case),
        )
    )
    manifest.update(
        named(
            Case.HugeDiagram,
            f"diagram with {HUGE_PEOPLE} people and {HUGE_EVENTS} events",
            user=owner,
            diagram=_ref(owner, huge_case),
        )
    )
    manifest.update(
        named(
            Case.StaleVersion,
            f"diagram row stored at version {STALE_VERSION}; a client holding the "
            f"older snapshot {STALE_CLIENT_VERSION} must be rejected",
            user=owner,
            diagram=_ref(owner, stale_case),
            stored_version=STALE_VERSION,
            client_version=STALE_CLIENT_VERSION,
        )
    )
    manifest.update(
        named(
            Case.SharedReadOnly,
            "case owned by the peer and shared read-only with the main user",
            user=owner,
            diagram=_ref(peer, ro_case),
            owner=peer,
        )
    )
    manifest.update(
        named(
            Case.SharedReadWrite,
            "case owned by the peer and shared read-write with the main user",
            user=owner,
            diagram=_ref(peer, rw_case),
            owner=peer,
        )
    )
    manifest.update(
        named(
            Case.NoAccess,
            "case owned by the peer that the main user has no access to",
            user=owner,
            diagram=_ref(peer, private_case),
            owner=peer,
        )
    )
    manifest.update(
        named(Case.ExpiredLicense, "user whose licenses are inactive", user=expired)
    )
    manifest.update(
        named(Case.NoLicense, "user with no license or machine at all", user=unlicensed)
    )
    manifest.update(named(Case.NoFreeDiagram, "user with no free diagram", user=nofree))
    manifest.update(
        named(
            Case.OrphanDiscussion,
            "discussion whose user_id is NULL",
            discussion=orphan["summary"],
            diagram=_ref(owner, names_case),
        )
    )
    manifest.update(
        named(
            Case.ForeignDiagramDiscussion,
            "discussion bound to a diagram its user does not own",
            user=owner,
            discussion=foreign["summary"],
            diagram=_ref(peer, private_case),
        )
    )
    manifest.update(
        named(
            Case.EmojiStatement,
            "statement whose text is emoji and zero-width joiners",
            user=owner,
            discussion=extremes["summary"],
            statement_order=1,
        )
    )
    manifest.update(
        named(
            Case.HugeStatement,
            f"statement of {HUGE_STATEMENT_LEN} characters",
            user=owner,
            discussion=extremes["summary"],
            statement_order=3,
        )
    )

    return {
        "users": [
            {"username": owner, "first_name": "Hos", "last_name": "Tile"},
            {"username": peer, "first_name": "Peer", "last_name": "Tile"},
            {
                "username": expired,
                "first_name": "Ex",
                "last_name": "Pired",
                "license": LicenseState.Expired.value,
            },
            {
                "username": unlicensed,
                "first_name": "No",
                "last_name": "License",
                "license": LicenseState.None_.value,
            },
            {
                "username": nofree,
                "first_name": "No",
                "last_name": "Free",
                "free_diagram": False,
            },
        ],
        "diagrams": [
            {"user": owner, "name": names_case, "data": _hostile_names_data()},
            {
                "user": owner,
                "name": empty_case,
                "data": _data([], [], [], name=empty_case),
            },
            {"user": owner, "name": huge_case, "data": _huge_data()},
            {
                "user": owner,
                "name": stale_case,
                "version": STALE_VERSION,
                "data": _data([], [], [], name=stale_case),
            },
            {"user": peer, "name": ro_case, "data": _data([], [], [], name=ro_case)},
            {"user": peer, "name": rw_case, "data": _data([], [], [], name=rw_case)},
            {
                "user": peer,
                "name": private_case,
                "data": _data([], [], [], name=private_case),
            },
        ],
        "discussions": [orphan, foreign, extremes],
        "access_rights": [
            {"diagram": _ref(peer, ro_case), "user": owner, "right": ACCESS_READ_ONLY},
            {"diagram": _ref(peer, rw_case), "user": owner, "right": ACCESS_READ_WRITE},
        ],
        "manifest": manifest,
    }


NAME_POOL = [
    "",
    "Mom",
    "Dad",
    UNICODE_NAME,
    LONG_NAME,
    "Sam",
    "Sam",
    "Ada",
    "Bernard",
    "Clara",
    "Dennis",
    "Elena",
    "Felix",
    "Greta",
    "O'Brien-Nakamura",
    "李",
    "Jean-Luc",
    "X",
]

LAST_NAME_POOL = ["", "Whitfield", "Reyes", "Okonkwo", "Þórsdóttir", "李", "Marsh"]

SHIFT_POOL = list(VariableShift)
RELATIONSHIP_POOL = list(RelationshipKind)


def random_family(seed: int = 0, people: int = 12) -> dict:
    """Deterministic structurally-valid family of `people` members. Same seed
    and size always produce byte-identical seed data."""
    rng = _random.Random(seed)
    username = f"random{seed}@test"
    case_name = f"Random {seed} x{people}"

    person_chunks = []
    for i in range(1, people + 1):
        person_chunks.append(
            _person(
                id=i,
                name=rng.choice(NAME_POOL),
                last_name=rng.choice(LAST_NAME_POOL),
                gender=rng.choice(list(PersonKind)),
            )
        )

    next_id = people + 1
    bond_chunks = []
    unbonded = list(range(1, people + 1))
    rng.shuffle(unbonded)
    while len(unbonded) >= 2 and rng.random() < 0.85:
        a, b = unbonded.pop(), unbonded.pop()
        bond_chunks.append(
            _bond(id=next_id, person_a=a, person_b=b, married=rng.random() < 0.7)
        )
        next_id += 1

    event_chunks = []
    for bond in bond_chunks:
        year = rng.randint(1940, 2010)
        event_chunks.append(
            _event(
                id=next_id,
                kind=EventKind.Married if bond["married"] else EventKind.Bonded,
                person=bond["person_a"],
                spouse=bond["person_b"],
                dateTime=f"{year}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            )
        )
        next_id += 1
        for child_index in range(rng.randint(0, 3)):
            child = rng.choice(person_chunks)
            if child["id"] in (bond["person_a"], bond["person_b"]) or child.get(
                "parents"
            ):
                continue
            child["parents"] = bond["id"]
            event_chunks.append(
                _event(
                    id=next_id,
                    kind=EventKind.Birth,
                    person=bond["person_a"],
                    spouse=bond["person_b"],
                    child=child["id"],
                    dateTime=f"{year + 2 + child_index}-{rng.randint(1, 12):02d}-01",
                )
            )
            next_id += 1

    for _ in range(rng.randint(people, people * 3)):
        subject = rng.choice(person_chunks)
        event_chunks.append(
            _event(
                id=next_id,
                kind=EventKind.Shift,
                person=subject["id"],
                description=f"Shift {next_id}",
                dateTime=f"{rng.randint(1960, 2026)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                dateCertainty=rng.choice(list(DateCertainty)),
                symptom=rng.choice(SHIFT_POOL),
                anxiety=rng.choice(SHIFT_POOL),
                functioning=rng.choice(SHIFT_POOL),
                relationship=rng.choice(RELATIONSHIP_POOL),
                relationshipTargets=[rng.choice(person_chunks)["id"]],
            )
        )
        next_id += 1

    return {
        "users": [{"username": username, "first_name": "Rand", "last_name": str(seed)}],
        "diagrams": [
            {
                "user": username,
                "name": case_name,
                "data": _data(
                    person_chunks,
                    event_chunks,
                    bond_chunks,
                    last_item_id=next_id,
                    name=case_name,
                ),
            }
        ],
        "discussions": [],
        "access_rights": [],
        "manifest": {
            Case.RandomFamily.value: {
                "what": f"deterministic random family, seed {seed}, {people} people",
                "user": username,
                "diagram": _ref(username, case_name),
                "seed": seed,
                "people": people,
            }
        },
    }


PROFILES = {
    "minimal": minimal,
    "family": family,
    "hostile": hostile,
    "random": random_family,
}

EMPTY_SPEC = {
    "users": [],
    "diagrams": [],
    "discussions": [],
    "access_rights": [],
    "manifest": {},
}


def merge(*specs: dict) -> dict:
    merged = {
        key: list(value) if isinstance(value, list) else dict(value)
        for key, value in EMPTY_SPEC.items()
    }
    for spec in specs:
        for key, empty in EMPTY_SPEC.items():
            value = spec.get(key, empty)
            if isinstance(empty, list):
                merged[key].extend(value)
            else:
                merged[key].update(value)
    return merged


def spec(profile: str | None) -> dict:
    """Resolve a profile expression to a seed spec.

    `"family+hostile"` composes profiles; `"random:7:20"` passes positional
    integer arguments to the generator.
    """
    if not profile:
        return merge()
    specs = []
    for token in profile.split("+"):
        name, _, args = token.strip().partition(":")
        if name not in PROFILES:
            raise ValueError(f"Unknown seed profile {name!r}; have {sorted(PROFILES)}")
        specs.append(PROFILES[name](*[int(x) for x in args.split(":") if x]))
    return merge(*specs)
