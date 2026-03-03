import pickle

from unittest.mock import patch, MagicMock

import btcopilot
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram
from btcopilot.schema import (
    Event,
    EventKind,
    Cluster,
    ClusterPattern,
    ClusterResult,
    asdict,
)
from btcopilot.personal.clusters import compute_cache_key, detect_clusters


def test_compute_cache_key_empty():
    result = compute_cache_key([])
    assert result == compute_cache_key([])
    assert len(result) == 16


def test_compute_cache_key_deterministic():
    events = [
        Event(id=1, kind=EventKind.Shift, dateTime="2024-01-15", symptom="up"),
        Event(id=2, kind=EventKind.Shift, dateTime="2024-01-20", anxiety="down"),
    ]
    key1 = compute_cache_key(events)
    key2 = compute_cache_key(events)
    assert key1 == key2


def test_compute_cache_key_changes_with_data():
    events1 = [Event(id=1, kind=EventKind.Shift, dateTime="2024-01-15", symptom="up")]
    events2 = [Event(id=1, kind=EventKind.Shift, dateTime="2024-01-15", symptom="down")]
    key1 = compute_cache_key(events1)
    key2 = compute_cache_key(events2)
    assert key1 != key2


def test_detect_clusters_empty():
    result = detect_clusters([])
    assert isinstance(result, ClusterResult)
    assert result.clusters == []
    assert result.cacheKey == "empty"


def test_detect_clusters_calls_llm():
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
    mock_response.clusters = [
        Cluster(
            id="c1",
            title="Anxiety Episode",
            summary="Two-day anxiety cascade",
            eventIds=[1, 2],
            pattern=ClusterPattern.AnxietyCascade,
            dominantVariable="A",
        )
    ]

    with patch(
        "btcopilot.personal.clusters.gemini_structured_sync", return_value=mock_response
    ):
        result = detect_clusters(events)

    assert isinstance(result, ClusterResult)
    assert len(result.clusters) == 1
    assert result.clusters[0].title == "Anxiety Episode"
    assert result.clusters[0].eventIds == [1, 2]
    assert result.clusters[0].startDate == "2024-01-15"
    assert result.clusters[0].endDate == "2024-01-16"
    assert result.cacheKey is not None


def test_detect_clusters_route_missing_events(subscriber):
    diagram = subscriber.user.free_diagram

    response = subscriber.post(f"/personal/diagrams/{diagram.id}/clusters", json={})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_detect_clusters_route_not_found(subscriber):
    response = subscriber.post("/personal/diagrams/99999/clusters", json={"events": []})
    assert response.status_code == 404


def test_detect_clusters_route_forbidden(subscriber, test_user_2):
    test_user_2.set_free_diagram(pickle.dumps({}))
    db.session.commit()
    other_diagram = test_user_2.free_diagram

    response = subscriber.post(
        f"/personal/diagrams/{other_diagram.id}/clusters", json={"events": []}
    )
    assert response.status_code == 403


def test_detect_clusters_route_success(subscriber):
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
    mock_response.clusters = [
        Cluster(
            id="c1",
            title="Anxiety Cascade",
            summary="Brief cascade",
            eventIds=[1, 2],
            pattern=ClusterPattern.AnxietyCascade,
        )
    ]

    with patch(
        "btcopilot.personal.clusters.gemini_structured_sync", return_value=mock_response
    ):
        response = subscriber.post(
            f"/personal/diagrams/{diagram.id}/clusters", json={"events": events_data}
        )

    assert response.status_code == 200
    data = response.get_json()
    assert "clusters" in data
    assert "cacheKey" in data
    assert len(data["clusters"]) == 1
    assert data["clusters"][0]["title"] == "Anxiety Cascade"


def test_detect_clusters_idempotent():
    """Calling detect_clusters with the same events produces the same cache key (T7-12)."""
    events = [
        Event(id=1, kind=EventKind.Shift, dateTime="2024-01-15", symptom="up"),
        Event(id=2, kind=EventKind.Shift, dateTime="2024-01-16", anxiety="up"),
    ]

    mock_response = MagicMock()
    mock_response.clusters = [
        Cluster(
            id="c1",
            title="Test Cluster",
            summary="Test",
            eventIds=[1, 2],
            pattern=ClusterPattern.AnxietyCascade,
        )
    ]

    with patch(
        "btcopilot.personal.clusters.gemini_structured_sync", return_value=mock_response
    ):
        result1 = detect_clusters(events)
        result2 = detect_clusters(events)

    assert result1.cacheKey == result2.cacheKey


def test_detect_clusters_handles_single_event():
    """Single event produces valid cluster result (T7-12 edge case)."""
    events = [
        Event(id=1, kind=EventKind.Shift, dateTime="2024-01-15", description="Solo event"),
    ]

    mock_response = MagicMock()
    mock_response.clusters = []

    with patch(
        "btcopilot.personal.clusters.gemini_structured_sync", return_value=mock_response
    ):
        result = detect_clusters(events)

    assert isinstance(result, ClusterResult)
    assert result.clusters == []
    assert result.cacheKey is not None


