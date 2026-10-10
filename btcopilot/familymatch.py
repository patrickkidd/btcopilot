"""Pass 1 of matching the people of two family diagrams: deterministic rules
on family structure plus names. What it cannot settle it leaves ambiguous,
with candidates, for the model call per nuclear family and then the question
to the person."""

import enum
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from functools import cache

from btcopilot.schema import EventKind, PersonKind

NICKNAMES = [
    {"bob", "bobby", "rob", "robbie", "robert", "bert"},
    {"wally", "walt", "walter", "wallace"},
    {
        "lisa",
        "alissa",
        "alyssa",
        "elisa",
        "elizabeth",
        "liz",
        "beth",
        "betsy",
        "betty",
        "eliza",
    },
    {
        "katy",
        "katie",
        "kate",
        "kathy",
        "kathleen",
        "katherine",
        "catherine",
        "cathy",
        "kat",
    },
    {"jim", "jimmy", "jamie", "james"},
    {"bill", "billy", "will", "willie", "william", "liam"},
    {"joe", "joey", "joseph"},
    {"tony", "anthony"},
    {"mike", "mikey", "michael", "mick"},
    {"chris", "christopher", "christine", "christina", "kristen", "kristin"},
    {"sam", "sammy", "samuel", "samantha"},
    {"jenny", "jen", "jennifer"},
    {"connie", "constance"},
    {"leeann", "leann", "leanne"},
    {"dick", "rick", "ricky", "rich", "richard"},
    {"ted", "teddy", "ed", "eddie", "edward", "ned", "theodore"},
    {"tom", "tommy", "thomas"},
    {"dan", "danny", "daniel"},
    {"dave", "davey", "david"},
    {"steve", "steven", "stephen"},
    {"peggy", "maggie", "meg", "margaret", "marge", "margie"},
    {"pat", "patty", "patricia", "patrick", "paddy"},
    {"sue", "susie", "susan", "suzanne"},
    {"nick", "nicholas"},
    {"alex", "alexander", "alexandra", "sandy", "sandra"},
    {"andy", "andrew", "drew"},
    {"charlie", "chuck", "charles"},
    {"jack", "john", "johnny", "jon"},
    {"hank", "harry", "henry"},
    {"fred", "freddy", "frederick"},
    {"ben", "benny", "benjamin"},
    {"tim", "timmy", "timothy"},
    {"greg", "gregory"},
    {"matt", "matthew"},
    {"debbie", "deb", "deborah"},
    {"vicky", "vickie", "victoria"},
    {"becky", "rebecca"},
    {"molly", "polly", "mary", "mae"},
    {"nancy", "ann", "anne", "anna", "annie"},
]
ROLES = {
    "mother",
    "father",
    "mom",
    "dad",
    "parent",
    "partner",
    "wife",
    "husband",
    "spouse",
    "son",
    "daughter",
    "child",
    "baby",
    "brother",
    "sister",
    "sibling",
    "grandmother",
    "grandfather",
    "grandma",
    "grandpa",
    "aunt",
    "uncle",
    "cousin",
    "stepmother",
    "stepfather",
    "unknown",
    "unnamed",
}
THRESHOLD = 0.75
POSITION = 0.5
EPSILON = 0.05
YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")
PLACEHOLDER = re.compile(r"\w['’]s\b")


class Status(enum.StrEnum):
    Name = "name"
    Position = "position"
    Ambiguous = "ambiguous"
    Unmatched = "unmatched"


class Relation(enum.Enum):
    Parent = "parent"
    Partner = "partner"
    Child = "child"
    Sibling = "sibling"


@dataclass
class PersonMatch:
    status: Status
    other: int | None = None
    candidates: list[int] = field(default_factory=list)


@dataclass
class FamilyMatch:
    people: dict[int, PersonMatch]
    unpaired: list[int]
    pair_bonds: dict[int, int]
    events: dict[int, int]

    @property
    def ids(self) -> dict[int, int]:
        return {k: v.other for k, v in self.people.items() if v.other is not None}


