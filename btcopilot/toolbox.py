"""The coach's tools: read the record, change it, show it.

Three kinds, and the record is the only truth under all of them. A READ answers
from stored data. An EDIT is applied the moment it is called, through
`record.apply`, so the picture and the list move while the coach is still
talking. A SHOW names record ids and a view kind, and every id must resolve or
the call fails with words the model can act on [Oracle: R-0075].
"""

import datetime
import enum
import logging

from btcopilot import clusters, prompts, record, views
from btcopilot.models import Author, Change, Discussion, Statement
from btcopilot.recordtext import (
    change_line,
    date_text,
    event_line,
    on_map,
    person_line,
    question_line,
    question_order,
    version_line,
)
from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.schema import (
    MIN_CLUSTER_EVENTS,
    ClusterSource,
    DateCertainty,
    ITEM_COLLECTIONS,
    DiagramData,
    EventKind,
    ItemKind,
    PersonKind,
    QuestionKind,
    QuestionOutcome,
    QuestionState,
    RelationshipKind,
    VariableShift,
)

_log = logging.getLogger(__name__)

SHIFTS = ("anxiety", "symptom", "functioning")


class ToolName(enum.StrEnum):
    ReadPeople = "read_people"
    ReadEvents = "read_events"
    ReadNotes = "read_notes"
    ReadChanges = "read_changes"
    EditPerson = "edit_person"
    EditPairBond = "edit_pair_bond"
    EditEvent = "edit_event"
    EditCluster = "edit_cluster"
    Remove = "remove"
    Undo = "undo"
    Show = "show"
    AddQuestion = "add_question"
    SetQuestion = "set_question"
    ReadQuestions = "read_questions"


READS = (
    ToolName.ReadPeople,
    ToolName.ReadEvents,
    ToolName.ReadNotes,
    ToolName.ReadChanges,
    ToolName.ReadQuestions,
)

CHANGES_SHOWN = 10

# The kinds of thing a remove call can name. A question is closed instead.
REMOVABLE = {kind.value: kind for kind in ITEM_COLLECTIONS if kind is not ItemKind.Question}

# The tools that can change something already in the record.
CHANGES = (
    ToolName.EditPerson,
    ToolName.EditPairBond,
    ToolName.EditEvent,
    ToolName.EditCluster,
    ToolName.Remove,
    ToolName.SetQuestion,
)

EDITS = (
    ToolName.EditPerson,
    ToolName.EditPairBond,
    ToolName.EditEvent,
    ToolName.EditCluster,
    ToolName.Remove,
    ToolName.Undo,
)


def _enum_value(value):
    return getattr(value, "value", value)


def _values(cls) -> list[str]:
    return [member.value for member in cls]


def _enum_param(cls, description: str) -> dict:
    return {"type": "string", "enum": _values(cls), "description": description}


VERSION = {
    "type": "integer",
    "description": (
        "The record version your last look at this item showed: the number at "
        "the end of every read, or on the map. Needed to change or remove "
        "something already in the record; not needed to add."
    ),
}


