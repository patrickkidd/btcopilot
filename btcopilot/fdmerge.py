"""A desktop file brought into a diagram that already has people, in three
passes [Oracle: R-0851]. The rules first: whom the family matcher pairs by
name and family is one person, and whom it pairs with nobody is added. Then
the cheap side-call model, once per nuclear family of the file, on whom the
rules placed by position only or not at all, and on a matched person's events
of one kind on one day, judged by their words. Whoever it is unsure of becomes
a held question for the coach, asked in small doses [Oracle: R-0852]: both
people stay until the person answers, and the coach's merge joins them.

The file's items take ids past the diagram's [Oracle: R-0850]. Every choice
is a Decision naming the file's item by its id in the imported diagram."""

import collections
import copy
import datetime
import enum
import itertools
import re
from dataclasses import dataclass, field

# fdimport merges with this module and this module renumbers with fdimport;
# neither uses the other at import time.
from btcopilot import (
    coverage,
    diagramjson,
    fdcoding,
    fdimport,
    profile,
    prompts,
    record,
)
from btcopilot.familymatch import (
    PLACEHOLDER,
    Family,
    Relation,
    Status,
    match,
    tokens,
    unnamed,
)
from btcopilot.fdcoding import ask, heard, numbered
from btcopilot.fdledger import Decision
from btcopilot.llmutil import dataclass_to_json_schema
from btcopilot.schema import (
    DateCertainty,
    DiagramData,
    EventKind,
    ItemKind,
    PersonKind,
    QuestionKind,
    QuestionState,
    from_dict,
)

PROMPT = "import_merge"
ROOM = 2048
PER_ANSWER = 256
COLLECTIONS = ("people", "pair_bonds", "events")
LINKS = ("person", "spouse", "child")
MOVES = ("relationshipTargets", "relationshipTriangles")
EMPTY = (None, "", [], {})
# What a joined person takes from the file only where the diagram has nothing;
# the record's own merge brings over the rest.
MERGED = {"id", "parents", "name", "last_name", "gender", "notes"}
OFFSPRING = {kind.value for kind in EventKind if kind.isOffspring()}
FILE = "file"
DIAGRAM = "diagram"
JOINED = "The same kind of event for the same people within a year in both."
TWIN = "The same kind, day, people and what moved: the app counts it as one event."
OVER_DIAGRAM = (
    "Only the file had it.",
    "The diagram already said otherwise; its value is kept.",
)
OVER_FILE = (
    "Only this telling in the file had it.",
    "The file's earlier telling said otherwise; its value is kept.",
)
SAME_DAY = "the diagram's event of the same kind on the same day"
NEAR = "an event of the diagram about the same person within two years, of any kind"
REPEAT = "an event of the file about the same person within two years"
# Two years either way, in years.
SPAN = 2
# The most event pairs one call judges when the events go apart from people.
PER_CALL = 30
# What a person's line shows of their notes, events and the person's words.
NOTES = 300
TITLES = 10
SAID = 3
SENTENCE = 200
SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")
CHILD_WORDS = {PersonKind.Female: "daughter", PersonKind.Male: "son"}


class Pairing(enum.StrEnum):
    """Which of a joined person's events the model judges against the
    diagram's: one kind on one day, or any kind within two years."""

    SameDay = "same day"
    TwoYears = "two years"


class Shown(enum.StrEnum):
    """What the model is shown of each person: names, dates and relatives,
    or also their notes, events, grandparents, why the rules were unsure, and
    what the person said of them in conversation."""

    Names = "names"
    More = "more"


class Verdict(enum.StrEnum):
    Same = "same"
    Different = "different"
    Unsure = "unsure"


VERDICTS = {v.value for v in Verdict}


class Placed(enum.StrEnum):
    """How a file's person or event found its place in the diagram."""

    Rules = "rules"
    Model = "model"
    Asked = "asked"


@dataclass
class PersonVerdict:
    person: str = ""
    candidate: str = ""
    verdict: str = ""
    reason: str = ""


@dataclass
class EventVerdict:
    event: str = ""
    other: str = ""
    verdict: str = ""
    reason: str = ""


@dataclass
class Answer:
    people: list[PersonVerdict] = field(default_factory=list)
    events: list[EventVerdict] = field(default_factory=list)


@dataclass
class Call:
    """One nuclear family of the file: whom to judge against whom, and which
    events against which."""

    people: dict[int, list[int]] = field(default_factory=dict)
    events: list[tuple[int, int]] = field(default_factory=list)
    against: str = SAME_DAY


def _label(side: str, pid: int) -> str:
    return f"{side} {pid}"