def _groups() -> dict[str, frozenset[int]]:
    out = defaultdict(set)
    for i, names in enumerate(NICKNAMES):
        for name in names:
            out[name].add(i)
    return {k: frozenset(v) for k, v in out.items()}


GROUPS = _groups()


def tokens(text: str | None) -> list[str]:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z ]", " ", text.replace("'", "").replace("’", "")).split()


def spelling(word: str) -> str:
    word = word.replace("ph", "f")
    word = re.sub(r"(ie|ey|y|i)$", "I", word[0] + word[1:].replace("h", ""))
    word = word.replace("y", "i").replace("c", "k")
    word = word[:-1] if len(word) > 3 and word.endswith("e") else word
    return re.sub(r"(.)\1+", r"\1", word)


@cache
def token_score(s: str, t: str) -> float:
    if s == t:
        return 1.0
    if GROUPS.get(s, frozenset()) & GROUPS.get(t, frozenset()):
        return 0.9
    if spelling(s) == spelling(t):
        return 0.85
    if min(len(s), len(t)) >= 3 and (s.startswith(t) or t.startswith(s)):
        return 0.8
    if (len(s) == 1 or len(t) == 1) and s[0] == t[0]:
        return 0.75
    return 0.0


def year(value) -> int | None:
    found = YEAR.search(str(value)) if value else None
    return int(found.group(1)) if found else None


@dataclass(frozen=True)
class Kin:
    id: int
    first: str
    firsts: frozenset[str]
    lasts: frozenset[str]
    gender: PersonKind | None
    born: int | None
    primary: bool

    @property
    def unnamed(self) -> bool:
        return not self.first


def kin(person: dict, born: int | None) -> Kin:
    name = person.get("name") or ""
    own = tokens(name)
    if PLACEHOLDER.search(name) or set(own) <= ROLES:
        own = []
    given = own + tokens(person.get("nickName")) + tokens(person.get("middleName"))
    firsts = set(given) | ({"".join(own)} if len(own) > 1 else set())
    last = person.get("last_name") or person.get("lastName")
    gender = person.get("gender")
    return Kin(
        id=person["id"],
        first=given[0] if given else "",
        firsts=frozenset(firsts),
        lasts=frozenset(tokens(last) + tokens(person.get("birthName"))),
        gender=PersonKind(gender) if gender else None,
        born=born or year(person.get("birthDateTime")),
        primary=bool(person.get("primary")),
    )


class Family:
    def __init__(self, diagram: dict):
        ids = {p["id"] for p in diagram["people"]}
        bonds = {
            b["id"]: {b["person_a"], b["person_b"]} & ids for b in diagram["pair_bonds"]
        }
        self.parents = defaultdict(set)
        self.partners = defaultdict(set)
        self.bond_years = defaultdict(set)
        born = {}
        for p in diagram["people"]:
            self.parents[p["id"]] |= bonds.get(p.get("parents"), set())
        for pair in bonds.values():
            self._couple(pair)
        for e in diagram["events"]:
            kind = EventKind(e["kind"])
            pair = {e.get("person"), e.get("spouse")} & ids
            if kind.isOffspring() and e.get("child") in ids:
                self.parents[e["child"]] |= pair
                born.setdefault(e["child"], year(e.get("dateTime")))
            if kind.isPairBond():
                self._couple(pair)
            if (
                kind in (EventKind.Married, EventKind.Bonded)
                and len(pair) == 2
                and year(e.get("dateTime"))
            ):
                self.bond_years[frozenset(pair)].add(year(e.get("dateTime")))
        self.children = defaultdict(set)
        for child, parents in self.parents.items():
            parents.discard(child)
            for parent in parents:
                self.children[parent].add(child)
        self.people = {p["id"]: kin(p, born.get(p["id"])) for p in diagram["people"]}
        self.bonds = bonds
        self.events = {e["id"]: e for e in diagram["events"]}

    def _couple(self, pair: set):
        if len(pair) == 2:
            a, b = pair
            self.partners[a].add(b)
            self.partners[b].add(a)

    def related(self, pid: int, relation: Relation) -> set[int]:
        if relation is Relation.Parent:
            return self.parents[pid]
        if relation is Relation.Partner:
            return self.partners[pid]
        if relation is Relation.Child:
            return self.children[pid]
        return {s for p in self.parents[pid] for s in self.children[p]} - {pid}

    def shared(self, a: int, b: int) -> set[int]:
        return self.children[a] & self.children[b]


