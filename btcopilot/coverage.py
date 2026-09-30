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
    own = profile.own(data)
    if own is None:
        return []
    items: dict[Item, None] = {}
    placed: set[int] = set()

    def person(pid: int, depth: tuple, *extra: Fact):
        if pid in placed:
            return
        placed.add(pid)
        always, dead = depth
        for fact in (*always, *(dead if _death(data, pid) else ()), *extra):
            items.setdefault((fact, ItemKind.Person, pid))

    def couple(bid: int | None, *facts: Fact):
        # a person whose parents are not in the record has no parents' couple
        if bid is None:
            return
        for fact in facts:
            items.setdefault((fact, ItemKind.PairBond, bid))

    me = own["id"]
    person(me, SIBLING, Fact.Parents, Fact.Stress)
    mine = _couples(data, me)
    for bid in mine:
        person(_other(data, bid, me), SIBLING, Fact.Parents)
        couple(bid, Fact.Met, Fact.Children)
    for bid in mine:
        for kid in _children(data, bid):
            person(kid, SIBLING)

    home = _parents(data, me)
    parents = _partners(data, home)
    for pid in parents:
        person(pid, SIBLING, Fact.Parents)
    couple(home, Fact.Children)
    for pid in parents:
        for bid in _couples(data, pid):
            person(_other(data, bid, pid), FULL)
            couple(bid, Fact.Children)
    siblings = _siblings(data, me)
    for pid in siblings:
        person(pid, SIBLING)
    for pid in siblings:
        for bid in _couples(data, pid):
            couple(bid, Fact.Children)
            for kid in _children(data, bid):
                person(kid, COUSIN)

    for bid in mine:
        partner = _other(data, bid, me)
        theirs = _parents(data, partner)
        close = _attached(data, bid, partner)
        for pid in _partners(data, theirs):
            person(pid, FULL if close else FLOOR)
        couple(theirs, Fact.Children)
        for pid in _siblings(data, partner):
            person(pid, SIBLING if close else FLOOR)

    grand = [_parents(data, pid) for pid in parents]
    for bid in grand:
        for pid in _partners(data, bid):
            person(pid, FULL)
        couple(bid, Fact.Children)
    aunts = [pid for bid in grand for pid in _children(data, bid) if pid not in parents]
    for pid in aunts:
        person(pid, AUNT)
        for bid in _couples(data, pid):
            couple(bid, Fact.Children)
    for pid in aunts:
        for bid in _couples(data, pid):
            for kid in _children(data, bid):
                person(kid, COUSIN)

    for bid in grand:
        for pid in _partners(data, bid):
            for great in _partners(data, _parents(data, pid)):
                person(great, GREAT)
    return list(items)


def states(data: DiagramData) -> dict[Item, FactState]:
    """Known from the record, or from a closed fact question naming the item;
    said unknown or declined only from such a question; otherwise not asked.
    A question still open leaves its item not asked until it is closed."""
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


def _answers(data: DiagramData) -> dict[Item, FactState]:
    """The last closed question naming each item, by how it ended; one let go
    says nothing about the item."""
    out = {}
    for q in data.questions:
        if q.get("fact") is None or q["state"] != QuestionState.Resolved:
            continue
        state = ANSWERS.get(QuestionOutcome(q["outcome"]))
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
        case Fact.Health:
            return any(
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
            return any(
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
