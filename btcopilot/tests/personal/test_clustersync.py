"""Clusters are stored, not derived on read: a turn that moves an event
re-groups the line and writes the grouping into the record, a grouping the user
made is never regrouped away, and what the coach points at still resolves."""

import pytest
from mock import patch

from btcopilot.personal.timeline import build_timeline
from btcopilot.extensions import db
from btcopilot.personal import chips, recordtext
from btcopilot.personal.chips import ChipKind
from btcopilot.personal.clusters import ClusterError, sync
from btcopilot.personal.coachturn import CoachTurn
from btcopilot.personal.models import Author, Change
from btcopilot.personal.toolbox import ToolError, Toolbox, ToolName
from btcopilot.schema import (
    Cluster,
    ClusterResult,
    ClusterSource,
    DateCertainty,
    Event,
    EventKind,
    ItemKind,
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
        for n in range(6)
    ]
    data.lastItemId = 15
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
    with detects(("The hard spring", [10, 11, 12, 13, 14, 15, 16])):
        CoachTurn(
            discussion,
            "That winter she got sick too.",
            model=Model(
                called(
                    ToolName.EditEvent,
                    kind="shift",
                    date="1994-07-01",
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
    assert cluster["eventIds"] == [10, 11, 12, 13, 14, 15, 16]
    assert (cluster["startDate"], cluster["endDate"]) == ("1994-01-01", "1994-07-01")
    assert family.get_diagram_data().clusterCacheKey


def test_a_turn_that_changes_no_event_does_not_regroup(discussion, family):
    with detects(("Never asked for", [10, 11, 12])) as detect:
        CoachTurn(
            discussion, "Tell me about that.", model=Model(said("It was hard."))
        ).run()
    detect.assert_not_called()
    assert clusters_of(family) == {}


def test_the_grouping_is_written_by_the_coach_in_the_same_turn(discussion, family):
    with detects(("The hard spring", [10, 11, 12])):
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
                eventIds=[10, 11, 12],
                source=ClusterSource.User,
            )
        )
    ]
    family.set_diagram_data(data)
    db.session.commit()

    with detects(("Everything at once", [10, 11, 12, 13, 14, 15])):
        sync(family.id, turn_id="t1")

    stored = clusters_of(family)
    theirs = stored["c1"]
    assert theirs["name"] == "When he left"
    assert theirs["eventIds"] == [10, 11, 12]
    assert theirs["source"] == ClusterSource.User.value

    mine = [c for c in stored.values() if c["source"] == ClusterSource.Model.value]
    assert len(mine) == 1
    assert mine[0]["eventIds"] == [13, 14, 15]


def test_events_left_over_by_a_split_are_dots_not_a_cluster(discussion, family):
    """A grouping the user made takes two events out of a model grouping of
    three. The one event left over is not stored as a grouping of its own, and
    the other model grouping is stored as it was."""
    data = family.get_diagram_data()
    data.clusters = [
        asdict(
            Cluster(
                id="c1",
                title="When he left",
                summary="",
                name="When he left",
                eventIds=[11, 12],
                source=ClusterSource.User,
            )
        )
    ]
    family.set_diagram_data(data)
    db.session.commit()

    with detects(("The hard spring", [10, 11, 12]), ("The winter after", [13, 14, 15])):
        sync(family.id, turn_id="t1")

    stored = clusters_of(family)
    assert stored["c1"]["eventIds"] == [11, 12]
    mine = [c for c in stored.values() if c["source"] == ClusterSource.Model.value]
    assert [c["eventIds"] for c in mine] == [[13, 14, 15]]


def test_a_grouping_under_the_minimum_is_never_stored(discussion, family):
    """The write is the last gate: whatever hands `sync` a grouping of two —
    a model answer that slipped validation, or a server still running the rules
    of an older version — the record refuses it rather than storing a pair."""
    with detects(("The hard spring", [10, 11])):
        with pytest.raises(ClusterError, match="fewer than 3"):
            sync(family.id, turn_id="t1")

    assert clusters_of(family) == {}
    assert not family.get_diagram_data().clusterCacheKey


def test_the_coach_may_not_group_fewer_than_three_events(family):
    """The tool the coach groups with is a second writer, and the same floor
    binds it: the record refuses a pair with words the model can act on."""
    tools = Toolbox(family.id, turn_id="t1")

    with pytest.raises(ToolError, match="at least 3 events"):
        tools.call(ToolName.EditCluster.value, {"name": "The pair", "event_ids": [10, 11]})
    assert clusters_of(family) == {}


def test_the_coach_may_not_make_a_cluster_with_no_events_at_all(family):
    tools = Toolbox(family.id, turn_id="t1")

    with pytest.raises(ToolError, match="needs 3 events"):
        tools.call(ToolName.EditCluster.value, {"name": "Nothing in it"})
    assert clusters_of(family) == {}


def test_the_coach_groups_three_events_as_the_user_own_grouping(family):
    tools = Toolbox(family.id, turn_id="t1")

    tools.call(
        ToolName.EditCluster.value, {"name": "That spring", "event_ids": [10, 11, 12]}
    )
    stored = clusters_of(family)
    assert [c["eventIds"] for c in stored.values()] == [[10, 11, 12]]
    assert [c["source"] for c in stored.values()] == [ClusterSource.User.value]


def _grandfathered(diagram):
    """A grouping the owner made when two events were enough."""
    data = diagram.get_diagram_data()
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
    diagram.set_diagram_data(data)
    db.session.commit()