def schemas() -> list[dict]:
    """The coach's tool schemas. What a field means clinically comes from
    `prompts.tool_meanings()`, which fdserver overrides (R-0305); everything
    here is the shape of the value, not what it means to a clinician."""
    means = prompts.tool_meanings()
    return [
        {
            "name": ToolName.ReadPeople.value,
            "description": "Everyone in the record, with their ids, names and parents.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": ToolName.ReadEvents.value,
            "description": (
                "Events in the record, in date order. Narrow by ids, a date span, "
                "one person, or one cluster; with no filter it returns everything. "
                "Ask for the words to see what the user said that each event came "
                "from, and for the notes to see them in full."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ids": {"type": "array", "items": {"type": "integer"}},
                    "start": {"type": "string", "description": "YYYY-MM-DD"},
                    "end": {"type": "string", "description": "YYYY-MM-DD"},
                    "person": {"type": "integer"},
                    "cluster": {"type": "string"},
                    "words": {"type": "boolean"},
                    "notes": {"type": "boolean"},
                },
            },
        },
        {
            "name": ToolName.ReadNotes.value,
            "description": means[prompts.ToolText.ReadNotes],
            "input_schema": {
                "type": "object",
                "properties": {
                    "event": {
                        "type": "integer",
                        "description": "One event's id; leave it out for every event that has notes.",
                    },
                },
            },
        },
        {
            "name": ToolName.ReadChanges.value,
            "description": (
                "The latest changes to the record, newest first: the version each "
                "made, who made it, and what it set."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": f"How many; {CHANGES_SHOWN} if left out.",
                    },
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
                    "version": VERSION,
                    "name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "gender": _enum_param(PersonKind, "The person's gender."),
                    "parents": {
                        "type": "integer",
                        "description": means[prompts.ToolText.Parents],
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
                    "version": VERSION,
                    "person_a": {
                        "type": "integer",
                        "description": means[prompts.ToolText.PersonA],
                    },
                    "person_b": {
                        "type": "integer",
                        "description": means[prompts.ToolText.PersonB],
                    },
                    "married": {"type": "boolean"},
                },
            },
        },
        {
            "name": ToolName.EditEvent.value,
            "description": (
                "Add an event, or change one. Give id to change an existing event; "
                "leave it out to add one."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "version": VERSION,
                    "kind": _enum_param(EventKind, means[prompts.ToolText.EventKind]),
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {
                        "type": "string",
                        "description": means[prompts.ToolText.EndDate],
                    },
                    "date_certainty": _enum_param(
                        DateCertainty,
                        "Certain for a date they stated, approximate for within a "
                        "year or so, unknown for a guess. Left out on a new event "
                        "it is unknown; left out on a change it stays as it is. "
                        "Never leave the date itself out: a vague date beats none.",
                    ),
                    "description": {
                        "type": "string",
                        "description": means[prompts.ToolText.Description],
                    },
                    "notes": {
                        "type": "string",
                        "description": means[prompts.ToolText.Notes],
                    },
                    "location": {
                        "type": "string",
                        "description": means[prompts.ToolText.Location],
                    },
                    "person": {
                        "type": "integer",
                        "description": means[prompts.ToolText.Person],
                    },
                    "spouse": {
                        "type": "integer",
                        "description": means[prompts.ToolText.Spouse],
                    },
                    "child": {
                        "type": "integer",
                        "description": means[prompts.ToolText.Child],
                    },
                    "anxiety": _enum_param(
                        VariableShift, means[prompts.ToolText.Anxiety]
                    ),
                    "symptom": _enum_param(
                        VariableShift, means[prompts.ToolText.Symptom]
                    ),
                    "functioning": _enum_param(
                        VariableShift, means[prompts.ToolText.Functioning]
                    ),
                    "relationship": _enum_param(
                        RelationshipKind, means[prompts.ToolText.Relationship]
                    ),
                    "relationship_targets": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": means[prompts.ToolText.RelationshipTargets],
                    },
                    "relationship_triangles": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": means[prompts.ToolText.RelationshipTriangles],
                    },
                },
            },
        },
        {
            "name": ToolName.EditCluster.value,
            "description": (
                "Group events into a named cluster, or rename one. A cluster holds "
                f"at least {MIN_CLUSTER_EVENTS} events. You may group and name; you "
                "may never name an event that is not in the record."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "version": VERSION,
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
                    "version": VERSION,
                },
                "required": ["item_kind", "item_id", "version"],
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
            "name": ToolName.AddQuestion.value,
            "description": (
                "Keep a question in the record: asked when you ask it in this "
                "reply, held when you keep it to ask later."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The question word for word, as the person reads it.",
                    },
                    "kind": _enum_param(QuestionKind, "Food for thought, or a fact to find."),
                    "state": {
                        "type": "string",
                        "enum": [QuestionState.Held.value, QuestionState.Asked.value],
                    },
                    "item_kind": {
                        "type": "string",
                        "enum": [kind.value for kind in record.QUESTION_LINKS],
                        "description": "What the question is about, with item_id; or neither.",
                    },
                    "item_id": {"type": "string"},
                    "asked_in": {
                        "type": "integer",
                        "description": (
                            "Only when told to: the number of the coach message in a "
                            "past session that asked it, word for word."
                        ),
                    },
                },
                "required": ["text", "kind", "state"],
            },
        },
        {
            "name": ToolName.SetQuestion.value,
            "description": "Mark a kept question asked, or close it saying how it ended.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "version": VERSION,
                    "state": {
                        "type": "string",
                        "enum": [QuestionState.Asked.value, QuestionState.Resolved.value],
                    },
                    "outcome": {
                        "type": "string",
                        "enum": [
                            outcome.value
                            for outcome in QuestionOutcome
                            if outcome is not QuestionOutcome.DeclinedByUser
                        ],
                        "description": "How it ended; only with resolved.",
                    },
                },
                "required": ["id", "version", "state"],
            },
        },
        {
            "name": ToolName.ReadQuestions.value,
            "description": (
                "The questions kept in the record: the open ones and the ones the "
                "person declined; with closed, every closed one and how it ended."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"closed": {"type": "boolean"}},
            },
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
    """A tool call the record refused. The model reads the reason and retries;
    `plain` says why to the person reading the thread, with no ids."""

    def __init__(self, reason: str, plain: str):
        super().__init__(reason)
        self.plain = plain


