import pytest

from btcopilot.seed import seed_diagram_data
from btcopilot.timeline import GAP_DAYS, build_timeline
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


def test_two_directed_points_render_dots_only():
    # R-0008
    events = [
        _shift(10, 1, "2000-01-01", "anxiety", VariableShift.Up),
        _shift(11, 1, "2005-01-01", "anxiety", VariableShift.Down),
    ]
    lane = _lane(build_timeline(_data([1], events)), "p1:anxiety")
    assert lane["has_line"] is False
    assert lane["segments"] == []
    assert len(lane["points"]) == 2


def test_line_spans_only_its_own_points():
    # R-0008
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
    # R-0013, R-0009
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
    # R-0010
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
    # R-0008
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
    # R-0005
    timeline = build_timeline(seed_diagram_data())
    strip = timeline["strip"]["lanes"]
    assert 1 <= len(strip) <= 2
    for lane in strip:
        assert {m["type"] for m in lane["marks"]} <= {"dot"}
        assert {q["type"] for q in lane["questions"]} <= {"question"}
        for m in lane["marks"]:
            assert "band_days" not in m
            assert "certainty" not in m


def test_order_question_for_touching_ranges():
    # R-0011
    """Separation 1996+/-1yr vs sleep onset 1995+/-1yr: ranges touch -> a '?'."""
    timeline = build_timeline(seed_diagram_data())
    pairs = {(q["event_id"], q["other_event_id"]) for q in timeline["questions"]}
    assert (10, 34) in pairs
    question = next(q for q in timeline["questions"] if q["other_event_id"] == 34)
    assert question["lane"] == "p1:symptom"
    assert "Which came first" in question["sentence"]


def test_no_question_for_distant_ranges():
    # R-0011
    events = [
        _shift(10, 1, "2000-01-01", "symptom", VariableShift.Up),
        asdict(
            Event(
                id=11,
                kind=EventKind.Noted,
                person=1,
                description="moved out",
                dateTime="2010-01-01",
                dateCertainty=DateCertainty.Certain,
            )
        ),
    ]
    timeline = build_timeline(_data([1], events))
    assert timeline["questions"] == []


def test_every_mark_has_a_sentence():
    # R-0005
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


def test_a_record_with_no_stored_cluster_draws_none():
    # R-0371, R-0076
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
    # R-0076
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
    # R-0371
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
    # R-0076
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
    # R-0005
    events = [
        _shift(10, 1, "1996-01-01", "symptom", VariableShift.Up, DateCertainty.Approximate),
    ]
    event = build_timeline(_data([1], events))["events"][0]
    assert "1996" in event["sentence"]
    assert event["sentence"].endswith(".")


def test_the_axis_spans_every_dated_event_not_only_the_lane_marks():
    # R-0111
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


def test_every_event_carries_the_words_the_list_shows():
    # R-0318
    timeline = build_timeline(seed_diagram_data())
    assert len(timeline["events"]) == len(seed_diagram_data().events)
    for event in timeline["events"]:
        assert event["label"]
        assert event["person_name"]


def test_an_event_carries_the_fields_whoever_stored_it_left_out():
    # R-0318
    events = [{"id": 10, "kind": EventKind.Shift.value, "dateTime": "1990-01-01"}]
    event = build_timeline(_data([1], events))["events"][0]
    assert event["relationshipTargets"] == []
    assert event["relationshipTriangles"] == []
    assert event["spouse"] is None


def _named(ids_and_names, events):
    return DiagramData(
        people=[asdict(Person(id=i, name=n)) for i, n in ids_and_names],
        events=events,
    )


