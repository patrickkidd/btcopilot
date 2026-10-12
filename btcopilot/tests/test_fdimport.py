import datetime
import json
import random
from types import SimpleNamespace

import pytest

from btcopilot import (
    diagramjson,
    extensions,
    fdafter,
    fdcoding,
    fdfile,
    fdimport,
    fdledger,
    fdmerge,
    record,
)
from btcopilot.admin import admin
from btcopilot.extensions import db
from btcopilot.fdledger import Decision
from btcopilot.llmutil import Parsed, Served, Spent
from btcopilot.models import (
    Author,
    Change,
    Diagram,
    Discussion,
    Observation,
    ObservationKind,
    ProactiveMessage,
    Speaker,
    SpeakerType,
    Statement,
)
from btcopilot.models.modelcall import ModelCall, Purpose
from btcopilot.schema import NotedFact, from_dict
from btcopilot.tests.fdfixtures import bundle, dumps, event, person, scene, shift, when
from btcopilot.tests.test_fdmerge import Model, plain  # noqa: F401 (plain is autouse)
from btcopilot.toolbox import ToolName, Toolbox

TODAY = datetime.date(2026, 10, 10)


@pytest.fixture(autouse=True)
def coding(monkeypatch):
    """The coding pass, standing in: it hands the diagram back as it got it."""
    seen = []

    def code(data, model):
        seen.append([p["id"] for p in data["people"]])
        return data, [Decision("event 20", "notes", "", "", "Nothing to code.")]

    monkeypatch.setattr(fdcoding, "code", code)
    return seen


def imported(**more) -> fdimport.Imported:
    return fdimport.convert(fdfile.read(dumps(scene(**more))))


def built(**more) -> fdimport.Imported:
    return fdimport.build(fdfile.read(dumps(scene(**more))), Model())


def by_id(items: list[dict]) -> dict:
    return {item["id"]: item for item in items}


def reasons(out: fdimport.Imported, item: str) -> list[str]:
    return [one.field for one in out.decisions if one.item == item]


def test_people_and_their_other_names_kept():
    # R-0863
    ada = by_id(imported().data["people"])[1]
    assert ada == {
        "id": 1,
        "name": "Ada",
        "last_name": "Lund",
        "gender": "female",
        "notes": "Eldest of four.",
        "primary": True,
        "alias": "Mara",
        "nickName": "Addie",
        "middleName": "Jo",
        "birthName": "Berg",
    }
    assert by_id(imported().data["people"])[3]["parents"] == 10


def test_events_copied_with_their_date_certainty():
    # R-0859, R-0438
    events = by_id(imported().data["events"])
    assert events[20] == {
        "id": 20,
        "kind": "birth",
        "person": 1,
        "spouse": 2,
        "child": 3,
        "dateTime": "1990-05-11",
        "dateCertainty": "certain",
        "tags": ["family"],
    }
    assert events[21]["dateCertainty"] == "approximate"
    assert events[22]["dateCertainty"] == "approximate"


def test_time_of_day_dropped_and_in_the_ledger():
    # R-0873
    out = imported(
        events=[
            event(
                23,
                "shift",
                person=1,
                description="Left",
                dateTime=when(2000, 3, 4, 14, 30),
            )
        ]
    )
    assert by_id(out.data["events"])[23]["dateTime"] == "2000-03-04"
    [one] = [one for one in out.decisions if one.item == "event 23"]
    assert (one.field, one.before, one.after) == (
        "dateTime",
        "2000-03-04 14:30",
        "2000-03-04",
    )


def test_hand_coded_values_copied_from_the_event_and_its_dynamic_properties():
    # R-0859
    events = by_id(
        imported(
            events=[
                shift(23, symptom="up", functioning="down"),
                shift(
                    24,
                    relationshipTargets=[2],
                    dynamicProperties={"anxiety": "down", "relationship": "conflict"},
                ),
            ]
        ).data["events"]
    )
    assert (events[23]["symptom"], events[23]["functioning"]) == ("up", "down")
    assert (events[24]["anxiety"], events[24]["relationship"]) == ("down", "conflict")


def test_value_the_app_has_no_word_for_left_for_the_coding_pass():
    # R-0859, R-0868
    out = imported(
        events=[shift(23, dynamicProperties={"relationship": "reciprocity"})]
    )
    event = by_id(out.data["events"])[23]
    assert "relationship" not in event
    assert event[fdimport.RAW] == {"relationship": "reciprocity"}
    assert reasons(out, "event 23") == ["relationship"]


