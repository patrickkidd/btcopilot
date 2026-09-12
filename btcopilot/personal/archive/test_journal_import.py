import pytest
from mock import patch, AsyncMock

from btcopilot.pro.models import Diagram
from btcopilot.schema import PDP, PDPDeltas, Person, Event, EventKind, asdict


def test_import_journal_success(subscriber):
    diagram = subscriber.user.free_diagram
    initial_version = diagram.version

    mock_pdp = PDP(
        people=[Person(id=-1, name="Mom", confidence=0.8)],
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                person=-1,
                description="Called about money",
                confidence=0.7,
            )
        ],
    )
    mock_deltas = PDPDeltas(
        people=[Person(id=-1, name="Mom", confidence=0.8)],
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                person=-1,
                description="Called about money",
                confidence=0.7,
            )
        ],
    )

    with patch(
        "btcopilot.pdp.import_text",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ):
        response = subscriber.post(
            f"/personal/diagrams/{diagram.id}/import-text",
            json={"text": "Mom called me yesterday about money problems."},
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["summary"]["people"] == 1
    assert data["summary"]["events"] == 1
    assert "pdp" in data

    diagram = Diagram.query.get(diagram.id)
    diagram_data = diagram.get_diagram_data()
    assert len(diagram_data.pdp.people) == 1
    assert diagram_data.pdp.people[0].name == "Mom"


def test_import_journal_missing_text(subscriber):
    diagram = subscriber.user.free_diagram

    response = subscriber.post(
        f"/personal/diagrams/{diagram.id}/import-text",
        json={},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_import_journal_empty_text(subscriber):
    diagram = subscriber.user.free_diagram

    response = subscriber.post(
        f"/personal/diagrams/{diagram.id}/import-text",
        json={"text": "   "},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_import_journal_not_found(subscriber):
    response = subscriber.post(
        "/personal/diagrams/99999/import-text",
        json={"text": "Some journal text"},
    )

    assert response.status_code == 404


def test_import_journal_no_access(subscriber, test_user_2):
    import pickle
    from btcopilot.extensions import db

    test_user_2.set_free_diagram(pickle.dumps({}))
    db.session.commit()
    other_diagram = test_user_2.free_diagram

    response = subscriber.post(
        f"/personal/diagrams/{other_diagram.id}/import-text",
        json={"text": "Some journal text"},
    )

    assert response.status_code == 403


@pytest.mark.e2e
def test_import_journal_real_llm(subscriber):
    """Integration test that calls the real LLM. Run with: pytest -m e2e"""
    diagram = subscriber.user.free_diagram

    journal_text = """
    December 15, 2024

    Had a difficult call with Mom today. She was upset about Dad's health declining
    and started crying on the phone. I felt my anxiety spike immediately. I tried to
    stay calm and listen but found myself wanting to fix everything for her.

    Later that evening, my sister Sarah called. She's been distant lately and I think
    she's avoiding the family situation. We had a brief conversation but she cut it
    short saying she was busy with work.

    I noticed I've been having trouble sleeping this week. Keep waking up at 3am
    thinking about all of this.
    """

    response = subscriber.post(
        f"/personal/diagrams/{diagram.id}/import-text",
        json={"text": journal_text},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    print(f"\n=== Journal Import Results ===")
    print(f"People extracted: {data['summary']['people']}")
    print(f"Events extracted: {data['summary']['events']}")
    print(f"Pair bonds extracted: {data['summary']['pairBonds']}")

    if data.get("pdp"):
        pdp = data["pdp"]
        print(f"\n--- People ---")
        for p in pdp.get("people", []):
            print(
                f"  {p.get('id')}: {p.get('name')} (confidence: {p.get('confidence')})"
            )

        print(f"\n--- Events ---")
        for e in pdp.get("events", []):
            print(f"  {e.get('id')}: {e.get('kind')} - {e.get('description', '')[:50]}")
            print(
                f"       person: {e.get('person')}, S:{e.get('symptom')} A:{e.get('anxiety')} R:{e.get('relationship')} F:{e.get('functioning')}"
            )

    diagram = Diagram.query.get(diagram.id)
    diagram_data = diagram.get_diagram_data()
    assert diagram_data.pdp is not None
    print(f"\n=== Diagram PDP Updated ===")
    print(f"Total people in PDP: {len(diagram_data.pdp.people)}")
    print(f"Total events in PDP: {len(diagram_data.pdp.events)}")
