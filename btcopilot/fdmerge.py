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
import enum
from dataclasses import dataclass, field

# fdimport merges with this module and this module renumbers with fdimport;
# neither uses the other at import time.
from btcopilot import diagramjson, fdimport, prompts, record
from btcopilot.familymatch import PLACEHOLDER, Family, Relation, Status, match
from btcopilot.fdcoding import ask, heard, numbered
from btcopilot.fdledger import Decision
from btcopilot.llmutil import dataclass_to_json_schema
from btcopilot.models import Author
from btcopilot.schema import (
    EventKind,
    ItemKind,
    QuestionKind,
    QuestionState,
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


def _mapped(event: dict, same: dict[int, int]) -> dict:
    out = dict(event)
    for key in LINKS:
        if event.get(key) is not None:
            out[key] = same.get(event[key], event[key])
    for key in MOVES:
        if event.get(key):
            out[key] = [same.get(x, x) for x in event[key]]
    return out


def _schema(call: Call) -> dict:
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
        dict.fromkeys(_event_label(FILE, e) for e, _ in call.events)
    )
    events["properties"]["other"]["enum"] = list(
        dict.fromkeys(_event_label(DIAGRAM, f) for _, f in call.events)
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
    def __init__(self, existing: dict, imported: dict, model):
        self.existing = existing
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
            if owner not in same or event["id"] in self.structural or not _day(event):
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

    def grouped(self, doubted, pairs) -> list[Call]:
        calls = collections.defaultdict(Call)
        for y, candidates in doubted.items():
            calls[tuple(self.household(y))].people[y] = candidates
        for e, f in pairs:
            owner = _owner(self.events[e])
            calls[tuple(self.household(owner))].events.append((e, f))
        return list(calls.values())

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
                said.append(f"{record.KEPT_WORDS[fact]} {facts[fact]}")
        for relation in Relation:
            kin = self.family.related(pid, relation)
            if kin:
                names = ", ".join(_name(self.people[x]) for x in sorted(kin))
                said.append(f"{relation.value}: {names}")
        if pid in same:
            said.append(f"already known to be {_label(DIAGRAM, same[pid])}")
        return "; ".join(said)

    def said(self, eid: int) -> str:
        event = self.events[eid]
        side = DIAGRAM if eid in {e["id"] for e in self.existing["events"]} else FILE
        words = [
            f"{key}: {event[key]}"
            for key in ("title", "description", "notes", "location")
            if event.get(key)
        ]
        return f"{_event_label(side, eid)}: {event['kind']} on {_day(event)}; " + (
            "; ".join(words) or "no words"
        )

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
                + ", ".join(_label(DIAGRAM, x) for x in candidates)
                for y, candidates in call.people.items()
            )
            or "(none)",
            events="\n".join(
                f"- {self.said(e)}\n  against {self.said(f)}" for e, f in call.events
            )
            or "(none)",
        )

    def answer(self, call: Call, same: dict[int, int]) -> tuple[Answer | None, str]:
        size = sum(len(xs) for xs in call.people.values()) + len(call.events)
        return heard(
            self.model,
            self.prompt(call, same),
            Answer,
            _schema(call),
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
            (_event_label(FILE, e), _event_label(DIAGRAM, f)): (e, f)
            for e, f in call.events
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
                (e for e, _ in call.events if _event_label(FILE, e) == one.event), None
            )
            self.refuse("event", e, one.event, why, "Both events are kept.")
        return people, events

    # Joining

    def final(self, item: int) -> int:
        """The item a file's item is now, following every join."""
        while item in self.joined:
            item = self.joined[item]
        return item

    def join_event(self, keep: dict, drop: dict, reason: str) -> None:
        """One event of two: the diagram's values win, what only the file has
        is added, and the notes of both are kept, one after the other."""
        eid = drop["id"]
        for key, value in drop.items():
            if key in ("id", "notes", *LINKS, *MOVES) or value in EMPTY:
                continue
            if key == "tags":
                keep[key] = list(dict.fromkeys([*keep.get(key, []), *value]))
            elif keep.get(key) in EMPTY:
                keep[key] = value
                self.decide("event", eid, key, value, value, "Only the file had it.")
            elif diagramjson.to_json(keep[key]) != diagramjson.to_json(value):
                self.decide(
                    "event",
                    eid,
                    key,
                    value,
                    keep[key],
                    "The diagram already said otherwise; its value is kept.",
                )
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
        # A name the coach gave by family position stands for no name at all.
        named = (
            lost["name"]
            if record.generic_key(kept)
            and lost.get("name")
            and not record.generic_key(lost)
            else None
        )
        if named:
            self.decide(
                "person",
                drop,
                "name",
                named,
                named,
                f"The diagram named them only by their place in the family, as "
                f"{kept['name']}; the file's name takes its place.",
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

    def question(self, y: int, x: int, taken: set[str]) -> dict:
        person, other = self.people[y], self.people[x]
        born = record.facts(self.data, y)[record.Kept.Birth]
        theirs = _name(person) + (f", born {born[:4]}," if born else "")
        if PLACEHOLDER.search(other.get("name") or ""):
            ours = other["name"]
        elif other.get("name"):
            ours = f"the {other['name']} you've mentioned"
        else:
            ours = "someone you've already mentioned"
        qid = record.next_key("q", taken)
        taken.add(qid)
        return {
            "id": qid,
            "text": f"Is {theirs} {ours}?",
            "kind": QuestionKind.Thought.value,
            "item_kind": ItemKind.Person.value,
            "item_id": str(y),
            "fact": None,
            "state": QuestionState.Held.value,
            "outcome": None,
            "session_id": None,
            "asked_at": None,
        }

    def run(self) -> tuple[dict, list[Decision], list[dict]]:
        same = self.same()
        doubted = self.doubted()
        pairs = self.pairs(same)
        people, events = {}, {}
        for call in self.grouped(doubted, pairs):
            found_people, found_events = self.judged(call, same)
            people |= found_people
            events |= found_events
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
        primary = any(p.get("primary") for p in self.existing["people"])
        for y in sorted(self.found.people):
            if primary and self.people[y].pop("primary", None):
                self.decide(
                    "person",
                    y,
                    "primary",
                    True,
                    "",
                    "The diagram already says who it is about.",
                )
        for y, x in sorted(joined.items()):
            reason = (
                "The same name and family in the file and the diagram."
                if y in same
                else f"Judged the same person: {people[y, x][1]}"
            )
            self.join_person(x, y, reason)
        for y in sorted(set(self.found.people) - set(joined)):
            reason = (
                "Asked of the person: both are kept until they answer."
                if unsure.get(y)
                else "Nobody in the diagram is this person."
            )
            self.decide("person", y, "", "", f"person {y}", reason)
        asked = {y for y, xs in unsure.items() if xs}
        judged = {e for e, _ in pairs}
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
        self.parented()
        self.join_events(events)
        taken = {q["id"] for q in self.data.get("questions") or []}
        held = [self.question(y, x, taken) for y in sorted(unsure) for x in unsure[y]]
        self.validate(held)
        return self.data, self.decisions, held

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

    def validate(self, held: list[dict]) -> None:
        """The record's own rules on the diagram as the import leaves it."""
        trial = copy.deepcopy(self.data)
        trial["questions"] = [*(trial.get("questions") or []), *held]
        deltas = record.diff(
            {k: v for k, v in self.existing.items() if k != "questions"},
            {k: v for k, v in trial.items() if k != "questions"},
        )
        deltas += [
            {
                "item_kind": ItemKind.Question.value,
                "item_id": q["id"],
                "field": None,
                "before": None,
                "after": q,
            }
            for q in held
        ]
        record.validate(trial, deltas, Author.Pro, undoing=False)


def merge(
    existing: dict, imported: dict, model=ask
) -> tuple[dict, list[Decision], list[dict]]:
    """`existing` is the diagram as stored, `imported` the importer's coded
    diagram; `model` is called as fdcoding's is. Returns the merged diagram,
    the choices for the import record, and the held questions to add, which
    the merged diagram does not yet hold."""
    return Merge(existing, imported, model).run()
