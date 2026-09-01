"""Build a DiagramData from privacy-scrubbed lane JSON documents (the
chat/journal extraction format: entries[] with fraction-year dates and
certainty grades, structure[] with kinship/couple facts).

Certainty mapping: day/month -> Certain, year/decade-guess -> Approximate,
unknown -> undated (DateCertainty.Unknown, no axis position).
"""

import datetime

from btcopilot.schema import (
    DateCertainty,
    DiagramData,
    Event,
    EventKind,
    PairBond,
    Person,
    RelationshipKind,
    VariableShift,
    asdict,
)

ASSISTANT_ID = 2

CERTAINTY = {
    "day": DateCertainty.Certain,
    "month": DateCertainty.Certain,
    "year": DateCertainty.Approximate,
    "decade-guess": DateCertainty.Approximate,
    "unknown": DateCertainty.Unknown,
}

VARIABLES = ("symptom", "anxiety", "functioning")

RELATIONSHIP_KEYWORDS = (
    ("cut off", RelationshipKind.Cutoff),
    ("cutoff", RelationshipKind.Cutoff),
    ("arguing", RelationshipKind.Conflict),
    ("conflict", RelationshipKind.Conflict),
    ("blowup", RelationshipKind.Conflict),
    ("spat", RelationshipKind.Conflict),
    ("without contact", RelationshipKind.Distance),
    ("distance", RelationshipKind.Distance),
)


