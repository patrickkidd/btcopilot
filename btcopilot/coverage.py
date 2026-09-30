"""The basic data of a family evaluation as a checklist, worked out from the
record each time it is read: the relatives the record implies, the items each
one needs, and whether each item is known, said unknown, declined or not asked
(Kerr, Family Evaluation ch. 10; Bowen, FTiCP ch. 9). Nothing of it is stored
but the counts each coach turn keeps."""

import datetime

from btcopilot import profile
from btcopilot.schema import (
    DECLINED,
    DEFAULT_SUBJECT_NAME,
    DateCertainty,
    DiagramData,
    EventKind,
    Fact,
    FactState,
    ItemKind,
    PersonKind,
    QuestionOutcome,
    QuestionState,
    parse_date,
)

Item = tuple[Fact, ItemKind, int]

# Each depth is the items everyone at it needs, then those only someone the
# record says has died needs.
FULL = (
    (
        Fact.Name,
        Fact.BirthDate,
        Fact.Alive,
        Fact.Schooling,
        Fact.Work,
        Fact.Health,
        Fact.Marriages,
        Fact.Places,
        Fact.Contact,
    ),
    (Fact.DeathDate, Fact.CauseOfDeath),
)
SIBLING = ((*FULL[0], Fact.Order, Fact.Sex), FULL[1])
# Bowen's list for each sibling of each parent (FTiCP ch. 9).
AUNT = (
    (
        Fact.Name,
        Fact.Order,
        Fact.BirthDate,
        Fact.Alive,
        Fact.Work,
        Fact.Places,
        Fact.Marriages,
        Fact.LifeCourse,
        Fact.Contact,
    ),
    FULL[1],
)
COUSIN = ((Fact.Name, Fact.Order, Fact.Sex, Fact.Alive), ())
GREAT = ((Fact.Name, Fact.Alive, Fact.Places), (Fact.DeathDate,))
# The partner's parents and siblings when the person is little attached to
# the partner: by name and alive (Patrick, 2026-09-30).
FLOOR = ((Fact.Name, Fact.Alive), ())

# Evidence of attachment to a partner: married, children together, this many
# years together, this many of the partner's family in the record.
YEARS_TOGETHER = 5
PARTNER_FAMILY = 2
ATTACHED = 2

# What each relative is to the person: for a woman, a man, anyone else.
SELF = ("the person",) * 3
PARTNER = ("partner",) * 3
CHILD = ("daughter", "son", "child")
PARENT = ("mother", "father", "parent")
STEP = ("step-parent",) * 3
SIB = ("sister", "brother", "sibling")
NIECE = ("niece", "nephew", "niece or nephew")
IN_LAW = ("partner's mother", "partner's father", "partner's parent")
PARTNER_SIB = ("partner's sister", "partner's brother", "partner's sibling")
GRAND = ("grandmother", "grandfather", "grandparent")
AUNT_ROLE = ("aunt", "uncle", "aunt or uncle")
COUSIN_ROLE = ("cousin",) * 3
GREAT_ROLE = ("great-grandmother", "great-grandfather", "great-grandparent")

WORDS = {
    Fact.Name: "name",
    Fact.BirthDate: "birth date",
    Fact.Alive: "alive or not",
    Fact.DeathDate: "death date",
    Fact.CauseOfDeath: "cause of death",
    Fact.Schooling: "schooling",
    Fact.Work: "work",
    Fact.Health: "health",
    Fact.Marriages: "marriages with dates",
    Fact.Places: "where they lived",
    Fact.Contact: "contact with the family",
    Fact.LifeCourse: "how life went",
    Fact.Order: "birth order",
    Fact.Sex: "sex",
    Fact.Parents: "who their parents are",
    Fact.Children: "how many children",
    Fact.Met: "when they met",
    Fact.Stress: "periods of major stress",
}

# How many unasked items the coach's summary lists, and how many while its
# plateau note is in force, and for how many turns that note holds unless a
# new person or event comes first. The corpus sets no number of turns.
LEAD = 8
PLATEAU_LEAD = 3
# At most this many for one person or couple, so the list reaches past the
# first person with many gaps.
EACH = 3
PLATEAU_TURNS = 5
HEAD = "WHAT IS STILL UNKNOWN"