def test_relationship_lines_go_on_their_event_or_become_a_shift():
    # R-0859, R-0076, R-0013
    out = imported(
        events=[shift(23)],
        emotions=[
            {
                "kind": "conflict",
                "id": 30,
                "person": 1,
                "target": 2,
                "event": 23,
                "intensity": 2,
            },
            {
                "kind": "cutoff",
                "id": 31,
                "person": 3,
                "target": 1,
                "event": None,
                "notes": "No calls.",
            },
        ],
    )
    events = by_id(out.data["events"])
    assert (events[23]["relationship"], events[23]["relationshipTargets"]) == (
        "conflict",
        [2],
    )
    assert events[31] == {
        "id": 31,
        "kind": "shift",
        "person": 3,
        "dateCertainty": "unknown",
        "relationship": "cutoff",
        "relationshipTargets": [1],
        "description": "Cutoff",
        "title": "Cutoff move",
        "notes": "No calls.",
    }
    assert out.lines == 2
    assert out.joined == {"relationship line 30": 23}


def test_lines_with_no_other_person_left_for_the_coding_pass():
    # R-0869
    out = imported(
        events=[shift(23)],
        emotions=[
            {"kind": "inside", "id": 30, "person": 1, "target": 2, "event": 23},
            {
                "kind": "conflict",
                "id": 31,
                "person": 3,
                "target": None,
                "event": None,
                "startDate": when(2001, 2, 3),
            },
        ],
    )
    events = by_id(out.data["events"])
    assert "relationship" not in events[23]
    assert events[23][fdimport.RAW] == {"relationship": "inside"}
    assert "relationship" not in events[31]
    assert events[31][fdimport.RAW] == {"relationship": "conflict"}
    assert (events[31]["dateTime"], events[31]["dateCertainty"]) == (
        "2001-02-03",
        "certain",
    )


def test_notes_on_bonds_and_the_diagram_left_for_the_coding_pass():
    # R-0870
    bond = {
        "kind": "Marriage",
        "id": 10,
        "person_a": 1,
        "person_b": 2,
        "married": True,
        "notes": "Met at sea.",
    }
    out = imported(
        pair_bonds=[bond],
        layerItems=[{"kind": "Callout", "id": 40, "text": "Hard winter."}],
        people=[
            person(1, "Ada", "female", primary=True, diagramNotes="Quiet."),
            person(2, "Bo", "male"),
            person(3, "Cy", "male", parents=10),
        ],
    )
    assert out.data["pair_bonds"][0][fdimport.RAW] == {"notes": "Met at sea."}
    assert out.data[fdimport.RAW] == {"notes": "Hard winter."}
    assert by_id(out.data["people"])[1][fdimport.RAW] == {"diagramNotes": "Quiet."}


def test_the_files_values_go_to_the_pass_and_stay_in_the_ledger_only():
    # R-0873, R-0294
    fd = fdfile.read(
        dumps(
            scene(
                events=[shift(23, dynamicProperties={"relationship": "reciprocity"})],
                layerItems=[{"kind": "Callout", "id": 40, "text": "Hard winter."}],
                people=[
                    person(1, "Ada", "female", primary=True, diagramNotes="Quiet."),
                    person(2, "Bo", "male"),
                ],
            )
        )
    )
    out = fdimport.build(fd, Model())
    data = out.data
    assert not [
        item
        for item in (data, *data["people"], *data["pair_bonds"], *data["events"])
        if fdimport.RAW in item
    ]
    text = fdledger.text(
        "Lund family.fd", fd, fdimport.became(out), out.decisions, TODAY
    )
    assert "dynamicProperties.relationship: reciprocity" in text
    assert "diagramNotes: Quiet." in text


def test_moved_becomes_a_noted_place():
    # R-0864
    events = by_id(
        imported(
            events=[event(25, "moved", person=1, description="To the coast")]
        ).data["events"]
    )
    assert (events[25]["kind"], events[25]["item"]) == ("noted", "places")


def test_tags_kept_on_events_and_the_diagram():
    # R-0857
    out = imported()
    assert by_id(out.data["events"])[20]["tags"] == ["family"]
    assert out.data["tags"] == ["family", "work"]


def test_screen_positions_and_nodal_dropped():
    # R-0856, R-0861
    out = imported()
    data = out.data
    kept = {
        key
        for item in data["people"] + data["pair_bonds"] + data["events"]
        for key in item
    }
    assert not kept & {
        "itemPos",
        "color",
        "size",
        "nodal",
        "relationshipIntensity",
        "separated",
        "layers",
    }
    assert out.dropped["people.itemPos"] == 3
    assert out.dropped["events.nodal"] == 1
    assert out.dropped["events.relationshipIntensity"] == 3
    assert out.dropped["layers"] == 1


