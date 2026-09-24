import pickle

from btcopilot import diagramjson
from btcopilot.diagrams import migrate_json
from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.personal.recordtext import render


OLD = {
    "people": [
        {"id": 1, "name": "Ada", "parents": 30},
        {"id": 2, "name": "Ben"},
        {"id": 3, "name": "Cass"},
        {"id": 4, "name": "Dov"},
    ],
    "pair_bonds": [{"id": 30, "person_a": 2, "person_b": 3, "married": True}],
    "events": [
        {"id": 12, "kind": "shift", "person": 1, "dateTime": "2011-05-01",
         "description": "moved away", "anxiety": "up", "functioning": "down",
         "relationship": "distance", "relationshipTargets": [2, 3]},
        {"id": 13, "kind": "shift", "person": 1, "dateTime": "2012-01-15",
         "description": "took his side", "relationship": "inside",
         "relationshipTargets": [2], "relationshipTriangles": [3, 4]},
    ],
    "lastItemId": 30,
}


def _migrated(user) -> Diagram:
    diagram = Diagram(user_id=user.id, name="Old")
    diagram.data = pickle.dumps(OLD)
    db.session.add(diagram)
    db.session.commit()
    migrate_json.run()
    return diagram


def test_an_old_diagrams_timeline_moves_come_across_and_the_coach_reads_them(subscriber):
    # R-0052
    diagram = _migrated(subscriber.user)
    assert diagramjson.is_json(diagram.data)
    record = render(diagram.get_diagram_data())
    assert (
        '12 2011-05-01 [shift] person=1 "moved away" anxiety=up functioning=down '
        "relationship=distance targets=[2, 3]"
    ) in record
    assert "relationship=inside targets=[2] triangles=[3, 4]" in record


def test_an_old_diagrams_families_and_bonds_come_across(subscriber):
    # R-0052
    diagram = _migrated(subscriber.user)
    record = render(diagram.get_diagram_data())
    assert "1 Ada parents=30" in record
    assert "30 2+3 married" in record

