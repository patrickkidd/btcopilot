"""The play-by-play for one cluster, told by the coach as snapshots [R-0542].

The coach picks the point, the dates and the words; the page draws each
snapshot from the record. It tells the case through one tool call, checked
against the cluster before anything is kept: a call the cluster does not bear
out is handed back to the coach with what is wrong, and a coach that never
tells it fails the turn.

The case is a message in the session like any other, marked as a play, so
coming back a week later shows it where it happened and opens it again.

A cluster is told once until what the coach is shown of it changes: a play
told from the same events is the one kept, with no call.
"""

import hashlib
import json
import logging
import uuid

import anthropic

from btcopilot.extensions import db
from btcopilot import recordtext, turnstore, tuning
from btcopilot.case import Case, RecordFault, Tool, Untold, faults, tool
from btcopilot.coachmodel import CoachModel
from btcopilot.coachturn import Metered
from btcopilot.llmutil import ANTHROPIC_TIMEOUT
from btcopilot.models import (
    Discussion,
    Observation,
    ObservationKind,
    Statement,
    StatementKind,
)
from btcopilot import prompts
from btcopilot.schema import DiagramData, enum_val
from btcopilot.timeline import build_timeline

_log = logging.getLogger(__name__)

# How many times a case the cluster does not bear out is handed back.
TRIES = 3
# What an answer in words gets back: the coach's model refuses a forced call.
ASK = "Answer only by calling play_by_play once, with the pictures."
# The longest the server takes to answer, every try timing out at the model's
# own limit, and the page's wait for it (web/src/api.ts PLAY_WAIT_S) with a
# little over, so a slow model fails with the server's error, not the page's.
WAIT = TRIES * ANTHROPIC_TIMEOUT + 30


def events_of(data: DiagramData, cluster: dict) -> list[dict]:
    wanted = set(cluster.get("eventIds") or [])
    found = [e for e in data.events if isinstance(e, dict) and e.get("id") in wanted]
    return sorted(
        found,
        key=lambda e: (recordtext.date_text(e.get("dateTime")) or "", e["id"]),
    )


def told_about(cluster: dict, events: list[dict]) -> dict:
    """What the coach is shown of the cluster, which is all a telling can differ by."""
    return {
        "cluster": recordtext.cluster_line(cluster),
        "events": "\n".join(recordtext.event_line(e) for e in events),
    }


# What the play-by-play drawer reads of the timeline (web/src/snapshots.ts,
# web/src/drawer.ts): of the cluster, of each event, of each person, of a bond.
CLUSTER_FIELDS = ("id", "event_ids", "label", "title")
EVENT_FIELDS = (
    "id",
    "kind",
    "dateTime",
    "dateCertainty",
    "person",
    "spouse",
    "child",
    "relationshipTargets",
    "relationshipTriangles",
    "description",
    "symptom",
    "functioning",
    "anxiety",
    "relationship",
)
PERSON_FIELDS = ("id", "name", "last_name", "gender", "primary", "birth", "death_event", "parents")
BOND_FIELDS = ("id", "person_a", "person_b", "married")


def pick(item: dict, fields: tuple[str, ...]) -> dict:
    return {f: enum_val(item.get(f)) for f in fields}


def named(event: dict) -> list[int]:
    ids = [event.get("person"), event.get("spouse"), event.get("child")]
    ids += (event.get("relationshipTargets") or []) + (event.get("relationshipTriangles") or [])
    return [i for i in ids if i is not None]


def cast(tl: dict, events: list[dict]) -> set[int]:
    """Everyone the drawer draws for these events, found as its castOf does
    (web/src/snapshots.ts): the primary person and everyone the events name,
    the ancestors joining any two of them, and both parents of two of them."""
    people = {p["id"]: p for p in tl["people"]}
    bonds = {b["id"]: b for b in tl["pair_bonds"]}

    def pair(bond: dict) -> list[int]:
        return [i for i in (bond["person_a"], bond["person_b"]) if i is not None]

    def up(pid: int) -> list[int]:
        bond = bonds.get((people.get(pid) or {}).get("parents"))
        return pair(bond) if bond else []

    found = {i for e in events for i in named(e)}
    found |= {next((p["id"] for p in tl["people"] if p["primary"]), None)} - {None}

    def climb(pid: int, path: list[int]):
        of = up(pid)
        path = path + of
        for parent in of:
            if parent in found:
                found.update(path)
            climb(parent, path)

    while True:
        before = len(found)
        for pid in list(found):
            climb(pid, [])
        for bond in bonds.values():
            kids = [p for p in tl["people"] if p["parents"] == bond["id"] and p["id"] in found]
            if len(kids) > 1:
                found.update(pair(bond))
        if len(found) == before:
            return found