def test_renaming_a_grouping_stuck_under_the_floor_says_what_to_do(family):
    """The coach reads a sentence it can act on, never a stack trace: a rename
    carries no events, so nothing catches it before the write."""
    _grandfathered(family)
    tools = Toolbox(family.id, turn_id="t1")

    with pytest.raises(ToolError, match="Add an event to it, or remove the grouping"):
        tools.call(ToolName.EditCluster.value, {"id": "c1", "name": "That autumn"})
    assert clusters_of(family)["c1"]["name"] == "When he left"


def test_a_third_event_lifts_a_grouping_out_from_under_the_floor(family):
    _grandfathered(family)
    tools = Toolbox(family.id, turn_id="t1")

    tools.call(
        ToolName.EditCluster.value,
        {"id": "c1", "name": "That autumn", "event_ids": [10, 11, 12]},
    )
    assert clusters_of(family)["c1"]["eventIds"] == [10, 11, 12]


def test_a_grouping_stuck_under_the_floor_can_still_be_removed(family):
    _grandfathered(family)
    tools = Toolbox(family.id, turn_id="t1")

    tools.call(
        ToolName.Remove.value, {"item_kind": ItemKind.Cluster.value, "item_id": "c1"}
    )
    assert clusters_of(family) == {}


def test_undoing_the_removal_of_such_a_grouping_reads_as_words_too(family):
    """Undo commits without going through the apply path, so it needs the same
    translation: the coach is told why, not handed an exception."""
    _grandfathered(family)
    Toolbox(family.id, turn_id="t1").call(
        ToolName.Remove.value, {"item_kind": ItemKind.Cluster.value, "item_id": "c1"}
    )

    with pytest.raises(ToolError, match="Putting that back would leave"):
        Toolbox(family.id, turn_id="t2").call(ToolName.Undo.value, {})
    assert clusters_of(family) == {}


def test_a_grouping_of_unknown_provenance_is_left_alone(discussion, family):
    """A row written before provenance was recorded is treated as the user's:
    guessing that the model made it would lose a name the user chose."""
    data = family.get_diagram_data()
    stale = asdict(
        Cluster(id="c1", title="When he left", summary="", eventIds=[10, 11, 12])
    )
    del stale["source"]
    data.clusters = [stale]
    family.set_diagram_data(data)
    db.session.commit()

    with detects(("Everything at once", [10, 11, 12, 13, 14, 15])):
        sync(family.id, turn_id="t1")

    stored = clusters_of(family)
    assert stored["c1"]["eventIds"] == [10, 11, 12]
    assert "source" not in stored["c1"]
    mine = [c for c in stored.values() if c.get("source") == ClusterSource.Model.value]
    assert len(mine) == 1
    assert mine[0]["eventIds"] == [13, 14, 15]


def test_the_coach_is_never_told_the_model_made_a_grouping_it_may_not_have(family):
    stale = asdict(Cluster(id="c1", title="When he left", summary="", eventIds=[10]))
    del stale["source"]

    assert "(unknown)" in recordtext.cluster_line(stale)


def test_regrouping_keeps_the_id_the_coach_already_pointed_at(family):
    with detects(("The hard spring", [10, 11, 12])):
        sync(family.id, turn_id="t1")
    first = next(iter(clusters_of(family)))

    data = family.get_diagram_data()
    data.events.pop()
    family.set_diagram_data(data)
    db.session.commit()

    with detects(("The hard spring", [10, 11, 12, 13])):
        sync(family.id, turn_id="t2")
    assert list(clusters_of(family)) == [first]


def test_the_same_events_are_not_regrouped_twice(family):
    with detects(("The hard spring", [10, 11, 12])):
        sync(family.id, turn_id="t1")
    with detects(("Something else", [13, 14, 15])) as detect:
        assert sync(family.id, turn_id="t2") is None
    detect.assert_not_called()


def test_a_grouping_made_by_the_older_rules_is_regrouped(family, monkeypatch):
    monkeypatch.setattr("btcopilot.personal.clusters.DETECTION_VERSION", 1)
    with detects(("The hard spring", [10, 11, 12])):
        sync(family.id, turn_id="t1")
    was = family.get_diagram_data().clusterCacheKey

    monkeypatch.setattr("btcopilot.personal.clusters.DETECTION_VERSION", 2)
    with detects(("Something else", [13, 14, 15])) as detect:
        assert sync(family.id, turn_id="t2") is not None
    detect.assert_called_once()
    assert family.get_diagram_data().clusterCacheKey != was
    assert [c["eventIds"] for c in clusters_of(family).values()] == [[13, 14, 15]]


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
    clusters = build_timeline(data)["clusters"]
    assert [c["id"] for c in clusters] == [cluster_id]
    assert clusters[0]["title"] == "The hard spring"


def test_the_play_endpoint_resolves_a_stored_cluster(web, test_user, family):
    with detects(("The hard spring", [10, 11, 12, 13])):
        sync(family.id, turn_id="t1")
    cluster_id = next(iter(clusters_of(family)))
    token = csrf_token(web)

    with patch(
        "btcopilot.personal.playturn.PlayTurn.run", return_value={"steps": []}
    ) as play:
        response = web.post(
            "/personal/play",
            json={"cluster_id": cluster_id},
            headers={"X-CSRFToken": token},
        )
    assert response.status_code == 200
    play.assert_called_once()