UNNAMED = ("", profile.PLACEHOLDER_NAME, DEFAULT_SUBJECT_NAME)
ANSWERS = {
    QuestionOutcome.Fact: FactState.Known,
    QuestionOutcome.Answered: FactState.Known,
    QuestionOutcome.Unknown: FactState.SaidUnknown,
    **{outcome: FactState.Declined for outcome in DECLINED},
}
MARRIAGE = tuple(kind for kind in EventKind if kind.isCouple())
TOGETHER = (EventKind.Bonded, EventKind.Married)
APART = (EventKind.Separated, EventKind.Divorced)


def required(data: DiagramData) -> list[Item]:
    """Every item the record implies, in Kerr's loose order: the nuclear
    family, parents and siblings, the partner's side, grandparents, aunts and
    uncles, cousins, great-grandparents. A relative placed once keeps the
    depth of the first place."""
    return list(_walk(data))


def _walk(data: DiagramData) -> dict[Item, str]:
    """The required items, each with what its person or couple is to the
    person, in the order `required` gives."""
    own = profile.own(data)
    if own is None:
        return {}
    items: dict[Item, str] = {}
    placed: set[int] = set()

    def person(pid: int, role: tuple, depth: tuple, *extra: Fact):
        if pid in placed:
            return
        placed.add(pid)
        always, dead = depth
        word = _role(data, pid, role)
        for fact in (*always, *(dead if _death(data, pid) else ()), *extra):
            items.setdefault((fact, ItemKind.Person, pid), word)

    def couple(bid: int | None, role: str, *facts: Fact):
        # a person whose parents are not in the record has no parents' couple
        if bid is None:
            return
        for fact in facts:
            items.setdefault((fact, ItemKind.PairBond, bid), role)

    me = own["id"]
    person(me, SELF, SIBLING, Fact.Parents, Fact.Stress)
    mine = _couples(data, me)
    for bid in mine:
        person(_other(data, bid, me), PARTNER, SIBLING, Fact.Parents)
        couple(bid, "the person and partner", Fact.Met, Fact.Children)
    for bid in mine:
        for kid in _children(data, bid):
            person(kid, CHILD, SIBLING)

    home = _parents(data, me)
    parents = _partners(data, home)
    for pid in parents:
        person(pid, PARENT, SIBLING, Fact.Parents)
    couple(home, "parents", Fact.Children)
    for pid in parents:
        for bid in _couples(data, pid):
            person(_other(data, bid, pid), STEP, FULL)
            couple(bid, "a parent's couple", Fact.Children)
    siblings = _siblings(data, me)
    for pid in siblings:
        person(pid, SIB, SIBLING)
    for pid in siblings:
        for bid in _couples(data, pid):
            couple(bid, "a sibling's couple", Fact.Children)
            for kid in _children(data, bid):
                person(kid, NIECE, COUSIN)

    for bid in mine:
        partner = _other(data, bid, me)
        theirs = _parents(data, partner)
        close = _attached(data, bid, partner)
        for pid in _partners(data, theirs):
            person(pid, IN_LAW, FULL if close else FLOOR)
        couple(theirs, "partner's parents", Fact.Children)
        for pid in _siblings(data, partner):
            person(pid, PARTNER_SIB, SIBLING if close else FLOOR)

    grand = [_parents(data, pid) for pid in parents]
    for bid in grand:
        for pid in _partners(data, bid):
            person(pid, GRAND, FULL)
        couple(bid, "grandparents", Fact.Children)
    aunts = [pid for bid in grand for pid in _children(data, bid) if pid not in parents]
    for pid in aunts:
        person(pid, AUNT_ROLE, AUNT)
        for bid in _couples(data, pid):
            couple(bid, "an aunt's or uncle's couple", Fact.Children)
    for pid in aunts:
        for bid in _couples(data, pid):
            for kid in _children(data, bid):
                person(kid, COUSIN_ROLE, COUSIN)

    for bid in grand:
        for pid in _partners(data, bid):
            for great in _partners(data, _parents(data, pid)):
                person(great, GREAT_ROLE, GREAT)
    return items


def states(data: DiagramData) -> dict[Item, FactState]:
    """Known from the record, or from a closed fact question naming the item;
    asked while such a question is open; said unknown or declined only from
    such a question once closed; otherwise not asked."""
    answers = _answers(data)
    return {
        item: (
            FactState.Known
            if _recorded(data, item, answers)
            else answers.get(item, FactState.NotAsked)
        )
        for item in required(data)
    }


def counts(data: DiagramData) -> dict[str, int]:
    found = list(states(data).values())
    return {"required": len(found), **{s.value: found.count(s) for s in FactState}}