def _event_label(side: str, eid: int) -> str:
    return f"{side} event {eid}"


def _name(person: dict) -> str:
    return (
        " ".join(filter(None, (person.get("name"), person.get("last_name"))))
        or "no name"
    )


def _owner(event: dict):
    return event.get("child") if event["kind"] in OFFSPRING else event.get("person")


def _linked(event: dict) -> set:
    return {event.get(key) for key in LINKS} - {None}


def _day(event: dict) -> str | None:
    return record.day(event.get("dateTime"))


def _when(event: dict, on: str = "") -> str:
    """The date as the model is shown it: the year said as about when the date
    is approximate or only a year, so a guessed day is never read as known."""
    day = _day(event)
    if len(day) == 4 or event.get("dateCertainty") == DateCertainty.Approximate:
        return f"about {day[:4]}"
    return on + day


def _years(event: dict) -> float:
    day = _day(event)
    if len(day) == 4:
        return int(day)
    date = datetime.date.fromisoformat(day)
    return date.year + (date.timetuple().tm_yday - 1) / 366


def _near(a: dict, b: dict) -> bool:
    return abs(_years(a) - _years(b)) <= SPAN


def _words(event: dict) -> set[str]:
    text = " ".join(event.get(k) or "" for k in ("title", "description"))
    return {w for w in tokens(text) if len(w) > 3}


def _alike(a: dict, b: dict) -> bool:
    """Two tellings of one happening by their look: two words or more, and
    half their words, the same."""
    wa, wb = _words(a), _words(b)
    return len(wa & wb) >= 2 and len(wa & wb) * 2 >= len(wa | wb)


