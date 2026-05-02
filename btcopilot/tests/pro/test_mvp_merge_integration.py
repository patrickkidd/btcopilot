"""
End-to-end integration tests exercising the FULL stack of the MVP merge fix:
HTTP endpoints + Diagram model + apply_local_changes + reserve_ids.

These mirror the manual JOURNEYS.md scenarios at the Python integration
level. The MCP-driven harness journeys cover the UI layer once
familydiagram-testing's `save_diagram` bridge command is available.

Plan: familydiagram/doc/plans/2026-05-01--mvp-merge-fix/README.md
Journeys: familydiagram/doc/plans/2026-05-01--mvp-merge-fix/JOURNEYS.md
"""

import pickle
from datetime import datetime

import PyQt5.sip  # for unpickling QtCore types

from btcopilot.extensions import db
from btcopilot.pro.models import Diagram


def _put_diagram(client, diagram_id, blob, expected_version):
    return client.put(
        f"/v1/diagrams/{diagram_id}",
        data=pickle.dumps(
            {
                "data": blob,
                "updated_at": datetime.utcnow(),
                "expected_version": expected_version,
            }
        ),
    )


def _seed_diagram(test_user, people):
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps(
        {
            "people": people,
            "events": [],
            "pair_bonds": [],
            "emotions": [],
            "multipleBirths": [],
            "layers": [],
            "layerItems": [],
            "items": [],
            "pruned": [],
            "lastItemId": max([p["id"] for p in people], default=0),
        }
    )
    db.session.commit()
    return diagram


def test_j1a_pro_stale_save_preserves_personal_edit(flask_app, test_user):
    """
    J-1A integration: Pro is open with a stale snapshot of person A.
    Personal edits person A. Pro then saves something else (person B).
    Pro's stale snapshot of A must NOT clobber Personal's edit to A.
    """
    diagram = _seed_diagram(
        test_user,
        [
            {"id": 1, "name": "A", "cutoff": False},
            {"id": 2, "name": "B"},
            {"id": 3, "name": "C"},
        ],
    )
    base_version = diagram.version
    pro_open_snapshot = pickle.loads(diagram.data)

    # Personal saves an edit to A: cutoff=True.
    personal_local = pickle.loads(diagram.data)
    personal_local["people"] = [
        {"id": 1, "name": "A", "cutoff": True},
        {"id": 2, "name": "B"},
        {"id": 3, "name": "C"},
    ]
    with flask_app.test_client(user=test_user) as client:
        r = _put_diagram(
            client, diagram.id, pickle.dumps(personal_local), base_version
        )
    assert r.status_code == 200, f"Personal save failed: {r.status_code}"
    canonical_after_personal = pickle.loads(pickle.loads(r.data)["data"])
    assert canonical_after_personal["people"][0]["cutoff"] is True

    # Pro saves with stale snapshot — version is 1, but server is at 2 now.
    # Pro's local has stale A (cutoff=False) and a renamed B.
    pro_local = pro_open_snapshot.copy()
    pro_local["people"] = [
        {"id": 1, "name": "A", "cutoff": False},  # stale
        {"id": 2, "name": "B_PR"},  # Pro's edit
        {"id": 3, "name": "C"},
    ]

    # Apply the snapshot-diff merge as Pro's applyChange does.
    from btcopilot.schema import DiagramData

    server_state = pickle.loads(diagram.data)  # what server has now (after Personal's save)
    server_state["people"] = canonical_after_personal["people"]
    merged_people = DiagramData.apply_local_changes(
        server_state["people"],
        pro_open_snapshot["people"],
        pro_local["people"],
    )

    # Build Pro's outgoing blob: server's full state with merged people.
    pro_out = server_state.copy()
    pro_out["people"] = merged_people

    with flask_app.test_client(user=test_user) as client:
        r = _put_diagram(client, diagram.id, pickle.dumps(pro_out), base_version + 1)
    assert r.status_code == 200, f"Pro save failed: {r.status_code}"

    # Verify final DB state
    final_blob = pickle.loads(pickle.loads(r.data)["data"])
    final_people = {p["id"]: p for p in final_blob["people"]}
    assert final_people[1]["cutoff"] is True, (
        "Personal's cutoff edit must survive Pro's stale-snapshot save"
    )
    assert final_people[2]["name"] == "B_PR", "Pro's edit to B must apply"