def block(data: DiagramData, plateau: int | None = None) -> str:
    """The next unasked items in Kerr's loose order, grouped by whom they are
    about, the items said unknown, and coverage and resolution as fractions.
    `plateau` is the turn of the coach's plateau note still in force, which
    cuts the list to the nearest few. Empty when nothing is required."""
    roles = _walk(data)
    if not roles:
        return ""
    found = states(data)
    gaps = [i for i in roles if found[i] is FactState.NotAsked]
    lead = LEAD if plateau is None else PLATEAU_LEAD
    unknown = [i for i in roles if found[i] is FactState.SaidUnknown]
    tally = list(found.values())
    known = tally.count(FactState.Known)
    resolved = (
        known + tally.count(FactState.SaidUnknown) + tally.count(FactState.Declined)
    )
    lines = [HEAD]
    if plateau is not None:
        lines.append(
            f"Your plateau note holds, turn {plateau} of {PLATEAU_TURNS}: "
            f"the nearest {PLATEAU_LEAD} only."
        )
    lines += _grouped(data, _nearest(gaps, lead), roles)
    if unknown:
        lines.append("Said unknown: " + "; ".join(_grouped(data, unknown, roles)))
    lines.append(
        f"Coverage: {known} of {len(found)} known. Resolved: "
        f"{resolved} of {len(found)} known, said unknown or declined."
    )
    return "\n".join(lines)


def _nearest(gaps: list[Item], lead: int) -> list[Item]:
    """The first `lead` gaps, at most EACH of them on one person or couple."""
    out, per = [], {}
    for item in gaps:
        per[item[1:]] = per.get(item[1:], 0) + 1
        if per[item[1:]] <= EACH:
            out.append(item)
    return out[:lead]


def _grouped(data: DiagramData, items: list[Item], roles: dict) -> list[str]:
    """One line per person or couple, in the order the items come."""
    groups: dict[str, list[str]] = {}
    for item in items:
        fact, kind, iid = item
        groups.setdefault(_label(data, kind, iid, roles[item]), []).append(WORDS[fact])
    return [f"{label}: {', '.join(words)}" for label, words in groups.items()]


def _label(data: DiagramData, kind: ItemKind, iid: int, role: str) -> str:
    if kind is ItemKind.PairBond:
        names = " and ".join(_name(data, pid) for pid in _partners(data, iid))
        return f"couple {iid}, {names} ({role})"
    return f"{iid} {_name(data, iid)} ({role})"


def _name(data: DiagramData, pid: int) -> str:
    name = _person(data, pid).get("name") or ""
    return "unnamed" if name in UNNAMED else name


def _role(data: DiagramData, pid: int, role: tuple) -> str:
    woman, man, anyone = role
    return {PersonKind.Female: woman, PersonKind.Male: man}.get(
        _person(data, pid).get("gender"), anyone
    )


def _answers(data: DiagramData) -> dict[Item, FactState]:
    """What the last fact question naming each item says of it: asked while
    it is open, or how it was closed; one held or let go says nothing."""
    out = {}
    for q in data.questions:
        if q.get("fact") is None:
            continue
        if q["state"] == QuestionState.Asked:
            state = FactState.Asked
        elif q["state"] == QuestionState.Resolved:
            state = ANSWERS.get(QuestionOutcome(q["outcome"]))
        else:
            state = None
        if state is not None:
            out[(Fact(q["fact"]), ItemKind(q["item_kind"]), int(q["item_id"]))] = state
    return out


def _recorded(data: DiagramData, item: Item, answers: dict) -> bool:
    fact, _, iid = item
    match fact:
        case Fact.Name:
            return (_person(data, iid).get("name") or "") not in UNNAMED
        case Fact.BirthDate:
            return any(
                EventKind(e["kind"]).isOffspring()
                and e.get("child") == iid
                and _dated(e)
                for e in data.events
            )
        case Fact.Alive:
            return _death(data, iid) is not None
        case Fact.DeathDate:
            return _dated(_death(data, iid))
        case Fact.CauseOfDeath:
            return bool(_death(data, iid)["description"])
        case Fact.Schooling | Fact.Work:
            return _noted(data, iid, fact)
        case Fact.Health:
            return _noted(data, iid, fact) or any(
                e["kind"] == EventKind.Shift.value
                and e.get("person") == iid
                and e.get("symptom")
                for e in data.events
            )
        case Fact.Marriages:
            return any(
                EventKind(e["kind"]) in MARRIAGE
                and iid in (e.get("person"), e.get("spouse"))
                and _dated(e)
                for e in data.events
            )
        case Fact.Places:
            return _noted(data, iid, fact) or any(
                e["kind"] == EventKind.Noted.value
                and e.get("person") == iid
                and e.get("location")
                for e in data.events
            )
        case Fact.Order:
            return _ordered(data, iid, answers)
        case Fact.Sex:
            return _person(data, iid).get("gender") in (
                PersonKind.Male,
                PersonKind.Female,
            )
        case Fact.Parents:
            return _parents(data, iid) is not None
        case Fact.Met:
            return any(_dated(e) for e in _between(data, iid, TOGETHER))
        case Fact.Stress:
            return bool(data.clusters)
    return False