def drawn(tl: dict, cluster_id: str) -> dict | None:
    """What the drawer reads for this cluster: the cluster, its events, the
    people it draws in record order, every bond touching them, and the events
    that date those people's deaths and those couples' ties. None when the
    timeline has no such cluster to draw."""
    cluster = next((c for c in tl["clusters"] if c["id"] == cluster_id), None)
    if cluster is None:
        return None
    events = {e["id"]: e for e in tl["events"]}
    own = [events[i] for i in cluster["event_ids"]]
    who = cast(tl, own)
    people = [p for p in tl["people"] if p["id"] in who]
    bonds = [b for b in tl["pair_bonds"] if {b["person_a"], b["person_b"]} & who]
    couples = {
        frozenset((b["person_a"], b["person_b"]))
        for b in bonds
        if None not in (b["person_a"], b["person_b"])
    }
    also = [
        e
        for e in tl["events"]
        if e["id"] in {p["death_event"] for p in people}
        or frozenset((e.get("person"), e.get("spouse"))) in couples
    ]
    return {
        "cluster": pick(cluster, CLUSTER_FIELDS),
        "events": [pick(e, EVENT_FIELDS) for e in own + also],
        "people": [pick(p, PERSON_FIELDS) for p in people],
        "bonds": [pick(b, BOND_FIELDS) for b in bonds],
    }


def digest(tl: dict, cluster: dict, events: list[dict]) -> str:
    """What a play was told from and is drawn with: what the coach is shown of
    the cluster, its own title, what the drawer reads for it, and the play
    prompt, so a tuned prompt tells it again."""
    told = {
        "prompt": prompts.PLAY_BY_PLAY_PROMPT,
        "about": told_about(cluster, events),
        "title": cluster.get("title"),
        "drawn": drawn(tl, str(cluster["id"])),
    }
    return hashlib.sha256(json.dumps(told, sort_keys=True).encode()).hexdigest()


def digests(data: DiagramData, tl: dict) -> dict[str, str]:
    """Each cluster's digest as a play told now would carry it; `tl` is the
    record's timeline, the drawer's own input."""
    return {
        str(c["id"]): digest(tl, c, events_of(data, c))
        for c in data.clusters
        if isinstance(c, dict)
    }


class Untellable(Exception):
    """The coach did not tell the case: no call at all, or none the cluster bore
    out in every try. The page is told so in plain words (R-0182)."""

    def __init__(self, why: str):
        super().__init__("untold: The coach couldn't tell this one; try again.")
        self.why = why