def _canon(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(name, name)


def _date(t: float | None) -> str | None:
    if t is None:
        return None
    year = int(t)
    day = min(364, max(0, round((t - year) * 365)))
    return (datetime.date(year, 1, 1) + datetime.timedelta(days=day)).isoformat()


def _structure_certainty(t: float | None) -> DateCertainty:
    """Structure facts carry no certainty grade; a second decimal digit in
    the fraction-year (x.21, x.51, x.98) marks a month/day anchor, a plain
    .0/.5/.x0 marks a year-grade guess."""
    if t is None:
        return DateCertainty.Approximate
    return (
        DateCertainty.Certain
        if round(t * 100) % 10 != 0
        else DateCertainty.Approximate
    )


def _relationship_kind(desc: str, direction: str | None) -> RelationshipKind | None:
    lowered = desc.lower()
    for keyword, kind in RELATIONSHIP_KEYWORDS:
        if keyword in lowered:
            return kind
    if direction == "up":
        return RelationshipKind.Toward
    if direction == "down":
        return RelationshipKind.Distance
    return None


class _Builder:
    def __init__(self, primary: str, aliases: dict[str, str]):
        self.primary = primary
        self.aliases = aliases
        self.people: dict[str, int] = {}
        self.bonds: dict[tuple[int, int], int] = {}
        self.events: list[Event] = []
        self.next_id = ASSISTANT_ID + 1

    def person(self, name: str) -> int:
        name = _canon(name, self.aliases)
        if name == self.primary:
            return 1
        if name not in self.people:
            self.people[name] = self.next_id
            self.next_id += 1
        return self.people[name]

    def bond(self, a: str, b: str) -> int:
        key = tuple(sorted((self.person(a), self.person(b))))
        if key not in self.bonds:
            self.bonds[key] = self.next_id
            self.next_id += 1
        return self.bonds[key]

    def event(self, **kwargs) -> Event:
        event = Event(id=self.next_id, **kwargs)
        self.next_id += 1
        self.events.append(event)
        return event


def _load_structure(builder: _Builder, facts: list[dict]):
    """Deterministic keyword dispatch over the scrubbed fact strings. Facts
    that name no event (pure kinship) still register their people."""
    for fact in facts:
        text = fact["fact"]
        people = [_canon(p, builder.aliases) for p in fact["people"]]
        t = fact.get("t")
        for name in people:
            builder.person(name)
        date = _date(t)
        certainty = _structure_certainty(t)

        if " born" in text:
            child = people[0]
            kwargs = {}
            if "to father, stepmother" in text:
                kwargs = {
                    "person": builder.person(people[1]),
                    "spouse": builder.person(people[2]),
                }
            if date:
                builder.event(
                    kind=EventKind.Birth,
                    child=builder.person(child),
                    dateTime=date,
                    dateCertainty=certainty,
                    **kwargs,
                )
        elif "never divorced" in text:
            builder.bond(people[0], people[1])
        elif "divorced" in text or "divorce final" in text:
            bond_pair = (people[0], people[1])
            builder.bond(*bond_pair)
            if date:
                builder.event(
                    kind=EventKind.Divorced,
                    person=builder.person(bond_pair[0]),
                    spouse=builder.person(bond_pair[1]),
                    dateTime=date,
                    dateCertainty=certainty,
                )
        elif "separated" in text:
            builder.bond(people[0], people[1])
            if date:
                builder.event(
                    kind=EventKind.Separated,
                    person=builder.person(people[0]),
                    spouse=builder.person(people[1]),
                    dateTime=date,
                    dateCertainty=certainty,
                )
        elif "married" in text:
            builder.bond(people[0], people[1])
            if date:
                builder.event(
                    kind=EventKind.Married,
                    person=builder.person(people[0]),
                    spouse=builder.person(people[1]),
                    dateTime=date,
                    dateCertainty=certainty,
                )
        elif "partnered" in text:
            builder.bond(people[0], people[1])
            if date:
                builder.event(
                    kind=EventKind.Bonded,
                    person=builder.person(people[0]),
                    spouse=builder.person(people[1]),
                    dateTime=date,
                    dateCertainty=certainty,
                )
        elif "died" in text:
            if date:
                builder.event(
                    kind=EventKind.Death,
                    person=builder.person(people[0]),
                    dateTime=date,
                    dateCertainty=certainty,
                )
        # remaining facts are pure kinship: people already registered


def _structural_dup(builder: _Builder, person_id: int, date: str | None, desc: str) -> bool:
    """A death or wedding told in an entry usually duplicates a structure
    fact; the structural event wins."""
    lowered = desc.lower()
    if "death" not in lowered and "wedding" not in lowered:
        return False
    if date is None:
        return False
    year = int(date[:4])
    for event in builder.events:
        if event.kind not in (EventKind.Death, EventKind.Married, EventKind.Bonded):
            continue
        involved = {event.person, event.spouse, event.child} - {None}
        if person_id not in involved:
            continue
        if event.dateTime and abs(int(event.dateTime[:4]) - year) <= 1:
            return True
    return False


def _load_entries(builder: _Builder, entries: list[dict], rel_up_is_worse: bool):
    for entry in entries:
        who = builder.person(entry["who"])
        date = _date(entry.get("t"))
        end = _date(entry.get("t_end"))
        certainty = CERTAINTY[entry.get("certainty") or "unknown"]
        if certainty == DateCertainty.Unknown:
            date, end = None, None
        desc = entry.get("desc") or ""
        if _structural_dup(builder, who, date, desc):
            continue
        variable = entry.get("variable")
        direction = entry.get("direction")

        kwargs = {}
        if variable in VARIABLES:
            if direction in ("up", "down"):
                kwargs[variable] = VariableShift(direction)
            elif "unchanged" in desc.lower():
                kwargs[variable] = VariableShift.Same
        elif variable == "relationship":
            if rel_up_is_worse and direction in ("up", "down"):
                direction = "down" if direction == "up" else "up"
            kind = _relationship_kind(desc, direction)
            if kind is not None:
                kwargs["relationship"] = kind
                known = dict(builder.people, **{builder.primary: 1})
                canon = [_canon(o, builder.aliases) for o in entry.get("others", [])]
                targets = [known[o] for o in canon if o in known]
                kwargs["relationshipTargets"] = [t for t in targets if t != who]

        builder.event(
            kind=EventKind.Shift,
            person=who,
            description=desc,
            dateTime=date,
            endDateTime=end,
            dateCertainty=certainty,
            **kwargs,
        )


def _primary_name(docs: list[dict], aliases: dict[str, str]) -> str:
    """The diagram owner, named by the structure facts ("owner born",
    "... of owner"), never hardcoded."""
    for doc in docs:
        for fact in doc.get("structure", []):
            if fact["fact"].strip() == "owner born":
                return _canon(fact["people"][0], aliases)
    for doc in docs:
        for fact in doc.get("structure", []):
            if fact["fact"].strip().endswith("of owner"):
                return _canon(fact["people"][-1], aliases)
    raise ValueError("No owner-naming structure fact in any lane doc")


def lanes_diagram_data(
    docs: list[dict], aliases: dict[str, str] | None = None
) -> DiagramData:
    """aliases merges alternate spellings of one person across docs
    ({"name as written": "canonical name"}); pass at seed time, never
    embed identities in code."""
    aliases = aliases or {}
    builder = _Builder(_primary_name(docs, aliases), aliases)
    for doc in docs:
        _load_structure(builder, doc.get("structure", []))
    for doc in docs:
        # Some scrubbed docs declare inverted relationship polarity (journal
        # convention: relationship up = more/worse); normalize to up = closer.
        rel_up_is_worse = "relationship up = more" in (doc.get("notes") or "")
        _load_entries(builder, doc.get("entries", []), rel_up_is_worse)

    people = [dict(asdict(Person(id=1, name=builder.primary)), primary=True)]
    people.append(asdict(Person(id=ASSISTANT_ID, name="Assistant")))
    for name, id in sorted(builder.people.items(), key=lambda kv: kv[1]):
        people.append(asdict(Person(id=id, name=name)))

    pair_bonds = [
        asdict(PairBond(id=bond_id, person_a=a, person_b=b, married=True))
        for (a, b), bond_id in sorted(builder.bonds.items(), key=lambda kv: kv[1])
    ]
    return DiagramData(
        people=people,
        events=[asdict(e) for e in builder.events],
        pair_bonds=pair_bonds,
        lastItemId=builder.next_id,
    )
