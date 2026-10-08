"""The basic data of a family evaluation as a checklist, worked out from the
record each time it is read: the relatives the record implies, the items each
one needs, and whether each item is known, said unknown, declined or not asked
(Kerr, Family Evaluation ch. 10; Bowen, FTiCP ch. 9). Nothing of it is stored
but the counts each coach turn keeps."""

import datetime

from btcopilot import profile
from btcopilot.prompts import Role
from btcopilot.record import GENERIC, PLACEHOLDERS, ROLE_WORDS, generic_key
from btcopilot.recordtext import event_line, note_line, person_line
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
# The person's own: what a sibling needs, with the times they say the most was
# going on right after their birth date.
OWN = ((*SIBLING[0][:2], Fact.MostGoingOn, *SIBLING[0][2:]), SIBLING[1])
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
    Fact.MostGoingOn: "the two or three times when the most was going on",
}

# The items the checklist places on a couple; every other one is a person's.
COUPLE_FACTS = (Fact.Children, Fact.Met)

# The items that draw the family's structure, in the order Patrick gave them
# (2026-10-07: "the basic family structure should be mapped out at least
# earlier than later. Definitely before any Coach driven rabbit holes on
# stories"; the person's parents, each parent's parents, each person's
# siblings and their count, pair-bonds and their dates): first who each person
# is, whose parents are whose and how many children each couple had, then the
# bonds with their dates. When the next question is the coach's own to choose,
# these lead the list for every diagram until they are closed, and the story
# items follow. A topic the person brings is followed first; that is the
# prompt's rule, not the list's. The times the most was going on keep their
# place ahead of everything [R-0735].
LEADING = (Fact.MostGoingOn,)
TIERS = (LEADING, (Fact.Name, Fact.Parents, Fact.Children), (Fact.Marriages, Fact.Met))
STRUCTURE = (*TIERS[1], *TIERS[2])

# The everyday words the chat is searched for before a fact question is asked,
# each matched at the start of a word, so "child" finds "children" and "die"
# finds "died". The tool searches with these, not the coach, which may not know
# the words the person used (Patrick, 2026-10-04) [R-0760].
SEARCH_WORDS = {
    Fact.Name: ("name", "called"),
    Fact.BirthDate: ("born", "birthday", "birth", "years old", "turned", "turns"),
    Fact.Alive: (
        "alive", "living", "died", "dead", "death", "passed", "funeral", "buried",
        "still married", "still with us", "still around",
    ),
    Fact.DeathDate: ("died", "death", "passed", "funeral", "buried"),
    Fact.CauseOfDeath: (
        "died of", "died from", "cancer", "heart attack", "stroke", "suicide",
        "accident", "overdose",
    ),
    Fact.Schooling: (
        "school", "college", "university", "degree", "graduated", "studied",
        "dropped out",
    ),
    Fact.Work: ("work", "job", "career", "retired", "employ", "unemploy", "business", "laid off"),
    Fact.Health: (
        "health", "sick", "ill", "diagnos", "hospital", "cancer", "depress", "anxi",
        "disease", "surgery", "drink", "alcohol",
    ),
    Fact.Marriages: (
        "married", "marriage", "wedding", "divorce", "separated", "husband", "wife",
        "remarried", "engaged",
    ),
    Fact.Places: ("lived", "lives", "live in", "moved", "grew up", "hometown"),
    Fact.Contact: (
        "contact", "talk", "speak", "spoken", "visit", "call", "estranged", "cut off",
        "close",
    ),
    Fact.LifeCourse: ("life", "ended up", "turned out", "became"),
    Fact.Order: (
        "oldest", "youngest", "eldest", "middle child", "firstborn", "older", "younger",
        "twin",
    ),
    Fact.Sex: ("man", "woman", "boy", "girl", "male", "female"),
    Fact.Parents: ("parents", "mother", "father", "mom", "dad", "raised by", "adopted"),
    Fact.Children: (
        "children", "child", "kids", "son", "daughter", "pregnan", "baby", "babies",
        "IVF", "adopt", "miscarriage", "infertil", "start a family", "childless",
    ),
    Fact.Met: ("met", "meet", "dating", "started seeing", "got together", "introduced"),
    Fact.Stress: ("stress", "hardest", "worst", "crisis", "fell apart", "rough patch"),
    Fact.MostGoingOn: ("most was going on", "most going on", "busiest"),
}

