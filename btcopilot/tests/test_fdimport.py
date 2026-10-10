import json

import pytest

from btcopilot import diagramjson, fdfile, fdimport, record
from btcopilot.admin import admin
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Diagram
from btcopilot.tests.fdfixtures import bundle, dumps, event, scene, shift, when


def imported(**more) -> fdimport.Imported:
    return fdimport.convert(fdfile.read(dumps(scene(**more))))


def by_id(items: list[dict]) -> dict:
    return {item["id"]: item for item in items}


def test_people_and_their_other_names_kept():
    # R-0863
    ada = by_id(imported().people)[1]
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
    assert by_id(imported().people)[3]["parents"] == 10


def test_events_copied_with_their_date_certainty():
    # R-0859
    events = by_id(imported().events)
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


def test_hand_coded_values_copied_from_the_event_and_its_dynamic_properties():
    # R-0859
    events = by_id(
        imported(
            events=[
                shift(23, symptom="up", functioning="down"),
                shift(24, relationshipTargets=[2], dynamicProperties={"anxiety": "down", "relationship": "conflict"}),
            ]
        ).events
    )
    assert (events[23]["symptom"], events[23]["functioning"]) == ("up", "down")
    assert (events[24]["anxiety"], events[24]["relationship"]) == ("down", "conflict")


def test_value_the_app_has_no_word_for_left_blank_with_its_text_kept():
    # R-0859
    out = imported(events=[shift(23, dynamicProperties={"relationship": "reciprocity"})])
    event = by_id(out.events)[23]
    assert "relationship" not in event
    assert event[fdimport.RAW] == {"relationship": "reciprocity"}
    assert out.blanks == [{"event": 23, "field": "relationship", "raw": "reciprocity"}]


def test_relationship_lines_go_on_their_event_or_become_a_shift():
    # R-0859
    out = imported(
        events=[shift(23)],
        emotions=[
            {"kind": "conflict", "id": 30, "person": 1, "target": 2, "event": 23, "intensity": 2},
            {"kind": "cutoff", "id": 31, "person": 3, "target": 1, "event": None, "notes": "No calls."},
        ],
    )
    events = by_id(out.events)
    assert (events[23]["relationship"], events[23]["relationshipTargets"]) == ("conflict", [2])
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


def test_moved_becomes_a_noted_place():
    # R-0864
    events = by_id(imported(events=[event(25, "moved", person=1, description="To the coast")]).events)
    assert (events[25]["kind"], events[25]["item"]) == ("noted", "places")


def test_tags_kept_on_events_and_the_diagram():
    # R-0857
    out = imported()
    assert by_id(out.events)[20]["tags"] == ["family"]
    assert out.tags == ["family", "work"]


def test_screen_positions_and_nodal_dropped():
    # R-0856, R-0861
    out = imported()
    kept = {key for item in out.people + out.pair_bonds + out.events for key in item}
    assert not kept & {"itemPos", "color", "size", "nodal", "relationshipIntensity", "separated", "layers"}
    assert out.dropped["people.itemPos"] == 3
    assert out.dropped["events.nodal"] == 1
    assert out.dropped["events.relationshipIntensity"] == 3
    assert out.dropped["layers"] == 1


def test_one_change_turn_and_one_undo_takes_it_all_off(test_user):
    # R-0850
    out = imported(
        emotions=[{"kind": "cutoff", "id": 31, "person": 3, "target": 1, "event": None}]
    )
    diagram = fdimport.save(test_user.id, "Lund family", out, yes=True)
    [change] = Change.query.filter_by(diagram_id=diagram.id).all()
    assert (change.turn_id, change.author) == (fdimport.TURN.format(diagram.id), Author.Pro)
    data = diagram.get_diagram_data()
    assert (len(data.people), len(data.events), len(data.pair_bonds), data.tags) == (3, 4, 1, ["family", "work"])

    record.undo(diagram.id, change.turn_id, author=Author.User)
    data = diagramjson.loads(db.session.get(Diagram, diagram.id).data)
    assert (data["people"], data["events"], data["pair_bonds"]) == ([], [], [])


def test_record_rules_refuse_before_anything_is_written(test_user):
    # R-0850
    out = imported(events=[event(23, "shift", person=1, dateTime=when(2000, 1, 1))])
    with pytest.raises(record.Invalid):
        fdimport.save(test_user.id, "Lund family", out, yes=False)
    assert Diagram.query.filter_by(name="Lund family").count() == 0


def test_admin_import_previews_then_writes(flask_app, test_user, tmp_path):
    # R-0850
    path = bundle(tmp_path, scene())
    args = ["diagrams", "import", str(path), "--email", test_user.username, "--json"]
    runner = flask_app.test_cli_runner()

    dry = runner.invoke(admin, args)
    assert dry.exit_code == 0, dry.output
    assert {"what": "people", "count": 3, "detail": ""} in json.loads(dry.output)
    assert Diagram.query.filter_by(name="Lund family").count() == 0

    done = runner.invoke(admin, [*args, "--yes"])
    assert done.exit_code == 0, done.output
    assert Diagram.query.filter_by(name="Lund family", user_id=test_user.id).count() == 1