def first_score(a: Kin, b: Kin) -> float:
    return max((token_score(s, t) for s in a.firsts for t in b.firsts), default=0.0)


def lasts_agree(a: Kin, b: Kin) -> bool:
    return any(token_score(s, t) >= 0.85 for s in a.lasts for t in b.lasts)


def conflict(a: Kin, b: Kin) -> bool:
    sexes = (PersonKind.Male, PersonKind.Female)
    if a.gender in sexes and b.gender in sexes and a.gender != b.gender:
        return True
    return bool(a.born and b.born and abs(a.born - b.born) > 2)


class Matcher:
    def __init__(self, a: dict, b: dict):
        self.a, self.b = Family(a), Family(b)
        self.ab: dict[int, int] = {}
        self.ba: dict[int, int] = {}
        self.position: set[int] = set()
        self.doubt_a = defaultdict(set)
        self.doubt_b = defaultdict(set)

    def named(self, x: int, y: int) -> bool:
        ka, kb = self.a.people[x], self.b.people[y]
        return not ka.unnamed and not kb.unnamed and first_score(ka, kb) >= THRESHOLD

    def agree(self, x: int, y: int) -> bool:
        return self.ab.get(x) == y or self.named(x, y)

    def link(self, x: int, y: int, position: bool):
        self.ab[x], self.ba[y] = y, x
        if position:
            self.position.add(x)

    def kin_bonus(self, x: int, y: int) -> float:
        hits = sum(
            1
            for r in (Relation.Child, Relation.Partner)
            for c in self.a.related(x, r)
            for d in self.b.related(y, r)
            if self.agree(c, d)
        )
        return 0.1 * min(hits, 2)

    def weight(
        self, x: int, y: int, relation: Relation, p: int, q: int
    ) -> float | None:
        ka, kb = self.a.people[x], self.b.people[y]
        if conflict(ka, kb):
            return None
        if ka.unnamed or kb.unnamed:
            base = POSITION
            if relation is Relation.Partner and not any(
                self.ab.get(c) in self.b.shared(q, y) for c in self.a.shared(p, x)
            ):
                return None
        else:
            base = first_score(ka, kb)
            if base < THRESHOLD:
                return None
        w = base + self.kin_bonus(x, y)
        if ka.lasts and kb.lasts:
            w += 0.15 if lasts_agree(ka, kb) else -0.1
        if ka.born and kb.born and abs(ka.born - kb.born) <= 1:
            w += 0.2
        if relation is Relation.Partner:
            ya, yb = (
                self.a.bond_years[frozenset((p, x))],
                self.b.bond_years[frozenset((q, y))],
            )
            if ya and yb:
                w += 0.2 if any(abs(s - t) <= 1 for s in ya for t in yb) else -0.3
        return w

    def assign(self, edges: dict[tuple[int, int], float]) -> int:
        added = 0
        for xs, ys in components(edges):
            total = best(xs, ys, edges)
            ca = {
                x: {y for y in ys if forced(x, y, xs, ys, edges) >= total - EPSILON}
                for x in xs
            }
            cb = {y: {x for x in xs if y in ca[x]} for y in ys}
            for x in xs:
                y = next(iter(ca[x]), None)
                loose = best(xs - {x}, ys, edges) >= total - EPSILON
                if len(ca[x]) == 1 and cb[y] == {x} and not loose:
                    pos = self.a.people[x].unnamed or self.b.people[y].unnamed
                    self.link(x, y, pos)
                    added += 1
                elif ca[x]:
                    self.doubt_a[x] |= ca[x]
                    for y in ca[x]:
                        self.doubt_b[y].add(x)
        return added

    def walk(self):
        while True:
            added = 0
            for p in sorted(self.ab):
                q = self.ab[p]
                for r in Relation:
                    edges = {}
                    for x in self.a.related(p, r) - self.ab.keys():
                        for y in self.b.related(q, r) - self.ba.keys():
                            w = self.weight(x, y, r, p, q)
                            if w is not None:
                                edges[x, y] = w
                    added += self.assign(edges)
            if not added:
                return

    def full_name(self, k: Kin, side: Family) -> list[Kin]:
        return [
            o
            for o in side.people.values()
            if not o.unnamed
            and o.first == k.first
            and lasts_agree(o, k)
            and not conflict(o, k)
        ]

    def unique_pairs(self) -> list[tuple[int, int]]:
        pairs = []
        for ka in self.a.people.values():
            if ka.unnamed or not ka.lasts:
                continue
            hits = self.full_name(ka, self.b)
            if len(hits) == 1 and len(self.full_name(hits[0], self.a)) == 1:
                pairs.append((ka.id, hits[0].id))
        return pairs

    def parents_agree(self, x: int, y: int) -> bool:
        pa = [p for p in self.a.parents[x] if not self.a.people[p].unnamed]
        pb = [p for p in self.b.parents[y] if not self.b.people[p].unnamed]
        return (
            bool(pa and pb)
            and all(any(self.named(s, t) for t in pb) for s in pa)
            and all(any(self.named(s, t) for s in pa) for t in pb)
        )

    def evidence(self, x: int, y: int) -> bool:
        ka, kb = self.a.people[x], self.b.people[y]
        if ka.born and kb.born and abs(ka.born - kb.born) <= 1:
            return True
        return any(
            self.agree(s, t)
            for r in Relation
            for s in self.a.related(x, r)
            for t in self.b.related(y, r)
        )

    def anchors(self) -> list[tuple[int, int]]:
        found = [(x, y) for x, y in self.unique_pairs() if self.parents_agree(x, y)]
        pa = [k for k in self.a.people.values() if k.primary]
        pb = [k for k in self.b.people.values() if k.primary]
        if len(pa) == 1 and len(pb) == 1 and not conflict(pa[0], pb[0]):
            if pa[0].unnamed or pb[0].unnamed or first_score(pa[0], pb[0]) >= THRESHOLD:
                found.append((pa[0].id, pb[0].id))
        return found

    def run(self):
        for x, y in self.anchors():
            if x not in self.ab and y not in self.ba:
                self.link(x, y, False)
        self.walk()
        while True:
            fresh = [
                (x, y)
                for x, y in self.unique_pairs()
                if x not in self.ab and y not in self.ba and self.evidence(x, y)
            ]
            for x, y in fresh:
                self.link(x, y, False)
            if not fresh:
                return
            self.walk()

    def hints(self) -> dict[int, set[int]]:
        out = defaultdict(set)
        for p, q in self.ab.items():
            for r in Relation:
                for x in self.a.related(p, r) - self.ab.keys():
                    for y in self.b.related(q, r) - self.ba.keys():
                        if not conflict(self.a.people[x], self.b.people[y]):
                            out[x].add(y)
        return out

    def result(self) -> FamilyMatch:
        hints = self.hints()
        people = {}
        for x in self.a.people:
            if x in self.ab:
                status = Status.Position if x in self.position else Status.Name
                people[x] = PersonMatch(status, self.ab[x])
                continue
            doubt = sorted(self.doubt_a[x] - self.ba.keys())
            if doubt:
                people[x] = PersonMatch(Status.Ambiguous, candidates=doubt)
            else:
                people[x] = PersonMatch(Status.Unmatched, candidates=sorted(hints[x]))
        return FamilyMatch(
            people=people,
            unpaired=sorted(self.b.people.keys() - self.ba.keys()),
            pair_bonds=self.bond_map(),
            events=self.event_map(),
        )

    def bond_map(self) -> dict[int, int]:
        by_pair = defaultdict(list)
        for bid, pair in sorted(self.b.bonds.items()):
            by_pair[frozenset(pair)].append(bid)
        mine = defaultdict(list)
        for bid, pair in sorted(self.a.bonds.items()):
            if len(pair) == 2 and pair <= self.ab.keys():
                mine[frozenset(self.ab[p] for p in pair)].append(bid)
        return {s: t for key, ids in mine.items() for s, t in zip(ids, by_pair[key])}

    def event_map(self) -> dict[int, int]:
        theirs = defaultdict(list)
        for e in self.b.events.values():
            theirs[event_key(e, lambda pid: pid)].append(e)
        mine = defaultdict(list)
        for e in self.a.events.values():
            links = [
                e.get(k) for k in ("person", "spouse", "child") if e.get(k) is not None
            ]
            if all(pid in self.ab for pid in links):
                mine[event_key(e, self.ab.get)].append(e)
        out = {}
        for key, es in mine.items():
            fit = {
                e["id"]: [f["id"] for f in theirs[key] if dates_fit(e, f)] for e in es
            }
            back = defaultdict(list)
            for s, ts in fit.items():
                for t in ts:
                    back[t].append(s)
            out |= {
                s: ts[0]
                for s, ts in fit.items()
                if len(ts) == 1 and len(back[ts[0]]) == 1
            }
        return out