def _short(text: str, size: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= size else text[: size - 1].rstrip() + "…"


def _by_first(pairs: list[tuple[int, int]]) -> dict[int, list[int]]:
    out = collections.defaultdict(list)
    for e, f in pairs:
        out[e].append(f)
    return out


def _mapped(event: dict, same: dict[int, int]) -> dict:
    out = dict(event)
    for key in LINKS:
        if event.get(key) is not None:
            out[key] = same.get(event[key], event[key])
    for key in MOVES:
        if event.get(key):
            out[key] = [same.get(x, x) for x in event[key]]
    return out


def _schema(call: Call, label) -> dict:
    schema = dataclass_to_json_schema(Answer)
    people = schema["properties"]["people"]["items"]
    people["properties"]["person"]["enum"] = [_label(FILE, y) for y in call.people]
    people["properties"]["candidate"]["enum"] = list(
        dict.fromkeys(_label(DIAGRAM, x) for xs in call.people.values() for x in xs)
    )
    people["properties"]["verdict"]["enum"] = [v.value for v in Verdict]
    people["required"] = ["person", "candidate", "verdict", "reason"]
    events = schema["properties"]["events"]["items"]
    events["properties"]["event"]["enum"] = list(
        dict.fromkeys(label(e) for e, _ in call.events)
    )
    events["properties"]["other"]["enum"] = list(
        dict.fromkeys(label(f) for _, f in call.events)
    )
    events["properties"]["verdict"]["enum"] = [Verdict.Same, Verdict.Different]
    events["required"] = ["event", "other", "verdict", "reason"]
    if not call.people:
        del schema["properties"]["people"]
    if not call.events:
        del schema["properties"]["events"]
    return schema


def _renumbered(existing: dict, imported: dict) -> tuple[dict, dict[int, int]]:
    """The file's items under ids past every id the diagram holds, each
    reference following."""
    data = copy.deepcopy(imported)
    return data, fdimport.renumber(data, record.next_id(numbered(existing)))


class Merge:
    def __init__(
        self,
        existing: dict,
        imported: dict,
        model,
        pairing: Pairing = Pairing.SameDay,
        shown: Shown = Shown.Names,
        statements: list[str] = (),
    ):
        """`statements` are the person's own words to the coach, shown with
        `Shown.More` beside the people of the diagram they name."""
        self.existing = existing
        self.pairing, self.shown = pairing, shown
        self.sentences = [
            _short(one, SENTENCE)
            for text in statements
            for one in SENTENCES.split(text or "")
            if one.strip()
        ]
        self.view = from_dict(DiagramData, existing)
        own = profile.own(self.view)
        self.main = own["id"] if own else None
        self.ours_events = {e["id"] for e in existing["events"]}
        self.file, new = _renumbered(existing, imported)
        self.old = {n: o for o, n in new.items()}
        # Each item of the file joined to another, to the one it joined.
        self.joined: dict[int, int] = {}
        self.model = model
        self.data = copy.deepcopy(existing)
        for name in COLLECTIONS:
            self.data[name] = [*self.data.get(name, []), *self.file[name]]
        tags = [*(existing.get("tags") or []), *(imported.get("tags") or [])]
        if tags:
            self.data["tags"] = list(dict.fromkeys(tags))
        self.people = {p["id"]: p for p in self.data["people"]}
        self.events = {e["id"]: e for e in self.data["events"]}
        self.ours = {p["id"] for p in existing["people"]}
        self.family = Family(self.data)
        self.found = match(self.file, existing)
        # The matcher's pairs of births, deaths and couple events, one event by
        # kind, people and year; any other two are judged by their words.
        self.structural = {
            e: f
            for e, f in self.found.events.items()
            if EventKind(self.events[e]["kind"]).isStructural()
        }
        self.decisions: list[Decision] = []

    def decide(self, kind: str, item: int, name: str, before, after, reason: str):
        self.decisions.append(
            Decision(
                f"{kind} {self.old[item]}",
                name,
                "" if before is None else str(before),
                "" if after is None else str(after),
                reason,
            )
        )

    # Pass 1 and what pass 2 is asked

    def same(self) -> dict[int, int]:
        return {
            y: pm.other
            for y, pm in self.found.people.items()
            if pm.status is Status.Name
        }

    def doubted(self) -> dict[int, list[int]]:
        return {
            y: [pm.other] if pm.status is Status.Position else pm.candidates
            for y, pm in self.found.people.items()
            if pm.status is not Status.Name and (pm.other or pm.candidates)
        }

    def pairs(self, same: dict[int, int]) -> list[tuple[int, int]]:
        """A matched person's events and the diagram's of the same kind on the
        same day that the rules do not already count as one."""
        mine = collections.defaultdict(list)
        for event in self.existing["events"]:
            if _day(event):
                mine[event["kind"], _owner(event), _day(event)].append(event)
        out = []
        for event in self.file["events"]:
            owner = _owner(event)
            if (
                owner not in same
                or event["id"] in self.structural
                or event["id"] not in self.events
                or not _day(event)
            ):
                continue
            twin = record.twin_key(_mapped(event, same))
            out += [
                (event["id"], other["id"])
                for other in mine[event["kind"], same[owner], _day(event)]
                if record.twin_key(other) != twin
            ]
        return out

    # Pass 2

    def household(self, pid: int) -> list[int]:
        """The couple and children a person is a child of, or else the first
        couple they are in, or else them alone."""
        bond = self.people[pid].get("parents")
        if bond is None:
            bond = next(
                (
                    b["id"]
                    for b in self.data["pair_bonds"]
                    if pid in (b["person_a"], b["person_b"])
                ),
                None,
            )
        if bond is None:
            return [pid]
        couple = next(b for b in self.data["pair_bonds"] if b["id"] == bond)
        children = [p["id"] for p in self.data["people"] if p.get("parents") == bond]
        return [couple["person_a"], couple["person_b"], *children]

    def repeats(self) -> list[tuple[int, int]]:
        """Two events of the file about one person within two years that look
        like one happening told twice, the later against the earlier; the
        model judges them before anything is matched to the diagram."""
        mine = collections.defaultdict(list)
        for event in self.file["events"]:
            if _day(event) and _owner(event) is not None:
                mine[_owner(event)].append(event)
        return [
            (b["id"], a["id"])
            for events in mine.values()
            for a, b in itertools.combinations(events, 2)
            if _near(a, b) and _alike(a, b) and record.twin_key(a) != record.twin_key(b)
        ]

    def near(self) -> list[tuple[int, int]]:
        """Once people are joined, each event the file brought to a person of
        the diagram against each of the diagram's own about them within two
        years, of any kind, that the rules do not already count as one."""
        paired = set(self.structural.values())
        mine = collections.defaultdict(list)
        for event in self.data["events"]:
            eid = event["id"]
            owner = _owner(event)
            if eid in self.ours_events and eid not in paired and owner is not None:
                if _day(event):
                    mine[owner].append(event)
        return [
            (event["id"], other["id"])
            for event in self.data["events"]
            if event["id"] in self.old
            and event["id"] not in self.structural
            and _day(event)
            for other in mine[_owner(event)]
            if _near(event, other) and record.twin_key(event) != record.twin_key(other)
        ]

    def grouped(
        self, doubted, pairs, against: str = SAME_DAY, size: int | None = None
    ) -> list[Call]:
        """One call per family; with `size`, events apart in calls of at most
        that many pairs."""
        calls = collections.defaultdict(list)
        for y, candidates in doubted.items():
            key = tuple(self.household(y))
            calls[key] = calls[key] or [Call(against=against)]
            calls[key][0].people[y] = candidates
        for e, f in pairs:
            key = tuple(self.household(_owner(self.events[e])))
            calls[key] = calls[key] or [Call(against=against)]
            if size and len(calls[key][-1].events) >= size:
                calls[key].append(Call(against=against))
            calls[key][-1].events.append((e, f))
        return [call for group in calls.values() for call in group]

    def event_label(self, eid: int) -> str:
        return _event_label(DIAGRAM if eid in self.ours_events else FILE, eid)

    def line(self, pid: int, same: dict[int, int]) -> str:
        side = DIAGRAM if pid in self.ours else FILE
        person = self.people[pid]
        facts = record.facts(self.data, pid)
        said = [f"- {_label(side, pid)}: {_name(person)}"]
        for key in ("nickName", "alias", "middleName", "birthName"):
            if person.get(key):
                said.append(f"{key} {person[key]}")
        for fact in (record.Kept.Gender, record.Kept.Birth, record.Kept.Death):
            if facts[fact]:
                shown = (
                    _when(record.life(self.data, pid, fact))
                    if fact in record.LIFE
                    else facts[fact]
                )
                said.append(f"{record.KEPT_WORDS[fact]} {shown}")
        for relation in Relation:
            kin = self.family.related(pid, relation)
            if kin:
                names = ", ".join(_name(self.people[x]) for x in sorted(kin))
                said.append(f"{relation.value}: {names}")
        if pid in same:
            said.append(f"already known to be {_label(DIAGRAM, same[pid])}")
        if self.shown is Shown.More:
            said += self.more(pid)
        return "; ".join(said)

    def more(self, pid: int) -> list[str]:
        """What `Shown.More` adds to a person's line."""
        out = []
        grand = {
            g
            for p in self.family.related(pid, Relation.Parent)
            for g in self.family.related(p, Relation.Parent)
        }
        if grand:
            names = ", ".join(_name(self.people[g]) for g in sorted(grand))
            out.append(f"grandparents: {names}")
        if self.people[pid].get("notes"):
            out.append(f'notes: "{_short(self.people[pid]["notes"], NOTES)}"')
        events = sorted(
            (e for e in self.data["events"] if _owner(e) == pid),
            key=lambda e: _day(e) or "",
        )
        titles = [
            f"{_day(e)[:4] if _day(e) else 'undated'} "
            + (e.get("title") or e.get("description") or e["kind"])
            for e in events[:TITLES]
        ]
        if len(events) > TITLES:
            titles.append(f"and {len(events) - TITLES} more")
        if titles:
            out.append("events: " + ", ".join(titles))
        if pid in self.ours:
            role = self.role(pid)
            if role:
                out.append(f"in the conversation they are the person's {role}")
            out += [f'the person said: "{one}"' for one in self.spoken(pid)]
        return out

    def role(self, pid: int) -> str | None:
        """What the person of the diagram is to the one it is about, in the
        coach's words: "mother", "partner's father"; None for that one."""
        found = re.search(
            r"\(([^)]*)\)$", coverage.label(self.view, ItemKind.Person, pid)
        )
        return found.group(1) if found and pid != self.main else None

    def spoken(self, pid: int) -> list[str]:
        """Up to three of the person's sentences naming someone by name."""
        name = self.people[pid].get("name")
        if unnamed(name):
            return []
        names = {tokens(name)[0], " ".join(tokens(name))}
        pattern = re.compile(
            r"\b(" + "|".join(re.escape(n) for n in names) + r")\b", re.I
        )
        return [one for one in self.sentences if pattern.search(one)][:SAID]

    def said(self, eid: int) -> str:
        event = self.events[eid]
        words = [
            f"{key}: {event[key]}"
            for key in ("title", "description", "notes", "location")
            if event.get(key)
        ]
        return f"{self.event_label(eid)}: {event['kind']} {_when(event, 'on ')}; " + (
            "; ".join(words) or "no words"
        )

    def candidate(self, y: int, x: int) -> str:
        why = self.found.people[y].why.get(x) if y in self.found.people else None
        if self.shown is Shown.More and why:
            return f"{_label(DIAGRAM, x)} (the rules were unsure because: {why})"
        return _label(DIAGRAM, x)

    def prompt(self, call: Call, same: dict[int, int]) -> str:
        shown = []
        for y, candidates in call.people.items():
            shown += [
                *self.household(y),
                *(x for c in candidates for x in self.household(c)),
            ]
        for e, f in call.events:
            for eid in (e, f):
                shown += self.household(_owner(self.events[eid]))
        for pid in list(shown):
            if pid in same:
                shown += self.household(same[pid])
        shown = list(dict.fromkeys(shown))
        return prompts.files().text(
            PROMPT,
            file="\n".join(self.line(p, same) for p in shown if p not in self.ours)
            or "(none)",
            diagram="\n".join(self.line(p, same) for p in shown if p in self.ours)
            or "(none)",
            people="\n".join(
                f"- {_label(FILE, y)} against "
                + ", ".join(self.candidate(y, x) for x in candidates)
                for y, candidates in call.people.items()
            )
            or "(none)",
            events="\n".join(
                f"- {self.said(e)}"
                + "".join(f"\n  against {self.said(f)}" for f in others)
                for e, others in _by_first(call.events).items()
            )
            or "(none)",
            against=call.against,
            more=self.shown is Shown.More,
        )

    def answer(self, call: Call, same: dict[int, int]) -> tuple[Answer | None, str]:
        size = sum(len(xs) for xs in call.people.values()) + len(call.events)
        return heard(
            self.model,
            self.prompt(call, same),
            Answer,
            _schema(call, self.event_label),
            ROOM + PER_ANSWER * size,
        )

    def refuse(self, kind: str, item: int | None, label: str, why: str, then: str):
        self.decisions.append(
            Decision(
                label if item is None else f"{kind} {self.old[item]}",
                "",
                "",
                "",
                f"The model's answer was refused: {why} {then}",
            )
        )

    def judged(self, call: Call, same: dict[int, int]):
        """The model's verdicts on one family, each checked; a refused one is
        said by name and counts as unsure."""
        answer, failed = self.answer(call, same)
        people, events = {}, {}
        for y in call.people if failed else []:
            self.decide("person", y, "", "", "", f"The model was not heard: {failed}")
        for e, _ in call.events if failed else []:
            self.decide("event", e, "", "", "", f"The model was not heard: {failed}")
        asked = {
            (_label(FILE, y), _label(DIAGRAM, x)): (y, x)
            for y, xs in call.people.items()
            for x in xs
        }
        for one in answer.people if answer else []:
            key = asked.get((one.person, one.candidate))
            what = f"{one.person} against {one.candidate}"
            if key is None:
                why = f"it judged {what}, which it was not asked."
            elif key in people:
                why = f"it judged {what} twice."
            elif one.verdict not in VERDICTS:
                why = f"it answered {one.verdict!r} on {what}."
            else:
                people[key] = (Verdict(one.verdict), one.reason)
                continue
            if key is not None:
                people[key] = (Verdict.Unsure, "")
            y = next((y for y in call.people if _label(FILE, y) == one.person), None)
            self.refuse("person", y, one.person, why, "It counts as unsure.")
        pairs = {
            (self.event_label(e), self.event_label(f)): (e, f) for e, f in call.events
        }
        for one in answer.events if answer else []:
            key = pairs.get((one.event, one.other))
            what = f"{one.event} against {one.other}"
            if key is None:
                why = f"it judged {what}, which it was not asked."
            elif key in events:
                why = f"it judged {what} twice."
            elif one.verdict not in (Verdict.Same, Verdict.Different):
                why = f"it answered {one.verdict!r} on {what}."
            else:
                events[key] = (Verdict(one.verdict), one.reason)
                continue
            if key is not None:
                events[key] = (Verdict.Unsure, "")
            e = next(
                (e for e, _ in call.events if self.event_label(e) == one.event), None
            )
            self.refuse("event", e, one.event, why, "Both events are kept.")
        return people, events

    # Joining

    def final(self, item: int) -> int:
        """The item a file's item is now, following every join."""
        while item in self.joined:
            item = self.joined[item]
        return item

    def join_event(
        self, keep: dict, drop: dict, reason: str, words: tuple = OVER_DIAGRAM
    ) -> None:
        """One event of two: the kept one's values win, what only the other
        has is added, and the notes of both are kept, one after the other."""
        only, otherwise = words
        eid = drop["id"]
        for key, value in drop.items():
            if key in ("id", "notes", *LINKS, *MOVES) or value in EMPTY:
                continue
            if key == "tags":
                keep[key] = list(dict.fromkeys([*keep.get(key, []), *value]))
            elif keep.get(key) in EMPTY:
                keep[key] = value
                self.decide("event", eid, key, value, value, only)
            elif diagramjson.to_json(keep[key]) != diagramjson.to_json(value):
                self.decide("event", eid, key, value, keep[key], otherwise)
        notes = "\n\n".join(
            dict.fromkeys(filter(None, (keep.get("notes"), drop.get("notes"))))
        )
        if notes and notes != keep.get("notes"):
            self.decide(
                "event", eid, "notes", drop.get("notes"), notes, "Both notes are kept."
            )
            keep["notes"] = notes
        self.data["events"].remove(drop)
        del self.events[eid]
        self.joined[eid] = keep["id"]
        self.decide("event", eid, "", "", f"part of event {keep['id']}", reason)

    def join_bonds(self, keep: int, drop: int) -> None:
        """Before the record's merge makes one pair-bond of two, what only the
        file's says is added to the diagram's."""
        bonds = self.data["pair_bonds"]
        for bond in bonds:
            sides = {bond["person_a"], bond["person_b"]}
            if drop not in sides:
                continue
            other = (sides - {drop} or {drop}).pop()
            twin = next(
                (b for b in bonds if {b["person_a"], b["person_b"]} == {keep, other}),
                None,
            )
            if twin is None:
                continue
            self.joined[bond["id"]] = twin["id"]
            for key, value in bond.items():
                if key in ("id", "person_a", "person_b") or value in EMPTY:
                    continue
                if twin.get(key) in EMPTY:
                    twin[key] = value
                elif key == "notes" and value != twin[key]:
                    twin[key] = f"{twin[key]}\n\n{value}"
                else:
                    continue
                self.decide(
                    "pair-bond",
                    bond["id"],
                    key,
                    value,
                    twin[key],
                    f"Part of pair-bond {twin['id']} of the same couple.",
                )

    def join_person(self, keep: int, drop: int, reason: str) -> None:
        kept, lost = self.people[keep], self.people[drop]
        if record.kin(self.data, keep, drop):
            self.decide(
                "person",
                drop,
                "",
                "",
                "",
                f"Not joined to person {keep}: they are partners, or parent and "
                "child, in the diagram as it would be. Both are kept.",
            )
            return
        for fact in record.LIFE:
            ours, theirs = record.life(self.data, keep, fact), record.life(
                self.data, drop, fact
            )
            if ours and theirs:
                self.join_event(ours, theirs, f"The {fact.value} of the same person.")
        for key, value in lost.items():
            if key in MERGED or value in EMPTY:
                continue
            if kept.get(key) in EMPTY:
                kept[key] = value
                self.decide("person", drop, key, value, value, "Only the file had it.")
            elif kept[key] != value:
                self.decide(
                    "person",
                    drop,
                    key,
                    value,
                    kept[key],
                    "The diagram already said otherwise; its value is kept.",
                )
        # A name by family position, or the app's stand-in, is no name at all.
        named = (
            lost["name"]
            if unnamed(kept.get("name"))
            and lost.get("name")
            and not unnamed(lost["name"])
            else None
        )
        if named:
            self.decide(
                "person",
                drop,
                "name",
                named,
                named,
                f'The diagram had no name for them yet, only "{kept.get("name") or ""}"; '
                "the file's name takes its place.",
            )
        for key in ("name", "last_name"):
            if named and key == "name":
                continue
            if lost.get(key) and kept.get(key) and lost[key] != kept[key]:
                self.decide(
                    "person",
                    drop,
                    key,
                    lost[key],
                    kept[key],
                    "The diagram's name is kept.",
                )
        both = record.differing(self.data, keep, drop)
        for fact, (ours, theirs) in both.items():
            self.decide(
                "person",
                drop,
                fact.value,
                theirs,
                ours,
                "The diagram already said otherwise; its value is kept.",
            )
        self.join_bonds(keep, drop)
        take = {fact.value: record.Side.Keep.value for fact in both}
        for delta in record.merging(self.data, keep, drop, take, named).deltas:
            record.enact(self.data, delta)
        del self.people[drop]
        self.joined[drop] = keep
        self.events = {e["id"]: e for e in self.data["events"]}
        self.decide("person", drop, "", "", f"person {keep}", reason)

    # Pass 3

    def described(self, y: int) -> str:
        """The file's person by name and what tells them apart: their birth
        year, else their parents, else their partner."""
        person = self.people[y]
        born = record.facts(self.data, y)[record.Kept.Birth]
        if born:
            return f"{_name(person)} born {born[:4]}"
        for relation, word in (
            (Relation.Parent, CHILD_WORDS.get(person.get("gender"), "child")),
            (Relation.Partner, "partner"),
        ):
            kin = sorted({self.final(k) for k in self.family.related(y, relation)})
            if kin:
                names = " and ".join(_name(self.people[k]) for k in kin)
                return f"{_name(person)}, {word} of {names},"
        return _name(person)

    def called(self, x: int) -> str:
        """The diagram's person as the person knows them, with their birth
        year where the diagram has one."""
        name = self.people[x].get("name") or ""
        role = self.role(x)
        if role:
            ours = f"your {role}" + ("" if unnamed(name) else f" {name}")
        elif PLACEHOLDER.search(name):
            ours = name
        elif name:
            ours = f"the {name} you've mentioned"
        else:
            ours = "someone you've already mentioned"
        born = record.facts(self.data, x)[record.Kept.Birth]
        return f"{ours}, born {born[:4]}," if born else ours

    def question(self, y: int, x: int, taken: set[str]) -> dict:
        """Asks whether two people are one, naming what tells each apart
        [Oracle: R-0852]."""
        named = not PLACEHOLDER.search(self.people[y].get("name") or "")
        theirs = ("the " if named else "") + f"{self.described(y)} in the file"
        text = (
            f"Are you {theirs}?" if x == self.main else f"Is {self.called(x)} {theirs}?"
        )
        qid = record.next_key("q", taken)
        taken.add(qid)
        return {
            "id": qid,
            "text": text,
            "kind": QuestionKind.Thought.value,
            "item_kind": ItemKind.Person.value,
            "item_id": str(y),
            "fact": None,
            "state": QuestionState.Held.value,
            "outcome": None,
            "session_id": None,
            "asked_at": None,
        }

    def heard_all(self, calls: list[Call], same: dict[int, int]) -> tuple[dict, dict]:
        people, events = {}, {}
        for call in calls:
            found_people, found_events = self.judged(call, same)
            people |= found_people
            events |= found_events
        return people, events

    def repeated(self) -> list[tuple[int, int]]:
        """The file's own events told twice, judged and joined first."""
        pairs = self.repeats()
        _, judged = self.heard_all(self.grouped({}, pairs, REPEAT, PER_CALL), {})
        for (e, f), (verdict, reason) in judged.items():
            if verdict is Verdict.Same and e in self.events and f in self.events:
                self.join_event(
                    self.events[f],
                    self.events[e],
                    f"Judged one happening told twice in the file: {reason}",
                    OVER_FILE,
                )
        return pairs

    def run(self) -> tuple[dict, list[Decision], list[dict]]:
        repeats = self.repeated()
        same = self.same()
        doubted = self.doubted()
        pairs = self.pairs(same) if self.pairing is Pairing.SameDay else []
        people, events = self.heard_all(self.grouped(doubted, pairs), same)
        joined, unsure = dict(same), collections.defaultdict(list)
        claimed = collections.Counter()
        chosen = {}
        for y, candidates in doubted.items():
            said = {x: people.get((y, x), (Verdict.Unsure, ""))[0] for x in candidates}
            sames = [x for x, v in said.items() if v is Verdict.Same]
            if len(sames) == 1:
                chosen[y] = sames[0]
                claimed[sames[0]] += 1
                continue
            if len(sames) > 1:
                self.decide(
                    "person",
                    y,
                    "",
                    "",
                    "",
                    "The model's answer was refused: it called more than one person "
                    "in the diagram the same person. It counts as unsure.",
                )
            unsure[y] = [x for x, v in said.items() if v is not Verdict.Different]
        for y, x in chosen.items():
            if claimed[x] > 1:
                self.decide(
                    "person",
                    y,
                    "",
                    "",
                    "",
                    f"The model's answer was refused: it called more than one person "
                    f"in the file person {x} of the diagram. It counts as unsure.",
                )
                unsure[y] = [x]
            else:
                joined[y] = x
        # The file's person joined into the diagram's own keeps the mark: the
        # two are one person, the app's nameless stand-in among them.
        mains = {p["id"]: p for p in self.existing["people"] if p.get("primary")}
        named = any(not unnamed(p.get("name")) for p in mains.values())
        for y in sorted(self.found.people):
            if (
                mains
                and joined.get(y) not in mains
                and self.people[y].pop("primary", None)
            ):
                self.decide(
                    "person",
                    y,
                    "primary",
                    True,
                    "",
                    "The diagram already says who it is about."
                    if named
                    else "The app's stand-in for the person stays them until "
                    "they say which person in the file they are.",
                )
        for y, x in sorted(joined.items()):
            if y not in same:
                reason = f"Judged the same person: {people[y, x][1]}"
            elif x in mains and unnamed(mains[x].get("name")):
                reason = (
                    "The app's stand-in for the person takes the desktop file's "
                    "main person."
                )
            else:
                reason = "The same name and family in the file and the diagram."
            self.join_person(x, y, reason)
        for y in sorted(set(self.found.people) - set(joined)):
            reason = (
                "Asked of the person: both are kept until they answer."
                if unsure.get(y)
                else "Nobody in the diagram is this person."
            )
            self.decide("person", y, "", "", f"person {y}", reason)
        self.family = Family(self.data)
        self.parented()
        if self.pairing is Pairing.TwoYears:
            pairs = self.near()
            events |= self.heard_all(self.grouped({}, pairs, NEAR, PER_CALL), {})[1]
        asked = {y for y, xs in unsure.items() if xs}
        judged = {e for e, _ in [*pairs, *repeats]}
        self.placed = {
            Placed.Rules: collections.Counter(
                people=len(self.found.people) - len(doubted),
                events=len(self.file["events"]) - len(judged),
            ),
            Placed.Model: collections.Counter(
                people=len(doubted) - len(asked), events=len(judged)
            ),
            Placed.Asked: collections.Counter(people=len(asked)),
        }
        self.join_events(events)
        self.unnamed()
        taken = {q["id"] for q in self.data.get("questions") or []}
        held = [self.question(y, x, taken) for y in sorted(unsure) for x in unsure[y]]
        return self.data, self.decisions, held

    def unnamed(self) -> None:
        """An event the import adds or changes says what happened without
        naming anyone it links, by the names the diagram keeps for the people
        joined [Oracle: R-0457]: the coding pass read the file's names only."""
        ours = {e["id"]: e for e in self.existing["events"]}
        dropped = {kept: e for e, kept in self.joined.items() if e in self.old}
        for event in self.data["events"]:
            eid = event["id"]
            if ours.get(eid) == event or not any(
                record.linked_name(self.data, event, event.get(key) or "")
                for key in ("title", "description")
            ):
                continue
            source = eid if eid in self.old else dropped.get(eid)
            item = (
                f"event {self.old[source]}" if source else f"event {eid} of the diagram"
            )
            fdcoding.change(
                self.decisions,
                item,
                event,
                fdcoding.plain(self.data, event),
                "Its words named someone already on the event by the name the "
                "diagram keeps for them; they go to its notes.",
            )

    def parented(self) -> None:
        """A birth the file brought to a person of the diagram names the
        parents the diagram gives them."""
        bonds = {b["id"]: b for b in self.data["pair_bonds"]}
        ours = {e["id"] for e in self.existing["events"]}
        for event in self.data["events"]:
            if event["id"] in ours or event["kind"] not in OFFSPRING:
                continue
            bond = bonds.get(self.people[event["child"]].get("parents"))
            if bond is None:
                continue
            parents = {bond["person_a"], bond["person_b"]}
            if {event.get("person"), event.get("spouse")} == parents:
                continue
            said = ", ".join(
                _name(self.people[event[key]])
                for key in ("person", "spouse")
                if event.get(key) is not None
            )
            event["person"], event["spouse"] = bond["person_a"], bond["person_b"]
            self.decide(
                "event",
                event["id"],
                "parents",
                said,
                f"persons {bond['person_a']} and {bond['person_b']}",
                "The diagram already says who the parents are.",
            )

    def join_events(self, judged: dict) -> None:
        """The matcher's pairs once their people are one, the pairs the model
        judged the same, then any event the record would count twice."""
        ours = {e["id"] for e in self.existing["events"]}
        found = [
            (e, f, JOINED)
            for e, f in self.structural.items()
            if e in self.events
            and f in self.events
            and _linked(self.events[e]) == _linked(self.events[f])
        ]
        found += [
            (e, f, f"Judged the same event by its words: {reason}")
            for (e, f), (verdict, reason) in judged.items()
            if verdict is Verdict.Same
        ]
        for e, f, reason in found:
            if e in self.events and f in self.events:
                self.join_event(self.events[f], self.events[e], reason)
        twins = {record.twin_key(self.events[f]): f for f in ours if f in self.events}
        for e in [e for e in self.events if e not in ours]:
            f = twins.get(record.twin_key(self.events[e]))
            if f is not None:
                self.join_event(self.events[f], self.events[e], TWIN)


def merge(
    existing: dict, imported: dict, model=ask, **ways
) -> tuple[dict, list[Decision], list[dict]]:
    """`existing` is the diagram as stored, `imported` the importer's coded
    diagram; `model` is called as fdcoding's is; `ways` are Merge's pairing,
    shown and statements. Returns the merged diagram, the choices for the
    import record, and the held questions to add, which the merged diagram
    does not yet hold."""
    return Merge(existing, imported, model, **ways).run()