def test_a_moment_says_who_from_its_links_and_what_without_the_name():
    # R-0457
    """Owner ruling 2026-09-09: who comes from the links, what never repeats a
    linked person's name."""
    events = [
        asdict(
            Event(
                id=10,
                kind=EventKind.Birth,
                child=1,
                person=2,
                dateTime="1980-06-01",
                description="in Anchorage, AK",
            )
        ),
        asdict(
            Event(
                id=11,
                kind=EventKind.Divorced,
                person=2,
                spouse=3,
                dateTime="1990-01-01",
            )
        ),
        asdict(
            Event(
                id=12,
                kind=EventKind.Shift,
                person=1,
                spouse=3,
                anxiety=VariableShift.Up,
                dateTime="1992-01-01",
            )
        ),
        asdict(
            Event(
                id=13,
                kind=EventKind.Shift,
                person=1,
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[2],
                dateTime="1994-01-01",
            )
        ),
    ]
    timeline = _named([(1, "Elizabeth"), (2, "Ray"), (3, "Nora")], events)
    said = {
        e["id"]: (e["person_name"], e["label"])
        for e in build_timeline(timeline)["events"]
    }
    assert said[10] == ("Elizabeth", "born · in Anchorage, AK")
    assert said[11] == ("Ray & Nora", "divorced")
    assert said[12] == ("Elizabeth & Nora", "anxiety went up")
    assert said[13] == ("Elizabeth → Ray", "conflict")


@pytest.mark.parametrize(
    "kind, description, label",
    [
        (
            EventKind.Death,
            "died, possibly around July 4",
            "died, possibly around July 4",
        ),
        (EventKind.Death, "Death of a heart attack", "Death of a heart attack"),
        (EventKind.Death, "Passed away at home", "Passed away at home"),
        (EventKind.Birth, "Born at home", "Born at home"),
        (EventKind.Birth, "was born in Anchorage", "was born in Anchorage"),
        (EventKind.Married, "Got married in Reno", "Got married in Reno"),
        (EventKind.Married, "marriage to Nora", "marriage to Nora"),
        (EventKind.Married, "in Reno", "married \u00b7 in Reno"),
        (EventKind.Divorced, "divorce final", "divorce final"),
        (
            EventKind.Death,
            "Moved in with the man who died",
            "died \u00b7 Moved in with the man who died",
        ),
        (EventKind.Birth, "reborn in faith", "born \u00b7 reborn in faith"),
        (
            EventKind.Death,
            "Robert Belgard died, possibly around July 4",
            "Robert Belgard died, possibly around July 4",
        ),
        (EventKind.Married, "Robert married Ann", "Robert married Ann"),
        (EventKind.Birth, "Robert was born at home", "Robert was born at home"),
        (EventKind.Death, "Ann died", "died \u00b7 Ann died"),
        (EventKind.Death, "", "died"),
        (EventKind.Shift, "Moved to Anchorage", "Moved to Anchorage"),
    ],
)
def test_a_label_says_the_kind_once(kind, description, label):
    # R-0457
    events = [
        asdict(
            Event(
                id=1,
                kind=kind,
                person=1,
                dateTime="1990-07-04",
                description=description,
            )
        )
    ]
    said = build_timeline(_named([(1, "Robert Belgard")], events))["events"][0]
    assert said["label"] == label


def test_a_pair_bond_names_the_speaker_and_the_partner():
    # R-0457
    data = DiagramData(
        people=[
            {**asdict(Person(id=1, name="Patrick")), "primary": True},
            asdict(Person(id=2, name="Emily")),
        ],
        events=[
            asdict(
                Event(
                    id=10,
                    kind=EventKind.Bonded,
                    person=1,
                    spouse=2,
                    dateTime="2019-03-01",
                    description="together for about a year and a half",
                )
            )
        ],
    )
    event = build_timeline(data)["events"][0]
    assert (event["person_name"], event["label"]) == (
        "Patrick & Emily",
        "bonded \u00b7 together for about a year and a half",
    )


def test_a_noted_event_near_a_shift_is_a_lead_and_raises_the_question():
    # R-0366
    """A move is not a change in the family, but a coach may wonder whether it
    played in (R-0366)."""
    events = [
        _shift(10, 1, "2000-03-01", "symptom", VariableShift.Up),
        asdict(
            Event(
                id=11,
                kind=EventKind.Noted,
                person=1,
                description="moved to Arizona",
                location="Arizona",
                dateTime="2000-01-01",
                dateCertainty=DateCertainty.Approximate,
            )
        ),
    ]
    timeline = build_timeline(_data([1], events))
    assert {(q["event_id"], q["other_event_id"]) for q in timeline["questions"]} == {(10, 11)}
