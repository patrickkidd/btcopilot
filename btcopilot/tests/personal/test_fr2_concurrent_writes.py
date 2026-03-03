"""Tests for FR-2: Personal-owned fields must survive concurrent Pro app writes.

The Pro app sends a full DiagramData blob via ``update_with_version_check``
that does **not** include Personal-owned fields (pdp, clusters,
clusterCacheKey). Before the fix, those fields were silently destroyed.
These tests verify they are preserved.
"""
import pickle
import base64

from btcopilot.pro.models import Diagram
from btcopilot.pro.models.diagram import _merge_personal_fields, PERSONAL_OWNED_FIELDS
from btcopilot.schema import DiagramData, PDP, Person, asdict
from btcopilot.extensions import db


# ---------------------------------------------------------------------------
# Unit tests for _merge_personal_fields
# ---------------------------------------------------------------------------


def test_merge_preserves_pdp_when_absent_in_incoming(flask_app):
    """If incoming blob omits 'pdp', existing pdp must carry forward."""
    existing_dict = {
        "people": [{"id": 1, "name": "Alice"}],
        "pdp": {"people": [{"id": -1, "name": "Bob"}], "events": [], "pair_bonds": []},
        "lastItemId": 5,
    }
    incoming_dict = {
        "people": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Charlie"}],
        "lastItemId": 6,
        # NOTE: 'pdp' intentionally absent — simulates Pro app save
    }

    existing_blob = pickle.dumps(existing_dict)
    incoming_blob = pickle.dumps(incoming_dict)

    merged_blob = _merge_personal_fields(existing_blob, incoming_blob)
    merged = pickle.loads(merged_blob)

    # Pro-owned field updated
    assert len(merged["people"]) == 2
    assert merged["lastItemId"] == 6
    # Personal-owned field preserved
    assert "pdp" in merged
    assert merged["pdp"] == existing_dict["pdp"]


def test_merge_preserves_clusters_when_absent_in_incoming(flask_app):
    """If incoming blob omits clusters/clusterCacheKey, they carry forward."""
    existing_dict = {
        "people": [],
        "clusters": [{"id": "c1", "title": "Anxiety cascade"}],
        "clusterCacheKey": "abc123",
    }
    incoming_dict = {
        "people": [{"id": 1, "name": "Alice"}],
        # clusters and clusterCacheKey intentionally absent
    }

    existing_blob = pickle.dumps(existing_dict)
    incoming_blob = pickle.dumps(incoming_dict)

    merged_blob = _merge_personal_fields(existing_blob, incoming_blob)
    merged = pickle.loads(merged_blob)

    assert merged["clusters"] == [{"id": "c1", "title": "Anxiety cascade"}]
    assert merged["clusterCacheKey"] == "abc123"
    assert merged["people"] == [{"id": 1, "name": "Alice"}]


def test_merge_respects_incoming_pdp_when_present(flask_app):
    """If incoming blob includes pdp, it should NOT be overwritten by existing."""
    existing_dict = {
        "pdp": {"people": [{"id": -1, "name": "Old"}], "events": [], "pair_bonds": []},
    }
    incoming_dict = {
        "pdp": {"people": [{"id": -2, "name": "New"}], "events": [], "pair_bonds": []},
        "clusters": [{"id": "c2", "title": "New cluster"}],
        "clusterCacheKey": "new_key",
    }

    existing_blob = pickle.dumps(existing_dict)
    incoming_blob = pickle.dumps(incoming_dict)

    merged_blob = _merge_personal_fields(existing_blob, incoming_blob)
    merged = pickle.loads(merged_blob)

    # Incoming values kept intact
    assert merged["pdp"]["people"][0]["name"] == "New"
    assert merged["clusters"][0]["title"] == "New cluster"
    assert merged["clusterCacheKey"] == "new_key"


def test_merge_noop_when_existing_blob_empty(flask_app):
    """Brand-new diagram (no existing data) — incoming blob passes through."""
    incoming_dict = {"people": [], "lastItemId": 0}
    incoming_blob = pickle.dumps(incoming_dict)

    result = _merge_personal_fields(None, incoming_blob)
    assert result is incoming_blob

    result2 = _merge_personal_fields(b"", incoming_blob)
    assert result2 is incoming_blob


def test_merge_noop_when_all_personal_fields_present(flask_app):
    """If incoming already has all PERSONAL_OWNED_FIELDS, return unchanged."""
    incoming_dict = {
        "pdp": {},
        "clusters": [],
        "clusterCacheKey": None,
        "people": [],
    }
    incoming_blob = pickle.dumps(incoming_dict)
    existing_blob = pickle.dumps({"pdp": {"people": [{"id": -1}]}, "clusters": []})

    result = _merge_personal_fields(existing_blob, incoming_blob)
    # Must be the same object (no re-serialization)
    assert result is incoming_blob


# ---------------------------------------------------------------------------
# Integration test: Pro-style save does not destroy Personal data
# ---------------------------------------------------------------------------