SMALL_CLUSTER = f"A cluster needs at least {MIN_CLUSTER_EVENTS} events."
GONE = record.GONE


class Toolbox:
    """One turn's tools, bound to the diagram they read and write."""

    def __init__(
        self,
        diagram_id: int,
        turn_id: str,
        *,
        user_id: int | None = None,
        session_id: str | None = None,
        author: Author = Author.Coach,
        statement_id: int | None = None,
    ):
        self.diagram_id = diagram_id
        self.turn_id = turn_id
        self.user_id = user_id
        self.session_id = session_id
        self.author = author
        self.statement_id = statement_id
        self.deltas: list[dict] = []
        self.views: list[dict] = []
        # The record versions this turn's own writes made, undo included.
        self.versions: set[int] = set()

    @property
    def diagram(self) -> Diagram:
        """Read again from the database every time: another writer may have
        committed since this turn last looked."""
        diagram = db.session.get(Diagram, self.diagram_id)
        db.session.refresh(diagram)
        return diagram

    @property
    def data(self) -> DiagramData:
        return self.diagram.get_diagram_data()

    def call(self, name: str, args: dict) -> tuple[str, dict | None]:
        """Run one tool. Returns what the model reads and what the page sees.
        A change to something already in the record names the version it was
        based on, and is refused if anyone else has written since."""
        try:
            tool = ToolName(name)
        except ValueError:
            raise ToolError(f"There is no tool called {name}", "There is no such tool.")
        if tool in CHANGES and (tool is ToolName.Remove or args.get("id") is not None):
            self._fresh(args.get("version"))
        text, event = getattr(self, f"_{tool.value}")(args)
        if tool in READS:
            text = f"{text}\n\n{version_line(self.diagram.version)}"
        return text, event

    def _fresh(self, version) -> None:
        if version is None:
            raise ToolError(
                "Say which record version you are changing: the number at the end "
                "of your last read, or on the map",
                "It did not say which version of the record it had read.",
            )
        now = self.diagram.version
        own = self.versions | {
            row.version
            for row in Change.query.filter(
                Change.diagram_id == self.diagram_id,
                Change.turn_id == self.turn_id,
                Change.version > int(version),
            )
        }
        if set(range(int(version) + 1, now + 1)) - own:
            raise ToolError(
                f"The record has changed since version {version}; it is at {now} "
                "now. Read what you are changing again, then change it with the "
                "new version",
                "The record had changed since it was read; read it again.",
            )

    # ── READ ────────────────────────────────────────────────────────────────

    def _read_people(self, args: dict) -> tuple[str, None]:
        rows = [p for p in self.data.people if isinstance(p, dict) and p.get("id")]
        return ("\n".join(person_line(p) for p in rows) or "No one yet.", None)

    def _read_events(self, args: dict) -> tuple[str, None]:
        data = self.data
        events = [e for e in data.events if isinstance(e, dict) and e.get("id")]
        if args.get("ids") is not None:
            wanted = {self._event(data, e) for e in args["ids"]}
            events = [e for e in events if e["id"] in wanted]
        if args.get("cluster"):
            cluster = self._cluster(data, args["cluster"])
            wanted = set(cluster.get("eventIds") or [])
            events = [e for e in events if e["id"] in wanted]
        if args.get("person") is not None:
            events = [e for e in events if record.involves(e, args["person"])]
        if args.get("start"):
            events = [
                e for e in events if (date_text(e.get("dateTime")) or "") >= args["start"]
            ]
        if args.get("end"):
            events = [
                e for e in events if (date_text(e.get("dateTime")) or "") <= args["end"]
            ]
        events.sort(key=lambda e: (date_text(e.get("dateTime")) or "", e["id"]))
        words = self._words({e["id"] for e in events}) if args.get("words") else {}
        lines = []
        for e in events:
            lines.append(event_line(e))
            if e["id"] in words:
                lines.append(f"  words: {words[e['id']]}")
            if args.get("notes") and e.get("notes"):
                lines.append(f"  notes: {e['notes']}")
        return ("\n".join(lines) or "No events.", None)

    def _words(self, event_ids: set[int]) -> dict[int, str]:
        """What the user said in the turn that first wrote each event."""
        turns = {}
        rows = Change.query.filter_by(diagram_id=self.diagram_id).order_by(Change.id)
        for row in rows:
            for delta in row.deltas:
                event = delta["item_id"]
                if delta["item_kind"] == ItemKind.Event.value and int(event) in event_ids:
                    turns.setdefault(int(event), row.turn_id)
        said = {
            s.turn_id: s.text
            for s in Statement.query.join(Discussion).filter(
                Statement.turn_id.in_(set(turns.values())),
                Statement.speaker_id == Discussion.chat_user_speaker_id,
            )
        }
        return {event: said[turn] for event, turn in turns.items() if turn in said}

    def _read_notes(self, args: dict) -> tuple[str, None]:
        data = self.data
        events = [e for e in data.events if isinstance(e, dict) and e.get("notes")]
        if args.get("event") is not None:
            wanted = self._event(data, args["event"])
            events = [e for e in data.events if e.get("id") == wanted]
        lines = [f"{e['id']}: {e.get('notes') or 'no notes'}" for e in events]
        return ("\n".join(lines) or "No event has notes.", None)

    def _read_questions(self, args: dict) -> tuple[str, None]:
        shown = [q for q in self.data.questions if args.get("closed") or on_map(q)]
        lines = [question_line(q) for q in sorted(shown, key=question_order)]
        return ("\n".join(lines) or "No questions.", None)

    def _read_changes(self, args: dict) -> tuple[str, None]:
        rows = (
            Change.query.filter_by(diagram_id=self.diagram_id)
            .order_by(Change.id.desc())
            .limit(int(args.get("limit") or CHANGES_SHOWN))
        )
        return ("\n".join(change_line(r) for r in rows) or "No changes yet.", None)

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
        if args.get("id") is None and len(fields.keys() & {"person_a", "person_b"}) == 1:
            known = fields.get("person_a", fields.get("person_b"))
            missing = "person_b" if "person_a" in fields else "person_a"
            fields[missing] = self._generic(known, prompts.Role.Partner)
        return self._write(ItemKind.PairBond, args.get("id"), fields)

    #: The parent a birth names second, worked out from the one it names first.
    OTHER_PARENT = {
        PersonKind.Male.value: prompts.Role.Mother,
        PersonKind.Female.value: prompts.Role.Father,
    }
    ROLE_GENDER = {
        prompts.Role.Father: PersonKind.Male,
        prompts.Role.Mother: PersonKind.Female,
        prompts.Role.Partner: PersonKind.Unknown,
    }

    def _generic(self, other_id: int, role) -> int:
        """A parent or partner nobody named, added as a person so the bond has
        two sides and the birth has two parents (R-0325 rules 9 and 10). What
        they are called comes from the overridable prompts."""
        other = self._find_person(other_id)
        name = prompts.generic_name(other.get("name") or "someone", role)
        key = record.generic_key({"name": name})
        for person in self.data.people:
            if record.generic_key(person) == key:
                return int(person["id"])
        _, patch = self._write(
            ItemKind.Person,
            None,
            {"name": name, "gender": self.ROLE_GENDER[role].value},
        )
        return int(patch["deltas"][0]["item_id"])

    def _find_person(self, person_id) -> dict:
        for person in self.data.people:
            if str(person.get("id")) == str(person_id):
                return person
        raise ToolError(f"No person {person_id} in the record", views.NO_PERSON)

    def _edit_event(self, args: dict) -> tuple[str, dict]:
        data = self.data
        start = len(self.deltas)
        new = args.get("id") is None
        fields = {}
        if args.get("kind"):
            fields["kind"] = EventKind(args["kind"]).value
        if args.get("date"):
            fields["dateTime"] = args["date"]
        if args.get("end_date"):
            fields["endDateTime"] = args["end_date"]
        if args.get("date_certainty"):
            fields["dateCertainty"] = DateCertainty(args["date_certainty"]).value
        elif new:
            fields["dateCertainty"] = DateCertainty.Unknown.value
        if args.get("description"):
            fields["description"] = args["description"]
        for key in ("notes", "location"):
            if args.get(key):
                fields[key] = args[key]
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
        if new and not args.get("kind"):
            raise ToolError(
                "A new event needs a kind", "A new event needs to say what kind it is."
            )
        # An adoption invents no parent: adoptive parents are not yet designed
        # (R-0345), and a generic one would be named by biological role (R-0430).
        if (
            fields.get("kind") == EventKind.Birth.value
            and fields.get("person") is not None
            and fields.get("spouse") is None
            and fields.get("child") is not None
        ):
            known = self._find_person(fields["person"])
            role = self.OTHER_PARENT.get(
                _enum_value(known.get("gender")), prompts.Role.Partner
            )
            fields["spouse"] = self._generic(fields["child"], role)
        text, patch = self._write(ItemKind.Event, args.get("id"), fields)
        event_id = patch["deltas"][0]["item_id"]
        event = next(e for e in self.data.events if str(e.get("id")) == str(event_id))
        self._married(event)
        self._born_to(event)
        return text, {"deltas": self.deltas[start:], "turn_id": self.turn_id}

    def _bond(self, a: int, b: int) -> dict | None:
        pair = record.pair({"person_a": a, "person_b": b})
        return next((x for x in self.data.pair_bonds if record.pair(x) == pair), None)

    def _married(self, event: dict):
        """A marriage sets married on the couple's bond, adding the bond when
        they have none yet, so the picture draws them married (R-0430)."""
        a, b = event.get("person"), event.get("spouse")
        if _enum_value(event.get("kind")) != EventKind.Married.value or None in (a, b):
            return
        bond = self._bond(a, b)
        if bond is None:
            self._write(
                ItemKind.PairBond, None, {"person_a": a, "person_b": b, "married": True}
            )
        elif bond.get("married") is not True:
            self._write(ItemKind.PairBond, bond["id"], {"married": True})

    def _born_to(self, event: dict):
        """A birth naming both parents makes the child the offspring of their
        bond, adding the bond when they have none yet, so the child hangs from
        the parents in the picture (R-0438)."""
        a, b = event.get("person"), event.get("spouse")
        if (
            _enum_value(event.get("kind")) != EventKind.Birth.value
            or None in (a, b)
            or event.get("child") is None
            or self._find_person(event["child"]).get("parents") is not None
        ):
            return
        bond = self._bond(a, b)
        if bond is None:
            _, made = self._write(ItemKind.PairBond, None, {"person_a": a, "person_b": b})
            bond_id = made["deltas"][0]["item_id"]
        else:
            bond_id = bond["id"]
        self._write(ItemKind.Person, event["child"], {"parents": bond_id})

    def _edit_cluster(self, args: dict) -> tuple[str, dict]:
        data = self.data
        if args.get("id") is None and args.get("event_ids") is None:
            raise ToolError(f"A new cluster needs {MIN_CLUSTER_EVENTS} events", SMALL_CLUSTER)
        # A cluster named in conversation is the user's own grouping: automatic
        # re-detection yields to it rather than regrouping it away.
        fields = {"source": ClusterSource.User.value}
        if args.get("name"):
            fields["name"] = args["name"]
            fields["title"] = args["name"]
        fields["summary"] = args.get("summary") or ""
        # The coach's sentence explained a grouping the user has now changed.
        fields["reason"] = ""
        if args.get("event_ids") is not None:
            events = [self._event(data, e) for e in args["event_ids"]]
            if len(events) < MIN_CLUSTER_EVENTS:
                raise ToolError(
                    f"A cluster needs at least {MIN_CLUSTER_EVENTS} events", SMALL_CLUSTER
                )
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
            raise ToolError(f"No cluster {item_id} in the record", GONE)
        return self._write(ItemKind.Cluster, item_id, fields)

    def _remove(self, args: dict) -> tuple[str, dict]:
        if args["item_kind"] == ItemKind.Question:
            raise ToolError(*record.NEVER_REMOVED)
        if args["item_kind"] not in REMOVABLE:
            raise ToolError(
                f"There is no kind of thing called {args['item_kind']}",
                "There is no such kind of thing to remove.",
            )
        kind = REMOVABLE[args["item_kind"]]
        item_id = args["item_id"]
        if not self._exists(self.data, kind, item_id):
            raise ToolError(f"No {kind.value} {item_id} in the record", GONE)
        change = self._apply(
            [{"item_kind": kind.value, "item_id": item_id, "field": None, "after": None}]
        )
        return (f"Removed {kind.value} {item_id}.", self._patch(change))

    def _undo(self, args: dict) -> tuple[str, dict]:
        previous = self._previous_turn()
        if previous is None:
            raise ToolError(
                "There is nothing before this to put back",
                "There is nothing before this to put back.",
            )
        try:
            change = record.undo(
                self.diagram_id,
                previous,
                author=self.author,
                user_id=self.user_id,
                session_id=self.session_id,
            )
        except record.Conflict as e:
            raise ToolError(
                "That has already been changed since, so it cannot be put back "
                f"as it was: {e}",
                "That has been changed since, so it cannot be put back as it was.",
            )
        except record.Invalid as e:
            raise ToolError(f"Putting that back would leave {e}", e.plain)
        self.deltas.extend(change.deltas)
        self.versions.add(change.version)
        return ("Put back what the last turn changed.", self._patch(change))

    def _previous_turn(self) -> str | None:
        """The turn before this one on this diagram — what 'put that back' means.
        Questions are never put back, so a turn that touched only questions, a
        dismissal say, is not it."""
        rows = Change.query.filter(
            Change.diagram_id == self.diagram_id,
            Change.turn_id != self.turn_id,
            Change.turn_id.notlike("undo:%"),
        ).order_by(Change.id.desc())
        return next(
            (
                row.turn_id
                for row in rows
                if any(d["item_kind"] != ItemKind.Question.value for d in row.deltas)
            ),
            None,
        )

    # ── QUESTIONS ───────────────────────────────────────────────────────────

    def _add_question(self, args: dict) -> tuple[str, dict]:
        state = QuestionState(args["state"])
        fields = {
            "text": args["text"],
            "kind": QuestionKind(args["kind"]).value,
            "state": state.value,
            "outcome": None,
            "item_kind": args.get("item_kind"),
            "item_id": args.get("item_id"),
            "session_id": None,
            "asked_at": None,
        }
        said = None
        if args.get("asked_in") is not None:
            if state is not QuestionState.Asked:
                raise ToolError(
                    "asked_in is for a question asked in that message: state asked",
                    "It said where a question was asked without asking it.",
                )
            said = self._said(args["asked_in"], args["text"])
        if state is QuestionState.Asked:
            fields.update(self._asked(said))
        return self._write(ItemKind.Question, None, fields, said and said.id)

    def _set_question(self, args: dict) -> tuple[str, dict]:
        state = QuestionState(args["state"])
        fields = {"state": state.value}
        if args.get("outcome") is not None:
            fields["outcome"] = QuestionOutcome(args["outcome"]).value
        if state is QuestionState.Asked:
            fields.update(self._asked(None))
        return self._write(ItemKind.Question, args["id"], fields)

    def _asked(self, said: Statement | None) -> dict:
        """The session a question is asked in and the day: this turn's, or the
        past coach message it was asked in."""
        if said is None:
            return {
                "session_id": int(self.session_id),
                "asked_at": datetime.date.today().isoformat(),
            }
        return {
            "session_id": said.discussion_id,
            "asked_at": said.created_at.date().isoformat(),
        }

    def _said(self, statement_id: int, text: str) -> Statement:
        statement = (
            Statement.query.join(Discussion)
            .filter(
                Statement.id == statement_id,
                Discussion.diagram_id == self.diagram_id,
                Statement.speaker_id == Discussion.chat_ai_speaker_id,
            )
            .one_or_none()
        )
        if statement is None or text not in (statement.text or ""):
            raise ToolError(
                f"Message {statement_id} is not a coach message of this family that "
                "holds those words exactly",
                "Those words are not in that message.",
            )
        return statement

    # ── SHOW ────────────────────────────────────────────────────────────────

    def _show(self, args: dict) -> tuple[str, dict]:
        try:
            view = views.build(
                args["kind"], {k: v for k, v in args.items() if k != "kind"}, self.data
            )
        except views.Unshowable as e:
            raise ToolError(str(e), e.plain)
        self.views.append(view)
        return (f"Showing the {view['kind']}.", {"view": view})

    # ── the record itself ───────────────────────────────────────────────────

    def _person(self, data: DiagramData, person_id) -> int:
        if not self._exists(data, ItemKind.Person, person_id):
            raise ToolError(f"No person {person_id} in the record", views.NO_PERSON)
        return int(person_id)

    def _event(self, data: DiagramData, event_id) -> int:
        if not self._exists(data, ItemKind.Event, event_id):
            raise ToolError(f"No event {event_id} in the record", views.NO_EVENT)
        return int(event_id)

    def _cluster(self, data: DiagramData, cluster_id: str) -> dict:
        for cluster in data.clusters:
            if str(cluster.get("id")) == str(cluster_id):
                return cluster
        raise ToolError(f"No cluster {cluster_id} in the record", views.NO_CLUSTER)

    def _exists(self, data: DiagramData, kind: ItemKind, item_id) -> bool:
        collection = getattr(data, ITEM_COLLECTIONS[kind])
        return any(str(i.get("id")) == str(item_id) for i in collection)

    def _write(
        self, kind: ItemKind, item_id, fields: dict, statement_id: int | None = None
    ) -> tuple[str, dict]:
        if not fields:
            raise ToolError(
                f"Nothing to change on that {kind.value}", "It gave nothing to change."
            )
        data = self.data
        new = item_id is None
        taken = {str(i.get("id")) for i in getattr(data, ITEM_COLLECTIONS[kind])}
        if new:
            if kind is ItemKind.Cluster:
                item_id = clusters.next_id(taken)
            elif kind is ItemKind.Question:
                item_id = record.next_key("q", taken)
            else:
                item_id = record.next_id(data)
        elif not self._exists(data, kind, item_id):
            raise ToolError(f"No {kind.value} {item_id} in the record", GONE)

        deltas = [
            {"item_kind": kind.value, "item_id": item_id, "field": field, "after": value}
            for field, value in fields.items()
        ]
        if new and kind not in (ItemKind.Cluster, ItemKind.Question):
            deltas.append(
                {
                    "item_kind": ItemKind.Diagram.value,
                    "item_id": None,
                    "field": "lastItemId",
                    "after": item_id,
                }
            )
        change = self._apply(deltas, statement_id)
        verb = "Added" if new else "Changed"
        return (f"{verb} {kind.value} {item_id}.", self._patch(change))

    def _apply(self, deltas: list[dict], statement_id: int | None = None):
        try:
            change = record.apply(
                self.diagram_id,
                deltas,
                author=self.author,
                turn_id=self.turn_id,
                user_id=self.user_id,
                session_id=self.session_id,
                statement_id=statement_id or self.statement_id,
            )
        except record.Invalid as e:
            # the record says what is wrong in the coach's own words already
            raise ToolError(str(e), e.plain)
        self.deltas.extend(change.deltas)
        self.versions.add(change.version)
        return change

    def _patch(self, change) -> dict:
        return {"deltas": change.deltas, "turn_id": change.turn_id}
