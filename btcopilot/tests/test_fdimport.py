import datetime
import json
import random

import pytest

from btcopilot import (
    diagramjson,
    extensions,
    fdafter,
    fdfile,
    fdimport,
    fdledger,
    record,
)
from btcopilot.admin import admin
from btcopilot.extensions import db
from btcopilot.models import (
    Author,
    Change,
    Diagram,
    Observation,
    ObservationKind,
)
from btcopilot.tests.fdfixtures import bundle, dumps, event, person, scene, shift, when

TODAY = datetime.date(2026, 10, 10)


def imported(**more) -> fdimport.Imported:
    return fdimport.convert(fdfile.read(dumps(scene(**more))))


def built(**more) -> fdimport.Imported:
    return fdimport.build(fdfile.read(dumps(scene(**more))))


def by_id(items: list[dict]) -> dict:
    return {item["id"]: item for item in items}


def reasons(out: fdimport.Imported, item: str) -> list[str]:
    return [one.field for one in out.decisions if one.item == item]


def test_people_and_their_other_names_kept():
    # R-0922
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
    # R-0918, R-0438
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
    # R-0932
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
    [one] = [one for one in out.decisions if one.item == "event 23" and one.field == "dateTime"]
    assert (one.field, one.before, one.after) == (
        "dateTime",
        "2000-03-04 14:30",
        "2000-03-04",
    )


def test_hand_coded_values_copied_from_the_event_and_its_dynamic_properties():
    # R-0918
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


def test_value_the_app_has_no_word_for_kept_aside_for_the_import_record():
    # R-0918, R-0932
    out = imported(
        events=[shift(23, dynamicProperties={"relationship": "reciprocity"})]
    )
    event = by_id(out.data["events"])[23]
    assert "relationship" not in event
    assert event[fdimport.RAW] == {"relationship": "reciprocity"}
    assert reasons(out, "event 23") == ["title", "relationship", "kind"]


def test_relationship_lines_go_on_their_event_or_become_a_shift():
    # R-0918, R-0076, R-0013
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


def test_lines_with_no_other_person_kept_aside_for_the_import_record():
    # R-0932
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


def test_notes_on_bonds_and_the_diagram_kept_aside_for_the_import_record():
    # R-0929
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


def test_the_files_values_the_app_has_no_field_for_stay_in_the_ledger_only():
    # R-0932, R-0294
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
    out = fdimport.build(fd)
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
    # R-0923
    events = by_id(
        imported(
            events=[event(25, "moved", person=1, description="To the coast")]
        ).data["events"]
    )
    assert (events[25]["kind"], events[25]["item"]) == ("noted", "places")


def test_tags_kept_on_events_and_the_diagram():
    # R-0916
    out = imported()
    assert by_id(out.data["events"])[20]["tags"] == ["family"]
    assert out.data["tags"] == ["family", "work"]


def test_screen_positions_and_nodal_dropped():
    # R-0915, R-0920
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
    # R-0926
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
    # R-0926
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
    # R-0926, R-0548
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


def test_an_events_own_move_naming_no_one_kept_aside_for_the_import_record():
    # R-0932
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
    assert reasons(out, "event 23") == ["title", "relationship", "kind", "relationshipTargets"]


def test_deceased_with_no_death_event_gets_one_with_the_cause():
    # R-0929
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
    # R-0929
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
    # R-0930
    people = [
        person(pid, name, "male", primary=pid in marked)
        for pid, name in ((1, "Ada"), (2, "Bo"))
    ]
    out = imported(people=[*people, person(3, "Cy", "male", parents=10)])
    assert not any(p.get("primary") for p in out.data["people"])
    assert reasons(out, "diagram") == ["primary"]


def test_ids_renumbered_past_the_reserved_ones_with_every_reference_kept():
    # R-0455, R-0909
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
    assert out.labels[10] == "relationship line 31"


def test_became_names_what_each_file_item_is_now():
    # R-0932
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
    # R-0909
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
    out = built()
    out.data["events"][-1].update(kind="shift", title="Moved away", description="Moved away")
    with pytest.raises(record.Invalid):
        fdimport.save(test_user.id, "Lund family", out, yes=False)
    assert Diagram.query.filter_by(name="Lund family").count() == 0


