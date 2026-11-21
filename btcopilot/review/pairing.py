"""The ballot by pairing: every coder's version of one thing said in a cut,
put together by one model call when Patrick asks for the ballot, as a job on
the worker [Oracle: R-0961, R-0962].

The call reads the cut's lines and, from every finished coding, each person,
couple and event beside the statement that produced it, and answers pairings of
{coding_id, item_id}, each with a one-line reason and how sure it was. A fixed
check then holds every human coder's entry to exactly one pairing, and each
pairing to one kind of item; a failure is an observation on the cut's diagram
and leaves the ballot failed. Only Patrick joins or splits a pairing, before
the vote opens (R-0963). The coach's replay is read too, so the result screen
can say where it differed, but it is never checked or counted (R-0254).

An item is agreed only when every coder wrote it once and their versions
match, a person matched to a person through the people pairings and a couple
through the couple pairings, never by each copy's own numbers.
"""

import dataclasses
import enum
import hashlib
import json
import logging
import re
import uuid

from werkzeug.exceptions import Conflict

from btcopilot import extensions
from btcopilot.extensions import db
from btcopilot.metered import Metered
from btcopilot.models import Observation, ObservationKind, Purpose
from btcopilot.review import adapter, snapshot
from btcopilot.review.models import Cut, Item, ReviewStatus, Vote
from btcopilot.review.models.item import PairingConfidence
from btcopilot.schema import ItemKind, asdict

_log = logging.getLogger(__name__)

TASK = "review_pairings"
NAME = "pairing"
MODEL = "claude-fable-5-2"
LIMIT = 64000
LOST = "the pairing job stopped before it finished: its worker is gone"
SET_BY_PATRICK = "Set by Patrick"
CODER = "a coder"
COACH = "the coach, not a coder"
# What a reason says in place of a coding's label or number: a person reads
# the reason, and neither tells them anything (R-0969).
ONE_CODER = "one coder"
NUMBERED = re.compile(r"\bcod(?:ing|er)\s+#?\d+\b", re.IGNORECASE)
KINDS = {
    ItemKind.Person: "people",
    ItemKind.PairBond: "couples",
    ItemKind.Event: "events",
}
COLLECTION = {
    ItemKind.Person: "people",
    ItemKind.PairBond: "pair_bonds",
    ItemKind.Event: "events",
}
# What a version holds that is not what it says: its own number, the coder's
# own words, which two coders never write alike, and a person's name, only a
# provisional handle on who they are (R-0968).
UNSAID = ("id", "name", "notes", "confidence", "dateEvidence")
PEOPLE_FIELDS = ("person", "spouse", "child", "person_a", "person_b")
PEOPLE_LISTS = ("relationshipTargets", "relationshipTriangles")


class State(enum.StrEnum):
    Building = "building"
    Built = "built"
    Failed = "failed"


class Ballot(enum.StrEnum):
    Empty = "none"
    Building = "building"
    Built = "built"
    Failed = "failed"
    Open = "open"


@dataclasses.dataclass
class Entry:
    coder: str
    item_id: int


@dataclasses.dataclass
class Pairing:
    entries: list[Entry]
    reason: str
    confidence: PairingConfidence


@dataclasses.dataclass
class Answer:
    pairings: list[Pairing]


SCHEMA = {
    "type": "object",
    "properties": {
        "pairings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "coder": {"type": "string"},
                                "item_id": {"type": "integer"},
                            },
                            "required": ["coder", "item_id"],
                        },
                    },
                    "reason": {"type": "string"},
                    "confidence": {
                        "type": "string",
                        "enum": [c.value for c in PairingConfidence],
                    },
                },
                "required": ["entries", "reason", "confidence"],
            },
        }
    },
    "required": ["pairings"],
}


class CheckFailed(ValueError):
    pass


def ballot(cut: Cut) -> Ballot:
    """The ballot's state. A ballot building with no job holding its cut is a
    job whose worker died: it is failed here, once, as the case report's
    rewrite is."""
    if cut.vote_opened_at is not None:
        return Ballot.Open
    state = (cut.pairing_agent or {}).get("state")
    if state == State.Building and adapter.job_holder(held(cut.id)) is None:
        failed(cut, f"pairing-{cut.id}-lost", {"error": LOST})
        return Ballot.Failed
    return Ballot(state) if state else Ballot.Empty


def held(cut_id: int) -> str:
    return f"cut:{cut_id}:pairing"


def agent(cut: Cut) -> dict | None:
    if not cut.pairing_agent:
        return None
    return {k: cut.pairing_agent[k] for k in ("model", "prompt")}


