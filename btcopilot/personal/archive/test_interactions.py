from btcopilot.personal.models import Interaction
from btcopilot.personal.interactions import recent
from btcopilot.schema import ItemKind


def test_record_and_query(subscriber):
    diagram = subscriber.user.free_diagram

    for name in ["Ada", "Bea", "Cy"]:
        response = subscriber.post(
            "/personal/interactions/",
            json={
                "diagram_id": diagram.id,
                "kind": "look",
                "item_kind": ItemKind.Person.value,
                "item_id": name,
                "session_id": "s1",
            },
        )
        assert response.status_code == 200

    assert Interaction.query.filter_by(diagram_id=diagram.id).count() == 3
    assert [x.item_id for x in recent(diagram.id, 2)] == ["Cy", "Bea"]

    response = subscriber.get(f"/personal/interactions/?diagram_id={diagram.id}&n=2")
    assert response.status_code == 200
    assert len(response.get_json()["interactions"]) == 2


def test_record_rejects_unknown_kind(subscriber):
    diagram = subscriber.user.free_diagram

    response = subscriber.post(
        "/personal/interactions/",
        json={
            "diagram_id": diagram.id,
            "kind": "wave",
            "item_kind": ItemKind.Person.value,
            "item_id": "1",
        },
    )
    assert response.status_code == 500
