from mock import patch, AsyncMock

from btcopilot.extensions import db
from btcopilot.pro.models import Diagram
from btcopilot.schema import PDP, PDPDeltas, Person, Event, EventKind, asdict


def test_extract_success(subscriber, discussion):
    mock_pdp = PDP(
        people=[Person(id=-1, name="Mom", gender="female", confidence=0.8)],
        events=[
            Event(
                id=-2,
                kind=EventKind.Birth,
                person=-1,
                child=-1,
                description="Born",
                dateTime="1953-01-01",
                confidence=0.8,
            )
        ],
    )
    mock_deltas = PDPDeltas(people=mock_pdp.people, events=mock_pdp.events)

    with patch(
        "btcopilot.pdp.extract_full",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ):
        response = subscriber.post(
            f"/personal/discussions/{discussion.id}/extract",
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["people_count"] == 1
    assert data["events_count"] == 1
    assert data["pair_bonds_count"] == 0
    assert data["pdp"] == asdict(mock_pdp)

    diagram_data = discussion.diagram.get_diagram_data()
    assert len(diagram_data.pdp.people) == 1
    assert diagram_data.pdp.people[0].name == "Mom"


def test_extract_not_found(subscriber):
    response = subscriber.post("/personal/discussions/99999/extract")
    assert response.status_code == 404


def test_extract_no_diagram(subscriber):
    from btcopilot.personal.models import Discussion

    discussion = Discussion(user_id=subscriber.user.id, summary="No diagram")
    db.session.add(discussion)
    db.session.commit()

    response = subscriber.post(f"/personal/discussions/{discussion.id}/extract")
    assert response.status_code == 400