# What a relative is called in talk, by what they are to the person, searched
# beside their name. A mother's and a father's words are the record's own, and
# either is one of "my parents".
PARENTS = ("parents", "folks")
CALLED = {
    "partner": ("partner", "husband", "wife", "spouse", "boyfriend", "girlfriend", "fianc"),
    "daughter": ("daughter",),
    "son": ("son",),
    "child": ("child", "kid"),
    "mother": (*(word for word, role in ROLE_WORDS.items() if role is Role.Mother), *PARENTS),
    "father": (*(word for word, role in ROLE_WORDS.items() if role is Role.Father), *PARENTS),
    "parent": ("parent",),
    "step-parent": ("step",),
    "sister": ("sister",),
    "brother": ("brother",),
    "sibling": ("sibling",),
    "niece": ("niece",),
    "nephew": ("nephew",),
    "niece or nephew": ("niece", "nephew"),
    "grandmother": ("grandmother", "grandma", "granny", "nana"),
    "grandfather": ("grandfather", "grandpa", "grandad", "granddad", "gramps"),
    "grandparent": ("grandparent",),
    "aunt": ("aunt", "auntie"),
    "uncle": ("uncle",),
    "aunt or uncle": ("aunt", "uncle"),
    "cousin": ("cousin",),
    "great-grandmother": ("great-grand", "great grand"),
    "great-grandfather": ("great-grand", "great grand"),
    "great-grandparent": ("great-grand", "great grand"),
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
# A child counted but not named is added as "<the couple>'s child", the way an
# unnamed parent or partner is added (R-0325; Patrick, 2026-10-07: "sounds like
# you should at least add the person with no name"). Such a name is no name,
# so the child's own name is an open item.
CHILD_ROLE = "child"


def unnamed(name: str | None) -> bool:
    """Whether a person's name is no name: empty, a placeholder, or the generic
    name of a child nobody named."""
    name = (name or "").strip()
    match = GENERIC.match(name)
    return name in UNNAMED or bool(match and match.group(2).lower() == CHILD_ROLE)
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
    person(me, SELF, OWN, Fact.Parents, Fact.Stress)
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


def fits(fact: Fact, kind: ItemKind) -> bool:
    """Whether the item is one the checklist places on that kind of thing: how
    many children and when they met on a couple, everything else on a person."""
    return (fact in COUPLE_FACTS) == (kind is ItemKind.PairBond)


def state_of(data: DiagramData, fact: Fact, kind: ItemKind, iid: int) -> FactState:
    """One item's state, by the rules of `states`, whether or not the
    checklist requires it [R-0760]."""
    answers = _answers(data)
    item = (fact, kind, iid)
    if _recorded(data, item, answers):
        return FactState.Known
    return answers.get(item, FactState.NotAsked)


def evidence(data: DiagramData, fact: Fact, kind: ItemKind, iid: int) -> str | None:
    """What makes an item known, as the map writes it: the record entry that
    records it, or the closed question naming it; None while it is not known
    [R-0760]."""
    item = (fact, kind, iid)
    answers = _answers(data)
    if _recorded(data, item, answers):
        events = _records(data, fact, iid)
        if events:
            return event_line(events[0])
        if fact is Fact.Alive:
            return "they are the person you are talking with"
        if fact is Fact.Stress:
            return f"the record's {len(data.clusters)} clusters"
        if fact is Fact.Order:
            return "every child of their parents has a dated birth"
        return person_line(_person(data, iid))
    if answers.get(item) is FactState.Known:
        known = [o for o, s in ANSWERS.items() if s is FactState.Known]
        return note_line(_last(data, item, QuestionState.Resolved, known))
    return None


def asking(data: DiagramData, fact: Fact, kind: ItemKind, iid: int) -> dict | None:
    """The fact question naming the item that is asked and still open, if any."""
    return _last(data, (fact, kind, iid), QuestionState.Asked)


def label(data: DiagramData, kind: ItemKind, iid: int) -> str:
    """A person or couple as the coach's list names them, with what they are
    to the person when the record says."""
    return _label(data, kind, iid, _role_of(data, kind, iid))


def spoken_as(data: DiagramData, kind: ItemKind, iid: int) -> list[str] | None:
    """The words a message about a person or couple carries: their first name
    and what they are called for what they are to the person. None for the
    person themself and their own couples, who say "I" and "we"."""
    own = profile.own(data)
    people = [iid] if kind is ItemKind.Person else _partners(data, iid)
    if own is not None and own["id"] in people:
        return None
    words = []
    for pid in people:
        name = _person(data, pid).get("name") or ""
        if not unnamed(name) and generic_key({"name": name}) is None:
            words.append(name)
        role = _role_of(data, ItemKind.Person, pid)
        if role is not None:
            words.extend(_called(role))
    if _role_of(data, kind, iid) == "parents":
        words.append("parents")
    return list(dict.fromkeys(words))


def _role_of(data: DiagramData, kind: ItemKind, iid: int) -> str | None:
    return next(
        (role for (_, k, i), role in _walk(data).items() if (k, i) == (kind, iid)),
        None,
    )


def _called(role: str) -> tuple[str, ...]:
    """The everyday words for a relation: "partner's mother" is called by a
    mother's words and as an in-law."""
    if role in CALLED:
        return CALLED[role]
    words = CALLED.get(role.rsplit(" ", 1)[-1], ())
    return (*words, "in-law") if role.startswith("partner's") else words


def _last(
    data: DiagramData, item: Item, state: QuestionState, outcomes: list | None = None
) -> dict | None:
    """The last fact question naming the item that is in the state, and ended
    one of the ways given when any are."""
    fact, kind, iid = item
    found = None
    for q in data.questions:
        if (
            q.get("fact") == fact.value
            and q.get("item_kind") == kind.value
            and str(q.get("item_id")) == str(iid)
            and q["state"] == state
            and (outcomes is None or q.get("outcome") in outcomes)
        ):
            found = q
    return found


def block(data: DiagramData, plateau: int | None = None) -> str:
    """The next unasked items, the structure items first and then the rest,
    each in Kerr's loose order, grouped by whom they are about, the items said
    unknown, and coverage and resolution as fractions. `plateau` is the turn of
    the coach's plateau note still in force, which cuts the list to the nearest
    few. Empty when nothing is required."""
    roles = _walk(data)
    if not roles:
        return ""
    found = states(data)
    gaps = structure_first([i for i in roles if found[i] is FactState.NotAsked])
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


def structure_first(items: list[Item]) -> list[Item]:
    """The items with the times the most was going on first, then each tier of
    the structure items, then the rest, each part keeping the order given. The
    same rule for every diagram: the order comes from the record's shape, and
    no diagram is edited to get it."""
    rank = {fact: tier for tier, facts in enumerate(TIERS) for fact in facts}
    return sorted(items, key=lambda item: rank.get(item[0], len(TIERS)))


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


def _label(data: DiagramData, kind: ItemKind, iid: int, role: str | None) -> str:
    if kind is ItemKind.PairBond:
        names = " and ".join(_name(data, pid) for pid in _partners(data, iid))
        line = f"couple {iid}, {names}"
    else:
        line = f"{iid} {_name(data, iid)}"
    return f"{line} ({role})" if role else line


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
            return not unnamed(_person(data, iid).get("name"))
        case Fact.Alive:
            own = profile.own(data)
            if own is not None and iid == own["id"]:
                return True
        case Fact.Order:
            return _ordered(data, iid, answers)
        case Fact.Sex:
            return _person(data, iid).get("gender") in (
                PersonKind.Male,
                PersonKind.Female,
            )
        case Fact.Parents:
            return _parents(data, iid) is not None
        case Fact.Stress:
            return bool(data.clusters)
    return bool(_records(data, fact, iid))


def _records(data: DiagramData, fact: Fact, iid: int) -> list[dict]:
    """The events that record the item, for the items events record."""
    match fact:
        case Fact.BirthDate:
            return [
                e
                for e in data.events
                if EventKind(e["kind"]).isOffspring() and e.get("child") == iid and _dated(e)
            ]
        case Fact.Alive | Fact.DeathDate | Fact.CauseOfDeath:
            death = _death(data, iid)
            if death is None:
                return []
            told = {
                Fact.Alive: True,
                Fact.DeathDate: _dated(death),
                Fact.CauseOfDeath: _worded(death),
            }[fact]
            return [death] if told else []
        case Fact.Schooling | Fact.Work:
            return _noted(data, iid, fact)
        case Fact.Health:
            return _noted(data, iid, fact) + [
                e
                for e in data.events
                if e["kind"] == EventKind.Shift.value
                and e.get("person") == iid
                and e.get("symptom")
            ]
        case Fact.Marriages:
            return [
                e
                for e in data.events
                if EventKind(e["kind"]) in MARRIAGE
                and iid in (e.get("person"), e.get("spouse"))
                and _dated(e)
            ]
        case Fact.Places:
            return _noted(data, iid, fact) + [
                e
                for e in data.events
                if e["kind"] == EventKind.Noted.value
                and e.get("person") == iid
                and e.get("location")
            ]
        case Fact.Met:
            return [e for e in _between(data, iid, TOGETHER) if _dated(e)]
    return []


def _noted(data: DiagramData, pid: int, fact: Fact) -> list[dict]:
    """The noted events on the person that say they record this item."""
    return [
        e
        for e in data.events
        if e["kind"] == EventKind.Noted.value
        and e.get("person") == pid
        and e.get("item") == fact.value
    ]


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


def _worded(event: dict) -> bool:
    """Whether the event's words add to what its kind already says."""
    kind = EventKind(event["kind"])
    words = (event.get("description") or "").strip().lower()
    return (
        words not in (*PLACEHOLDERS, kind.value)
        if kind.isSelfDescribing()
        else bool(words)
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
