"""Clusters are stored, not derived on read: a turn that moves an event
re-groups the line and writes the grouping into the record, a grouping the user
made is never regrouped away, and what the coach points at still resolves."""

import pytest
from mock import patch

from btcopilot.timeline import build_timeline
from btcopilot.extensions import db
from btcopilot import chips, recordtext
from btcopilot.chips import ChipKind
from btcopilot.clusters import (
    ClusterError,
    ClusterListResponse,
    DETECTION_VERSION,
    PER_ANSWER,
    PER_EVENT,
    THINKING_ROOM,
    ModelCluster,
    sync,
)
from btcopilot.coachturn import CoachTurn
from btcopilot.llmutil import OutputTruncatedError, Parsed, Served, Spent
from btcopilot.models import (
    Author,
    Change,
    ModelCall,
    Observation,
    ObservationKind,
    Purpose,
)
from btcopilot.prompts import get_agent_prompt
from btcopilot.turnlog import TurnEventKind
from btcopilot.toolbox import ToolError, Toolbox, ToolName
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
from btcopilot.tests.conftest import (
    Model,
    called,
    calling,
    csrf_token,
    said,
    version,
    wrote,
)


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.metered.response_text_sync",
        lambda *a, **k: wrote("A session title"),
    )


@pytest.fixture(autouse=True)
def regrouping():
    """Put the real regrouping back over the suite-wide stub; the model call it
    makes is scripted per test."""
    with patch("btcopilot.clusters.sync", new=sync):
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
                title=f"Anxious moment {n}",
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


def detects(*groups: tuple, changes: tuple[str, ...] = ()):
    """Script the model's grouping: (name, event ids) per group, or (id, name,
    event ids) when the model hands back a grouping the record already has."""
    made = []
    for n, group in enumerate(groups):
        cluster_id, name, ids = group if len(group) == 3 else (f"model{n}", *group)
        made.append(
            Cluster(
                id=cluster_id,
                title=name,
                summary=f"{name} summary",
                eventIds=list(ids),
            )
        )
    return patch(
        "btcopilot.clusters.detect_clusters",
        return_value=ClusterResult(clusters=made, changes=list(changes)),
    )


def parsed(response: ClusterListResponse) -> Parsed:
    return Parsed(
        response, Spent(input=900, output=60), Served("gemini-3.1-flash-lite")
    )


def clusters_of(diagram) -> dict:
    return {c["id"]: c for c in diagram.get_diagram_data().clusters}


def noted(kind: ObservationKind) -> list[tuple]:
    return [
        (o.detail["attempt"], o.detail["check"], o.detail["groups"], o.detail["events"])
        for o in Observation.query.filter_by(kind=kind).order_by(Observation.id)
    ]


def flashlite(*answers: ClusterListResponse):
    """Stands in for the grouping model as it was seen on production: it fills
    in every field the answer's schema offers, so offered an `id`, it writes
    one for each group, made up when the record holds none."""
    script = list(answers)

    def answer(prompt, response_format, large=False, schema=None, limit=None):
        said = script.pop(0)
        fields = schema["properties"]["clusters"]["items"]["properties"]
        for n, group in enumerate(said.clusters):
            group.id = f"c_{n}" if "id" in fields else None
        return parsed(said)

    return patch("btcopilot.metered.gemini_structured_sync", side_effect=answer)