class PlayTurn:
    """One cluster in, one told case out."""

    def __init__(
        self,
        data: DiagramData,
        cluster: dict,
        *,
        discussion: Discussion | None = None,
        model: CoachModel | None = None,
    ):
        self.data = data
        self.cluster = cluster
        self.discussion = discussion
        self.turn_id = uuid.uuid4().hex
        self.model = model or CoachModel(timeout=ANTHROPIC_TIMEOUT)
        # Asked for in a session, the calls are charged to its owner like a turn's.
        if discussion is not None:
            self.model = Metered(
                self.model, discussion.user_id, discussion.diagram_id, self.turn_id
            )

    @classmethod
    def stored(cls, data: DiagramData, cluster_id: str, **kwargs) -> "PlayTurn":
        for cluster in data.clusters:
            if isinstance(cluster, dict) and str(cluster.get("id")) == str(cluster_id):
                return cls(data, cluster, **kwargs)
        raise ValueError(f"No cluster {cluster_id!r} in the record")

    @property
    def events(self) -> list[dict]:
        return events_of(self.data, self.cluster)

    def run(self) -> dict:
        events = self.events
        if not events:
            raise ValueError(f"Cluster {self.cluster['id']} has no events to play")
        wrong = faults(self.data)
        if wrong:
            raise RecordFault(f"record fault: {'; '.join(wrong)}. Correct the record first.")
        about = told_about(self.cluster, events)
        self.digest = digest(build_timeline(self.data), self.cluster, events)
        kept = self._kept()
        if kept is not None:
            return reply(kept)
        prompt = prompts.PLAY_BY_PLAY_PROMPT.format(**about)
        system = prompts.get_agent_prompt(record=recordtext.render(self.data))
        messages = [{"role": "user", "content": prompt}]
        told = self._tell(system, messages, events)
        return reply(
            self._persist(
                text=told.point,
                cluster_id=told.cluster_id,
                told_case=told.asdict(),
                turn_id=self.turn_id,
            )
        )

    def _kept(self) -> Statement | None:
        """The newest play of this diagram told from the same cluster contents,
        in this session: one from another session is copied into this one, with
        no turn of its own since nothing was called."""
        if self.discussion is None:
            return None
        kept = (
            Statement.query.join(Discussion)
            .filter(
                Discussion.diagram_id == self.discussion.diagram_id,
                Statement.kind == StatementKind.Play,
                Statement.cluster_id == str(self.cluster["id"]),
                Statement.digest == self.digest,
            )
            .order_by(Statement.id.desc())
            .first()
        )
        if kept is None or kept.discussion_id == self.discussion.id:
            return kept
        return self._persist(
            text=kept.text, cluster_id=kept.cluster_id, told_case=kept.told_case
        )

    def _tell(self, system: str, messages: list[dict], events: list[dict]) -> Case:
        try:
            return self._tries(system, messages, events)
        except Untellable as untellable:
            self._observe(
                ObservationKind.PlayFailed,
                {"why": untellable.why, "reason": tuning.reason(untellable.why)},
            )
            raise
        finally:
            # every call is charged, the ones that told nothing too
            db.session.commit()

    def _tries(self, system: str, messages: list[dict], events: list[dict]) -> Case:
        for attempt in range(1, TRIES + 1):
            turn = self._call(system, messages)
            call = next((c for c in turn.calls if c.name == Tool.PlayByPlay), None)
            if call is None:
                # an answer in words: asked again for the one call it must make
                _log.info("Play answered in words; asked for the call")
                self._observe(
                    ObservationKind.PlayRefused,
                    {"attempt": attempt, "reason": "answered in words, not the tool"},
                )
                messages = messages + [
                    {"role": "assistant", "content": turn.blocks},
                    {"role": "user", "content": ASK},
                ]
                continue
            try:
                return Case.told(call.args, self.cluster, events)
            except Untold as untold:
                _log.info(f"Case handed back: {untold}")
                self._observe(
                    ObservationKind.PlayRefused,
                    {
                        "attempt": attempt,
                        "untold": str(untold),
                        "reason": tuning.reason(str(untold)),
                    },
                )
                messages = messages + [
                    {"role": "assistant", "content": turn.blocks},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": call.id,
                                "content": str(untold),
                                "is_error": True,
                            }
                        ],
                    },
                ]
        raise Untellable(f"not told in {TRIES} tries")

    def _observe(self, kind: ObservationKind, detail: dict) -> None:
        """Kept for the tuning queue; a play asked for outside a session belongs
        to no record, so it keeps nothing."""
        if self.discussion is not None:
            db.session.add(
                Observation(
                    diagram_id=self.discussion.diagram_id,
                    turn_id=self.turn_id,
                    kind=kind,
                    detail=detail,
                )
            )

    def _call(self, system: str, messages: list[dict]):
        words = self.model.turn(system, messages, [tool()])
        while True:
            try:
                next(words)
            except StopIteration as stop:
                return stop.value
            except anthropic.APIStatusError as refused:
                # the API turned the request away; a server fault there stays a 500
                if refused.status_code >= 500:
                    raise
                raise Untellable(f"the API refused the call: {refused.status_code} {refused.message}") from refused

    def _persist(self, turn_id: str | None = None, **told) -> Statement:
        """The play as a message; outside a session it is kept nowhere."""
        statement = Statement(
            kind=StatementKind.Play, digest=self.digest, turn_id=turn_id, **told
        )
        if self.discussion is None:
            return statement
        statement.discussion_id = self.discussion.id
        statement.speaker = self.discussion.chat_ai_speaker
        statement.order = self.discussion.next_order()
        db.session.add(statement)
        db.session.flush()
        if turn_id:
            turnstore.save(turn_id, self.discussion.id, [turnstore.done(statement.id)])
        db.session.commit()
        return statement


def reply(statement: Statement) -> dict:
    return {
        "kind": StatementKind.Play.value,
        "cluster_id": statement.cluster_id,
        "statement": statement.text,
        "statement_id": statement.id,
        "case": statement.told_case,
        "digest": statement.digest,
    }
