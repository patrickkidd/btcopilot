"""The scribe's own tools: one for each shape of thing a coder says, so every
argument a tool takes is right for every kind of entry it writes (R-0886).

Each call runs as the coach's own tool calls through the toolbox, so the
record's rules, the version check and the calls kept with the turn are the
coach's. Someone or something added earlier in the same answer is named by
the ref the model gave it, since the model reads no result between the calls
of one answer.
"""

import enum

from btcopilot.review import adapter
from btcopilot.schema import (
    DateCertainty,
    EventKind,
    ItemKind,
    NotedFact,
    PersonKind,
    RelationshipKind,
    VariableShift,
)

ToolName = adapter.ToolName
ToolError = adapter.ToolError


class ScribeTool(enum.StrEnum):
    AddPerson = "add_person"
    AddBond = "add_bond"
    AddBirth = "add_birth"
    AddAdoption = "add_adoption"
    AddCoupleEvent = "add_couple_event"
    AddDeath = "add_death"
    AddShift = "add_shift"
    AddNoted = "add_noted"
    ChangePerson = "change_person"
    ChangeBond = "change_bond"
    ChangeEvent = "change_event"
    Delete = "delete"


class Married(enum.StrEnum):
    Yes = "yes"
    No = "no"
    Unsaid = "unsaid"


class Clear(enum.StrEnum):
    """What change_event may empty, by the coach's names but for parents."""

    EndDate = "end_date"
    Description = "description"
    Notes = "notes"
    Location = "location"
    Item = "item"
    Parents = "parents"
    Symptom = "symptom"
    Anxiety = "anxiety"
    Functioning = "functioning"
    Relationship = "relationship"


MARRIED = {Married.Yes: True, Married.No: False, Married.Unsaid: None}
COUPLE_KINDS = (
    EventKind.Married,
    EventKind.Bonded,
    EventKind.Separated,
    EventKind.Divorced,
)
BORN_KINDS = (EventKind.Birth, EventKind.Adopted)
#: The kinds one person's own event can be, by who it is about.
ONE_KINDS = (EventKind.Death, EventKind.Shift, EventKind.Noted)
#: What each change_event role argument may name, by the event's kind.
ROLES = {
    "person": ONE_KINDS,
    "couple": COUPLE_KINDS,
    "child": BORN_KINDS,
    "parents": BORN_KINDS,
}
CLEARED = {
    Clear.Parents: ("person", "spouse"),
    Clear.Relationship: (
        "relationship",
        "relationship_targets",
        "relationship_triangles",
    ),
}
#: The coach tool each scribe tool writes through, which a refused call is
#: counted under so the learning loop reads it as the coach's (R-0871).
COACH = {
    ScribeTool.AddPerson: ToolName.EditPerson,
    ScribeTool.ChangePerson: ToolName.EditPerson,
    ScribeTool.AddBond: ToolName.EditPairBond,
    ScribeTool.ChangeBond: ToolName.EditPairBond,
    ScribeTool.Delete: ToolName.Remove,
}
DELETED = (ItemKind.Person, ItemKind.PairBond, ItemKind.Event)
SHIFTS = ("symptom", "anxiety", "functioning")
GENDERED = (PersonKind.Male.value, PersonKind.Female.value)
UNKNOWN_REF = "It named someone or something it had not added."


def _values(cls) -> list[str]:
    return [one.value for one in cls]


def _enum(values: list[str], description: str) -> dict:
    return {"type": "string", "enum": values, "description": description}


def _ids(description: str) -> dict:
    return {"type": "array", "items": {"type": "integer"}, "description": description}


