"""A record in the shape the Pro app saves, with every field the chat app
does not write — relationship moves with their targets and triangles, emotions,
layers, Qt dates, colours and points — goes through the chat app's storage and
comes back to Pro equal, and the chat app reads the relationship sub-fields."""

import pickle

from PyQt5.QtCore import QDate, QDateTime, QPointF

from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot.tests.chat.personal.conftest import csrf_token

PEOPLE = [
    {"id": 1, "name": "Ada", "last_name": "Lund", "gender": "female", "parents": 30,
     "nickname": "A", "deceased": False, "size": 4, "color": "#ff102030", "layers": [40],
     "itemPos": QPointF(12.5, -7.25)},
    {"id": 2, "name": "Ben", "last_name": "Lund", "gender": "male", "parents": None},
    {"id": 3, "name": "Cass", "last_name": "Lund", "gender": "female", "parents": None},
    {"id": 4, "name": "Dov", "last_name": "Lund", "gender": "male", "parents": None},
]
PAIR_BONDS = [
    {"id": 30, "person_a": 2, "person_b": 3, "married": True, "separated": False,
     "divorced": None, "custody": None, "notes": "met in 1979", "confidence": 0.9},
]
EVENTS = [
    {"id": 10, "kind": "married", "person": 2, "spouse": 3, "dateTime": QDateTime(1980, 6, 1, 0, 0),
     "dateCertainty": "certain"},
    {"id": 11, "kind": "birth", "child": 1, "dateTime": QDateTime(1983, 4, 9, 10, 30),
     "dateCertainty": "approximate", "location": "Duluth"},
    {"id": 12, "kind": "shift", "person": 1, "dateTime": QDateTime(2011, 5, 1, 0, 0),
     "endDateTime": QDateTime(2011, 8, 1, 0, 0), "dateCertainty": "certain",
     "description": "moved away and went quiet", "notes": "her words",
     "anxiety": "up", "symptom": None, "functioning": "down",
     "relationship": "distance", "relationshipTargets": [2, 3], "relationshipTriangles": [],
     "relationshipIntensity": 2, "color": "#ff336699"},
    {"id": 13, "kind": "shift", "person": 1, "dateTime": QDateTime(2012, 1, 15, 0, 0),
     "dateCertainty": "certain", "description": "took her father's side",
     "relationship": "inside", "relationshipTargets": [2], "relationshipTriangles": [3, 4]},
]
EMOTIONS = [
    {"id": 50, "kind": "conflict", "intensity": 2, "event": 12, "person": 1, "target": 2,
     "color": "#80c00000", "notes": None, "layers": [40]},
]
LAYERS = [
    {"id": 40, "name": "Now", "description": "", "order": 0, "active": True, "internal": False,
     "storeGeometry": True, "itemProperties": {"1": {"itemPos": QPointF(1, 2)}}},
]
RECORD = {
    "people": PEOPLE, "events": EVENTS, "pair_bonds": PAIR_BONDS, "emotions": EMOTIONS,
    "layers": LAYERS, "multipleBirths": [], "layerItems": [], "items": [], "pruned": [],
    "lastItemId": 50, "currentDate": QDate(2026, 9, 16), "alias": "ada-family",
    "clusters": [{"id": "c1", "title": "The move", "summary": "", "eventIds": [12, 13],
                  "startDate": "2011-05-01", "endDate": "2012-01-15",
                  "pattern": None, "dominantVariable": None}],
    "pdp": {"people": [], "events": [], "pair_bonds": [], "delete": []},
}


def test_a_pro_record_survives_storage_and_comes_back_to_pro_equal(flask_app, test_user):
    """The importer's own step: the pickle the Pro app saved becomes the JSON
    row the chat app keeps, and Pro gets an equal pickle back."""
    diagram = test_user.free_diagram
    diagram.data = diagramjson.store(pickle.dumps(RECORD))
    db.session.commit()
    db.session.refresh(diagram)
    assert diagramjson.is_json(diagram.data)
    assert diagramjson.loads(diagram.data) == RECORD
    assert pickle.loads(diagram.pickled) == RECORD


def test_the_chat_app_reads_the_relationship_sub_fields(web, test_user):
    diagram = test_user.free_diagram
    diagram.data = diagramjson.store(pickle.dumps(RECORD))
    db.session.commit()

    csrf_token(web)
    events = {e["id"]: e for e in web.get("/personal/timeline").get_json()["events"]}
    assert events[12]["relationship"] == "distance"
    assert events[12]["relationshipTargets"] == [2, 3]
    assert events[13]["relationship"] == "inside"
    assert events[13]["relationshipTargets"] == [2]
    assert events[13]["relationshipTriangles"] == [3, 4]
    assert events[11]["child"] == 1
    assert events[10]["spouse"] == 3


def test_editing_an_event_by_hand_keeps_the_fields_only_the_desktop_knows(web, test_user):
    """The chat editor writes the fields it shows; relationshipIntensity and the
    desktop's drawing fields on the same event are not its to drop."""
    diagram = test_user.free_diagram
    diagram.data = diagramjson.store(pickle.dumps(RECORD))
    db.session.commit()

    saved = web.patch(
        "/personal/events/12",
        json={"description": "moved away and went quiet for a year"},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert saved.status_code == 200
    db.session.refresh(diagram)
    event = next(e for e in diagramjson.loads(diagram.data)["events"] if e["id"] == 12)
    assert event["description"] == "moved away and went quiet for a year"
    assert event["relationshipIntensity"] == 2
    assert event["color"] == "#ff336699"
    assert event["relationshipTargets"] == [2, 3]