def version() -> str:
    """The pairing prompt as the cut names it: its text with nothing filled in,
    hashed, as the coach's prompt is named."""
    text = adapter.prompt_text(NAME, lines="", codings="")
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def start(cut: Cut, user_id: int) -> None:
    """The pairing job, started; it replaces the cut's items when it finishes.
    Never while the vote is open or a vote stands on the cut's items: those
    votes are the coders' and nothing deletes them on the way."""
    if ballot(cut) in (Ballot.Open, Ballot.Building):
        raise Conflict(f"the ballot is {ballot(cut).value}")
    voted = Vote.query.join(Item).filter(Item.cut_id == cut.id).count()
    if voted:
        raise Conflict(f"{voted} votes stand on this cut's items")
    job = f"pairing-{cut.id}-{uuid.uuid4().hex[:8]}"
    if not adapter.seize_job(held(cut.id), job):
        raise Conflict("the ballot is building")
    cut.pairing_agent = {"model": MODEL, "prompt": version(), "state": State.Building}
    db.session.commit()
    extensions.celery.send_task(
        TASK, args=[cut.id], kwargs={"user_id": user_id, "job": job}
    )


def built(cut_id: int, *, user_id: int, job: str) -> None:
    """The worker's pairing task, holding its cut while it runs. Anything that
    stops it before the pairings are stored fails the ballot with an
    observation; nothing is tried again until Patrick asks again. A job that
    waited in the queue past its hold takes it again, unless a newer job holds
    it or the ballot is no longer building."""
    key = held(cut_id)
    if not adapter.seize_job(key, job):
        return
    with adapter.job_held(key, job):
        cut = db.session.get(Cut, cut_id)
        if ballot(cut) is not Ballot.Building:
            return
        try:
            _built(cut, user_id, job)
        # every way the job ends without a ballot is a failed ballot, then raised
        except Exception as error:
            db.session.rollback()
            failed(db.session.get(Cut, cut_id), job, {"error": repr(error)})
            raise


def _built(cut: Cut, user_id: int, turn_id: str) -> None:
    codings = snapshot.done_codings(cut)
    versions = listed(codings)
    voters = voter_ids(cut)
    names = labels([c.id for c in codings], voters)
    meter = Metered(user_id, cut.diagram_id, turn_id, Purpose.Pairing)
    answer = meter.structured(
        prompt(cut, codings, versions, names), Answer, SCHEMA, LIMIT, model=MODEL
    )
    groups = unlabelled(answer, names)
    found = problems([g[0] for g in groups], versions, voters)
    if found:
        failed(cut, turn_id, found)
        return
    stored(cut, groups, versions)
    _log.info(f"Cut {cut.id}: {len(groups)} pairings built")


def stored(cut: Cut, groups: list[tuple], versions: dict) -> None:
    """The cut's items replaced by these pairings, each (entries, reason,
    confidence), and the ballot built."""
    Item.query.filter_by(cut_id=cut.id).delete()
    db.session.add_all(
        row(cut, keys, versions, reason, confidence)
        for keys, reason, confidence in groups
    )
    db.session.flush()
    settle(cut)
    cut.pairing_agent = dict(cut.pairing_agent or {}, state=State.Built)
    db.session.commit()


def failed(cut: Cut, turn_id: str, detail: dict) -> None:
    db.session.add(
        Observation(
            diagram_id=cut.diagram_id,
            turn_id=turn_id,
            kind=ObservationKind.PairingCheck,
            detail=dict(detail, cut_id=cut.id),
        )
    )
    cut.pairing_agent = dict(cut.pairing_agent, state=State.Failed)
    db.session.commit()
    _log.warning(f"Cut {cut.id}: the ballot failed: {detail}")


def voter_ids(cut: Cut) -> set[int]:
    return {c.id for c in snapshot.voters(cut)}


def listed(codings) -> dict[tuple[int, int], tuple[ItemKind, dict, int | None]]:
    """Every version each coding holds, by (coding_id, item_id): its kind, the
    item as the schema writes it, and the line it was written from."""
    found = {}
    for coding in codings:
        pdp = adapter.pdp_of(adapter.diagram_of(coding.diagram_id))
        for kind in KINDS:
            lines = adapter.coded_in(coding.diagram_id, kind)
            for item in getattr(pdp, COLLECTION[kind]):
                said = lines.get(item.id, {}).get("statement_id")
                found[(coding.id, item.id)] = (kind, asdict(item), said)
    return found


def labels(coding_ids: list[int], voters: set[int]) -> dict[int, str]:
    """Each coding as the call reads it: a letter by its position, never its
    database number, which the call could echo into a reason (R-0969)."""
    return {
        coding_id: f"{'coder' if coding_id in voters else 'coach'} {letter(at)}"
        for at, coding_id in enumerate(coding_ids)
    }