def test_a_turn_that_adds_an_event_stores_the_grouping(discussion, family):
    # R-0208, R-0076
    with detects(("The hard spring", [10, 11, 12, 13, 14, 15, 16])):
        CoachTurn(
            discussion,
            "That winter she got sick too.",
            purpose=Purpose.Coach,
            model=Model(
                called(
                    ToolName.EditEvent,
                    kind="shift",
                    date="1994-07-01",
                    title="Got sick",
                    description="got sick",
                    person=1,
                    symptom="up", date_certainty="certain",
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
    # R-0208
    with detects(("Never asked for", [10, 11, 12])) as detect:
        CoachTurn(
            discussion,
            "Tell me about that.",
            purpose=Purpose.Coach,
            model=Model(said("It was hard.")),
        ).run()
    detect.assert_not_called()
    assert clusters_of(family) == {}


def test_a_turn_that_answers_when_the_most_was_going_on_regroups(discussion, family):
    # R-0853
    discussion.chat_user_speaker_id = discussion.speakers[0].id
    db.session.commit()
    with detects(("After the move", [10, 11, 12])) as detect:
        CoachTurn(
            discussion,
            "The worst was 1994, the year we moved.",
            purpose=Purpose.Coach,
            model=Model(
                calling(
                    (
                        ToolName.AddQuestion,
                        {
                            "text": "When in your life was the most going on?",
                            "kind": "fact",
                            "state": "resolved",
                            "outcome": "answered",
                            "fact": "most_going_on",
                            "item_kind": "person",
                            "item_id": "1",
                        },
                    )
                ),
                said("That year stands out."),
            ),
        ).run()
    detect.assert_called_once()
    assert [c["name"] for c in clusters_of(family).values()] == ["After the move"]


def test_the_grouping_is_written_by_the_coach_in_the_same_turn(discussion, family):
    # R-0084
    with detects(("The hard spring", [10, 11, 12])):
        reply = CoachTurn(
            discussion,
            "She got sick.",
            purpose=Purpose.Coach,
            model=Model(
                called(
                    ToolName.EditEvent,
                    kind="shift",
                    date="1994-05-01",
                    title="Got sick",
                    description="got sick",
                    person=1,
                    symptom="up", date_certainty="certain",
                ),
                said("Noted."),
            ),
        ).run()

    change = (
        Change.query.filter_by(diagram_id=family.id, turn_id=reply["turn_id"])
        .order_by(Change.id.desc())
        .first()
    )
    assert change.author is Author.Coach
    assert {d["item_kind"] for d in change.deltas} == {"cluster", "diagram"}


def test_a_grouping_the_user_made_is_kept_through_a_regroup(discussion, family):
    # R-0850
    """The model's periods are stored beside the person's own, which stays
    as they drew it."""
    data = family.get_diagram_data()
    theirs = asdict(
        Cluster(
            id="c1",
            title="When he left",
            summary="",
            name="When he left",
            eventIds=[10, 11, 12],
            source=ClusterSource.User,
        )
    )
    data.clusters = [theirs]
    family.set_diagram_data(data)
    db.session.commit()

    with detects(("The winter after", [13, 14, 15])):
        sync(family.id, turn_id="t1", user_id=family.user_id)

    stored = clusters_of(family)
    assert stored["c1"] == theirs
    assert [(c["eventIds"], c["source"]) for c in stored.values()] == [
        ([10, 11, 12], ClusterSource.User.value),
        ([13, 14, 15], ClusterSource.Model.value),
    ]


def test_a_grouping_under_the_minimum_is_never_stored(discussion, family):
    # R-0215
    """The write is the last gate: whatever hands `sync` a grouping of two —
    a model answer that slipped validation, or a server still running the rules
    of an older version — the record refuses it rather than storing a pair."""
    with detects(("The hard spring", [10, 11])):
        with pytest.raises(ClusterError, match="fewer than 3"):
            sync(family.id, turn_id="t1", user_id=family.user_id)

    assert clusters_of(family) == {}
    assert not family.get_diagram_data().clusterCacheKey


def test_the_coach_may_not_group_fewer_than_three_events(family):
    # R-0215
    """The tool the coach groups with is a second writer, and the same floor
    binds it: the record refuses a pair with words the model can act on."""
    tools = Toolbox(family.id, turn_id="t1")

    with pytest.raises(ToolError, match="at least 3 events"):
        tools.call(
            ToolName.EditCluster.value, {"name": "The pair", "event_ids": [10, 11]}
        )
    assert clusters_of(family) == {}


def test_the_coach_may_not_make_a_cluster_with_no_events_at_all(family):
    # R-0215
    tools = Toolbox(family.id, turn_id="t1")

    with pytest.raises(ToolError, match="needs 3 events"):
        tools.call(ToolName.EditCluster.value, {"name": "Nothing in it"})
    assert clusters_of(family) == {}


def test_the_coach_groups_three_events_as_the_user_own_grouping(family):
    # R-0282
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
    # R-0215
    """The coach reads a sentence it can act on, never a stack trace: a rename
    carries no events, so nothing catches it before the write."""
    _grandfathered(family)
    tools = Toolbox(family.id, turn_id="t1")

    with pytest.raises(
        ToolError, match="add an event to the cluster, or remove the grouping"
    ):
        tools.call(
            ToolName.EditCluster.value,
            {"id": "c1", "name": "That autumn", "version": version(family)},
        )
    assert clusters_of(family)["c1"]["name"] == "When he left"


def test_a_third_event_lifts_a_grouping_out_from_under_the_floor(family):
    # R-0215
    _grandfathered(family)
    tools = Toolbox(family.id, turn_id="t1")

    tools.call(
        ToolName.EditCluster.value,
        {
            "id": "c1",
            "name": "That autumn",
            "event_ids": [10, 11, 12],
            "version": version(family),
        },
    )
    assert clusters_of(family)["c1"]["eventIds"] == [10, 11, 12]


def test_a_grouping_stuck_under_the_floor_can_still_be_removed(family):
    # R-0215
    _grandfathered(family)
    tools = Toolbox(family.id, turn_id="t1")

    tools.call(
        ToolName.Remove.value,
        {"item_kind": ItemKind.Cluster.value, "item_id": "c1", "version": version(family)},
    )
    assert clusters_of(family) == {}


def test_undoing_the_removal_of_such_a_grouping_reads_as_words_too(family):
    # R-0215
    """Undo commits without going through the apply path, so it needs the same
    translation: the coach is told why, not handed an exception."""
    _grandfathered(family)
    Toolbox(family.id, turn_id="t1").call(
        ToolName.Remove.value,
        {"item_kind": ItemKind.Cluster.value, "item_id": "c1", "version": version(family)},
    )

    with pytest.raises(ToolError, match="Putting that back would leave"):
        Toolbox(family.id, turn_id="t2").call(ToolName.Undo.value, {})
    assert clusters_of(family) == {}


def test_a_grouping_of_unknown_provenance_is_kept_like_the_users(
    discussion, family
):
    # R-0850
    """A row written before provenance was recorded is treated as the user's,
    and the user's stays as it was drawn."""
    data = family.get_diagram_data()
    stale = asdict(
        Cluster(id="c1", title="When he left", summary="", eventIds=[10, 11, 12])
    )
    del stale["source"]
    data.clusters = [stale]
    family.set_diagram_data(data)
    db.session.commit()

    with detects(("The winter after", [13, 14, 15])):
        sync(family.id, turn_id="t1", user_id=family.user_id)

    stored = clusters_of(family)
    assert [c["eventIds"] for c in stored.values()] == [[10, 11, 12], [13, 14, 15]]


def test_the_coach_is_never_told_the_model_made_a_grouping_it_may_not_have(family):
    # R-0205
    stale = asdict(Cluster(id="c1", title="When he left", summary="", eventIds=[10]))
    del stale["source"]

    assert "(unknown)" in recordtext.cluster_line(stale)


def test_the_grouping_keeps_the_id_the_model_handed_back(family):
    # R-0842
    """The model says which stored grouping each one it returns is, so what the
    coach already pointed at still resolves after the line is regrouped."""
    with detects(("The hard spring", [10, 11, 12])):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    first = next(iter(clusters_of(family)))

    data = family.get_diagram_data()
    data.events.pop()
    family.set_diagram_data(data)
    db.session.commit()

    with detects((first, "The hard spring", [10, 11, 12, 13])):
        sync(family.id, turn_id="t2", user_id=family.user_id)
    assert list(clusters_of(family)) == [first]
    assert clusters_of(family)[first]["eventIds"] == [10, 11, 12, 13]


def test_the_same_events_are_not_regrouped_twice(family):
    # R-0208
    with detects(("The hard spring", [10, 11, 12])):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    with detects(("Something else", [13, 14, 15])) as detect:
        assert sync(family.id, turn_id="t2", user_id=family.user_id) is None
    detect.assert_not_called()


def test_a_chip_to_a_stored_cluster_resolves_and_the_picture_can_aim_at_it(family):
    # R-0085, R-0373
    with detects(("The hard spring", [10, 11, 12, 13])):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    data = family.get_diagram_data()
    cluster_id = next(iter(clusters_of(family)))

    assert chips.resolves(ChipKind.Cluster, cluster_id, data, None)
    assert (
        chips.validate(f"[[cluster:{cluster_id}|that spring]]", data, None)
        == f"[[cluster:{cluster_id}|that spring]]"
    )
    clusters = build_timeline(data)["clusters"]
    assert [c["id"] for c in clusters] == [cluster_id]
    assert clusters[0]["title"] == "The hard spring"


def test_the_play_endpoint_resolves_a_stored_cluster(web, test_user, family):
    # R-0078
    with detects(("The hard spring", [10, 11, 12, 13])):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    cluster_id = next(iter(clusters_of(family)))
    token = csrf_token(web)

    with patch(
        "btcopilot.playturn.PlayTurn.run", return_value={"steps": []}
    ) as play:
        response = web.post(
            "/app/play",
            json={"cluster_id": cluster_id},
            headers={"X-CSRFToken": token},
        )
    assert response.status_code == 200
    play.assert_called_once()


MOVED = "The summer she got sick sits with the spring they argued, not apart from it."


def test_what_changed_is_in_the_tool_answer_before_the_coach_answers(
    discussion, family
):
    # R-0412, R-0372
    """The regrouping runs before the last thing the coach says, so the
    sentences it wrote are in the tool answer the coach reads next. The system
    prompt is the same for every call in the turn, so the wire keeps it."""
    with detects(("The hard spring", [10, 11, 12]), changes=(MOVED,)):
        model = Model(
            called(
                ToolName.EditEvent,
                kind="shift",
                date="1994-07-01",
                title="Got sick",
                description="got sick",
                person=1,
                symptom="up", date_certainty="certain",
            ),
            said("Those look like one story to me now, not two."),
        )
        reply = CoachTurn(
            discussion, "She got sick that summer.", purpose=Purpose.Coach, model=model
        ).run()

    assert len(set(model.systems)) == 1
    assert MOVED not in model.systems[0]
    answer = model.histories[-1][-1]["content"][-1]
    assert answer["type"] == "tool_result"
    assert MOVED in answer["content"]
    assert "What changed in the story" in answer["content"]
    assert "cluster" not in reply["statement"].lower()


def test_a_regroup_leaves_the_prompt_and_the_turn_so_far_untouched(discussion, family):
    # R-0412
    with detects(("The hard spring", [10, 11, 12]), changes=(MOVED,)):
        model = Model(
            called(
                ToolName.EditEvent,
                kind="shift",
                date="1994-07-01",
                title="Caught pneumonia",
                description="caught pneumonia",
                person=1,
                symptom="up", date_certainty="certain",
            ),
            said("Those look like one story to me now, not two."),
        )
        CoachTurn(
            discussion, "She got sick that summer.", purpose=Purpose.Coach, model=model
        ).run()

    first, second = model.systems
    assert second == first
    assert "pneumonia" not in second
    earlier = model.histories[-1][-2]
    assert earlier["role"] == "assistant"
    assert earlier["content"][-1]["type"] == "tool_use"


def test_what_changed_goes_out_on_the_turn_for_nobody_to_draw(discussion, family):
    # R-0372
    with detects(("The hard spring", [10, 11, 12]), changes=(MOVED,)):
        reply = CoachTurn(
            discussion,
            "She got sick that summer.",
            purpose=Purpose.Coach,
            model=Model(
                called(
                    ToolName.EditEvent,
                    kind="shift",
                    date="1994-07-01",
                    title="Got sick",
                    description="got sick",
                    person=1,
                    symptom="up", date_certainty="certain",
                ),
                said("Those look like one story to me now, not two."),
            ),
        ).run()

    story = [e for e in reply["events"] if e["type"] == TurnEventKind.Story.value]
    assert [e["sentences"] for e in story] == [[MOVED]]


def test_the_coach_is_told_never_to_name_the_grouping_out_loud():
    # R-0373
    system = get_agent_prompt()
    assert 'Never say "cluster"' in system
    assert "was regrouped, recalculated, or updated" in system


def test_a_grouping_that_fails_its_checks_twice_keeps_the_groups_and_the_turn_replies(
    discussion, family
):
    # R-0410, R-0371, R-0517, R-0844
    with detects(("The hard spring", [10, 11, 12, 13, 14, 15])):
        CoachTurn(
            discussion,
            "She was anxious all that spring.",
            purpose=Purpose.Coach,
            model=Model(
                called(
                    ToolName.EditEvent,
                    id=15,
                    description="moment five",
                    version=version(family),
                ),
                said("Noted."),
            ),
        ).run()
    kept = clusters_of(family)
    assert len(kept) == 1

    invents = ClusterListResponse(
        clusters=[
            ModelCluster(
                id="c8", eventIds=[10, 11, 12, 13, 14, 15, 16], name="New", reason="r"
            )
        ]
    )
    with patch(
        "btcopilot.metered.gemini_structured_sync",
        side_effect=[parsed(invents), parsed(invents)],
    ):
        reply = CoachTurn(
            discussion,
            "That winter she got sick too.",
            purpose=Purpose.Coach,
            model=Model(
                called(
                    ToolName.EditEvent,
                    kind="shift",
                    date="1994-07-01",
                    title="Got sick",
                    description="got sick",
                    person=1,
                    symptom="up", date_certainty="certain",
                ),
                said("I put that down."),
            ),
        ).run()

    assert reply["statement"] == "I put that down."
    assert clusters_of(family) == kept
    assert noted(ObservationKind.ClusterRefused) == [
        (1, "unknown_group", 1, 7),
        (2, "unknown_group", 1, 7),
    ]
    failed = Observation.query.filter_by(kind=ObservationKind.ClusterFailed).one()
    assert (failed.detail["check"], failed.detail["fallback"]) == (
        "unknown_group",
        False,
    )


def test_regrouping_writes_a_ledger_row_for_the_person_and_their_family(family):
    # R-0388
    grouped = ClusterListResponse(
        clusters=[
            ModelCluster(
                eventIds=[10, 11, 12, 13, 14, 15], name="A hard year", reason="r"
            )
        ]
    )
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(grouped)
    ):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    rows = ModelCall.query.filter_by(purpose=Purpose.Cluster).all()
    assert [(r.user_id, r.diagram_id, r.turn_id, r.input_tokens) for r in rows] == [
        (family.user_id, family.id, "t1", 900)
    ]


GROUPED = ClusterListResponse(
    clusters=[
        ModelCluster(eventIds=[10, 11, 12, 13, 14, 15], name="A hard year", reason="r")
    ]
)
PAIR = ClusterListResponse(
    clusters=[ModelCluster(eventIds=[10, 11], name="A pair", reason="r")]
)


def test_a_refused_grouping_answer_is_written_down_with_the_models_answer(family):
    # R-0517, R-0844
    with patch(
        "btcopilot.metered.gemini_structured_sync",
        side_effect=[parsed(PAIR), parsed(GROUPED)],
    ):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    assert noted(ObservationKind.ClusterRefused) == [(1, "too_small", 1, 2)]
    row = Observation.query.filter_by(kind=ObservationKind.ClusterRefused).one()
    assert (row.turn_id, row.diagram_id) == ("t1", family.id)
    assert (row.detail["name"], row.detail["eventIds"]) == ("A pair", [10, 11])
    assert (row.detail["start"], row.detail["end"]) == ("1994-01-01", "1994-02-01")
    assert [c["title"] for c in clusters_of(family).values()] == ["A hard year, 1994"]
    assert not Observation.query.filter_by(kind=ObservationKind.ClusterFailed).count()


def test_an_accepted_grouping_answer_writes_no_observation(family):
    # R-0517
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    assert Observation.query.count() == 0


def test_twice_refused_with_no_groups_stores_nothing_named_after_its_years(family):
    # R-0517, R-0844, R-0850
    with patch(
        "btcopilot.metered.gemini_structured_sync",
        side_effect=[parsed(PAIR), parsed(PAIR)],
    ):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    assert clusters_of(family) == {}
    failed = Observation.query.filter_by(kind=ObservationKind.ClusterFailed).one()
    assert (failed.detail["check"], failed.detail["fallback"]) == ("too_small", False)
    assert family.get_diagram_data().clusterCacheKey


def test_a_model_that_fills_every_offered_field_still_groups_a_new_record(family):
    # R-0517, R-0844
    """On production the grouping model wrote a made-up id on every new group
    and both answers were refused, so a record of 91 events had no clusters.
    The answer's schema now offers no id when the record holds no groups."""
    with flashlite(GROUPED, GROUPED):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    assert [c["title"] for c in clusters_of(family).values()] == ["A hard year, 1994"]
    assert Observation.query.count() == 0


def test_an_answer_cut_off_at_its_limit_is_refused_and_asked_again(family):
    # R-0517, R-0844
    """A grouping answer once repeated a sentence until it hit the limit. The
    limit is set from the record's size, and a cut-off answer is refused and
    asked again like any other."""
    cut = OutputTruncatedError(
        "truncated", Served("gemini-3.1-flash-lite"), Spent(input=900, output=4000)
    )
    with patch(
        "btcopilot.metered.gemini_structured_sync",
        side_effect=[cut, parsed(GROUPED)],
    ) as asked:
        sync(family.id, turn_id="t1", user_id=family.user_id)
    assert [c.kwargs["limit"] for c in asked.call_args_list] == [THINKING_ROOM + PER_EVENT * 6 + PER_ANSWER] * 2
    assert noted(ObservationKind.ClusterRefused) == [(1, "cut_off", 0, 0)]
    assert [c["title"] for c in clusters_of(family).values()] == ["A hard year, 1994"]
    assert ModelCall.query.filter_by(purpose=Purpose.Cluster).count() == 2


def test_a_grouping_call_that_fails_twice_never_fails_the_turn(discussion, family):
    # R-0517, R-0844, R-0850
    with patch(
        "btcopilot.metered.gemini_structured_sync",
        side_effect=[TimeoutError(), TimeoutError()],
    ):
        reply = CoachTurn(
            discussion,
            "That winter she got sick too.",
            purpose=Purpose.Coach,
            model=Model(
                called(
                    ToolName.EditEvent,
                    kind="shift",
                    date="1994-07-01",
                    title="Got sick",
                    description="got sick",
                    person=1,
                    symptom="up",
                    date_certainty="certain",
                ),
                said("I put that down."),
            ),
        ).run()
    assert reply["statement"] == "I put that down."
    assert noted(ObservationKind.ClusterRefused) == [
        (1, "call_failed", 0, 0),
        (2, "call_failed", 0, 0),
    ]
    failed = Observation.query.filter_by(kind=ObservationKind.ClusterFailed).one()
    assert (failed.detail["check"], failed.detail["fallback"]) == ("call_failed", False)
    assert clusters_of(family) == {}
    assert not family.get_diagram_data().clusterCacheKey


def stored_beside_theirs(family, cache_key: str) -> None:
    data = family.get_diagram_data()
    data.clusters = [
        asdict(
            Cluster(
                id="c1",
                title="A cold spring",
                summary="",
                name="A cold spring",
                eventIds=[10, 11, 12],
                source=ClusterSource.Model,
            )
        ),
        asdict(
            Cluster(
                id="c2",
                title="When he left",
                summary="",
                name="When he left",
                eventIds=[13, 14, 15],
                source=ClusterSource.User,
            )
        ),
    ]
    data.clusterCacheKey = cache_key
    family.set_diagram_data(data)
    db.session.commit()


def asked_with(cluster_id: str | None):
    """The grouping model, answering one cluster on the first three events and
    keeping what it was handed: the prompt and the schema of each call."""
    seen = []

    def answer(prompt, response_format, large=False, schema=None, limit=None):
        seen.append((prompt, schema))
        group = ModelCluster(eventIds=[10, 11, 12], name="A cold spring", reason="r")
        group.id = cluster_id
        return parsed(ClusterListResponse(clusters=[group]))

    return seen, patch("btcopilot.metered.gemini_structured_sync", side_effect=answer)


def test_clusters_from_an_older_version_are_not_handed_back_and_are_set_aside(family):
    # R-0772, R-0851
    """After a prompt change the old answer's clusters would anchor the new
    one: the model is handed only the person's own period, and every stored
    model cluster it does not return is set aside, never deleted."""
    stored_beside_theirs(family, f"v{DETECTION_VERSION - 1}:0123456789abcdef")
    seen, model = asked_with(None)
    with model:
        sync(family.id, turn_id="t1", user_id=family.user_id)
    (prompt, schema), = seen
    assert "A cold spring" not in prompt
    assert "When he left" in prompt
    assert "id" not in schema["properties"]["clusters"]["items"]["properties"]
    stored = clusters_of(family)
    assert stored["c1"]["setAside"]
    assert not stored["c2"]["setAside"]
    assert [
        (c["eventIds"], c["source"]) for i, c in stored.items() if i not in ("c1", "c2")
    ] == [([10, 11, 12], ClusterSource.Model.value)]


def test_the_catch_up_regroups_from_scratch_on_the_same_version(family):
    # R-0772, R-0851
    stored_beside_theirs(family, f"v{DETECTION_VERSION}:0123456789abcdef")
    seen, model = asked_with(None)
    with model:
        sync(family.id, turn_id="t1", user_id=family.user_id, force=True, fresh=True)
    (prompt, _), = seen
    assert "A cold spring" not in prompt
    assert "When he left" in prompt
    assert clusters_of(family)["c1"]["setAside"]


def test_clusters_from_the_same_version_are_handed_back(family):
    # R-0772, R-0851
    stored_beside_theirs(family, f"v{DETECTION_VERSION}:0123456789abcdef")
    seen, model = asked_with("c1")
    with model:
        sync(family.id, turn_id="t1", user_id=family.user_id)
    (prompt, schema), = seen
    assert "A cold spring" in prompt
    assert "When he left" in prompt
    fields = schema["properties"]["clusters"]["items"]["properties"]
    assert fields["id"]["enum"] == ["c1"]
    stored = clusters_of(family)
    assert sorted(stored) == ["c1", "c2"]
    assert not stored["c1"]["setAside"]


def added(family, *events: Event) -> None:
    data = family.get_diagram_data()
    data.events += [asdict(e) for e in events]
    data.lastItemId = max(e.id for e in events)
    family.set_diagram_data(data)
    db.session.commit()


def moved(event_id: int, day: str) -> Event:
    return Event(
        id=event_id,
        kind=EventKind.Noted,
        person=1,
        dateTime=day,
        dateCertainty=DateCertainty.Approximate,
        description="moved house",
    )


def test_an_event_added_inside_a_live_clusters_days_joins_it(family):
    # R-0873
    """Handed back as it was stored, the model leaves the new event out; the
    cluster is the events within its period, whatever the date's certainty."""
    stored_beside_theirs(family, f"v{DETECTION_VERSION}:0123456789abcdef")
    added(family, moved(16, "1994-02-15"))
    _, model = asked_with("c1")
    with model:
        sync(family.id, turn_id="t1", user_id=family.user_id)
    assert clusters_of(family)["c1"]["eventIds"] == [10, 11, 12, 16]


def test_an_event_added_the_day_after_a_clusters_end_stays_out(family):
    # R-0873
    stored_beside_theirs(family, f"v{DETECTION_VERSION}:0123456789abcdef")
    added(family, moved(16, "1994-03-02"))
    _, model = asked_with("c1")
    with model:
        sync(family.id, turn_id="t1", user_id=family.user_id)
    stored = clusters_of(family)
    assert [stored[i]["eventIds"] for i in ("c1", "c2")] == [[10, 11, 12], [13, 14, 15]]


def test_an_event_added_inside_the_persons_period_joins_it(family):
    # R-0873, R-0853
    stored_beside_theirs(family, f"v{DETECTION_VERSION}:0123456789abcdef")
    added(family, moved(16, "1994-05-15"))
    _, model = asked_with("c1")
    with model:
        sync(family.id, turn_id="t1", user_id=family.user_id)
    assert clusters_of(family)["c2"]["eventIds"] == [13, 14, 15, 16]


def held_live(family, ids=(10, 11, 12)) -> None:
    data = family.get_diagram_data()
    data.clusters = [
        asdict(
            Cluster(
                id="c1",
                title="A cold spring",
                summary="",
                name="A cold spring",
                eventIds=list(ids),
                openingEventId=ids[0],
                source=ClusterSource.Model,
            )
        )
    ]
    data.clusterCacheKey = f"v{DETECTION_VERSION}:0123456789abcdef"
    family.set_diagram_data(data)
    db.session.commit()


def answering(*groups: tuple):
    """The grouping model giving the same answer on every call: (id, name,
    event ids, opening event) per period."""

    def answer(prompt, response_format, large=False, schema=None, limit=None):
        return parsed(
            ClusterListResponse(
                clusters=[
                    ModelCluster(
                        id=cluster_id,
                        eventIds=list(ids),
                        name=name,
                        reason="r",
                        openingId=opening,
                    )
                    for cluster_id, name, ids, opening in groups
                ]
            )
        )

    return patch("btcopilot.metered.gemini_structured_sync", side_effect=answer)


KEPT = ("c1", "A cold spring", [10, 11, 12], 10)
NEW = (None, "The summer after", [13, 14, 15], 13)


def waiting(family) -> dict:
    (row,) = [c for c in family.get_diagram_data().clusters if c["id"] != "c1"]
    return row


def test_a_new_cluster_sharing_no_event_with_a_live_one_waits_set_aside(family):
    # R-0873
    held_live(family)
    with answering(KEPT, NEW):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    data = family.get_diagram_data()
    row = waiting(family)
    assert (row["eventIds"], row["setAside"]) == ([13, 14, 15], True)
    assert row["proposedAt"] == data.clusterCacheKey
    assert [c["id"] for c in data.drawn_clusters()] == ["c1"]


def test_a_waiting_cluster_proposed_by_the_next_detection_is_shown(family):
    # R-0873
    """The second answer's days and name win, under the waiting row's id."""
    held_live(family)
    with answering(KEPT, NEW):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    first = waiting(family)["id"]
    with answering(KEPT, (None, "The long summer", [13, 14, 15, 16], 13)):
        added(family, moved(16, "1994-07-01"))
        sync(family.id, turn_id="t2", user_id=family.user_id)
    row = waiting(family)
    assert row["id"] == first
    assert (row["setAside"], row["proposedAt"]) == (False, None)
    assert (row["name"], row["endDate"]) == ("The long summer, 1994", "1994-07-01")


def test_a_waiting_cluster_not_proposed_again_stays_aside(family):
    # R-0873
    held_live(family)
    with answering(KEPT, NEW):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    with answering(KEPT):
        sync(family.id, turn_id="t2", user_id=family.user_id, force=True)
    row = waiting(family)
    assert (row["setAside"], row["proposedAt"]) == (True, None)


def test_a_diagrams_first_detection_shows_its_clusters_at_once(family):
    # R-0873
    with answering(NEW):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    (row,) = family.get_diagram_data().drawn_clusters()
    assert row["eventIds"] == [13, 14, 15]
    assert "proposedAt" not in row


def test_a_catch_up_from_scratch_shows_its_clusters_at_once(family):
    # R-0873, R-0772
    held_live(family)
    with answering(NEW):
        sync(family.id, turn_id="t1", user_id=family.user_id, force=True, fresh=True)
    (row,) = family.get_diagram_data().drawn_clusters()
    assert row["eventIds"] == [13, 14, 15]
    assert "proposedAt" not in row


def test_a_new_cluster_absorbing_a_live_ones_events_replaces_it_at_once(family):
    # R-0873
    """Seen on Patrick's diagram: the live cluster folded into one opening an
    event earlier, so those years showed no cluster for a detection."""
    held_live(family, ids=(11, 12, 13))
    with answering((None, "Two hard seasons", [10, 11, 12, 13], 10)):
        sync(family.id, turn_id="t1", user_id=family.user_id)
    rows = clusters_of(family)
    (row,) = family.get_diagram_data().drawn_clusters()
    assert row["eventIds"] == [10, 11, 12, 13]
    assert "proposedAt" not in row
    assert rows["c1"]["setAside"] is True