def test_unnamed_people_named_by_family_position():
    # R-0867
    out = imported(
        people=[
            person(1, "", "female", primary=True),
            person(2, "", "male"),
            person(3, "Cy", "male", parents=10),
            person(4, "", "female", parents=10),
            person(5, "", "male"),
        ]
    )
    names = {p["id"]: p.get("name", "") for p in out.data["people"]}
    assert names == {
        1: "Cy's mother",
        2: "Cy's father",
        3: "Cy",
        4: "Cy's mother's child",
        5: "Unnamed person 1",
    }
    assert reasons(out, "person 5") == ["name"]


def test_second_unnamed_partner_never_takes_the_same_name():
    # R-0867
    bonds = [
        {"kind": "Marriage", "id": 10, "person_a": 1, "person_b": 2, "married": True},
        {"kind": "Marriage", "id": 11, "person_a": 1, "person_b": 4, "married": False},
    ]
    out = imported(
        people=[
            person(1, "Ada", "female", primary=True),
            person(2, "", "male"),
            person(3, "Cy", "male", parents=10),
            person(4, "", "male"),
        ],
        pair_bonds=bonds,
    )
    names = {p["id"]: p["name"] for p in out.data["people"]}
    assert (names[2], names[4]) == ("Cy's father", "Ada's partner")


def test_a_shared_name_falls_back_to_the_full_name_then_a_count():
    # R-0867, R-0548
    pairs = [(1, 2), (3, 4), (3, 5), (6, 7), (8, 9), (10, 11)]
    bonds = [
        {"kind": "Marriage", "id": 20 + n, "person_a": a, "person_b": b}
        for n, (a, b) in enumerate(pairs)
    ]
    out = imported(
        people=[
            person(1, "Ada", "female", primary=True),
            person(2, "", "male"),
            person(3, "Ada", "female", lastName="Berg"),
            person(4, "", "male"),
            person(5, "", "male"),
            person(6, "", "male"),
            person(7, "", "female"),
            person(8, "Ada", "female"),
            person(9, "", "male"),
            person(10, "Ada", "female"),
            person(11, "", "male"),
        ],
        pair_bonds=bonds,
        events=[],
    )
    names = {p["id"]: p["name"] for p in out.data["people"] if p["name"] != "Ada"}
    assert names == {
        2: "Ada's partner",
        4: "Ada Berg's partner",
        5: "Ada Berg's partner 2",
        6: "Unnamed person 1",
        7: "Unnamed person 2",
        9: "Ada Lund's partner",
        11: "Ada Lund 2's partner",
    }


def test_an_events_own_move_naming_no_one_left_for_the_coding_pass():
    # R-0869
    out = imported(
        events=[
            shift(23, relationship="inside", relationshipTargets=[2]),
            shift(24, dynamicProperties={"relationship": "cutoff"}),
        ]
    )
    events = by_id(out.data["events"])
    assert "relationship" not in events[23] and "relationship" not in events[24]
    assert events[23][fdimport.RAW] == {"relationship": "inside"}
    assert events[24][fdimport.RAW] == {"relationship": "cutoff"}
    assert reasons(out, "event 23") == ["relationship"]


def test_events_the_record_counts_as_one_are_made_one_with_every_word_kept():
    # R-0489, R-0874, R-0873
    day = when(2010, 5, 1)
    out = built(
        events=[
            event(
                23,
                "noted",
                person=1,
                description="Graduated from college",
                dateTime=day,
            ),
            event(
                24,
                "noted",
                person=1,
                description="Went to rehab",
                notes="Weeks.",
                dateTime=day,
            ),
        ]
    )
    [kept] = out.data["events"]
    assert kept["notes"] == "Went to rehab\nWeeks."
    assert (
        fdimport.became(out)["event 24"]
        == f"part of event {kept['id']}, noted: Graduated from college"
    )
    assert any("the same event as event 23" in one.reason for one in out.decisions)


def test_a_merge_keeps_both_events_notes_and_only_the_words_that_differ():
    # R-0874, R-0431, R-0489
    day = when(2010, 5, 1)
    out = built(
        events=[
            event(
                23,
                "noted",
                person=1,
                description="Went to rehab",
                notes="Weeks.",
                dateTime=day,
            ),
            event(
                24,
                "noted",
                person=1,
                description="Went to rehab",
                notes="Relapsed.",
                dateTime=day,
            ),
            event(25, "noted", person=1, description="Saw a clinic", dateTime=day),
        ]
    )
    [kept] = out.data["events"]
    assert kept["notes"] == "Weeks.\n\nRelapsed.\n\nSaw a clinic"
    assert sum(one.reason.startswith("The app counts it") for one in out.decisions) == 2