def test_auto_detect_clusters_after_pdp_accept(subscriber):
    """T7-12: After PDP accept (events committed to diagram), clusters are auto-detected
    via the /clusters endpoint without manual intervention.

    This simulates the full flow:
    1. Import text → PDP events created
    2. Accept PDP → events committed to diagram
    3. Auto-detect clusters (client calls /clusters with committed events)
    4. Clusters returned and up-to-date
    """
    from mock import AsyncMock
    from btcopilot.schema import PDP, PDPDeltas, Person

    diagram = subscriber.user.free_diagram

    # Step 1: Import text to create PDP events
    events = [
        Event(
            id=-1,
            kind=EventKind.Shift,
            dateTime="2024-06-01",
            description="Anxiety spike after family call",
            anxiety="up",
            person=-10,
        ),
        Event(
            id=-2,
            kind=EventKind.Shift,
            dateTime="2024-06-02",
            description="Sleep disrupted, racing thoughts",
            symptom="up",
            person=-10,
        ),
        Event(
            id=-3,
            kind=EventKind.Shift,
            dateTime="2024-06-03",
            description="Conflict with spouse about schedule",
            relationship="conflict",
            person=-10,
        ),
        Event(
            id=-4,
            kind=EventKind.Shift,
            dateTime="2024-06-10",
            description="Processing session with therapist",
            functioning="up",
            person=-10,
        ),
        Event(
            id=-5,
            kind=EventKind.Shift,
            dateTime="2024-06-11",
            description="Good conversation with spouse, reconnecting",
            relationship="toward",
            person=-10,
        ),
        Event(
            id=-6,
            kind=EventKind.Shift,
            dateTime="2024-07-01",
            description="Work deadline stress",
            anxiety="up",
            person=-10,
        ),
        Event(
            id=-7,
            kind=EventKind.Shift,
            dateTime="2024-07-02",
            description="Headaches started",
            symptom="up",
            person=-10,
        ),
        Event(
            id=-8,
            kind=EventKind.Shift,
            dateTime="2024-07-03",
            description="Snapped at coworker",
            relationship="conflict",
            person=-10,
        ),
        Event(
            id=-9,
            kind=EventKind.Shift,
            dateTime="2024-07-15",
            description="Went for long walk, felt calmer",
            anxiety="down",
            person=-10,
        ),
        Event(
            id=-10,
            kind=EventKind.Shift,
            dateTime="2024-07-16",
            description="Talked it out with manager",
            relationship="toward",
            person=-10,
        ),
    ]
    mock_pdp = PDP(
        people=[Person(id=-10, name="Self", confidence=0.9)],
        events=events,
    )
    mock_deltas = PDPDeltas(
        people=[Person(id=-10, name="Self", confidence=0.9)],
        events=events,
    )

    with patch(
        "btcopilot.pdp.import_text",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ):
        response = subscriber.post(
            f"/personal/diagrams/{diagram.id}/import-text",
            json={"text": "Journal with 10 events spanning June-July 2024."},
        )

    assert response.status_code == 200
    pdp_data = response.get_json()["pdp"]
    assert len(pdp_data["events"]) == 10

    # Step 2: Simulate accept — events are now "committed" in diagram
    # (In real app, client calls commit_pdp_items then diagram.save)

    # Step 3: Auto-detect clusters (what the client does after PDP accept)
    committed_events = [asdict(e) for e in events]
    # Simulate committed events with positive IDs (as they would be after commit)
    for i, e in enumerate(committed_events):
        e["id"] = i + 1  # Positive IDs after commit

    mock_cluster_response = MagicMock()
    mock_cluster_response.clusters = [
        Cluster(
            id="c1",
            title="Family Anxiety Cascade",
            summary="Family call triggers anxiety, sleep disruption, and spousal conflict",
            eventIds=[1, 2, 3, 4, 5],
            pattern=ClusterPattern.AnxietyCascade,
            dominantVariable="A",
        ),
        Cluster(
            id="c2",
            title="Work Stress Episode",
            summary="Work deadline triggers physical symptoms and interpersonal conflict",
            eventIds=[6, 7, 8, 9, 10],
            pattern=ClusterPattern.WorkFamilySpillover,
            dominantVariable="A",
        ),
    ]

    with patch(
        "btcopilot.personal.clusters.gemini_structured_sync",
        return_value=mock_cluster_response,
    ):
        response = subscriber.post(
            f"/personal/diagrams/{diagram.id}/clusters",
            json={"events": committed_events},
        )

    assert response.status_code == 200
    data = response.get_json()
    assert "clusters" in data
    assert "cacheKey" in data
    assert len(data["clusters"]) == 2

    # Verify cluster content
    cluster_titles = {c["title"] for c in data["clusters"]}
    assert "Family Anxiety Cascade" in cluster_titles
    assert "Work Stress Episode" in cluster_titles

    # Verify all 10 events are covered by the two clusters
    all_cluster_event_ids = set()
    for c in data["clusters"]:
        all_cluster_event_ids.update(c["eventIds"])
    assert all_cluster_event_ids == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}

    # Verify cache key is stable (idempotency)
    first_cache_key = data["cacheKey"]
    with patch(
        "btcopilot.personal.clusters.gemini_structured_sync",
        return_value=mock_cluster_response,
    ):
        response2 = subscriber.post(
            f"/personal/diagrams/{diagram.id}/clusters",
            json={"events": committed_events},
        )

    assert response2.get_json()["cacheKey"] == first_cache_key
