from btcopilot.personal.seed import seed_diagram_data
from btcopilot.personal.timeline import GAP_DAYS, build_timeline
from btcopilot.schema import (
    Cluster,
    DateCertainty,
    DiagramData,
    Event,
    EventKind,
    PairBond,
    Person,
    RelationshipKind,
    VariableShift,
    asdict,
)


def _shift(id, person, dateTime, variable, direction, certainty=DateCertainty.Certain):
    kwargs = {variable: direction}
    return asdict(
        Event(
            id=id,
            kind=EventKind.Shift,
            person=person,
            dateTime=dateTime,
            dateCertainty=certainty,
            **kwargs,
        )
    )


def _data(people_ids, events):
    return DiagramData(
        people=[asdict(Person(id=i, name=f"P{i}")) for i in people_ids],
        events=events,
    )


def _lane(timeline, key):
    return next(l for l in timeline["lanes"] if l["key"] == key)


def test_per_person_isolation():
    """One person's line must never be influenced by another's events (the
    known QML mixed-sum bug)."""
    up, down = VariableShift.Up, VariableShift.Down
    events = [
        _shift(10, 1, "2000-01-01", "symptom", up),
        _shift(11, 2, "2001-01-01", "symptom", down),
        _shift(12, 1, "2002-01-01", "symptom", up),
        _shift(13, 2, "2003-01-01", "symptom", down),
        _shift(14, 1, "2004-01-01", "symptom", up),
    ]
    timeline = build_timeline(_data([1, 2], events))
    p1 = _lane(timeline, "p1:symptom")
    p2 = _lane(timeline, "p2:symptom")
    assert [p["value"] for p in p1["points"]] == [1, 2, 3]
    assert [p["value"] for p in p2["points"]] == [-1, -2]


def test_two_directed_points_render_dots_only():
    events = [
        _shift(10, 1, "2000-01-01", "anxiety", VariableShift.Up),
        _shift(11, 1, "2005-01-01", "anxiety", VariableShift.Down),
    ]
    lane = _lane(build_timeline(_data([1], events)), "p1:anxiety")
    assert lane["has_line"] is False
    assert lane["segments"] == []
    assert len(lane["points"]) == 2


def test_line_spans_only_its_own_points():
    events = [
        _shift(10, 1, "2000-06-01", "symptom", VariableShift.Up),
        _shift(11, 1, "2001-06-01", "symptom", VariableShift.Up),
        _shift(12, 1, "2002-06-01", "symptom", VariableShift.Down),
    ]
    lane = _lane(build_timeline(_data([1], events)), "p1:symptom")
    assert lane["has_line"] is True
    assert lane["segments"][0]["a"] == "2000-06-01"
    assert lane["segments"][-1]["b"] == "2002-06-01"


def test_certainty_bands_and_undated_shelf():
    events = [
        _shift(10, 1, "2000-01-01", "symptom", VariableShift.Up),
        _shift(
            11, 1, "2005-01-01", "symptom", VariableShift.Up, DateCertainty.Approximate
        ),
        _shift(12, 1, None, "symptom", VariableShift.Up),
        _shift(13, 1, "2010-01-01", "symptom", VariableShift.Up, DateCertainty.Unknown),
    ]
    timeline = build_timeline(_data([1], events))
    lane = _lane(timeline, "p1:symptom")
    bands = {p["event_id"]: p["band_days"] for p in lane["points"]}
    assert bands == {10: 7, 11: 365}
    assert {s["event_id"] for s in timeline["shelf"]} == {12, 13}


def test_gap_distinct_from_recorded_no_change():
    up, same = VariableShift.Up, VariableShift.Same
    events = [
        _shift(10, 1, "2000-01-01", "symptom", up),
        _shift(11, 1, "2001-01-01", "symptom", up),
        _shift(12, 1, "2010-01-01", "symptom", up),
        _shift(13, 1, "2010-06-01", "symptom", same),
    ]
    lane = _lane(build_timeline(_data([1], events)), "p1:symptom")
    gap_flags = {(s["a"], s["b"]): s["gap"] for s in lane["segments"]}
    assert gap_flags[("2001-01-01", "2010-01-01")] is True
    assert gap_flags[("2000-01-01", "2001-01-01")] is False
    assert gap_flags[("2010-01-01", "2010-06-01")] is False
    assert len(lane["same_marks"]) == 1
    assert lane["same_marks"][0]["event_id"] == 13
    assert lane["directed_count"] == 3


def test_same_events_do_not_count_toward_line():
    up, same = VariableShift.Up, VariableShift.Same
    events = [
        _shift(10, 1, "2000-01-01", "symptom", up),
        _shift(11, 1, "2001-01-01", "symptom", up),
        _shift(12, 1, "2002-01-01", "symptom", same),
    ]
    lane = _lane(build_timeline(_data([1], events)), "p1:symptom")
    assert lane["directed_count"] == 2
    assert lane["has_line"] is False