def test_noted_events_recording_different_items_on_one_day_stay_two(monkeypatch):
    # R-0489, R-0364
    def code(data, model):
        for one, item in zip(data["events"], (NotedFact.Places, NotedFact.Work)):
            one["item"] = item
        return data, []

    monkeypatch.setattr(fdcoding, "code", code)
    day = when(2019, 3, 1)
    out = built(
        events=[
            event(23, "noted", person=1, description="Moved to Tulsa", dateTime=day),
            event(
                24, "noted", person=1, description="Started at the mill", dateTime=day
            ),
        ]
    )
    assert len(out.data["events"]) == 2


def test_deceased_with_no_death_event_gets_one_with_the_cause():
    # R-0870
    out = imported(
        people=[
            person(
                1, "Ada", "female", primary=True, deceased=True, deceasedReason="Stroke"
            ),
            person(2, "Bo", "male", deceasedReason="Fell"),
            person(3, "Cy", "male", parents=10),
        ]
    )
    deaths = {e["person"]: e for e in out.data["events"] if e["kind"] == "death"}
    assert (
        deaths[1]["dateCertainty"] == "unknown" and deaths[1]["description"] == "Stroke"
    )
    assert "dateTime" not in deaths[1]
    assert deaths[2]["id"] == 22 and deaths[2]["description"] == "Fell"
    assert reasons(out, "person 1") == ["deceased", "deceasedReason"]


@pytest.mark.parametrize(
    "flags, had, made",
    [
        ({"separated": True}, [], ["separated"]),
        ({"separated": True, "divorced": True}, [], ["divorced"]),
        ({"separated": True}, ["divorced"], []),
    ],
)
def test_a_couple_ticked_apart_gets_the_event_the_app_records_it_as(flags, had, made):
    # R-0870
    bond = {"kind": "Marriage", "id": 10, "person_a": 1, "person_b": 2, "married": True}
    events = [event(23 + n, kind, person=1, spouse=2) for n, kind in enumerate(had)]
    out = imported(
        pair_bonds=[{**bond, **flags}],
        events=scene()["events"] + events,
    )
    parted = [
        e
        for e in out.data["events"]
        if e["kind"] in ("separated", "divorced") and e["id"] not in (23, 24)
    ]
    assert [
        (e["kind"], e["person"], e["spouse"], e["dateCertainty"]) for e in parted
    ] == [(kind, 1, 2, "unknown") for kind in made]
    assert "pair_bonds.separated" not in out.dropped


@pytest.mark.parametrize("marked", [[], [1, 2]])
def test_primary_left_unset_unless_exactly_one(marked):
    # R-0871
    people = [
        person(pid, name, "male", primary=pid in marked)
        for pid, name in ((1, "Ada"), (2, "Bo"))
    ]
    out = imported(people=[*people, person(3, "Cy", "male", parents=10)])
    assert not any(p.get("primary") for p in out.data["people"])
    assert out.primaries == marked
    assert reasons(out, "diagram") == ["primary"]


def test_ids_renumbered_past_the_reserved_ones_with_every_reference_kept(coding):
    # R-0455, R-0850
    out = built(
        emotions=[
            {"kind": "cutoff", "id": 31, "person": 3, "target": 1, "event": None}
        ],
        people=[
            person(1, "Ada", "female", primary=True),
            person(2, "Bo", "male", primary=True),
            person(3, "Cy", "male", parents=10),
        ],
    )
    assert coding == [[1, 2, 3]]
    people, bonds, events = (by_id(out.data[name]) for name in fdimport.COLLECTIONS)
    assert (
        sorted(people) == [3, 4, 5]
        and sorted(bonds) == [6]
        and sorted(events) == [7, 8, 9, 10]
    )
    assert (people[5]["parents"], bonds[6]["person_a"], bonds[6]["person_b"]) == (
        6,
        3,
        4,
    )
    assert (
        events[7]["child"],
        events[7]["person"],
        events[10]["relationshipTargets"],
    ) == (5, 3, [3])
    assert out.primaries == [3, 4]
    assert out.labels[10] == "relationship line 31"
    assert out.decisions[-1].reason == "Nothing to code."


def test_became_names_what_each_file_item_is_now():
    # R-0873
    out = built(
        events=[*scene()["events"], shift(23)],
        emotions=[
            {"kind": "conflict", "id": 30, "person": 1, "target": 2, "event": 23}
        ],
    )
    said = fdimport.became(out)
    assert said["person 1"] == "person 3, Ada Lund"
    assert said["event 23"] == "event 10, shift: Lost the job"
    assert said["relationship line 30"] == "part of event 10, shift: Lost the job"