def test_j2a_personal_delete_survives_pro_save(flask_app, test_user):
    """
    J-2A integration: Personal deletes event 10. Pro saves (a different edit)
    with a stale snapshot that still has event 10. Event must stay deleted.
    """
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps(
        {
            "people": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}],
            "events": [{"id": 10, "kind": "Birth", "person": 1}],
            "pair_bonds": [], "emotions": [], "multipleBirths": [],
            "layers": [], "layerItems": [], "items": [], "pruned": [],
            "lastItemId": 10,
        }
    )
    db.session.commit()
    base_version = diagram.version
    pro_open_snapshot = pickle.loads(diagram.data)

    # Personal deletes event 10.
    personal_local = pickle.loads(diagram.data)
    personal_local["events"] = []
    with flask_app.test_client(user=test_user) as client:
        r = _put_diagram(
            client, diagram.id, pickle.dumps(personal_local), base_version
        )
    assert r.status_code == 200

    # Pro edits B's name with stale snapshot (still has event 10 locally).
    pro_local = pro_open_snapshot.copy()
    pro_local["people"] = [
        {"id": 1, "name": "A"},
        {"id": 2, "name": "B_PR"},
    ]
    pro_local["events"] = [{"id": 10, "kind": "Birth", "person": 1}]  # stale

    from btcopilot.schema import DiagramData

    server_state = pickle.loads(diagram.data)
    server_state["events"] = []  # server has no event 10 after Personal's delete

    merged_events = DiagramData.apply_local_changes(
        server_state["events"],
        pro_open_snapshot["events"],
        pro_local["events"],
    )
    merged_people = DiagramData.apply_local_changes(
        server_state["people"],
        pro_open_snapshot["people"],
        pro_local["people"],
    )
    pro_out = server_state.copy()
    pro_out["events"] = merged_events
    pro_out["people"] = merged_people

    with flask_app.test_client(user=test_user) as client:
        r = _put_diagram(client, diagram.id, pickle.dumps(pro_out), base_version + 1)
    assert r.status_code == 200
    final_blob = pickle.loads(pickle.loads(r.data)["data"])
    assert final_blob["events"] == [], (
        "Event 10 must stay deleted; Pro's stale snapshot must NOT resurrect it"
    )
    final_people = {p["id"]: p for p in final_blob["people"]}
    assert final_people[2]["name"] == "B_PR", "Pro's name edit must apply"


def test_j3_block_allocation_prevents_id_collision(flask_app, test_user):
    """
    J-3 integration: Pro reserves a block. Personal commits a PDP item server-side.
    Both subsequently get distinct ids — no collision.
    """
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"people": [], "lastItemId": 10})
    db.session.commit()

    # Pro requests block of 100. Server bumps lastItemId to 110.
    with flask_app.test_client(user=test_user) as client:
        r = client.post(
            f"/v1/diagrams/{diagram.id}/reserve_ids",
            data=pickle.dumps({"count": 100}),
        )
    assert r.status_code == 200
    block = pickle.loads(r.data)
    assert block["start"] == 11
    assert block["end"] == 110

    # Now another reservation (e.g., a second Pro instance) gets a different block.
    with flask_app.test_client(user=test_user) as client:
        r2 = client.post(
            f"/v1/diagrams/{diagram.id}/reserve_ids",
            data=pickle.dumps({"count": 100}),
        )
    block2 = pickle.loads(r2.data)
    assert block2["start"] == 111, "Second block must not overlap the first"
    assert block2["end"] == 210

    # Verify server's stored lastItemId reflects both reservations.
    refreshed = Diagram.query.get(diagram.id)
    assert pickle.loads(refreshed.data)["lastItemId"] == 210


def test_canonical_blob_returned_on_200(flask_app, test_user):
    """
    Latent fix 3a integration: PUT 200 must return canonical post-write blob
    so client can refresh its snapshot.
    """
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"people": [], "lastItemId": 0})
    db.session.commit()

    new_blob = pickle.dumps({"people": [{"id": 1, "name": "X"}], "lastItemId": 1})
    with flask_app.test_client(user=test_user) as client:
        r = _put_diagram(client, diagram.id, new_blob, diagram.version)
    assert r.status_code == 200
    body = pickle.loads(r.data)
    assert "data" in body
    canonical = pickle.loads(body["data"])
    assert canonical["people"][0]["name"] == "X"