def test_strip_vocabulary_is_line_dots_question_only():
    timeline = build_timeline(seed_diagram_data())
    strip = timeline["strip"]["lanes"]
    assert 1 <= len(strip) <= 2
    for lane in strip:
        assert {m["type"] for m in lane["marks"]} <= {"dot"}
        assert {q["type"] for q in lane["questions"]} <= {"question"}
        for m in lane["marks"]:
            assert "band_days" not in m
            assert "certainty" not in m


def test_lane_picker_data_from_diagram():
    timeline = build_timeline(seed_diagram_data())
    assert {p["id"] for p in timeline["people"]} == {1, 3, 4, 5, 6, 7}
    assert {b["id"] for b in timeline["pair_bonds"]} == {8, 9}
    assert {b["label"] for b in timeline["pair_bonds"]} == {
        "Alex & Sam",
        "Diane & Robert",
    }


def test_order_question_for_touching_ranges():
    """Move 1994+/-1yr vs sleep onset 1995+/-1yr: ranges touch -> a '?'."""
    timeline = build_timeline(seed_diagram_data())
    pairs = {(q["event_id"], q["other_event_id"]) for q in timeline["questions"]}
    assert (10, 30) in pairs
    question = next(q for q in timeline["questions"] if q["other_event_id"] == 30)
    assert question["lane"] == "p1:symptom"
    assert "Which came first" in question["sentence"]


def test_no_question_for_distant_ranges():
    events = [
        _shift(10, 1, "2000-01-01", "symptom", VariableShift.Up),
        asdict(
            Event(
                id=11,
                kind=EventKind.Moved,
                person=1,
                dateTime="2010-01-01",
                dateCertainty=DateCertainty.Certain,
            )
        ),
    ]
    timeline = build_timeline(_data([1], events))
    assert timeline["questions"] == []


def test_every_mark_has_a_sentence():
    timeline = build_timeline(seed_diagram_data())
    for lane in timeline["lanes"]:
        for entry in lane["points"] + lane["same_marks"]:
            assert entry["sentence"]
    for lane in timeline["bond_lanes"]:
        for entry in lane["marks"]:
            assert entry["sentence"]
    for entry in timeline["shelf"]:
        assert entry["sentence"]
    for entry in timeline["questions"]:
        assert entry["sentence"]


def test_seed_fixture_covers_every_move_the_play_by_play_draws():
    """The play-by-play has one symbol per move kind; the fixture has to walk
    through all of them or the stepping is never exercised."""
    events = seed_diagram_data().events
    assert {e["relationship"] for e in events if e.get("relationship")} == {
        kind.value for kind in RelationshipKind
    }
    for variable in ("symptom", "anxiety", "functioning"):
        directions = {e[variable] for e in events if e.get(variable)}
        assert {VariableShift.Up.value, VariableShift.Down.value} <= directions
    clusters = build_timeline(seed_diagram_data())["clusters"]
    # A stored cluster is a cluster of its own, so a cluster is as big as the
    # cluster the coach named; nothing on the line stands alone.
    assert all(cluster["count"] >= 3 for cluster in clusters)


def test_seed_fixture_covers_every_rule():
    data = seed_diagram_data()
    assert len(data.people) >= 5
    assert len(data.pair_bonds) == 2
    dated = [
        e
        for e in data.events
        if e.get("dateTime") and e.get("dateCertainty") != DateCertainty.Unknown.value
    ]
    assert len(dated) >= 20
    certainties = {e["dateCertainty"] for e in dated}
    assert DateCertainty.Certain.value in certainties
    assert DateCertainty.Approximate.value in certainties

    timeline = build_timeline(data)
    directed = {l["key"]: l["directed_count"] for l in timeline["lanes"]}
    assert any(n >= 3 for n in directed.values())
    assert any(n < 3 for n in directed.values())
    gap_segments = [s for l in timeline["lanes"] for s in l["segments"] if s["gap"]]
    assert gap_segments
    assert any(l["same_marks"] for l in timeline["lanes"])
    assert timeline["questions"]
    assert timeline["shelf"]
    assert timeline["bond_lanes"]


def test_a_record_with_no_stored_cluster_draws_none():
    """The picture draws the clusters the record holds. Moments no cluster
    claims are dots on the wire, never boxed with whatever happened near
    them."""
    events = [
        _shift(10, 1, "1990-01-01", "symptom", VariableShift.Up),
        _shift(11, 1, "1991-06-01", "symptom", VariableShift.Down),
        _shift(12, 1, "2005-01-01", "symptom", VariableShift.Up),
        _shift(13, 1, "2006-01-01", "symptom", VariableShift.Down),
    ]
    timeline = build_timeline(_data([1], events))
    assert timeline["clusters"] == []
    assert [e["id"] for e in timeline["events"]] == [10, 11, 12, 13]


