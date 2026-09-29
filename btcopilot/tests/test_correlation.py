from btcopilot.correlation import Firing, Variable, firings
from btcopilot.schema import (
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

APPROXIMATE = DateCertainty.Approximate


def _event(id, kind, when, certainty=DateCertainty.Certain, **kwargs):
    return asdict(
        Event(id=id, kind=kind, dateTime=when, dateCertainty=certainty, **kwargs)
    )


def _worse(id, when, certainty=DateCertainty.Certain, person=1, **variables):
    return _event(id, EventKind.Shift, when, certainty, person=person, **variables)


def _record(events, people=(1, 2, 3), bonds=(), parents=None):
    return DiagramData(
        people=[
            asdict(Person(id=i, name=f"P{i}", parents=(parents or {}).get(i)))
            for i in people
        ],
        events=events,
        pair_bonds=[asdict(b) for b in bonds],
    )


def test_two_endings_with_different_people_fire_once_at_the_second():
    # R-0004
    record = _record(
        [
            _event(10, EventKind.Separated, "1998-11-01", person=1, spouse=2),
            _worse(11, "1998-11-15", symptom=VariableShift.Up),
            _event(
                20,
                EventKind.Shift,
                "2010-10-01",
                APPROXIMATE,
                person=1,
                relationship=RelationshipKind.Cutoff,
                relationshipTargets=[3],
            ),
            _worse(21, "2010-10-01", APPROXIMATE, symptom=VariableShift.Up),
            _worse(22, "2010-10-20", symptom=VariableShift.Up),
        ]
    )
    assert firings(record) == [Firing(1, Variable.Symptom, ((10, 11), (20, 21)))]


def test_one_ending_with_two_bad_turns_is_one_occurrence():
    # R-0004
    record = _record(
        [
            _event(10, EventKind.Divorced, "2001-03-01", person=1, spouse=2),
            _worse(11, "2001-03-10", anxiety=VariableShift.Up),
            _worse(12, "2001-04-10", anxiety=VariableShift.Up),
        ]
    )
    assert firings(record) == []


def test_year_only_undated_and_earlier_shifts_do_not_count():
    # R-0004
    record = _record(
        [
            _event(10, EventKind.Separated, "2001-01-01", APPROXIMATE, person=1),
            _worse(11, "2001-02-01", symptom=VariableShift.Up),
            _event(20, EventKind.Separated, "2005-06-01", person=1),
            _worse(21, "2005-06-10", DateCertainty.Unknown, symptom=VariableShift.Up),
            _worse(22, "2005-05-20", symptom=VariableShift.Up),
            _event(30, EventKind.Separated, "2009-06-01", person=1),
            _worse(31, "2009-06-10", symptom=VariableShift.Up),
        ]
    )
    assert firings(record) == []


def test_a_month_only_date_widens_the_window_by_a_month():
    # R-0004
    day_certain = [
        _event(10, EventKind.Separated, "2001-10-01", person=1),
        _worse(11, "2001-12-15", functioning=VariableShift.Down),
        _event(20, EventKind.Separated, "2005-10-01", person=1),
        _worse(21, "2005-12-15", functioning=VariableShift.Down),
    ]
    assert firings(_record(day_certain)) == []
    month_only = [dict(e, dateCertainty=APPROXIMATE.value) for e in day_certain]
    assert firings(_record(month_only)) == [
        Firing(1, Variable.Functioning, ((10, 11), (20, 21)))
    ]


def test_a_parents_death_counts_for_the_child_and_a_spouses_for_the_widow():
    # R-0004
    record = _record(
        [
            _event(10, EventKind.Death, "1990-05-03", person=4),
            _worse(11, "1990-06-01", person=1, symptom=VariableShift.Up),
            _worse(12, "1990-06-01", person=5, symptom=VariableShift.Up),
            _event(20, EventKind.Death, "2004-02-03", person=6),
            _worse(22, "2004-03-01", person=5, symptom=VariableShift.Up),
            _event(30, EventKind.Death, "2010-02-03", person=5),
            _worse(31, "2010-03-01", person=1, symptom=VariableShift.Up),
        ],
        people=(1, 4, 5, 6),
        bonds=[PairBond(id=7, person_a=4, person_b=5), PairBond(id=8, person_a=5, person_b=6)],
        parents={1: 7},
    )
    assert firings(record) == [
        Firing(1, Variable.Symptom, ((10, 11), (30, 31))),
        Firing(5, Variable.Symptom, ((10, 12), (20, 22))),
    ]
