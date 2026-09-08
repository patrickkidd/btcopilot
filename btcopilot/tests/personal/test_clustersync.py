"""Clusters are stored, not derived on read: a turn that moves an event
re-groups the line and writes the grouping into the record, a grouping the user
made is never regrouped away, and what the coach points at still resolves."""

import pytest
from mock import patch

from btcopilot.companion.timeline import build_timeline
from btcopilot.extensions import db
from btcopilot.personal import chips
from btcopilot.personal.chips import ChipKind
from btcopilot.personal.clusters import sync
from btcopilot.personal.coachturn import CoachTurn
from btcopilot.personal.models import Author, Change
from btcopilot.personal.toolbox import ToolName
from btcopilot.schema import (
    Cluster,
    ClusterResult,
    ClusterSource,
    DateCertainty,
    Event,
    EventKind,
    Person,
    asdict,
)
from btcopilot.tests.personal.conftest import Model, called, csrf_token, said


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.personal.models.discussion.response_text_sync",
        lambda *a, **k: "A session title",
    )


@pytest.fixture(autouse=True)
def regrouping():
    """Put the real regrouping back over the suite-wide stub; the model call it
    makes is scripted per test."""
    with patch("btcopilot.personal.clusters.sync", new=sync):
        yield


@pytest.fixture
def family(test_user):
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren"))]
    data.events = [
        asdict(
            Event(
                id=10 + n,
                kind=EventKind.Shift,
                person=1,
                dateTime=f"1994-0{n + 1}-01",
                dateCertainty=DateCertainty.Certain,
                description=f"moment {n}",
                anxiety="up",
            )
        )
        for n in range(4)
    ]
    data.lastItemId = 13
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def detects(*groups: tuple[str, list[int]]):
    """Script the model's grouping: one (name, event ids) pair per group."""
    return patch(
        "btcopilot.personal.clusters.detect_clusters",
        return_value=ClusterResult(
            clusters=[
                Cluster(id=f"model{n}", title=name, summary=f"{name} summary",
                         eventIds=list(ids))
                for n, (name, ids) in enumerate(groups)
            ]
        ),
    )


def clusters_of(diagram) -> dict:
    return {c["id"]: c for c in diagram.get_diagram_data().clusters}


def test_a_turn_that_adds_an_event_stores_the_grouping(discussion, family):
    with detects(("The hard spring", [10, 11, 12, 13, 14])):
        CoachTurn(
            discussion,
            "That winter she got sick too.",
            model=Model(
                called(
                    ToolName.EditEvent,
                    kind="shift",
                    date="1994-05-01",
                    description="got sick",
                    person=1,
                    symptom="up",
                ),
                said("I put that down."),
            ),
        ).run()

    stored = clusters_of(family)
    assert len(stored) == 1
    cluster = next(iter(stored.values()))
    assert cluster["name"] == "The hard spring"
    assert cluster["source"] == ClusterSource.Model.value
    assert cluster["eventIds"] == [10, 11, 12, 13, 14]
    assert (cluster["startDate"], cluster["endDate"]) == ("1994-01-01", "1994-05-01")
    assert family.get_diagram_data().clusterCacheKey


def test_a_turn_that_changes_no_event_does_not_regroup(discussion, family):
    with detects(("Never asked for", [10, 11])) as detect:
        CoachTurn(
            discussion, "Tell me about that.", model=Model(said("It was hard."))
        ).run()
    detect.assert_not_called()
    assert clusters_of(family) == {}


def test_the_grouping_is_written_by_the_coach_in_the_same_turn(discussion, family):
    with detects(("The hard spring", [10, 11])):
        reply = CoachTurn(
            discussion,
            "She got sick.",
            model=Model(
                called(ToolName.EditEvent, kind="shift", date="1994-05-01",
                       description="got sick", person=1),
                said("Noted."),
            ),
        ).run()

    change = Change.query.filter_by(
        diagram_id=family.id, turn_id=reply["turn_id"]
    ).order_by(Change.id.desc()).first()
    assert change.author is Author.Coach
    assert {d["item_kind"] for d in change.deltas} == {"cluster", "diagram"}


def test_a_grouping_the_user_made_survives_regrouping(discussion, family):
    data = family.get_diagram_data()
    data.clusters = [
        asdict(
            Cluster(
                id="c1",
                title="When he left",
                summary="",
                name="When he left",
                eventIds=[10, 11],
                source=ClusterSource.User,
            )
        )
    ]
    family.set_diagram_data(data)
    db.session.commit()

    with detects(("Everything at once", [10, 11, 12, 13])):
        sync(family.id, turn_id="t1")

    stored = clusters_of(family)
    theirs = stored["c1"]
    assert theirs["name"] == "When he left"
    assert theirs["eventIds"] == [10, 11]
    assert theirs["source"] == ClusterSource.User.value

    mine = [c for c in stored.values() if c["source"] == ClusterSource.Model.value]
    assert len(mine) == 1
    assert mine[0]["eventIds"] == [12, 13]


def test_regrouping_keeps_the_id_the_coach_already_pointed_at(family):
    with detects(("The hard spring", [10, 11])):
        sync(family.id, turn_id="t1")
    first = next(iter(clusters_of(family)))

    data = family.get_diagram_data()
    data.events.pop()
    family.set_diagram_data(data)
    db.session.commit()

    with detects(("The hard spring", [10, 11, 12])):
        sync(family.id, turn_id="t2")
    assert list(clusters_of(family)) == [first]


def test_the_same_events_are_not_regrouped_twice(family):
    with detects(("The hard spring", [10, 11])):
        sync(family.id, turn_id="t1")
    with detects(("Something else", [12, 13])) as detect:
        assert sync(family.id, turn_id="t2") is None
    detect.assert_not_called()


def test_a_chip_to_a_stored_cluster_resolves_and_the_picture_can_aim_at_it(family):
    with detects(("The hard spring", [10, 11, 12, 13])):
        sync(family.id, turn_id="t1")
    data = family.get_diagram_data()
    cluster_id = next(iter(clusters_of(family)))

    assert chips.resolves(ChipKind.Cluster, cluster_id, data)
    assert (
        chips.validate(f"[[cluster:{cluster_id}|that spring]]", data)
        == f"[[cluster:{cluster_id}|that spring]]"
    )
    chapters = build_timeline(data)["chapters"]
    assert [c["id"] for c in chapters] == [cluster_id]
    assert chapters[0]["title"] == "The hard spring"


def test_the_play_endpoint_resolves_a_stored_cluster(web, test_user, family):
    with detects(("The hard spring", [10, 11, 12, 13])):
        sync(family.id, turn_id="t1")
    cluster_id = next(iter(clusters_of(family)))
    token = csrf_token(web)

    with patch(
        "btcopilot.personal.playturn.PlayTurn.run", return_value={"steps": []}
    ) as play:
        response = web.post(
            "/companion/play",
            json={"cluster_id": cluster_id},
            headers={"X-CSRFToken": token},
        )
    assert response.status_code == 200
    play.assert_called_once()
