"""The coach's tools: read the record, change it, show it.

Three kinds, and the record is the only truth under all of them. A READ answers
from stored data. An EDIT is applied the moment it is called, through
`record.apply`, so the picture and the list move while the coach is still
talking. A SHOW names record ids and a view kind, and every id must resolve or
the call fails with words the model can act on [Oracle: R-0075].
"""

import enum
import logging

from btcopilot.personal import clusters, record, views
from btcopilot.personal.models import Author, Change
from btcopilot.personal.recordtext import date_text, event_line, person_line
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram
from btcopilot.schema import (
    ClusterSource,
    DateCertainty,
    DiagramData,
    EventKind,
    ItemKind,
    PersonKind,
    RelationshipKind,
    VariableShift,
)

_log = logging.getLogger(__name__)

SHIFTS = ("anxiety", "symptom", "functioning")


class ToolName(enum.StrEnum):
    ReadPeople = "read_people"
    ReadEvents = "read_events"
    EditPerson = "edit_person"
    EditPairBond = "edit_pair_bond"
    EditEvent = "edit_event"
    EditCluster = "edit_cluster"
    Remove = "remove"
    Undo = "undo"
    Show = "show"


EDITS = (
    ToolName.EditPerson,
    ToolName.EditPairBond,
    ToolName.EditEvent,
    ToolName.EditCluster,
    ToolName.Remove,
    ToolName.Undo,
)


def _values(cls) -> list[str]:
    return [member.value for member in cls]


def _enum_param(cls, description: str) -> dict:
    return {"type": "string", "enum": _values(cls), "description": description}


SCHEMAS = [
    {
        "name": ToolName.ReadPeople.value,
        "description": "Everyone in the record, with their ids, names and parents.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": ToolName.ReadEvents.value,
        "description": (
            "Events in the record, in date order. Narrow by a date span, one "
            "person, or one cluster; with no filter it returns everything."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "YYYY-MM-DD"},
                "end": {"type": "string", "description": "YYYY-MM-DD"},
                "person": {"type": "integer"},
                "cluster": {"type": "string"},
            },
        },
    },
    {
        "name": ToolName.EditPerson.value,
        "description": (
            "Add a person, or change one. Give id to change an existing person; "
            "leave it out to add one."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "last_name": {"type": "string"},
                "gender": _enum_param(PersonKind, "The person's gender."),
                "parents": {
                    "type": "integer",
                    "description": "The id of the pair bond this person was born into.",
                },
            },
        },
    },
    {
        "name": ToolName.EditPairBond.value,
        "description": "Add or change the bond between two people.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "person_a": {"type": "integer"},
                "person_b": {"type": "integer"},
                "married": {"type": "boolean"},
            },
        },
    },
    {
        "name": ToolName.EditEvent.value,
        "description": (
            "Add an event, or change one. Give id to change an existing event; "
            "leave it out to add one. A shift carries the variables that moved."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "kind": _enum_param(EventKind, "What kind of event this is."),
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                "date_certainty": _enum_param(
                    DateCertainty, "How sure the date is. Default certain."
                ),
                "description": {"type": "string"},
                "person": {"type": "integer"},
                "spouse": {"type": "integer"},
                "child": {"type": "integer"},
                "anxiety": _enum_param(VariableShift, "Which way anxiety moved."),
                "symptom": _enum_param(VariableShift, "Which way symptom moved."),
                "functioning": _enum_param(
                    VariableShift, "Which way functioning moved."
                ),
                "relationship": _enum_param(
                    RelationshipKind, "The relationship move this event is."
                ),
                "relationship_targets": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "The people the move is aimed at.",
                },
                "relationship_triangles": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "The third people the move triangles in.",
                },
            },
        },
    },
    {
        "name": ToolName.EditCluster.value,
        "description": (
            "Group events into a named cluster, or rename one. You may group and "
            "name; you may never name an event that is not in the record."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "summary": {"type": "string"},
                "event_ids": {"type": "array", "items": {"type": "integer"}},
            },
        },
    },
    {
        "name": ToolName.Remove.value,
        "description": "Remove one item from the record.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_kind": _enum_param(ItemKind, "What kind of item to remove."),
                "item_id": {"type": "string"},
            },
            "required": ["item_kind", "item_id"],
        },
    },
    {
        "name": ToolName.Undo.value,
        "description": (
            "Put back what the last turn changed. Use it when the user says to "
            "undo, or that you got it wrong and should reverse it."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": ToolName.Show.value,
        "description": (
            "Aim the picture at something in the record. Every id must be one "
            "the record holds."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": _enum_param(views.ViewKind, "Which view to draw."),
                "persons": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "triangle: exactly three people.",
                },
                "start": {"type": "string", "description": "span: YYYY-MM-DD"},
                "end": {"type": "string", "description": "span: YYYY-MM-DD"},
                "event_a": {"type": "integer", "description": "compare: one event."},
                "event_b": {"type": "integer", "description": "compare: the other."},
                "events": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "sequence: the events in the order to step.",
                },
                "cluster": {"type": "string", "description": "cluster: its id."},
            },
            "required": ["kind"],
        },
    },
]