def test_one_change_turn_and_one_undo_takes_it_all_off(test_user):
    # R-0850
    out = built(
        emotions=[{"kind": "cutoff", "id": 31, "person": 3, "target": 1, "event": None}]
    )
    diagram = fdimport.save(test_user.id, "Lund family", out, yes=True, turn="t1")
    [change] = Change.query.filter_by(diagram_id=diagram.id).all()
    assert (change.turn_id, change.author) == ("t1", Author.Pro)
    data = diagram.get_diagram_data()
    assert (len(data.people), len(data.events), len(data.pair_bonds), data.tags) == (
        3,
        4,
        1,
        ["family", "work"],
    )

    record.undo(diagram.id, change.turn_id, author=Author.User)
    data = diagramjson.loads(db.session.get(Diagram, diagram.id).data)
    assert (data["people"], data["events"], data["pair_bonds"]) == ([], [], [])


def test_record_rules_refuse_before_anything_is_written(test_user):
    # R-0593
    out = built(events=[event(23, "shift", person=1, dateTime=when(2000, 1, 1))])
    [shift] = [e for e in out.data["events"] if e["kind"] == "noted"]
    shift.update(kind="shift", title="Moved away", description="Moved away")
    with pytest.raises(record.Invalid):
        fdimport.save(test_user.id, "Lund family", out, yes=False)
    assert Diagram.query.filter_by(name="Lund family").count() == 0


def test_admin_import_previews_then_writes_and_mails_the_record(
    flask_app, test_user, tmp_path, monkeypatch
):
    # R-0850, R-0873, R-0878, R-0208, R-0517
    path = bundle(tmp_path, scene())
    ledger = tmp_path / "record.txt"
    args = ["diagrams", "import", str(path), "--email", test_user.username, "--json"]
    runner = flask_app.test_cli_runner()
    caught = []
    monkeypatch.setattr(
        fdafter, "catch_up", lambda *args, **kwargs: caught.append((args, kwargs))
    )
    monkeypatch.setattr("btcopilot.proactive.push.send", lambda *args: None)

    dry = runner.invoke(admin, [*args, "--ledger", str(ledger)])
    assert dry.exit_code == 0, dry.output
    assert {"what": "people", "count": 3, "detail": ""} in json.loads(dry.output)
    assert "Ada Lund (person 1)" in ledger.read_text()
    assert Diagram.query.filter_by(name="Lund family").count() == 0
    assert (caught, ProactiveMessage.query.count(), Observation.query.count()) == (
        [],
        0,
        0,
    )

    flask_app.config["MAIL_SERVER"] = "localhost"
    with extensions.mail.record_messages() as outbox:
        done = runner.invoke(admin, [*args, "--yes"])
    assert done.exit_code == 0, done.output
    made = Diagram.query.filter_by(name="Lund family", user_id=test_user.id).one()
    turn = Change.query.filter_by(diagram_id=made.id).first().turn_id
    assert caught == [((made.id,), {"turn_id": turn, "user_id": test_user.id})]
    [message] = ProactiveMessage.query.all()
    assert (message.diagram_id, message.key) == (made.id, turn)
    assert message.question.startswith(
        "Your file is in: 3 people, 3 events and 1 pair-bond."
    )
    [counted] = Observation.query.filter_by(kind=ObservationKind.Import).all()
    assert (counted.diagram_id, counted.turn_id, counted.detail) == (
        made.id,
        turn,
        {
            "people": 3,
            "events": 3,
            "pair_bonds": 1,
            "rules": {"people": 3, "events": 3},
            "model": {"people": 0, "events": 0},
            "asked": {"people": 0, "events": 0},
        },
    )
    [mail] = outbox
    assert mail.recipients == [test_user.username]
    [attached] = mail.attachments
    assert attached.filename == "Lund family - import record.txt"
    assert "Ada Lund (person 1)" in attached.data.decode()


def family() -> dict:
    """The diagram from the conversation: Ada, her husband not yet named, and
    their son Cy."""
    return {
        "people": [
            {"id": 1, "name": "Ada", "last_name": "Lund", "gender": "female"},
            {"id": 2, "name": "Ada's husband", "gender": "male"},
            {
                "id": 3,
                "name": "Cy",
                "last_name": "Lund",
                "gender": "male",
                "parents": 4,
            },
        ],
        "pair_bonds": [{"id": 4, "person_a": 1, "person_b": 2, "married": True}],
        "events": [
            {
                "id": 5,
                "kind": "birth",
                "child": 3,
                "person": 1,
                "spouse": 2,
                "dateTime": "1990-05-11",
                "dateCertainty": "certain",
            }
        ],
        "questions": [],
        "lastItemId": 5,
    }


def stored(user) -> Diagram:
    diagram = Diagram(
        user_id=user.id, name="Ada's diagram", data=diagramjson.dumps(family())
    )
    db.session.add(diagram)
    db.session.commit()
    return diagram


def answered(prompt, response_format, schema=None, limit=None) -> Parsed:
    """The side-call model with nothing to say: every doubt stays a doubt."""
    return Parsed(
        from_dict(response_format, {}), Spent(10, 5), Served("gemini-3.1-flash-lite")
    )