def event_key(e: dict, remap) -> tuple:
    kind = EventKind(e["kind"])
    pair = frozenset(remap(e[k]) for k in ("person", "spouse") if e.get(k) is not None)
    child = remap(e["child"]) if e.get("child") is not None else None
    return kind, pair, child


def dates_fit(e: dict, f: dict) -> bool:
    if EventKind(e["kind"]).isStructural():
        ye, yf = year(e.get("dateTime")), year(f.get("dateTime"))
        return not (ye and yf) or abs(ye - yf) <= 1
    return bool(
        e.get("dateTime") and str(e["dateTime"])[:10] == str(f.get("dateTime"))[:10]
    )


def components(edges: dict) -> list[tuple[frozenset, frozenset]]:
    left, right = defaultdict(set), defaultdict(set)
    for x, y in edges:
        left[x].add(y)
        right[y].add(x)
    seen, out = set(), []
    for start in sorted(left):
        if start in seen:
            continue
        xs, ys, todo = set(), set(), [start]
        while todo:
            x = todo.pop()
            if x in xs:
                continue
            xs.add(x)
            for y in left[x] - ys:
                ys.add(y)
                todo += right[y]
        seen |= xs
        out.append((frozenset(xs), frozenset(ys)))
    return out


def best(xs: frozenset, ys: frozenset, edges: dict) -> float:
    order = sorted(xs)

    @cache
    def go(i: int, used: frozenset) -> float:
        if i == len(order):
            return 0.0
        x = order[i]
        top = go(i + 1, used)
        for y in ys - used:
            if (x, y) in edges:
                top = max(top, edges[x, y] + go(i + 1, used | {y}))
        return top

    return go(0, frozenset())