class ToolError(Exception):
    """A tool call the record refused. The model sees the words and retries."""


class Toolbox:
    """One turn's tools, bound to the diagram they read and write."""

    def __init__(
        self,
        diagram_id: int,
        turn_id: str,
        *,
        user_id: int | None = None,
        session_id: str | None = None,
    ):
        self.diagram_id = diagram_id
        self.turn_id = turn_id
        self.user_id = user_id
        self.session_id = session_id
        self.deltas: list[dict] = []
        self.views: list[dict] = []

    @property
    def data(self) -> DiagramData:
        return db.session.get(Diagram, self.diagram_id).get_diagram_data()

    def call(self, name: str, args: dict) -> tuple[str, dict | None]:
        """Run one tool. Returns what the model reads and what the page sees."""
        try:
            tool = ToolName(name)
        except ValueError:
            raise ToolError(f"There is no tool called {name}")
        handler = getattr(self, f"_{tool.value}")
        return handler(args)

    # ── READ ────────────────────────────────────────────────────────────────

    def _read_people(self, args: dict) -> tuple[str, None]:
        rows = [p for p in self.data.people if isinstance(p, dict) and p.get("id")]
        return ("\n".join(person_line(p) for p in rows) or "No one yet.", None)

    def _read_events(self, args: dict) -> tuple[str, None]:
        data = self.data
        events = [e for e in data.events if isinstance(e, dict) and e.get("id")]
        if args.get("cluster"):
            cluster = self._cluster(data, args["cluster"])
            wanted = set(cluster.get("eventIds") or [])
            events = [e for e in events if e["id"] in wanted]
        if args.get("person") is not None:
            person = int(args["person"])
            events = [
                e
                for e in events
                if person
                in {e.get("person"), e.get("spouse"), e.get("child")}
                | set(e.get("relationshipTargets") or [])
                | set(e.get("relationshipTriangles") or [])
            ]
        if args.get("start"):
            events = [
                e for e in events if (date_text(e.get("dateTime")) or "") >= args["start"]
            ]
        if args.get("end"):
            events = [
                e for e in events if (date_text(e.get("dateTime")) or "") <= args["end"]
            ]
        events.sort(key=lambda e: (date_text(e.get("dateTime")) or "", e["id"]))
        return ("\n".join(event_line(e) for e in events) or "No events.", None)

    # ── EDIT ────────────────────────────────────────────────────────────────

    def _edit_person(self, args: dict) -> tuple[str, dict]:
        fields = {}
        for key in ("name", "last_name", "parents"):
            if args.get(key) is not None:
                fields[key] = args[key]
        if args.get("gender"):
            fields["gender"] = PersonKind(args["gender"]).value
        return self._write(ItemKind.Person, args.get("id"), fields)

    def _edit_pair_bond(self, args: dict) -> tuple[str, dict]:
        data = self.data
        fields = {}
        for key in ("person_a", "person_b"):
            if args.get(key) is not None:
                fields[key] = self._person(data, args[key])
        if args.get("married") is not None:
            fields["married"] = bool(args["married"])
        return self._write(ItemKind.PairBond, args.get("id"), fields)

    def _edit_event(self, args: dict) -> tuple[str, dict]:
        data = self.data
        fields = {}
        if args.get("kind"):
            fields["kind"] = EventKind(args["kind"]).value
        if args.get("date"):
            fields["dateTime"] = args["date"]
        if args.get("end_date"):
            fields["endDateTime"] = args["end_date"]
        fields["dateCertainty"] = DateCertainty(
            args.get("date_certainty") or DateCertainty.Certain
        ).value
        if args.get("description"):
            fields["description"] = args["description"]
        for key in ("person", "spouse", "child"):
            if args.get(key) is not None:
                fields[key] = self._person(data, args[key])
        for key in SHIFTS:
            if args.get(key):
                fields[key] = VariableShift(args[key]).value
        if args.get("relationship"):
            fields["relationship"] = RelationshipKind(args["relationship"]).value
        for arg, key in (
            ("relationship_targets", "relationshipTargets"),
            ("relationship_triangles", "relationshipTriangles"),
        ):
            if args.get(arg) is not None:
                fields[key] = [self._person(data, p) for p in args[arg]]
        if args.get("id") is None and not args.get("kind"):
            raise ToolError("A new event needs a kind")
        return self._write(ItemKind.Event, args.get("id"), fields)

    def _edit_cluster(self, args: dict) -> tuple[str, dict]:
        data = self.data
        # A cluster named in conversation is the user's own grouping: automatic
        # re-detection yields to it rather than regrouping it away.
        fields = {"source": ClusterSource.User.value}
        if args.get("name"):
            fields["name"] = args["name"]
            fields["title"] = args["name"]
        fields["summary"] = args.get("summary") or ""
        if args.get("event_ids") is not None:
            events = [self._event(data, e) for e in args["event_ids"]]
            if not events:
                raise ToolError("A cluster needs at least one event")
            fields["eventIds"] = events
            dates = sorted(
                date
                for e in data.events
                if e.get("id") in set(events)
                for date in [date_text(e.get("dateTime"))]
                if date
            )
            if dates:
                fields["startDate"], fields["endDate"] = dates[0], dates[-1]
        item_id = args.get("id")
        if item_id is not None and str(item_id) not in {
            str(c.get("id")) for c in data.clusters
        }:
            raise ToolError(f"No cluster {item_id} in the record")
        return self._write(ItemKind.Cluster, item_id, fields)

    def _remove(self, args: dict) -> tuple[str, dict]:
        kind = ItemKind(args["item_kind"])
        item_id = args["item_id"]
        if not self._exists(self.data, kind, item_id):
            raise ToolError(f"No {kind.value} {item_id} in the record")
        change = self._apply(
            [{"item_kind": kind.value, "item_id": item_id, "field": None, "after": None}]
        )
        return (f"Removed {kind.value} {item_id}.", self._patch(change))

    def _undo(self, args: dict) -> tuple[str, dict]:
        previous = self._previous_turn()
        if previous is None:
            raise ToolError("There is nothing before this to put back")
        try:
            change = record.undo(
                self.diagram_id,
                previous,
                author=Author.Coach,
                user_id=self.user_id,
                session_id=self.session_id,
            )
        except record.Conflict as e:
            raise ToolError(
                "That has already been changed since, so it cannot be put back "
                f"as it was: {e}"
            )
        self.deltas.extend(change.deltas)
        return ("Put back what the last turn changed.", self._patch(change))

    def _previous_turn(self) -> str | None:
        """The turn before this one on this diagram — what 'put that back' means."""
        last = (
            Change.query.filter(
                Change.diagram_id == self.diagram_id,
                Change.turn_id != self.turn_id,
                Change.turn_id.notlike("undo:%"),
            )
            .order_by(Change.id.desc())
            .first()
        )
        return last.turn_id if last else None

    # ── SHOW ────────────────────────────────────────────────────────────────

    def _show(self, args: dict) -> tuple[str, dict]:
        try:
            view = views.build(
                views.ViewKind(args["kind"]),
                {k: v for k, v in args.items() if k != "kind"},
                self.data,
            )
        except ValueError as e:
            raise ToolError(str(e))
        self.views.append(view)
        return (f"Showing the {view['kind']}.", {"view": view})

    # ── the record itself ───────────────────────────────────────────────────

    def _person(self, data: DiagramData, person_id) -> int:
        if not self._exists(data, ItemKind.Person, person_id):
            raise ToolError(f"No person {person_id} in the record")
        return int(person_id)

    def _event(self, data: DiagramData, event_id) -> int:
        if not self._exists(data, ItemKind.Event, event_id):
            raise ToolError(f"No event {event_id} in the record")
        return int(event_id)

    def _cluster(self, data: DiagramData, cluster_id: str) -> dict:
        for cluster in data.clusters:
            if str(cluster.get("id")) == str(cluster_id):
                return cluster
        raise ToolError(f"No cluster {cluster_id} in the record")

    def _exists(self, data: DiagramData, kind: ItemKind, item_id) -> bool:
        collection = {
            ItemKind.Person: data.people,
            ItemKind.Event: data.events,
            ItemKind.PairBond: data.pair_bonds,
            ItemKind.Cluster: data.clusters,
            ItemKind.Emotion: data.emotions,
        }[kind]
        return any(str(i.get("id")) == str(item_id) for i in collection)

    def _next_id(self, data: DiagramData) -> int:
        used = [
            item["id"]
            for collection in (data.people, data.events, data.pair_bonds, data.emotions)
            for item in collection
            if isinstance(item, dict) and isinstance(item.get("id"), int)
        ]
        return max(used + [data.lastItemId or 0]) + 1

    def _next_cluster_id(self, data: DiagramData) -> str:
        return clusters.next_id({str(c.get("id")) for c in data.clusters})

    def _write(self, kind: ItemKind, item_id, fields: dict) -> tuple[str, dict]:
        if not fields:
            raise ToolError(f"Nothing to change on that {kind.value}")
        data = self.data
        new = item_id is None
        if new:
            if kind is ItemKind.Cluster:
                item_id = self._next_cluster_id(data)
            else:
                item_id = self._next_id(data)
        elif not self._exists(data, kind, item_id):
            raise ToolError(f"No {kind.value} {item_id} in the record")

        deltas = [
            {"item_kind": kind.value, "item_id": item_id, "field": field, "after": value}
            for field, value in fields.items()
        ]
        if new and kind is not ItemKind.Cluster:
            deltas.append(
                {
                    "item_kind": ItemKind.Diagram.value,
                    "item_id": None,
                    "field": "lastItemId",
                    "after": item_id,
                }
            )
        change = self._apply(deltas)
        verb = "Added" if new else "Changed"
        return (f"{verb} {kind.value} {item_id}.", self._patch(change))

    def _apply(self, deltas: list[dict]):
        change = record.apply(
            self.diagram_id,
            deltas,
            author=Author.Coach,
            turn_id=self.turn_id,
            user_id=self.user_id,
            session_id=self.session_id,
        )
        self.deltas.extend(change.deltas)
        return change

    def _patch(self, change) -> dict:
        return {"deltas": change.deltas, "turn_id": change.turn_id}
