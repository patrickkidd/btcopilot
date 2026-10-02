"""The basic data's checklist, worked out from the record as it grows: the
items it requires, the state of each, and the counts each coach turn keeps.

Invented names only.
"""

import pytest

from btcopilot import coverage, record
from btcopilot.extensions import db
from btcopilot.models import Author, TurnEvent
from btcopilot.modelturn import ModelTurn
from btcopilot.schema import (
    DiagramData,
    Fact,
    FactState,
    ItemKind,
    PairBond,
    Person,
    PersonKind,
    asdict,
)
from btcopilot.tests.conftest import Model, called, calling, said, version
from btcopilot.tests.test_coachnotes import NOTES
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


def counts(required, known, unknown=0, declined=0, asked=0) -> dict:
    return {
        "required": required,
        "known": known,
        "asked": asked,
        "said_unknown": unknown,
        "declined": declined,
        "not_asked": required - known - unknown - declined - asked,
    }


RESOLVED = (
    "Coverage: {known} of {required} known. Resolved: {resolved} of {required} "
    "known, said unknown or declined."
)


def shown(model: Model) -> str:
    """The block of what is still unknown in the prompt the coach was sent."""
    prompt = model.systems[0]
    start = prompt.index(coverage.HEAD)
    return prompt[start : prompt.index("\n\n", start)]


def data_of(diagram) -> DiagramData:
    db.session.expire_all()
    return diagram.get_diagram_data()


