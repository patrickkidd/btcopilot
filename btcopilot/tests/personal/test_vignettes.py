import pickle

from unittest.mock import patch, MagicMock

import btcopilot
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram
from btcopilot.schema import (
    Event,
    EventKind,
    Vignette,
    VignettePattern,
    VignetteResult,
    asdict,
)
from btcopilot.personal.vignettes import computeCacheKey, detectVignettes


def test_compute_cache_key_empty():
    result = computeCacheKey([])
    assert result == computeCacheKey([])
    assert len(result) == 16


def test_compute_cache_key_deterministic():
    events = [
        Event(id=1, kind=EventKind.Shift, dateTime="2024-01-15", symptom="up"),
        Event(id=2, kind=EventKind.Shift, dateTime="2024-01-20", anxiety="down"),
    ]
    key1 = computeCacheKey(events)
    key2 = computeCacheKey(events)
    assert key1 == key2


def test_compute_cache_key_changes_with_data():
    events1 = [Event(id=1, kind=EventKind.Shift, dateTime="2024-01-15", symptom="up")]
    events2 = [Event(id=1, kind=EventKind.Shift, dateTime="2024-01-15", symptom="down")]
    key1 = computeCacheKey(events1)
    key2 = computeCacheKey(events2)
    assert key1 != key2


def test_detect_vignettes_empty():
    result = detectVignettes([])
    assert isinstance(result, VignetteResult)
    assert result.vignettes == []
    assert result.cacheKey == "empty"


def test_detect_vignettes_calls_llm():
    events = [
        Event(
            id=1,
            kind=EventKind.Shift,
            dateTime="2024-01-15",
            description="Feeling anxious",
            symptom="up",
        ),
        Event(
            id=2,
            kind=EventKind.Shift,
            dateTime="2024-01-16",
            description="Sleep problems",
            anxiety="up",
        ),
    ]

    mock_response = MagicMock()
    mock_response.vignettes = [
        Vignette(
            id="v1",
            title="Anxiety Episode",
            summary="Two-day anxiety cascade",
            eventIds=[1, 2],
            pattern=VignettePattern.AnxietyCascade,
            dominantVariable="A",
        )
    ]

    with patch("btcopilot.personal.vignettes.llm.submit_one", return_value=mock_response):
        result = detectVignettes(events)

    assert isinstance(result, VignetteResult)
    assert len(result.vignettes) == 1
    assert result.vignettes[0].title == "Anxiety Episode"
    assert result.vignettes[0].eventIds == [1, 2]
    assert result.vignettes[0].startDate == "2024-01-15"
    assert result.vignettes[0].endDate == "2024-01-16"
    assert result.cacheKey is not None


def test_detect_vignettes_route_missing_events(subscriber):
    diagram = subscriber.user.free_diagram

    response = subscriber.post(f"/personal/diagrams/{diagram.id}/vignettes", json={})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_detect_vignettes_route_not_found(subscriber):
    response = subscriber.post("/personal/diagrams/99999/vignettes", json={"events": []})
    assert response.status_code == 404


def test_detect_vignettes_route_forbidden(subscriber, test_user_2):
    test_user_2.set_free_diagram(pickle.dumps({}))
    db.session.commit()
    other_diagram = test_user_2.free_diagram

    response = subscriber.post(
        f"/personal/diagrams/{other_diagram.id}/vignettes", json={"events": []}
    )
    assert response.status_code == 403


def test_detect_vignettes_route_success(subscriber):
    diagram = subscriber.user.free_diagram

    events_data = [
        {
            "id": 1,
            "kind": "shift",
            "dateTime": "2024-01-15",
            "description": "Anxious day",
            "anxiety": "up",
        },
        {
            "id": 2,
            "kind": "shift",
            "dateTime": "2024-01-16",
            "description": "Sleep issues",
            "symptom": "up",
        },
    ]

    mock_response = MagicMock()
    mock_response.vignettes = [
        Vignette(
            id="v1",
            title="Anxiety Cascade",
            summary="Brief cascade",
            eventIds=[1, 2],
            pattern=VignettePattern.AnxietyCascade,
        )
    ]

    with patch("btcopilot.personal.vignettes.llm.submit_one", return_value=mock_response):
        response = subscriber.post(
            f"/personal/diagrams/{diagram.id}/vignettes", json={"events": events_data}
        )

    assert response.status_code == 200
    data = response.get_json()
    assert "vignettes" in data
    assert "cacheKey" in data
    assert len(data["vignettes"]) == 1
    assert data["vignettes"][0]["title"] == "Anxiety Cascade"
