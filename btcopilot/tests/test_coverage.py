"""The basic data's checklist, worked out from the record as it grows: the
items it requires, the state of each, and the counts each coach turn keeps.

Invented names only.
"""

import pytest

from btcopilot import coverage, record
from btcopilot.extensions import db
from btcopilot.models import Author, TurnEvent
from btcopilot.schema import DiagramData, Fact, FactState, ItemKind
from btcopilot.tests.conftest import Model, calling, said, version
from btcopilot.tests.test_turnhistory import coach, family, post, titles  # noqa: F401
from btcopilot.tests.test_turns import token  # noqa: F401
from btcopilot.toolbox import ToolName
from btcopilot.turnlog import TurnEventKind

BORN = "When were you born?"
ME = 1
ADA, TOM, HOME, NELL = 2, 3, 4, 5
SAM, BOND = 6, 7


def done(turn_id: str) -> dict:
    return (
        TurnEvent.query.filter_by(turn_id=turn_id, kind=TurnEventKind.Done.value)
        .one()
        .payload["coverage"]
    )


def counts(required, known, unknown=0, declined=0) -> dict:
    return {
        "required": required,
        "known": known,
        "said_unknown": unknown,
        "declined": declined,
        "not_asked": required - known - unknown - declined,
    }


def data_of(diagram) -> DiagramData:
    db.session.expire_all()
    return diagram.get_diagram_data()


def test_the_checklist_grows_with_the_record_turn_by_turn(
    web, token, family, monkeypatch
):
    # R-0006
    coach(
        monkeypatch,
        Model(
            calling(
                (
                    ToolName.AddQuestion,
                    {
                        "text": BORN,
                        "kind": "fact",
                        "state": "asked",
                        "item_kind": "person",
                        "item_id": str(ME),
                        "fact": "birth_date",
                    },
                )
            ),
            said(BORN),
        ),
    )
    first = post(web, token, "I want to talk about my family.").get_json()

    data = data_of(family)
    assert coverage.required(data) == [
        (fact, ItemKind.Person, ME)
        for fact in (
            *coverage.SIBLING[0],
            Fact.Parents,
            Fact.Stress,
        )
    ]
    assert (
        coverage.states(data)[(Fact.BirthDate, ItemKind.Person, ME)]
        is FactState.NotAsked
    )
    assert done(first["turn_id"]) == {"before": counts(13, 1), "after": counts(13, 1)}

    at = version(family)
    coach(
        monkeypatch,
        Model(
            calling(
                (
                    ToolName.SetQuestion,
                    {
                        "id": "q1",
                        "version": at,
                        "state": "resolved",
                        "outcome": "unknown",
                    },
                ),
                (ToolName.EditPerson, {"name": "Ada", "gender": "female"}),
                (ToolName.EditPerson, {"name": "Tom", "gender": "male"}),
                (ToolName.EditPairBond, {"person_a": ADA, "person_b": TOM}),
                (
                    ToolName.EditPerson,
                    {"id": ME, "version": at, "gender": "female", "parents": HOME},
                ),
                (
                    ToolName.EditPerson,
                    {"name": "Nell", "gender": "female", "parents": HOME},
                ),
            ),
            said("Ada, Tom and Nell."),
        ),
    )
    second = post(
        web,
        token,
        "I don't know when I was born. My parents are Ada and Tom; my sister is Nell.",
    ).get_json()

    data = data_of(family)
    asked = next(q for q in data.questions if q["id"] == "q1")
    assert (asked["state"], asked["outcome"], asked["fact"], asked["item_id"]) == (
        "resolved",
        "unknown",
        "birth_date",
        str(ME),
    )
    found = coverage.states(data)
    assert found[(Fact.BirthDate, ItemKind.Person, ME)] is FactState.SaidUnknown
    assert found[(Fact.Parents, ItemKind.Person, ME)] is FactState.Known
    assert found[(Fact.Children, ItemKind.PairBond, HOME)] is FactState.NotAsked
    assert found[(Fact.Order, ItemKind.Person, NELL)] is FactState.NotAsked
    # the person, each parent with who their parents are, the parents'
    # number of children, the sister
    assert done(second["turn_id"]) == {
        "before": counts(13, 1),
        "after": counts(49, 9, 1),
    }

    at = version(family)
    coach(
        monkeypatch,
        Model(
            calling(
                (ToolName.EditPerson, {"name": "Sam", "gender": "male"}),
                (ToolName.EditPairBond, {"person_a": ME, "person_b": SAM}),
                (
                    ToolName.EditEvent,
                    {
                        "kind": "bonded",
                        "date": "2012-05-01",
                        "date_certainty": "certain",
                        "person": ME,
                        "spouse": SAM,
                    },
                ),
            ),
            said("You met Sam in 2012."),
        ),
    )
    third = post(web, token, "I met Sam in 2012.").get_json()

    found = coverage.states(data_of(family))
    assert found[(Fact.Met, ItemKind.PairBond, BOND)] is FactState.Known
    assert found[(Fact.Marriages, ItemKind.Person, SAM)] is FactState.Known
    assert found[(Fact.Parents, ItemKind.Person, SAM)] is FactState.NotAsked
    # Sam with who his parents are, and when they met and how many children
    assert done(third["turn_id"]) == {
        "before": counts(49, 9, 1),
        "after": counts(63, 14, 1),
    }