def test_pro_save_preserves_personal_pdp(subscriber):
    """Simulate Pro app overwriting diagram while Personal PDP exists.

    1. Personal app writes PDP into the diagram.
    2. Pro app saves scene data (without PDP).
    3. PDP must still be present in the diagram.
    """
    diagram = subscriber.user.free_diagram

    # Step 1: Personal app writes PDP via set_diagram_data
    diagram_data = diagram.get_diagram_data()
    diagram_data.pdp = PDP(
        people=[Person(id=-1, name="PDP Person")],
        events=[],
        pair_bonds=[],
    )
    diagram.set_diagram_data(diagram_data)
    db.session.commit()

    # Verify PDP is stored
    diagram = Diagram.query.get(diagram.id)
    assert len(diagram.get_diagram_data().pdp.people) == 1

    # Step 2: Pro app saves scene data — blob intentionally omits pdp
    pro_scene = {
        "people": [{"id": 1, "name": "User"}, {"id": 2, "name": "Assistant"}],
        "events": [],
        "pair_bonds": [],
        "lastItemId": 2,
        "items": [],
    }
    pro_blob = pickle.dumps(pro_scene)

    # Use update_with_version_check the same way pro/routes.py does
    current_version = diagram.version
    success, new_version = diagram.update_with_version_check(
        current_version, new_data=pro_blob
    )
    assert success
    db.session.commit()

    # Step 3: Verify PDP survived the Pro write
    diagram = Diagram.query.get(diagram.id)
    dd = diagram.get_diagram_data()
    assert len(dd.pdp.people) == 1, "PDP was destroyed by Pro app save"
    assert dd.pdp.people[0].name == "PDP Person"
    # Pro-owned data updated
    assert len(dd.people) == 2


def test_pro_save_preserves_clusters(subscriber):
    """Clusters written by Personal app must survive a Pro app save."""
    diagram = subscriber.user.free_diagram

    # Step 1: Inject clusters into existing data
    existing = pickle.loads(diagram.data) if diagram.data else {}
    existing["clusters"] = [{"id": "c1", "title": "Anxiety cascade", "eventIds": []}]
    existing["clusterCacheKey"] = "sha256_abc"
    diagram.data = pickle.dumps(existing)
    db.session.commit()

    # Step 2: Pro app save (no clusters)
    pro_scene = {"people": [], "events": [], "lastItemId": 0}
    pro_blob = pickle.dumps(pro_scene)

    diagram = Diagram.query.get(diagram.id)
    success, _ = diagram.update_with_version_check(diagram.version, new_data=pro_blob)
    assert success
    db.session.commit()

    # Step 3: Verify clusters survived
    diagram = Diagram.query.get(diagram.id)
    stored = pickle.loads(diagram.data)
    assert len(stored["clusters"]) == 1
    assert stored["clusterCacheKey"] == "sha256_abc"


def test_personal_save_can_update_pdp(subscriber):
    """Personal app sends a blob WITH pdp — new PDP must be written."""
    diagram = subscriber.user.free_diagram

    # Write initial PDP
    diagram_data = diagram.get_diagram_data()
    diagram_data.pdp = PDP(
        people=[Person(id=-1, name="Old PDP")],
        events=[],
        pair_bonds=[],
    )
    diagram.set_diagram_data(diagram_data)
    db.session.commit()

    # Personal app sends full blob including updated PDP
    diagram = Diagram.query.get(diagram.id)
    dd = diagram.get_diagram_data()
    dd.pdp = PDP(
        people=[Person(id=-2, name="New PDP Person")],
        events=[],
        pair_bonds=[],
    )
    full_blob = pickle.dumps(asdict(dd))

    success, _ = diagram.update_with_version_check(diagram.version, new_data=full_blob)
    assert success
    db.session.commit()

    # Verify updated PDP is stored
    diagram = Diagram.query.get(diagram.id)
    new_dd = diagram.get_diagram_data()
    assert len(new_dd.pdp.people) == 1
    assert new_dd.pdp.people[0].name == "New PDP Person"


def test_concurrent_pro_personal_writes_via_http(subscriber):
    """Full HTTP integration: Personal writes PDP, then Pro-style save via PUT.

    This is the original FR-2 bug scenario, exercised through the Personal
    app's HTTP endpoint.
    """
    diagram = subscriber.user.free_diagram

    # Step 1: Personal app writes PDP
    diagram_data = diagram.get_diagram_data()
    diagram_data.pdp = PDP(
        people=[Person(id=-1, name="PDP Alice")],
        events=[],
        pair_bonds=[],
    )
    diagram.set_diagram_data(diagram_data)
    db.session.commit()

    # Step 2: Simulate a Pro-style save through the Personal PUT endpoint
    # (Pro app sends scene data WITHOUT pdp)
    pro_scene = {
        "people": [{"id": 10, "name": "Pro Person"}],
        "events": [],
        "pair_bonds": [],
        "lastItemId": 10,
    }
    pro_blob_b64 = base64.b64encode(pickle.dumps(pro_scene)).decode("utf-8")

    diagram = Diagram.query.get(diagram.id)
    response = subscriber.put(
        f"/personal/diagrams/{diagram.id}",
        json={"data": pro_blob_b64, "expected_version": diagram.version},
    )
    assert response.status_code == 200

    # Step 3: PDP must still exist
    diagram = Diagram.query.get(diagram.id)
    dd = diagram.get_diagram_data()
    assert len(dd.pdp.people) == 1, "PDP destroyed by concurrent write via HTTP"
    assert dd.pdp.people[0].name == "PDP Alice"