def test_a_cluster_takes_its_title_from_a_stored_cluster_inside_it():
    events = [
        _shift(10, 1, "1990-01-01", "symptom", VariableShift.Up),
        _shift(11, 1, "1991-01-01", "symptom", VariableShift.Down),
    ]
    data = _data([1], events)
    data.clusters = [
        asdict(
            Cluster(
                id="cl-1",
                title="The year everything moved",
                summary="Two shifts in a row.",
                eventIds=[10, 11],
                startDate="1990-06-01",
                endDate="1991-01-01",
            )
        )
    ]
    cluster = build_timeline(data)["clusters"][0]
    assert cluster["title"] == "The year everything moved"
    assert cluster["cluster_ids"] == ["cl-1"]


def test_two_clusters_inside_one_run_of_events_stay_two_groupings():
    """Without this the picture draws a single blob over a dense record, which
    is the shape Patrick's first look at the beta rejected."""
    events = [
        _shift(10 + i, 1, f"2019-0{i + 1}-01", "symptom", VariableShift.Up)
        for i in range(6)
    ]
    data = _data([1], events)
    data.clusters = [
        asdict(
            Cluster(
                id="cl-a",
                title="The first hard winter",
                summary="",
                eventIds=[10, 11, 12],
                startDate="2019-01-01",
                endDate="2019-03-01",
            )
        ),
        asdict(
            Cluster(
                id="cl-b",
                title="After the diagnosis",
                summary="",
                eventIds=[13, 14, 15],
                startDate="2019-04-01",
                endDate="2019-06-01",
            )
        ),
    ]
    clusters = build_timeline(data)["clusters"]
    assert [c["event_ids"] for c in clusters] == [[10, 11, 12], [13, 14, 15]]
    assert [c["title"] for c in clusters] == [
        "The first hard winter",
        "After the diagnosis",
    ]


def test_events_no_cluster_claims_stay_off_every_cluster():
    events = [
        _shift(10, 1, "1990-01-01", "symptom", VariableShift.Up),
        _shift(11, 1, "1990-06-01", "symptom", VariableShift.Down),
        _shift(12, 1, "2010-01-01", "symptom", VariableShift.Up),
        _shift(13, 1, "2010-06-01", "symptom", VariableShift.Down),
    ]
    data = _data([1], events)
    data.clusters = [
        asdict(
            Cluster(
                id="cl-a",
                title="The early years",
                summary="",
                eventIds=[10, 11],
                startDate="1990-01-01",
                endDate="1990-06-01",
            )
        )
    ]
    timeline = build_timeline(data)
    assert [c["event_ids"] for c in timeline["clusters"]] == [[10, 11]]
    assert [c["cluster_ids"] for c in timeline["clusters"]] == [["cl-a"]]
    # the two the stored cluster does not claim are still on the line
    assert [e["id"] for e in timeline["events"]] == [10, 11, 12, 13]


def test_every_dated_event_says_itself_in_a_sentence():
    events = [
        _shift(10, 1, "1996-01-01", "symptom", VariableShift.Up, DateCertainty.Approximate),
    ]
    event = build_timeline(_data([1], events))["events"][0]
    assert "1996" in event["sentence"]
    assert event["sentence"].endswith(".")


def test_the_axis_spans_every_dated_event_not_only_the_lane_marks():
    events = [
        asdict(
            Event(
                id=10,
                kind=EventKind.Birth,
                person=1,
                child=1,
                dateTime="1980-01-01",
                dateCertainty=DateCertainty.Certain,
            )
        ),
        _shift(11, 1, "1996-01-01", "symptom", VariableShift.Up),
    ]
    assert build_timeline(_data([1], events))["axis"] == {
        "min": "1980-01-01",
        "max": "1996-01-01",
    }


def test_undated_events_belong_to_no_cluster_but_stay_in_the_list():
    events = [
        _shift(10, 1, "1990-01-01", "symptom", VariableShift.Up),
        _shift(
            11, 1, "1991-01-01", "symptom", VariableShift.Down, DateCertainty.Unknown
        ),
    ]
    timeline = build_timeline(_data([1], events))
    assert [e["id"] for e in timeline["events"]] == [10, 11]
    assert timeline["clusters"] == []


def test_every_event_carries_the_words_the_list_shows():
    timeline = build_timeline(seed_diagram_data())
    assert len(timeline["events"]) == len(seed_diagram_data().events)
    for event in timeline["events"]:
        assert event["label"]
        assert event["person_name"]


def test_an_event_carries_the_fields_whoever_stored_it_left_out():
    events = [{"id": 10, "kind": EventKind.Shift.value, "dateTime": "1990-01-01"}]
    event = build_timeline(_data([1], events))["events"][0]
    assert event["relationshipTargets"] == []
    assert event["relationshipTriangles"] == []
    assert event["spouse"] is None