@pytest.fixture
def side_call(monkeypatch):
    monkeypatch.setattr("btcopilot.metered.gemini_structured_sync", answered)


def test_into_a_diagram_one_turn_holds_the_doubt_and_one_undo_takes_it_off(
    test_user, side_call
):
    # R-0850, R-0851, R-0852
    diagram = stored(test_user)
    model = fdimport.meter(test_user.id, diagram)
    out = fdimport.build(fdfile.read(dumps(scene())), model.structured, into=diagram)
    fdimport.save(test_user.id, "", out, yes=True, turn=model.turn_id)
    [change] = Change.query.filter_by(diagram_id=diagram.id).all()
    assert change.turn_id == model.turn_id
    data = diagramjson.loads(db.session.get(Diagram, diagram.id).data)
    people = {p["name"]: p for p in data["people"]}
    assert sorted(people) == ["Ada", "Ada's husband", "Bo", "Cy"]
    assert [e["kind"] for e in data["events"] if e.get("child") == 3] == ["birth"]
    [question] = data["questions"]
    assert (question["state"], question["item_id"]) == (
        "held",
        str(people["Bo"]["id"]),
    )

    record.undo_changes(diagram.id, [change.id], author=Author.Coach)
    data = diagramjson.loads(db.session.get(Diagram, diagram.id).data)
    assert [p["name"] for p in data["people"]] == ["Ada", "Ada's husband", "Cy"]
    assert ([e["id"] for e in data["events"]], data["questions"]) == ([5], [])


def test_the_coachs_undo_takes_off_an_import_and_its_questions_but_not_an_earlier_one(
    test_user, side_call
):
    # R-0850, R-0084
    diagram = stored(test_user)
    Toolbox(diagram.id, "t0", session_id=7, author=Author.Coach).call(
        ToolName.AddQuestion,
        {
            "text": "When did Ada and her husband marry?",
            "kind": "fact",
            "state": "held",
            "item_kind": "person",
            "item_id": "1",
        },
    )
    model = fdimport.meter(test_user.id, diagram)
    out = fdimport.build(fdfile.read(dumps(scene())), model.structured, into=diagram)
    fdimport.save(test_user.id, "", out, yes=True, turn=model.turn_id)
    data = diagramjson.loads(db.session.get(Diagram, diagram.id).data)
    assert [q["state"] for q in data["questions"]] == ["held", "held"]

    Toolbox(diagram.id, "t2", session_id=7, author=Author.Coach).call(ToolName.Undo, {})
    data = diagramjson.loads(db.session.get(Diagram, diagram.id).data)
    assert [p["name"] for p in data["people"]] == ["Ada", "Ada's husband", "Cy"]
    assert [(q["text"], q["state"]) for q in data["questions"]] == [
        ("When did Ada and her husband marry?", "held")
    ]


def test_every_model_call_of_an_import_is_on_the_ledger_as_the_imports(
    test_user, side_call, monkeypatch
):
    # R-0876
    def code(data, model):
        model("prompt", fdcoding.Answer, {}, 100)
        return data, []

    monkeypatch.setattr(fdcoding, "code", code)
    model = fdimport.meter(test_user.id)
    out = fdimport.build(fdfile.read(dumps(scene())), model.structured)
    made = fdimport.save(test_user.id, "Lund", out, yes=True, turn=model.turn_id)
    diagram = stored(test_user)
    into = fdimport.meter(test_user.id, diagram)
    fdimport.build(fdfile.read(dumps(scene())), into.structured, into=diagram)
    calls = ModelCall.query.filter(
        ModelCall.turn_id.in_([model.turn_id, into.turn_id])
    ).all()
    assert sorted((c.purpose, c.user_id, c.diagram_id) for c in calls) == [
        (Purpose.Import, test_user.id, made.id),
        (Purpose.Import, test_user.id, diagram.id),
        (Purpose.Import, test_user.id, diagram.id),
    ]


def test_the_ledger_names_what_each_file_item_became_in_the_diagram(test_user):
    # R-0873, R-0851
    diagram = stored(test_user)
    out = fdimport.build(fdfile.read(dumps(scene())), Model(), into=diagram)
    said = fdimport.became(out)
    assert said["person 1"] == "the same as person 1, Ada Lund"
    assert said["person 3"] == "the same as person 3, Cy Lund"
    assert said["person 2"].endswith(", Bo Lund")
    assert said["event 20"].startswith("part of event 5, birth")
    assert "Asked of the person: both are kept until they answer." in [
        one.reason for one in out.decisions if one.item == "person 2"
    ]