def letter(at: int) -> str:
    return (letter(at // 26 - 1) if at >= 26 else "") + chr(ord("A") + at % 26)


def unlabelled(answer: Answer, names: dict[int, str]) -> list[tuple]:
    """The call's pairings as (entries, reason, confidence), each entry by its
    coding again. A label no coding holds stays as it is, so the fixed check
    names it unknown."""
    back = {label: coding_id for coding_id, label in names.items()}
    return [
        (
            [(back.get(e.coder, e.coder), e.item_id) for e in p.entries],
            reworded(p.reason, names.values()),
            p.confidence,
        )
        for p in answer.pairings
    ]


def reworded(reason: str, names) -> str:
    """A reason that names a coding by its label or its number says "one
    coder" there instead (the coach's label, "the coach"); the call is never
    asked again for its wording."""

    def put(said: str):
        return lambda found: said.capitalize() if found.start() == 0 else said

    for label in sorted(names, key=len, reverse=True):
        said = "the coach" if label.startswith("coach") else ONE_CODER
        found = re.compile(rf"\b{re.escape(label)}\b", re.IGNORECASE)
        reason = found.sub(put(said), reason)
    return NUMBERED.sub(put(ONE_CODER), reason)


def prompt(cut: Cut, codings, versions, names: dict[int, str]) -> str:
    lines = [
        (s.id, (s.speaker.name if s.speaker else None) or "Someone", s.text or "")
        for s in adapter.statements_between(
            cut.diagram_id, cut.start_statement_id, cut.end_statement_id
        )
    ]
    voters = voter_ids(cut)
    written = [
        block(
            names[coding.id],
            coding.id in voters,
            {
                kind: [
                    said(item, line)
                    for (coding_id, _), (each, item, line) in versions.items()
                    if coding_id == coding.id and each is kind
                ]
                for kind in KINDS
            },
        )
        for coding in codings
    ]
    return render(lines, written)


def block(label: str, voter: bool, versions: dict[ItemKind, list[dict]]) -> dict:
    """One coding as the call reads it: its label, whether a coder wrote it,
    and its versions by kind."""
    return {
        "coder": label,
        "role": CODER if voter else COACH,
        **{KINDS[kind]: versions[kind] for kind in KINDS},
    }


def said(item: dict, line: int | None) -> dict:
    """One version as the call reads it: what it holds, and its line."""
    return dict({k: v for k, v in item.items() if v not in (None, [], "")}, line=line)


def render(lines: list[tuple], written: list[dict]) -> str:
    return adapter.prompt_text(
        NAME,
        lines="\n".join(f"[line {n}] {who}: {text}" for n, who, text in lines),
        codings=json.dumps(written, indent=1, ensure_ascii=False),
    )


def problems(groups: list[list[tuple]], versions: dict, voters: set[int]) -> dict:
    """What breaks the fixed check: an entry no coding holds, an entry in two
    pairings, a coder's entry in none, a pairing of more than one kind or of
    nothing at all. Empty when the pairings stand."""
    seen: dict[tuple, int] = {}
    for keys in groups:
        for key in keys:
            seen[key] = seen.get(key, 0) + 1
    found = {
        "unknown": [k for k in seen if k not in versions],
        "repeated": [k for k, n in seen.items() if n > 1],
        "missing": [k for k in versions if k[0] in voters and k not in seen],
        "mixed": [
            keys
            for keys in groups
            if len({versions[k][0] for k in keys if k in versions}) > 1
        ],
        "empty": sum(1 for keys in groups if not keys),
    }
    return {
        k: [list(v) for v in found[k]] if isinstance(found[k], list) else found[k]
        for k in found
        if found[k]
    }


def row(cut: Cut, keys, versions, reason: str, confidence) -> Item:
    keys = sorted(keys)
    return Item(
        cut_id=cut.id,
        item_kind=versions[keys[0]][0],
        opinions=[entry(k, versions) for k in keys],
        status=ReviewStatus.Disputed,
        pairing_reason=reason,
        pairing_confidence=PairingConfidence(confidence),
    )


def entry(key: tuple[int, int], versions) -> dict:
    return {"coding_id": key[0], "item_id": key[1], "item": versions[key][1]}


def entries_of(cut: Cut) -> list[list[tuple]]:
    return [
        [(o["coding_id"], o["item_id"]) for o in item.opinions or []]
        for item in cut.items
    ]


def check(cut: Cut) -> None:
    """The fixed check over the cut's pairings as they stand, before the vote
    opens: a coding finished after the pairings were built fails it, and the
    ballot is failed until it is built again."""
    found = problems(
        entries_of(cut), listed(snapshot.done_codings(cut)), voter_ids(cut)
    )
    if found:
        failed(cut, f"pairing-{cut.id}-open", found)
        raise CheckFailed("the pairings no longer hold every coder's versions")


def moved(
    cut: Cut, target: Item | None, named: list[dict]
) -> tuple[list[Item], list[int]]:
    """Patrick's join or split: the entries named go into `target`, or into a
    new pairing when there is none, out of whatever pairing held them; a
    pairing left empty is deleted. Every pairing touched is his, sure."""
    if ballot(cut) is not Ballot.Built:
        raise ValueError("pairings change only on a built ballot before the vote opens")
    keys = [(int(o["coding_id"]), int(o["item_id"])) for o in named]
    if not keys or len(set(keys)) != len(keys):
        raise ValueError("name each version once")
    holder, whole = {}, {}
    for item in cut.items:
        for o in item.opinions or []:
            holder[(o["coding_id"], o["item_id"])] = item
            whole[(o["coding_id"], o["item_id"])] = o
    if any(k not in holder for k in keys):
        raise ValueError("that version is not on this ballot")
    if len({holder[k].item_kind for k in keys}) > 1:
        raise ValueError("a pairing holds one kind of item")
    if target is not None:
        if target.cut_id != cut.id:
            raise ValueError("that pairing is not on this ballot")
        own = {(o["coding_id"], o["item_id"]) for o in target.opinions or []}
        if not own <= set(keys):
            raise ValueError(
                "a join keeps the pairing's own versions; split them off instead"
            )
    if target is None:
        target = Item(
            cut_id=cut.id,
            item_kind=holder[keys[0]].item_kind,
            opinions=[],
            status=ReviewStatus.Disputed,
        )
        db.session.add(target)
    touched, deleted = {id(target): target}, []
    for item in {id(holder[k]): holder[k] for k in keys}.values():
        if item is target:
            continue
        item.opinions = [
            o for o in item.opinions if (o["coding_id"], o["item_id"]) not in keys
        ]
        if item.opinions:
            touched[id(item)] = item
        else:
            deleted.append(item.id)
            db.session.delete(item)
    target.opinions = [whole[k] for k in sorted(keys)]
    for item in touched.values():
        item.pairing_reason = SET_BY_PATRICK
        item.pairing_confidence = PairingConfidence.Sure
    db.session.flush()
    settle(cut)
    return list(touched.values()), deleted


def settle(cut: Cut) -> None:
    """Each pairing agreed or disputed, people and couples compared by who
    they are."""
    voters = voter_ids(cut)
    items = Item.query.filter_by(cut_id=cut.id).all()
    who = tokens(items, ItemKind.Person)
    bonds = tokens(items, ItemKind.PairBond)
    for item in items:
        item.status = status(item, voters, who, bonds)
    db.session.flush()


def tokens(items: list[Item], kind: ItemKind) -> dict[tuple[int, int], int]:
    """Each coder's person (or couple) by the pairing it is in: two coders'
    numbers for the same person map to the one pairing's id."""
    return {
        (o["coding_id"], o["item_id"]): item.id
        for item in items
        if item.item_kind is kind
        for o in item.opinions or []
    }


def status(item: Item, voters: set[int], who: dict, bonds: dict) -> ReviewStatus:
    """Agreed when every coder wrote it once and the same way. What the coach
    wrote is on the row but never decides it (R-0254)."""
    theirs = [o for o in item.opinions or [] if o["coding_id"] in voters]
    coders = [o["coding_id"] for o in theirs]
    if not theirs or sorted(coders) != sorted(voters):
        return ReviewStatus.Disputed
    said = [comparable(o, who, bonds) for o in theirs]
    if all(one == said[0] for one in said[1:]):
        return ReviewStatus.Agreed
    return ReviewStatus.Disputed


def comparable(opinion: dict, who: dict, bonds: dict) -> dict:
    coding_id = opinion["coding_id"]

    def person(value):
        return who.get((coding_id, value), ("unpaired", coding_id, value))

    found = {}
    for key, value in opinion["item"].items():
        if key in UNSAID:
            continue
        if value is not None and key in PEOPLE_FIELDS:
            value = person(value)
        elif key in PEOPLE_LISTS:
            value = sorted(map(str, (person(v) for v in value or [])))
        elif key == "parents" and value is not None:
            value = bonds.get((coding_id, value), ("unpaired", coding_id, value))
        found[key] = value
    if opinion["item"].keys() >= {"person_a", "person_b"}:
        found["person_a"], found["person_b"] = sorted(
            map(str, (found["person_a"], found["person_b"]))
        )
    return found