def test_the_checklist_grows_with_the_record_turn_by_turn(
    web, token, family, monkeypatch
):
    # R-0006
    model = coach(
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
    assert shown(model) == "\n".join(
        [
            coverage.HEAD,
            "1 Wren (the person): birth date, schooling, work",
            RESOLVED.format(known=2, resolved=2, required=13),
        ]
    )

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
        coverage.states(data)[(Fact.BirthDate, ItemKind.Person, ME)] is FactState.Asked
    )
    # the person chatting is alive
    assert coverage.states(data)[(Fact.Alive, ItemKind.Person, ME)] is FactState.Known
    assert done(first["turn_id"]) == {
        "before": counts(13, 2),
        "after": counts(13, 2, asked=1),
    }

    at = version(family)
    model = coach(
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
    # the question is open, so the birth date is asked, not listed
    assert shown(model) == "\n".join(
        [
            coverage.HEAD,
            "1 Wren (the person): schooling, work, health",
            RESOLVED.format(known=2, resolved=2, required=13),
        ]
    )

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
        "before": counts(13, 2, asked=1),
        "after": counts(49, 10, 1),
    }

    at = version(family)
    model = coach(
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
    # at most three on one person, so the list reaches the parents; the birth
    # date said unknown is listed apart
    assert shown(model) == "\n".join(
        [
            coverage.HEAD,
            "1 Wren (the person): schooling, work, health",
            "2 Ada (mother): birth date, alive or not, schooling",
            "3 Tom (father): birth date, alive or not",
            "Said unknown: 1 Wren (the person): birth date",
            RESOLVED.format(known=10, resolved=11, required=49),
        ]
    )

    found = coverage.states(data_of(family))
    assert found[(Fact.Met, ItemKind.PairBond, BOND)] is FactState.Known
    assert found[(Fact.Marriages, ItemKind.Person, SAM)] is FactState.Known
    assert found[(Fact.Parents, ItemKind.Person, SAM)] is FactState.NotAsked
    # Sam with who his parents are, and when they met and how many children
    assert done(third["turn_id"]) == {
        "before": counts(49, 10, 1),
        "after": counts(63, 15, 1),
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


def parents(data: DiagramData) -> DiagramData:
    """The family after the second turn: Wren, her parents and her sister."""
    data.people[0]["parents"] = HOME
    data.people += [
        asdict(Person(id=ADA, name="Ada", gender=PersonKind.Female)),
        asdict(Person(id=TOM, name="Tom", gender=PersonKind.Male)),
        asdict(Person(id=NELL, name="Nell", gender=PersonKind.Female, parents=HOME)),
    ]
    data.pair_bonds = [asdict(PairBond(id=HOME, person_a=ADA, person_b=TOM))]
    return data


def test_under_a_plateau_the_list_is_cut_to_the_nearest_few(family):
    # R-0006, R-0520
    data = parents(family.get_diagram_data())
    full = coverage.block(data).splitlines()
    assert len(full) == 5
    assert coverage.block(data, plateau=2).splitlines() == [
        coverage.HEAD,
        "Your plateau note holds, turn 2 of 5: the nearest 3 only.",
        "1 Wren (the person): birth date, schooling, work",
        full[-1],
    ]


def plateaued(reached: bool) -> ModelTurn:
    return called(
        ToolName.CoachNotes,
        **{**NOTES, "plateau": {"reached": reached, "biggest_gap": "the parents"}},
    )


def held(model: Model) -> str:
    return shown(model).splitlines()[1]


def test_a_plateau_note_lapses_after_five_turns(web, token, family, monkeypatch):
    # R-0006, R-0520, R-0648
    seen = []
    for _ in range(coverage.PLATEAU_TURNS + 2):
        model = coach(monkeypatch, Model(plateaued(True), said("Go on.")))
        post(web, token, "Go on.")
        seen.append(held(model))
    assert seen[1:-1] == [
        f"Your plateau note holds, turn {turn} of 5: the nearest 3 only."
        for turn in range(1, coverage.PLATEAU_TURNS + 1)
    ]
    assert seen[0] == seen[-1] == "1 Wren (the person): birth date, schooling, work"


def test_a_new_person_ends_the_plateau(web, token, family, monkeypatch):
    # R-0006, R-0520, R-0648
    coach(monkeypatch, Model(plateaued(True), said("Go on.")))
    post(web, token, "Go on.")
    model = coach(
        monkeypatch,
        Model(
            calling(
                (ToolName.CoachNotes, plateaued(True).calls[0].args),
                (ToolName.EditPerson, {"name": "Nell", "gender": "female"}),
            ),
            said("Nell."),
        ),
    )
    post(web, token, "My sister is Nell.")
    assert held(model).startswith("Your plateau note holds, turn 1 of 5")

    model = coach(monkeypatch, Model(plateaued(True), said("Go on.")))
    post(web, token, "Go on.")
    assert not held(model).startswith("Your plateau note holds")


def test_a_job_told_unasked_and_noted_as_work_counts_as_known(family):
    # R-0006
    data = family.get_diagram_data()
    work = (Fact.Work, ItemKind.Person, ME)
    assert coverage.states(data)[work] is FactState.NotAsked

    data.events = [
        {
            "id": 2,
            "kind": "noted",
            "person": ME,
            "description": "Started at the bakery",
            "dateTime": "2019-03-01",
            "item": "work",
        }
    ]
    assert coverage.states(data)[work] is FactState.Known


def test_only_a_noted_event_names_the_item_it_records(family):
    # R-0006
    bakery = {
        "id": 2,
        "kind": "noted",
        "person": ME,
        "description": "Started at the bakery",
        "dateTime": "2019-03-01",
        "dateCertainty": "certain",
        "item": "work",
    }
    record.apply(
        family.id,
        [
            {
                "item_kind": ItemKind.Event.value,
                "item_id": 2,
                "field": None,
                "before": None,
                "after": bakery,
            }
        ],
        author=Author.Coach,
        turn_id="t1",
    )
    with pytest.raises(record.Invalid, match="only a noted event says"):
        record.apply(
            family.id,
            [
                {
                    "item_kind": ItemKind.Event.value,
                    "item_id": 2,
                    "field": "kind",
                    "before": "noted",
                    "after": "death",
                }
            ],
            author=Author.Coach,
            turn_id="t2",
        )


def test_a_death_without_words_leaves_its_cause_unknown(family):
    # R-0364
    data = family.get_diagram_data()
    cause = (Fact.CauseOfDeath, ItemKind.Person, ME)
    data.events = [{"id": 2, "kind": "death", "person": ME, "dateTime": "2013-01-01"}]
    assert coverage.states(data)[cause] is FactState.NotAsked

    data.events[0]["description"] = "Death"
    assert coverage.states(data)[cause] is FactState.NotAsked

    data.events[0]["description"] = "Stroke"
    assert coverage.states(data)[cause] is FactState.Known