def schemas() -> list[dict]:
    """Flat schemas: integers, strings and string enums only, so Gemini and
    Claude read them alike."""
    means = adapter.meanings()
    text = adapter.ToolText
    one = (
        "An id from the record, or the ref you gave someone or something you "
        "added earlier in this same answer."
    )
    ref = {
        "type": "integer",
        "description": (
            "A negative number of your choosing (-1, -2, ...) that later calls in "
            "this same answer use in place of the id the record gives it."
        ),
    }
    version = {
        "type": "integer",
        "description": "The record version: the number at the end of the record.",
    }
    date = {
        "type": "string",
        "description": "YYYY-MM-DD; a year alone is YYYY-01-01, a month YYYY-MM-01.",
    }
    certainty = _enum(
        _values(DateCertainty), f"How sure the date is: {adapter.CERTAINTY}."
    )
    person = {"type": "integer", "description": f"Who it is about. {one}"}
    parents = _ids(
        "0 to 2 people. One: the other parent is the other side of the child's "
        f"parents, or is added generically named. {one}"
    )
    shift = {
        "symptom": _enum(_values(VariableShift), means[text.Symptom]),
        "anxiety": _enum(_values(VariableShift), means[text.Anxiety]),
        "functioning": _enum(_values(VariableShift), means[text.Functioning]),
        "relationship": _enum(_values(RelationshipKind), means[text.Relationship]),
        "relationship_targets": _ids(f"{means[text.RelationshipTargets]} {one}"),
        "relationship_triangles": _ids(f"{means[text.RelationshipTriangles]} {one}"),
    }
    words = {
        "title": {"type": "string", "description": means[text.Title]},
        "description": {"type": "string", "description": means[text.Description]},
    }
    location = {"type": "string", "description": means[text.Location]}
    end_date = {"type": "string", "description": means[text.EndDate]}
    item = _enum(_values(NotedFact), means[text.Item])
    sex = _enum(
        _values(PersonKind),
        "A pregnancy lost is its own person: miscarriage or abortion.",
    )
    born = {
        "child": {"type": "integer", "description": f"{means[text.Child]} {one}"},
        "parents": parents,
        "date": date,
        "date_certainty": certainty,
        "location": location,
        "ref": ref,
    }

    def tool(
        name: ScribeTool, description: str, properties: dict, required: list[str]
    ) -> dict:
        return {
            "name": name.value,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    dated = ["date", "date_certainty"]
    return [
        tool(
            ScribeTool.AddPerson,
            "Add a person who is not in the record yet, with their birth when the "
            "coder gave its date.",
            {
                "name": {
                    "type": "string",
                    "description": 'Their first name, or whose relation they are when nobody named them, as "Marcus\'s aunt".',
                },
                "last_name": {"type": "string"},
                "sex": sex,
                "parents": parents,
                "birth_date": date,
                "birth_date_certainty": certainty,
                "ref": ref,
            },
            ["name"],
        ),
        tool(
            ScribeTool.AddBond,
            "Make two people a couple when the coder says they are, with no event or date.",
            {
                "couple": _ids(
                    f"1 or 2 people. One: the partner is added generically named. {one}"
                ),
                "married": _enum(
                    _values(Married),
                    "Whether they married; unsaid when the coder did not say.",
                ),
                "ref": ref,
            },
            ["couple"],
        ),
        tool(
            ScribeTool.AddBirth,
            "A birth: who was born, to whom, when.",
            born,
            ["child", *dated],
        ),
        tool(
            ScribeTool.AddAdoption,
            "An adoption: who was taken in, by whom, when.",
            born,
            ["child", *dated],
        ),
        tool(
            ScribeTool.AddCoupleEvent,
            "A marriage, a pairing, a separation or a divorce between exactly two people.",
            {
                "kind": _enum(
                    [k.value for k in COUPLE_KINDS],
                    "bonded is the day they got together.",
                ),
                "couple": _ids(f"Exactly 2 people, in any order. {one}"),
                "date": date,
                "date_certainty": certainty,
                "location": location,
                "ref": ref,
            },
            ["kind", "couple", *dated],
        ),
        tool(
            ScribeTool.AddDeath,
            "A death: who died, when, and the cause when the coder gave one.",
            {
                "person": {"type": "integer", "description": f"Who died. {one}"},
                "date": date,
                "date_certainty": certainty,
                "description": {
                    "type": "string",
                    "description": f"The cause. {means[text.Description]}",
                },
                "location": location,
                "ref": ref,
            },
            ["person", *dated],
        ),
        tool(
            ScribeTool.AddShift,
            "A change in symptom, anxiety, functioning or a relationship, for one person.",
            {
                "person": person,
                **words,
                "date": date,
                "date_certainty": certainty,
                "end_date": end_date,
                **shift,
                "location": location,
                "ref": ref,
            },
            ["person", "title", "description", *dated],
        ),
        tool(
            ScribeTool.AddNoted,
            "Anything else worth writing down about one person: a move, a job, a course, an illness.",
            {
                "person": person,
                **words,
                "date": date,
                "date_certainty": certainty,
                "end_date": end_date,
                "item": item,
                "location": location,
                "ref": ref,
            },
            ["person", "title", "description", *dated],
        ),
        tool(
            ScribeTool.ChangePerson,
            "Change a person already in the record.",
            {
                "id": person,
                "version": version,
                "name": {"type": "string"},
                "last_name": {"type": "string"},
                "sex": sex,
                "parents": parents,
            },
            ["id", "version"],
        ),
        tool(
            ScribeTool.ChangeBond,
            "Change whether a couple already in the record married.",
            {
                "id": {
                    "type": "integer",
                    "description": f"The couple's pair-bond. {one}",
                },
                "version": version,
                "married": _enum(
                    [Married.Yes.value, Married.No.value], "Whether they married."
                ),
            },
            ["id", "version", "married"],
        ),
        tool(
            ScribeTool.ChangeEvent,
            "Change an event already in the record. Its kind never changes: delete "
            "a wrong kind and add the right one. Give only what the coder changed.",
            {
                "id": {"type": "integer", "description": f"The event. {one}"},
                "version": version,
                "date": date,
                "date_certainty": _enum(
                    _values(DateCertainty),
                    f"How sure the date is: {adapter.CERTAINTY}. Needed with a new date.",
                ),
                "end_date": end_date,
                **words,
                "notes": {"type": "string", "description": means[text.Notes]},
                "location": location,
                "item": item,
                "person": {
                    "type": "integer",
                    "description": f"On a death, shift or noted event: who it is about. {one}",
                },
                "couple": _ids(
                    f"On a marriage, pairing, separation or divorce: exactly 2 people. {one}"
                ),
                "child": {
                    "type": "integer",
                    "description": f"On a birth or adoption: {means[text.Child]} {one}",
                },
                "parents": _ids(f"On a birth or adoption: {parents['description']}"),
                **shift,
                "clear": {
                    "type": "array",
                    "items": {"type": "string", "enum": _values(Clear)},
                    "description": "Fields to empty because what is there is wrong.",
                },
            },
            ["id", "version"],
        ),
        tool(
            ScribeTool.Delete,
            "Remove one person, pair-bond or event the coder says is wrong. A person "
            "goes with their events and pair-bonds. Never used to fix a name or a date.",
            {
                "kind": _enum([k.value for k in DELETED], "What it removes."),
                "id": {"type": "integer", "description": one},
                "version": version,
            },
            ["kind", "id", "version"],
        ),
    ]


class ScribeTools:
    """One scribe turn's tools on the toolbox it writes through."""

    def __init__(self, toolbox):
        self.toolbox = toolbox
        self.tools = schemas()
        # An argument a tool does not declare is dropped, never passed on: a
        # title on a marriage is not a thing the scribe can say (R-0886).
        self.declared = {
            tool["name"]: set(tool["input_schema"]["properties"]) for tool in self.tools
        }
        self.refs: dict[int, tuple[ItemKind, int]] = {}

    def call(self, name: str, args: dict) -> tuple[str, str, list[dict]]:
        """What the model reads, the refusal's plain words when the record or
        the tool refused it, and the coach calls it ran, kept as a coach
        turn keeps its own, each with the scribe tool's name beside it."""
        kept: list[dict] = []
        try:
            tool = ScribeTool(name)
        except ValueError:
            return f"There is no tool called {name}", "There is no such tool.", []
        args = {key: value for key, value in args.items() if key in self.declared[tool]}
        try:
            self._fresh_ref(args.get("ref"))
            text = getattr(self, f"_{tool.value}")(args, kept)
            plain = ""
        except ToolError as e:
            text, plain = str(e), e.plain
            if not kept or not kept[-1]["refusal"]:
                coach, form = self._form(tool, args)
                kept.append(dict(self._asked(coach, form), refusal=plain, result=text))
        return text, plain, [dict(one, scribe=tool.value) for one in kept]

    def _asked(self, coach: ToolName, args: dict) -> dict:
        return adapter.toolcall(self.toolbox.data, coach, args)

    def _run(self, kept: list[dict], coach: ToolName, args: dict) -> tuple[str, dict]:
        args = {key: value for key, value in args.items() if value is not None}
        asked = self._asked(coach, args)
        try:
            text, patch = self.toolbox.call(coach, args)
        except ToolError as e:
            kept.append(dict(asked, refusal=e.plain, result=str(e)))
            raise
        kept.append(dict(asked, refusal=None, result=text))
        return text, patch

    def _fresh_ref(self, ref) -> None:
        if ref is not None and (int(ref) >= 0 or int(ref) in self.refs):
            raise ToolError(
                f"ref {ref} must be a negative number not used yet in this answer",
                "It labelled an entry it added in a way it could not use.",
            )

    def _made(self, patch: dict, args: dict, kind: ItemKind) -> tuple[int, str]:
        """The id an add was given, kept under its ref. Its own entry is the
        first of its kind: a generically named person or a couple's bond the
        add needed is written before it."""
        made = int(
            next(d for d in patch["deltas"] if d["item_kind"] == kind.value)["item_id"]
        )
        ref = args.get("ref")
        if ref is None:
            return made, ""
        ref = int(ref)
        self.refs[ref] = (kind, made)
        return made, f" Ref {ref} is {kind.value} {made}."

    def _id(self, kind: ItemKind, value) -> int | None:
        if value is None:
            return None
        value = int(value)
        if value >= 0:
            return value
        found = self.refs.get(value)
        if found is None:
            raise ToolError(
                f"Nothing was added in this answer as ref {value}: add it first, or "
                "use an id from the record",
                UNKNOWN_REF,
            )
        if found[0] is not kind:
            raise ToolError(
                f"ref {value} is a {found[0].value}, not a {kind.value}", UNKNOWN_REF
            )
        return found[1]

    def _people(self, values) -> list[int]:
        return [self._id(ItemKind.Person, one) for one in values or []]

    def _version(self) -> int:
        return self.toolbox.diagram.version

    def _find(self, kind: ItemKind, item_id) -> dict:
        collection = {
            ItemKind.Person: self.toolbox.data.people,
            ItemKind.PairBond: self.toolbox.data.pair_bonds,
            ItemKind.Event: self.toolbox.data.events,
        }[kind]
        for one in collection:
            if str(one.get("id")) == str(item_id):
                return one
        raise ToolError(f"No {kind.value} {item_id} in the record", adapter.GONE)

    def _form(self, tool: ScribeTool, args: dict) -> tuple[ToolName, dict]:
        """A call as the coach's tool would have taken it, ids as given, for
        counting a call refused before it reached the record."""
        coach = COACH.get(tool, ToolName.EditEvent)
        if tool in (ScribeTool.AddPerson, ScribeTool.ChangePerson):
            return coach, _person_args(args)
        if tool is ScribeTool.AddBond:
            couple = list(args.get("couple") or [])
            return coach, {
                "person_a": couple[0] if couple else None,
                "person_b": couple[1] if len(couple) > 1 else None,
            }
        if tool is ScribeTool.ChangeBond:
            return coach, {"id": args.get("id"), "version": args.get("version")}
        if tool is ScribeTool.Delete:
            return coach, _removed(args)
        return coach, {
            k: v
            for k, v in _event_args(_kind(tool, args), args).items()
            if v is not None
        }

    def _add_person(self, args: dict, kept: list[dict]) -> str:
        parents = self._people(args.get("parents"))
        text, patch = self._run(kept, ToolName.EditPerson, _person_args(args))
        made, said = self._made(patch, args, ItemKind.Person)
        if args.get("birth_date") is not None:
            born = dict(
                _event_args(
                    EventKind.Birth,
                    {
                        **args,
                        "date": args["birth_date"],
                        "date_certainty": args.get("birth_date_certainty"),
                    },
                ),
                child=made,
                person=parents[0] if parents else None,
                spouse=parents[1] if len(parents) > 1 else None,
            )
            more, _ = self._run(kept, ToolName.EditEvent, born)
            text = f"{text} {more}"
        elif parents:
            more = self._parents(
                kept, made, parents, {"id": made, "version": self._version()}
            )
            text = f"{text} {more}"
        return text + said

    def _parents(
        self, kept: list[dict], child: int, given: list[int], args: dict
    ) -> str:
        """The child's parents set to the bond of the two given, or of the one
        given and the other side worked out, the bond added when they have none."""
        pair = self._pair(child, given)
        if len(pair) == 1:
            pair.append(self.toolbox._other_parent(child, pair[0]))
        bond = self.toolbox._bond(*pair)
        said = ""
        if bond is None:
            said, patch = self._run(
                kept, ToolName.EditPairBond, {"person_a": pair[0], "person_b": pair[1]}
            )
            bond = {"id": patch["deltas"][0]["item_id"]}
        text, _ = self._run(
            kept, ToolName.EditPerson, dict(args, parents=int(bond["id"]))
        )
        return f"{said} {text}".strip()

    def _pair(self, child: int, given: list[int]) -> list[int]:
        """Both parents, when one is given: the other side of the bond the child
        is born to, or, when the one given is not a side of it, the side whose
        sex differs from the one given. One alone when the child has no parents
        yet, for the record to name the other."""
        if len(given) > 2:
            raise ToolError(
                "A child has at most 2 parents", "It named more than two parents."
            )
        if len(given) != 1:
            return list(given)
        one = given[0]
        bond_id = self._find(ItemKind.Person, child).get("parents")
        if bond_id is None:
            return [one]
        bond = self._find(ItemKind.PairBond, bond_id)
        sides = [int(bond["person_a"]), int(bond["person_b"])]
        if one in sides:
            return [one, next(side for side in sides if side != one)]
        sex = _sex(self._find(ItemKind.Person, one))
        same = [
            side
            for side in sides
            if sex in GENDERED and _sex(self._find(ItemKind.Person, side)) == sex
        ]
        if len(same) != 1:
            raise ToolError(
                f"person {child} has two parents already and person {one} is not one "
                "of them: give both parents",
                "It named one parent where the child already has two.",
            )
        return [one, next(side for side in sides if side != same[0])]

    def _add_bond(self, args: dict, kept: list[dict]) -> str:
        couple = self._people(args.get("couple"))
        if len(couple) not in (1, 2):
            raise ToolError(
                "A couple is 1 or 2 people", "It named no one as the couple."
            )
        married = MARRIED[
            adapter.choice(
                Married, args.get("married") or Married.Unsaid, "married values"
            )
        ]
        text, patch = self._run(
            kept,
            ToolName.EditPairBond,
            {
                "person_a": couple[0],
                "person_b": couple[1] if len(couple) > 1 else None,
                "married": married,
            },
        )
        return text + self._made(patch, args, ItemKind.PairBond)[1]

    def _born(self, kind: EventKind, args: dict, kept: list[dict]) -> str:
        parents = self._people(args.get("parents"))
        if len(parents) > 2:
            raise ToolError(
                "A child has at most 2 parents", "It named more than two parents."
            )
        fields = dict(
            _event_args(kind, args),
            child=self._id(ItemKind.Person, args.get("child")),
            person=parents[0] if parents else None,
            spouse=parents[1] if len(parents) > 1 else None,
        )
        return self._event(fields, args, kept)

    def _event(self, fields: dict, args: dict, kept: list[dict]) -> str:
        text, patch = self._run(kept, ToolName.EditEvent, fields)
        return text + self._made(patch, args, ItemKind.Event)[1]

    def _add_birth(self, args: dict, kept: list[dict]) -> str:
        return self._born(EventKind.Birth, args, kept)

    def _add_adoption(self, args: dict, kept: list[dict]) -> str:
        return self._born(EventKind.Adopted, args, kept)

    def _add_couple_event(self, args: dict, kept: list[dict]) -> str:
        kind = adapter.choice(EventKind, args.get("kind"), "event kinds")
        if kind not in COUPLE_KINDS:
            raise ToolError(
                f"{kind.value} is not a couple's event: one of {', '.join(k.value for k in COUPLE_KINDS)}",
                "It asked for a kind of event that is not a couple's.",
            )
        couple = self._couple(args.get("couple"))
        fields = dict(_event_args(kind, args), person=couple[0], spouse=couple[1])
        return self._event(fields, args, kept)

    def _couple(self, values) -> list[int]:
        couple = self._people(values)
        if len(couple) != 2:
            raise ToolError(
                "A couple's event names exactly 2 people in couple",
                "A couple's event needs both partners.",
            )
        return couple

    def _one(self, kind: EventKind, args: dict, kept: list[dict]) -> str:
        fields = dict(
            _event_args(kind, args),
            person=self._id(ItemKind.Person, args.get("person")),
        )
        for key in ("relationship_targets", "relationship_triangles"):
            if args.get(key) is not None:
                fields[key] = self._people(args[key])
        return self._event(fields, args, kept)

    def _add_death(self, args: dict, kept: list[dict]) -> str:
        return self._one(EventKind.Death, args, kept)

    def _add_shift(self, args: dict, kept: list[dict]) -> str:
        return self._one(EventKind.Shift, args, kept)

    def _add_noted(self, args: dict, kept: list[dict]) -> str:
        return self._one(EventKind.Noted, args, kept)

    def _change_person(self, args: dict, kept: list[dict]) -> str:
        fields = dict(
            _person_args(args),
            id=self._id(ItemKind.Person, args.get("id")),
            version=args.get("version"),
        )
        if args.get("parents") is None:
            text, _ = self._run(kept, ToolName.EditPerson, fields)
            return text
        return self._parents(kept, fields["id"], self._people(args["parents"]), fields)

    def _change_bond(self, args: dict, kept: list[dict]) -> str:
        bond_id = self._id(ItemKind.PairBond, args.get("id"))
        married = MARRIED[
            adapter.choice(Married, args.get("married"), "married values")
        ]
        if married is None:
            raise ToolError(
                "married is yes or no on a change",
                "It gave no answer to whether they married.",
            )
        bond = self._find(ItemKind.PairBond, bond_id)
        couple = {str(bond["person_a"]), str(bond["person_b"])}
        if married is False and any(
            adapter.plain(event.get("kind")) == EventKind.Married.value
            and {str(event.get("person")), str(event.get("spouse"))} == couple
            for event in self.toolbox.data.events
        ):
            raise ToolError(
                f"pair bond {bond_id} has a marriage event: remove that event first, "
                "or leave married as it is",
                "That couple has a marriage in the diagram.",
            )
        text, _ = self._run(
            kept,
            ToolName.EditPairBond,
            {"id": bond_id, "version": args.get("version"), "married": married},
        )
        return text

    def _change_event(self, args: dict, kept: list[dict]) -> str:
        event_id = self._id(ItemKind.Event, args.get("id"))
        event = self._find(ItemKind.Event, event_id)
        kind = EventKind(adapter.plain(event.get("kind")))
        for role, kinds in ROLES.items():
            if args.get(role) is not None and kind not in kinds:
                raise ToolError(
                    f"{role} is not on a {kind.value} event: {_roles(kind)}",
                    "It named someone in a role this kind of event does not have.",
                )
        cleared = [
            adapter.choice(Clear, one, "fields to clear")
            for one in args.get("clear") or []
        ]
        if Clear.Parents in cleared and kind not in BORN_KINDS:
            raise ToolError(
                f"A {kind.value} event has no parents to clear",
                "That event has no parents.",
            )
        fields = dict(
            _event_args(kind, args),
            id=event_id,
            version=args.get("version"),
            clear=[name for one in cleared for name in CLEARED.get(one, (one.value,))]
            or None,
        )
        fields["person"] = self._id(ItemKind.Person, args.get("person"))
        for key in ("relationship_targets", "relationship_triangles"):
            if args.get(key) is not None:
                fields[key] = self._people(args[key])
        if args.get("couple") is not None:
            fields["person"], fields["spouse"] = self._couple(args["couple"])
        if kind in BORN_KINDS:
            child = self._id(ItemKind.Person, args.get("child")) or event.get("child")
            fields["child"] = child
            if args.get("parents") is not None:
                pair = (
                    self._pair(child, self._people(args["parents"]))
                    if child is not None
                    else self._people(args["parents"])
                )
                fields["person"] = pair[0] if pair else None
                fields["spouse"] = pair[1] if len(pair) > 1 else None
        text, _ = self._run(kept, ToolName.EditEvent, fields)
        return text

    def _delete(self, args: dict, kept: list[dict]) -> str:
        kind = adapter.choice(ItemKind, args.get("kind"), "kinds of thing")
        if kind not in DELETED:
            raise ToolError(
                f"Only a {', '.join(k.value for k in DELETED)} can be deleted",
                "There is no such kind of thing to remove.",
            )
        fields = dict(_removed(args), item_id=self._id(kind, args.get("id")))
        text, _ = self._run(kept, ToolName.Remove, fields)
        return text


def _kind(tool: ScribeTool, args: dict) -> str | None:
    return {
        ScribeTool.AddBirth: EventKind.Birth.value,
        ScribeTool.AddAdoption: EventKind.Adopted.value,
        ScribeTool.AddDeath: EventKind.Death.value,
        ScribeTool.AddShift: EventKind.Shift.value,
        ScribeTool.AddNoted: EventKind.Noted.value,
    }.get(tool, args.get("kind"))


def _event_args(kind, args: dict) -> dict:
    """The coach's edit_event arguments a scribe call gives under the same
    names; who the event links is set by each tool."""
    out = {"kind": getattr(kind, "value", kind)}
    for key in (
        "date",
        "date_certainty",
        "end_date",
        "title",
        "description",
        "notes",
        "location",
        "item",
        *SHIFTS,
        "relationship",
        "relationship_targets",
        "relationship_triangles",
        "person",
        "child",
    ):
        out[key] = args.get(key)
    couple = list(args.get("couple") or [])
    parents = list(args.get("parents") or [])
    pair = couple or parents
    if pair:
        out["person"] = pair[0]
        out["spouse"] = pair[1] if len(pair) > 1 else None
    return out


def _person_args(args: dict) -> dict:
    return {
        "name": args.get("name"),
        "last_name": args.get("last_name"),
        "gender": args.get("sex"),
    }


def _removed(args: dict) -> dict:
    return {
        "item_kind": args.get("kind"),
        "item_id": args.get("id"),
        "version": args.get("version"),
    }


def _sex(person: dict) -> str:
    return adapter.plain(person.get("gender")) or ""


def _roles(kind: EventKind) -> str:
    return "give " + " or ".join(role for role, kinds in ROLES.items() if kind in kinds)