def forced(x: int, y: int, xs: frozenset, ys: frozenset, edges: dict) -> float:
    if (x, y) not in edges:
        return float("-inf")
    return edges[x, y] + best(xs - {x}, ys - {y}, edges)


def canonical(diagram: dict) -> str:
    keys = ("people", "pair_bonds", "events")
    return json.dumps({k: diagram[k] for k in keys}, sort_keys=True, default=str)


def invert(m: FamilyMatch) -> FamilyMatch:
    people = {y: PersonMatch(Status.Unmatched) for y in m.unpaired}
    for x, pm in m.people.items():
        if pm.other is not None:
            people[pm.other] = PersonMatch(pm.status, x)
    for status in (Status.Ambiguous, Status.Unmatched):
        for x, pm in sorted(m.people.items()):
            if pm.status is not status:
                continue
            for y in pm.candidates:
                if (
                    people[y].status in (status, Status.Unmatched)
                    and people[y].other is None
                ):
                    people[y].status = status
                    people[y].candidates.append(x)
    return FamilyMatch(
        people=dict(sorted(people.items())),
        unpaired=sorted(x for x, pm in m.people.items() if pm.other is None),
        pair_bonds={t: s for s, t in m.pair_bonds.items()},
        events={t: s for s, t in m.events.items()},
    )


def match(a: dict, b: dict) -> FamilyMatch:
    if canonical(a) > canonical(b):
        return invert(match(b, a))
    matcher = Matcher(a, b)
    matcher.run()
    return matcher.result()