def _noted(data: DiagramData, pid: int, fact: Fact) -> bool:
    """A noted event on the person that says it records this item."""
    return any(
        e["kind"] == EventKind.Noted.value
        and e.get("person") == pid
        and e.get("item") == fact.value
        for e in data.events
    )


def _ordered(data: DiagramData, pid: int, answers: dict) -> bool:
    """Birth order is read from the record when every child of the parents
    has a dated birth and the record holds them all: two or more of them, or
    the parents' number of children known."""
    home = _parents(data, pid)
    if home is None:
        return False
    kids = _children(data, home)
    complete = (
        len(kids) > 1
        or answers.get((Fact.Children, ItemKind.PairBond, home)) is FactState.Known
    )
    return complete and all(
        _recorded(data, (Fact.BirthDate, ItemKind.Person, kid), answers) for kid in kids
    )


def _attached(data: DiagramData, bid: int, partner: int) -> bool:
    """How much the partner's side is required scales with the person's
    attachment to the partner: married, children together, years together,
    and how much of the partner's family is in the record (Patrick,
    2026-09-30)."""
    started = [
        parse_date(e["dateTime"]) for e in _between(data, bid, TOGETHER) if _dated(e)
    ]
    ended = [parse_date(e["dateTime"]) for e in _between(data, bid, APART) if _dated(e)]
    years = 0
    if started:
        years = (
            (min(ended) if ended else datetime.date.today()) - min(started)
        ).days / 365
    family = len(_partners(data, _parents(data, partner))) + len(
        _siblings(data, partner)
    )
    signals = (
        bool(_between(data, bid, (EventKind.Married,))),
        bool(_children(data, bid)),
        years >= YEARS_TOGETHER,
        family >= PARTNER_FAMILY,
    )
    return sum(signals) >= ATTACHED


def _between(data: DiagramData, bid: int, kinds: tuple) -> list[dict]:
    pair = set(_partners(data, bid))
    return [
        e
        for e in data.events
        if EventKind(e["kind"]) in kinds and {e.get("person"), e.get("spouse")} == pair
    ]


def _dated(event: dict) -> bool:
    return (
        bool(event.get("dateTime"))
        and event.get("dateCertainty") != DateCertainty.Unknown
    )


def _death(data: DiagramData, pid: int) -> dict | None:
    return next(
        (
            e
            for e in data.events
            if e["kind"] == EventKind.Death.value and e.get("person") == pid
        ),
        None,
    )


def _person(data: DiagramData, pid: int) -> dict:
    return next(p for p in data.people if p["id"] == pid)


def _parents(data: DiagramData, pid: int) -> int | None:
    return _person(data, pid).get("parents")


def _partners(data: DiagramData, bid: int | None) -> list[int]:
    if bid is None:
        return []
    bond = next(b for b in data.pair_bonds if b["id"] == bid)
    return [pid for pid in (bond["person_a"], bond["person_b"]) if pid is not None]


def _other(data: DiagramData, bid: int, pid: int) -> int:
    return next(other for other in _partners(data, bid) if other != pid)


def _couples(data: DiagramData, pid: int) -> list[int]:
    return [b["id"] for b in data.pair_bonds if pid in (b["person_a"], b["person_b"])]


def _children(data: DiagramData, bid: int | None) -> list[int]:
    if bid is None:
        return []
    return [p["id"] for p in data.people if p.get("parents") == bid]


def _siblings(data: DiagramData, pid: int) -> list[int]:
    """Full, half and step: every child of the parents' couples but this one."""
    home = _parents(data, pid)
    bonds = [
        home,
        *(b for q in _partners(data, home) for b in _couples(data, q) if b != home),
    ]
    return [kid for bid in bonds for kid in _children(data, bid) if kid != pid]
