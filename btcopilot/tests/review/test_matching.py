"""What the ballot reads of each coding's family, and the matching of the
coach's clusters and records against the room's."""

from btcopilot.matching import match_clusters
from btcopilot.review.coachscore import compare
from btcopilot.schema import Cluster
from btcopilot.tests.review.conftest import coded


def _person(person_id, name, gender="male", parents=None):
    return {"id": person_id, "name": name, "gender": gender, "parents": parents}


def _bond(bond_id, a, b):
    return {"id": bond_id, "person_a": a, "person_b": b}


def test_the_records_say_the_family_each_version_is_drawn_against(patrick, cut):
    # R-0326
    """A version of a person is drawn as a fragment, so the ballot is handed the
    people, the bonds and the events of the coding it came from."""
    coded(
        patrick.user,
        cut,
        {
            "people": [
                _person(1, "Marcus"),
                _person(2, "Delphine", "female"),
                _person(3, "Corinne", "female", parents=10),
            ],
            "pair_bonds": [dict(_bond(10, 1, 2), married=True)],
            "events": [
                {
                    "id": 20,
                    "kind": "married",
                    "person": 1,
                    "spouse": 2,
                    "dateTime": "1970-06-01",
                }
            ],
        },
    )
    response = patrick.get(f"/review/records?cut_id={cut.id}")
    assert response.status_code == 200

    record = response.json[0]
    assert [p["name"] for p in record["people"]] == ["Marcus", "Delphine", "Corinne"]
    assert record["people"][2]["parents"] == 10
    assert record["pair_bonds"] == [
        {"id": 10, "person_a": 1, "person_b": 2, "married": True}
    ]
    assert record["events"][0]["dateTime"] == "1970-06-01"


def _cluster(cluster_id, events):
    return Cluster(id=cluster_id, title=cluster_id, summary="", eventIds=list(events))


def test_clusters_sharing_half_their_events_match_and_disjoint_ones_do_not():
    # R-0597
    mine = [_cluster("a", [11, 12, 13, 14]), _cluster("b", [15, 16, 17])]
    agreed = [_cluster("x", [1, 2, 9]), _cluster("y", [5, 6, 7])]
    found = match_clusters(mine, agreed, {11: 1, 12: 2, 13: 3, 15: 8})
    assert [(a.id, b.id) for a, b in found.matched_pairs] == [("a", "x")]
    assert [c.id for c in found.ai_unmatched] == ["b"]
    assert [c.id for c in found.gt_unmatched] == ["y"]


def test_a_comparison_scores_pair_bonds_and_clusters():
    # R-0597
    events = [
        {
            "id": i,
            "kind": "noted",
            "person": 1,
            "description": "Moved",
            "dateTime": f"199{i}-05-01",
            "dateCertainty": "certain",
        }
        for i in (3, 4, 5)
    ]
    agreed = {
        "people": [_person(1, "Marcus"), _person(2, "Delphine", "female")],
        "pair_bonds": [_bond(10, 1, 2)],
        "events": events,
        "clusters": [{"id": "c", "title": "c", "summary": "", "eventIds": [3, 4, 5]}],
    }
    same = compare(agreed, agreed)
    assert (same["pair_bonds"], same["clusters"]) == (1.0, 1.0)
    bare = compare(dict(agreed, pair_bonds=[], clusters=[]), agreed)
    assert (bare["pair_bonds"], bare["clusters"]) == (0.0, 0.0)