def test_a_diagram_changed_since_the_import_read_it_is_not_written(test_user):
    # R-0480
    diagram = stored(test_user)
    out = fdimport.build(fdfile.read(dumps(scene())), Model(), into=diagram)
    diagram.version += 1
    db.session.commit()
    with pytest.raises(ValueError, match="changed since the import read it"):
        fdimport.save(test_user.id, "", out, yes=True)


def test_admin_import_into_a_diagram_previews_then_writes(
    flask_app, test_user, tmp_path, side_call, monkeypatch
):
    # R-0851, R-0873, R-0876
    monkeypatch.setattr("btcopilot.proactive.push.send", lambda *args: None)
    diagram = stored(test_user)
    path = bundle(tmp_path, scene())
    args = [
        "diagrams",
        "import",
        str(path),
        "--email",
        test_user.username,
        "--into",
        str(diagram.id),
        "--json",
    ]
    runner = flask_app.test_cli_runner()

    dry = runner.invoke(admin, [*args, "--ledger", str(tmp_path / "record.txt")])
    assert dry.exit_code == 0, dry.output
    assert {"what": "held_questions", "count": 1, "detail": ""} in json.loads(
        dry.output
    )
    assert Change.query.filter_by(diagram_id=diagram.id).count() == 0

    flask_app.config["MAIL_SERVER"] = "localhost"
    with extensions.mail.record_messages() as outbox:
        done = runner.invoke(admin, [*args, "--yes"])
    assert done.exit_code == 0, done.output
    assert Change.query.filter_by(diagram_id=diagram.id).count() == 1
    calls = ModelCall.query.filter_by(diagram_id=diagram.id).all()
    assert {(c.purpose, c.user_id) for c in calls} == {(Purpose.Import, test_user.id)}
    [mail] = outbox
    assert mail.attachments[0].filename == "Ada's diagram - import record.txt"


def into(people: list[dict]) -> SimpleNamespace:
    """A diagram the import reads but never writes."""
    data = {
        "people": people,
        "pair_bonds": [],
        "events": [],
        "questions": [],
        "lastItemId": 1,
    }
    return SimpleNamespace(id=1, version=1, data=diagramjson.dumps(data))


STAND_IN = {"id": 1, "name": "User", "primary": True}


def test_the_stand_in_for_the_user_becomes_the_files_one_primary_person():
    # R-0871, R-0851
    out = fdimport.build(fdfile.read(dumps(scene())), Model(), into=into([STAND_IN]))
    [you] = [p for p in out.data["people"] if p.get("primary")]
    assert (you["id"], you["name"], you["last_name"]) == (1, "Ada", "Lund")
    assert "User" not in [p["name"] for p in out.data["people"]]
    assert out.primaries == []


@pytest.mark.parametrize("marked", [(), (1, 2)])
def test_with_none_or_several_marked_the_stand_in_stays_and_the_choice_is_asked(
    marked,
):
    # R-0871
    fd = scene()
    for chunk in fd["people"]:
        chunk["primary"] = chunk["id"] in marked
    out = fdimport.build(fdfile.read(dumps(fd)), Model(), into=into([STAND_IN]))
    people = by_id(out.data["people"])
    assert people[1]["name"] == "User" and people[1]["primary"]
    assert sorted(people[i]["name"] for i in out.primaries) == sorted(
        ["Ada", "Bo"][: len(marked)]
    )


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_refusal_of_one_event_anywhere_leaves_out_that_event_only(
    test_user, seed, monkeypatch
):
    # R-0868, R-0850
    fd = scene(
        events=[
            *scene()["events"],
            shift(23),
            event(
                24,
                "noted",
                person=2,
                description="Quit drinking",
                dateTime=when(2001, 1, 1),
            ),
        ]
    )
    events = [e["description"] for e in fd["events"] if e.get("description")]
    refused = random.Random(seed).choice(events)
    validate = record.validate

    def refusing(data, deltas, *args, **kwargs):
        for delta in deltas:
            one = record._find(data, record.ItemKind.Event, delta["item_id"])
            if (
                delta["item_kind"] == "event"
                and one
                and refused in (one.get("notes") or "") + (one.get("description") or "")
            ):
                raise record.Invalid("refused", "Refused for the test.")
        return validate(data, deltas, *args, **kwargs)

    monkeypatch.setattr(record, "validate", refusing)
    out = fdimport.build(fdfile.read(dumps(fd)), Model())
    made = fdimport.save(test_user.id, "Lund family", out, yes=True)
    assert made is not None
    kept = diagramjson.loads(db.session.get(Diagram, made.id).data)["events"]
    assert len(kept) == len(fd["events"]) - 1
    [left] = [d for d in out.decisions if d.after == "left out"]
    assert refused in left.before and "Refused for the test." in left.reason


