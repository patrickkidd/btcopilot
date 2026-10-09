import json

from PyQt5.QtCore import QDateTime

from btcopilot import clusters
from btcopilot.admin import admin
from btcopilot.extensions import db
from btcopilot.models import Change
from btcopilot.schema import Event, Person, asdict, from_dict


def dates(flask_app, *args) -> list[dict]:
    result = flask_app.test_cli_runner().invoke(admin, ["diagrams", "dates", *args, "--json"])
    assert result.exit_code == 0, (result.output, result.exception)
    return json.loads(result.output)


def test_the_repair_turns_a_hand_edits_qt_date_into_text(flask_app, test_user):
    # R-0084
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren"))]
    data.events = [
        {
            "id": 2,
            "kind": "shift",
            "person": 1,
            "title": "Slept badly",
            "description": "Slept badly after the move",
            "dateTime": QDateTime(2019, 4, 2, 0, 0),
            "dateCertainty": "approximate",
            "symptom": "up",
        }
    ]
    data.lastItemId = 2
    diagram.set_diagram_data(data)
    db.session.commit()
    seen = [("2019-04-02T00:00:00", "2019-04-02")]

    planned = dates(flask_app)
    assert [(r["diagram"], r["event"], r["field"]) for r in planned] == [(diagram.id, 2, "dateTime")]
    assert [(r["before"], r["after"], r["refused"], r["change"]) for r in planned] == [
        (*seen[0], None, None)
    ]
    db.session.refresh(diagram)
    assert not isinstance(diagram.get_diagram_data().events[0]["dateTime"], str)

    applied = dates(flask_app, "--apply")
    assert [(r["before"], r["after"]) for r in applied] == seen
    assert applied[0]["change"] == Change.query.order_by(Change.id.desc()).first().id
    db.session.refresh(diagram)
    events = diagram.get_diagram_data().events
    assert events[0]["dateTime"] == "2019-04-02"
    assert clusters.compute_cache_key([from_dict(Event, e) for e in events])
    assert dates(flask_app) == []


def test_the_repair_turns_the_date_alone_past_an_older_fault_in_the_event(flask_app, test_user):
    # R-0084
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren"))]
    wordless = {
        "id": 2,
        "kind": "shift",
        "person": 1,
        "description": "",
        "dateTime": QDateTime(2019, 4, 2, 0, 0),
        "dateCertainty": "approximate",
    }
    data.events = [dict(wordless)]
    data.lastItemId = 2
    diagram.set_diagram_data(data)
    db.session.commit()

    [planned] = dates(flask_app)
    assert planned["refused"] is None

    [applied] = dates(flask_app, "--apply")
    db.session.refresh(diagram)
    [event] = diagram.get_diagram_data().events
    assert event == dict(wordless, dateTime="2019-04-02")

    result = flask_app.test_cli_runner().invoke(
        admin, ["diagrams", "undo", str(diagram.id), str(applied["change"]), "--yes", "--json"]
    )
    assert result.exit_code == 0, (result.output, result.exception)
    db.session.refresh(diagram)
    [event] = diagram.get_diagram_data().events
    assert not isinstance(event["dateTime"], str)
    assert {k: v for k, v in event.items() if k != "dateTime"} == {
        k: v for k, v in wordless.items() if k != "dateTime"
    }