def test_admin_import_previews_then_writes_and_mails_the_record(
    flask_app, test_user, tmp_path, monkeypatch
):
    # R-0909, R-0932, R-0208, R-0517
    path = bundle(tmp_path, scene())
    ledger = tmp_path / "record.txt"
    args = ["diagrams", "import", str(path), "--email", test_user.username, "--json"]
    runner = flask_app.test_cli_runner()
    caught = []
    monkeypatch.setattr(
        fdafter, "catch_up", lambda *args, **kwargs: caught.append((args, kwargs))
    )

    dry = runner.invoke(admin, [*args, "--ledger", str(ledger)])
    assert dry.exit_code == 0, dry.output
    assert {"what": "people", "count": 3, "detail": ""} in json.loads(dry.output)
    assert "Ada Lund (person 1)" in ledger.read_text()
    assert Diagram.query.filter_by(name="Lund family").count() == 0
    assert (caught, Observation.query.count()) == ([], 0)

    flask_app.config["MAIL_SERVER"] = "localhost"
    with extensions.mail.record_messages() as outbox:
        done = runner.invoke(admin, [*args, "--yes"])
    assert done.exit_code == 0, done.output
    made = Diagram.query.filter_by(name="Lund family", user_id=test_user.id).one()
    turn = Change.query.filter_by(diagram_id=made.id).first().turn_id
    assert caught == []
    [counted] = Observation.query.filter_by(kind=ObservationKind.Import).all()
    assert (counted.diagram_id, counted.turn_id, counted.detail) == (
        made.id,
        turn,
        {
            "people": 3,
            "events": 3,
            "pair_bonds": 1,
            "left_out": 0,
        },
    )
    [mail] = outbox
    assert mail.recipients == [test_user.username]
    [attached] = mail.attachments
    assert attached.filename == "Lund family - import record.txt"
    assert "Ada Lund (person 1)" in attached.data.decode()


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_refusal_of_one_event_anywhere_leaves_out_that_event_only(
    test_user, seed, monkeypatch
):
    # R-0905, R-0909
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
    out = fdimport.build(fdfile.read(dumps(fd)))
    made = fdimport.save(test_user.id, "Lund family", out, yes=True)
    assert made is not None
    kept = diagramjson.loads(db.session.get(Diagram, made.id).data)["events"]
    assert len(kept) == len(fd["events"]) - 1
    [left] = [d for d in out.decisions if d.after == "left out"]
    assert refused in left.before and "Refused for the test." in left.reason


def test_a_death_the_file_only_ticks_is_named_in_the_ledger_by_whom_it_is_about():
    # R-0929, R-0932
    fd = scene()
    fd["people"][0]["deceased"] = True
    out = fdimport.build(fdfile.read(dumps(fd)))
    assert "the new death event of person 1" in fdimport.became(out)




def test_a_refused_event_is_left_out_and_kept_as_a_question_the_coach_asks_later(test_user):
    # R-0905, R-0909
    out = built(events=[*scene()["events"], event(23, "shift", person=1, description="Ada lost the job", anxiety="up", dateTime=when(2000, 3, 4))])
    assert "Ada lost the job" not in [e.get("description") for e in out.data["events"]]
    [asked] = out.data["questions"]
    assert asked["text"].startswith(
        'The file had an event for Ada Lund on 4 March 2000, "Ada lost the job".'
    )
    assert (asked["state"], asked["kind"], asked["item_id"]) == ("held", "fact", 3)
    assert out.brought[fdimport.LEFT_OUT] == 1
    diagram = fdimport.save(test_user.id, "Lund family", out, yes=True, turn="t1")
    [change] = Change.query.filter_by(diagram_id=diagram.id).all()
    [kept] = diagram.get_diagram_data().questions
    assert (change.turn_id, kept["text"]) == ("t1", asked["text"])


def test_a_second_copy_of_an_event_is_left_out_and_asked_about():
    # R-0905, R-0432
    moved = dict(person=1, description="Moved to Tulsa", dateTime=when(2000, 3, 4))
    out = built(events=[event(23, "noted", **moved), event(24, "noted", **moved)])
    assert [e["description"] for e in out.data["events"]] == ["Moved to Tulsa"]
    [asked] = out.data["questions"]
    assert asked["text"].endswith(fdimport.SECOND_COPY)


def test_the_import_record_lists_each_left_out_item_and_its_question():
    # R-0905, R-0932
    named = event(23, "noted", person=1, description="Ada left", dateTime=when(2000, 3, 4))
    fd = fdfile.read(dumps(scene(events=[*scene()["events"], named])))
    out = fdimport.build(fd)
    [asked] = out.data["questions"]
    text = fdledger.text("Lund family.fd", fd, fdimport.became(out), out.decisions, TODAY)
    assert "left out" in text and asked["text"] in text


def test_a_shift_the_file_codes_nothing_for_comes_in_as_a_noted_event_with_its_whole_words(test_user):
    # R-0906, R-0907
    words = "Lost the job at the mill after the second round of layoffs"
    out = built(events=[*scene()["events"], event(23, "shift", person=1, description=words, dateTime=when(2000, 3, 4))])
    [kept] = [e for e in out.data["events"] if e.get("description") == words]
    assert (kept["kind"], kept["title"], out.data.get("questions")) == ("noted", words, None)
    assert fdimport.save(test_user.id, "Lund family", out, yes=True) is not None


def test_a_shift_the_file_codes_stays_a_shift():
    # R-0906, R-0918
    out = built(events=[*scene()["events"], shift(23, anxiety="up")])
    [kept] = [e for e in out.data["events"] if e.get("description") == "Lost the job"]
    assert (kept["kind"], kept["anxiety"]) == ("shift", "up")