def test_events_the_coding_pass_drew_from_the_notes_are_counted_apart(monkeypatch):
    # R-0878, R-0860
    def code(data, model):
        data["events"].append(
            {
                "id": 99,
                "kind": "noted",
                "person": 1,
                "title": "Moved to Tulsa",
                "description": "Moved to Tulsa",
                "dateCertainty": "unknown",
            }
        )
        return data, []

    monkeypatch.setattr(fdcoding, "code", code)
    out = built()
    assert out.brought == {"people": 3, "pair_bonds": 1, "events": 4, "drawn": 1}


def test_an_event_drawn_from_the_notes_that_one_in_the_file_already_tells_joins_it(
    monkeypatch,
):
    # R-0868, R-0873, R-0874
    def code(data, model):
        told = next(e for e in data["events"] if e["id"] == 23)
        data["events"].append({**told, "id": 41, "title": "Moved again"})
        return data, [Decision("event 41", "anxiety", "", "up", "Read in the notes.")]

    monkeypatch.setattr(fdcoding, "code", code)
    moved = event(
        23, "noted", person=1, description="Moved to Tulsa", dateTime=when(2000, 3, 4)
    )
    out = built(events=[moved])
    [kept] = out.data["events"]
    drawn = 'the new noted event "Moved again" of person 1'
    assert (
        fdimport.became(out)[drawn]
        == f"part of event {kept['id']}, noted: Moved to Tulsa"
    )
    assert [d.field for d in out.decisions if d.item == drawn] == ["anxiety", "notes"]
    ledger = fdledger.text(
        "Lund family.fd", scene(), fdimport.became(out), out.decisions, TODAY
    )
    assert (
        f'{drawn}, anxiety: was ""; the new diagram has "up". Read in the notes.'
        in ledger
    )


def test_a_death_the_file_only_ticks_is_named_in_the_ledger_by_whom_it_is_about():
    # R-0870, R-0873
    fd = scene()
    fd["people"][0]["deceased"] = True
    out = fdimport.build(fdfile.read(dumps(fd)), Model())
    assert "the new death event of person 1" in fdimport.became(out)


def test_a_file_comes_into_a_diagram_nothing_has_been_written_to_yet(
    test_user, side_call
):
    # R-0880, R-0851
    diagram = Diagram(user_id=test_user.id, name="New", data=diagramjson.dumps({}))
    db.session.add(diagram)
    db.session.commit()
    model = fdimport.meter(test_user.id, diagram)
    out = fdimport.build(fdfile.read(dumps(scene())), model.structured, into=diagram)
    fdimport.save(test_user.id, "", out, yes=True, turn=model.turn_id)
    data = diagramjson.loads(db.session.get(Diagram, diagram.id).data)
    assert sorted(p["name"] for p in data["people"]) == ["Ada", "Bo", "Cy"]


def talked(user, diagram: Diagram, said: list[tuple[SpeakerType, str]]) -> None:
    discussion = Discussion(user_id=user.id, diagram_id=diagram.id)
    db.session.add(discussion)
    db.session.flush()
    speakers = {
        kind: Speaker(discussion_id=discussion.id, name=kind.value, type=kind)
        for kind in SpeakerType
    }
    db.session.add_all(speakers.values())
    db.session.flush()
    for order, (kind, text) in enumerate(said):
        db.session.add(
            Statement(
                discussion_id=discussion.id,
                speaker_id=speakers[kind].id,
                text=text,
                order=order,
            )
        )
    db.session.commit()


@pytest.mark.parametrize(
    "ways, statements",
    [
        ({}, []),
        (
            {"pairing": fdmerge.Pairing.TwoYears, "shown": fdmerge.Shown.More},
            ["My son Cy moved away.", "Cy calls on Sundays."],
        ),
    ],
)
def test_the_import_runs_the_merge_the_way_it_is_asked_with_the_persons_own_words(
    test_user, side_call, monkeypatch, ways, statements
):
    # R-0851, R-0853
    diagram = stored(test_user)
    talked(
        test_user,
        diagram,
        [
            (SpeakerType.Subject, "My son Cy moved away."),
            (SpeakerType.Expert, "What was that like?"),
            (SpeakerType.Subject, "Cy calls on Sundays."),
        ],
    )
    seen = []
    init = fdmerge.Merge.__init__

    def merge(self, *args):
        seen.append(args[3:])
        init(self, *args)

    monkeypatch.setattr(fdmerge.Merge, "__init__", merge)
    model = fdimport.meter(test_user.id, diagram)
    fdimport.build(
        fdfile.read(dumps(scene())), model.structured, into=diagram, **ways
    )
    assert seen == [
        (
            ways.get("pairing", fdmerge.Pairing.SameDay),
            ways.get("shown", fdmerge.Shown.Names),
            statements,
        )
    ]