def test_the_partners_parents_are_required_as_far_as_the_person_is_attached(family):
    # R-0006
    data = family.get_diagram_data()
    data.people += [
        {"id": SAM, "name": "Sam", "gender": "male", "parents": 11},
        {"id": 12, "name": "Joan", "gender": "female"},
        {"id": 13, "name": "Ray", "gender": "male"},
    ]
    data.pair_bonds += [
        {"id": BOND, "person_a": ME, "person_b": SAM, "married": True},
        {"id": 11, "person_a": 12, "person_b": 13, "married": True},
    ]
    joan = {item for item in coverage.required(data) if item[2] == 12}
    assert {fact for fact, _, _ in joan} == {Fact.Name, Fact.Alive}

    data.events += [
        {
            "id": 20,
            "kind": "bonded",
            "person": ME,
            "spouse": SAM,
            "dateTime": "2008-01-01",
        },
        {
            "id": 21,
            "kind": "married",
            "person": ME,
            "spouse": SAM,
            "dateTime": "2010-01-01",
        },
    ]
    joan = {item for item in coverage.required(data) if item[2] == 12}
    assert {fact for fact, _, _ in joan} == set(coverage.FULL[0])


def test_a_declined_question_counts_as_declined_and_one_let_go_as_not_asked(family):
    # R-0006
    data = family.get_diagram_data()
    data.questions = [
        {
            "id": "q1",
            "text": "Where did you go to school?",
            "kind": "fact",
            "state": "resolved",
            "outcome": "declined_in_chat",
            "item_kind": "person",
            "item_id": "1",
            "fact": "schooling",
        },
        {
            "id": "q2",
            "text": "What do you do for work?",
            "kind": "fact",
            "state": "resolved",
            "outcome": "let_go",
            "item_kind": "person",
            "item_id": "1",
            "fact": "work",
        },
    ]
    found = coverage.states(data)
    assert found[(Fact.Schooling, ItemKind.Person, ME)] is FactState.Declined
    assert found[(Fact.Work, ItemKind.Person, ME)] is FactState.NotAsked


def test_only_a_fact_question_about_a_person_or_couple_names_its_item(family):
    # R-0006
    with pytest.raises(record.Invalid):
        record.apply(
            family.id,
            [
                {
                    "item_kind": ItemKind.Question.value,
                    "item_id": "q1",
                    "field": None,
                    "after": {
                        "id": "q1",
                        "text": "What was that like?",
                        "kind": "thought",
                        "state": "held",
                        "outcome": None,
                        "item_kind": "person",
                        "item_id": "1",
                        "fact": "work",
                        "session_id": None,
                        "asked_at": None,
                    },
                }
            ],
            author=Author.Coach,
            turn_id="t1",
        )
