"""The questions the coach keeps: stored whole, never removed, closed once,
dismissed only by the user, on the map, and shown on the page only once asked.

Invented names only.
"""

import datetime
import json

import pytest
from freezegun import freeze_time
from mock import patch

from btcopilot import chips, coachturn, coverage, observer, questions, record, turnlog
from btcopilot.discussions import open_session
from btcopilot.extensions import db
from btcopilot.interactions import recent
from btcopilot.models import (
    Author,
    Change,
    InteractionKind,
    Observation,
    ObservationKind,
    Statement,
)
from btcopilot.recordtext import outline
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
from btcopilot.tests.conftest import Model, called, calling, csrf_token, said, version
from btcopilot.tests.test_searchchat import says
from btcopilot.tests.test_turnhistory import coach, family, post, statements, titles  # noqa: F401
from btcopilot.toolbox import ToolError, ToolName, Toolbox, said_label

ASK = "Who were your father's brothers and sisters?"
LATER = "When did your grandmother die?"
NOW = datetime.datetime(2026, 9, 27, 12, 0)
TODAY = NOW.date().isoformat()


@pytest.fixture(autouse=True)
def clock():
    """A question is dated by the clock when it is written, so the clock is
    pinned: a run crossing midnight would date it a day after TODAY."""
    with freeze_time(NOW):
        yield


def box(diagram, turn="t1", author=Author.Coach) -> Toolbox:
    return Toolbox(diagram.id, turn, session_id=7, author=author)


def add(toolbox, text=ASK, kind="fact", state="asked", **args):
    return toolbox.call(
        ToolName.AddQuestion, {"text": text, "kind": kind, "state": state, **args}
    )


def settle(toolbox, diagram, question_id, **args):
    return toolbox.call(
        ToolName.SetQuestion, {"id": question_id, "version": version(diagram), **args}
    )


def dismiss(diagram, question_id, turn="t9"):
    return record.apply(
        diagram.id,
        [
            {"item_kind": "question", "item_id": question_id, "field": "state", "after": "resolved"},
            {"item_kind": "question", "item_id": question_id, "field": "outcome", "after": "declined_by_user"},
        ],
        author=Author.User,
        turn_id=turn,
    )


def stored(diagram) -> dict:
    db.session.expire_all()
    return {q["id"]: q for q in diagram.get_diagram_data().questions}


def test_a_question_is_added_whole_in_one_change_row(family):
    # R-0006, R-0084
    add(box(family), item_kind="person", item_id="1")

    row = Change.query.filter_by(diagram_id=family.id).one()
    assert [(d["field"], d["before"]) for d in row.deltas] == [(None, None)]
    assert row.deltas[0]["after"] == {
        "id": "q1",
        "text": ASK,
        "kind": "fact",
        "state": "asked",
        "outcome": None,
        "item_kind": "person",
        "item_id": "1",
        "fact": None,
        "session_id": 7,
        "asked_at": TODAY,
    }


def test_a_question_is_dated_on_the_clock_its_messages_are_dated_on(family):
    # R-0006, R-0084
    with freeze_time(NOW, tz_offset=14):
        assert datetime.date.today().isoformat() != TODAY
        add(box(family))

    assert stored(family)["q1"]["asked_at"] == TODAY


def test_undo_puts_back_the_turn_but_never_a_question(family):
    # R-0006, R-0084
    turn = box(family, "t1")
    turn.call(ToolName.EditPerson, {"name": "Nell"})
    add(turn)
    dismiss(family, "q1", "t2")

    box(family, "t3").call(ToolName.Undo, {})

    db.session.expire_all()
    assert [p["name"] for p in family.get_diagram_data().people] == ["Wren"]
    assert stored(family)["q1"]["outcome"] == "declined_by_user"


def test_a_question_is_never_removed_by_anyone(family):
    # R-0006, R-0084
    toolbox = box(family)
    add(toolbox)

    with pytest.raises(ToolError) as refused:
        toolbox.call(
            ToolName.Remove,
            {"item_kind": "question", "item_id": "q1", "version": version(family)},
        )
    assert refused.value.plain == "A question is never removed."
    for author in Author:
        with pytest.raises(record.Invalid) as invalid:
            record.apply(
                family.id,
                [{"item_kind": "question", "item_id": "q1", "field": None, "after": None}],
                author=author,
                turn_id="gone",
            )
        assert invalid.value.plain == "A question is never removed."
    assert list(stored(family)) == ["q1"]


def test_each_state_change_is_a_row_with_before_after_and_author(family):
    # R-0084
    toolbox = box(family)
    add(toolbox, state="held")
    settle(toolbox, family, "q1", state="asked")
    dismiss(family, "q1")

    rows = Change.query.filter_by(diagram_id=family.id).order_by(Change.id).all()[1:]
    assert [
        (row.author, [(d["field"], d["before"], d["after"]) for d in row.deltas])
        for row in rows
    ] == [
        (
            Author.Coach,
            [("state", "held", "asked"), ("session_id", None, 7), ("asked_at", None, TODAY)],
        ),
        (
            Author.User,
            [("state", "asked", "resolved"), ("outcome", None, "declined_by_user")],
        ),
    ]


REFUSED = [
    (ToolName.AddQuestion, {"text": "  ", "kind": "fact", "state": "asked"}, "It gave the question no words."),
    (ToolName.AddQuestion, {"text": ASK, "kind": "fact", "state": "asked", "item_kind": "person"},
     "It named what the question is about only halfway."),
    (ToolName.AddQuestion, {"text": ASK, "kind": "fact", "state": "asked", "item_kind": "person", "item_id": "99"},
     "That is not in the record."),
    (ToolName.SetQuestion, {"id": "q1", "state": "asked"}, "That question was already asked."),
    (ToolName.SetQuestion, {"id": "q1", "state": "resolved"}, "It did not say how the question ended."),
    (ToolName.SetQuestion, {"id": "q1", "state": "asked", "outcome": "fact"}, "That question was already asked."),
    (ToolName.SetQuestion, {"id": "q1", "state": "resolved", "outcome": "declined_by_user"},
     "Only you can dismiss a question."),
    (ToolName.SetQuestion, {"id": "q2", "state": "resolved", "outcome": "answered"}, "That question is already closed."),
    (ToolName.SetQuestion, {"id": "q9", "state": "asked"}, "That is not in the record."),
]


@pytest.mark.parametrize("tool,args,plain", REFUSED)
def test_a_question_the_record_cannot_take_is_refused_in_plain_words(family, tool, args, plain):
    # R-0006, R-0478
    toolbox = box(family)
    add(toolbox, "What did your mother do for work?")
    add(toolbox, LATER, state="held")
    settle(toolbox, family, "q2", state="resolved", outcome="let_go")

    with pytest.raises(ToolError) as refused:
        toolbox.call(tool, {**args, "version": version(family)} if tool is ToolName.SetQuestion else args)
    assert refused.value.plain == plain


def test_the_same_words_are_one_open_question_and_may_be_asked_again_once_closed(family):
    # R-0479, R-0482
    toolbox = box(family)
    add(toolbox, LATER, state="held")

    with pytest.raises(ToolError) as refused:
        add(toolbox, "  when did your GRANDMOTHER   die?")
    assert refused.value.plain == "That question is already there."
    assert "q1" in str(refused.value)
    settle(toolbox, family, "q1", state="resolved", outcome="unknown")
    add(toolbox, "  when did your GRANDMOTHER   die?")
    assert stored(family)["q2"]["state"] == "asked"


def test_the_words_of_a_question_the_user_turned_down_are_never_added_again(family):
    # R-0479, R-0482
    add(box(family))
    dismiss(family, "q1")

    with pytest.raises(ToolError) as refused:
        add(box(family), ASK.upper())
    assert refused.value.plain == "The user already turned this question down."
    assert list(stored(family)) == ["q1"]


def test_removing_what_a_question_is_about_lets_it_go_and_undo_puts_both_back(family):
    # R-0006, R-0084
    turn = box(family, "t1")
    turn.call(ToolName.EditPerson, {"name": "Nell"})
    add(turn, item_kind="person", item_id="2")
    add(turn, LATER, item_kind="person", item_id="2")
    settle(turn, family, "q2", state="resolved", outcome="answered")

    box(family, "t2").call(
        ToolName.Remove, {"item_kind": "person", "item_id": "2", "version": version(family)}
    )
    row = Change.query.filter_by(turn_id="t2").one()
    assert sorted((d["item_id"], d["field"], d["after"]) for d in row.deltas if d["item_kind"] == "question") == [
        ("q1", "item_id", None),
        ("q1", "item_kind", None),
        ("q1", "outcome", "let_go"),
        ("q1", "state", "resolved"),
        ("q2", "item_id", None),
        ("q2", "item_kind", None),
    ]
    box(family, "t3").call(ToolName.Undo, {})

    assert [(q["state"], q["outcome"], q["item_kind"], q["item_id"]) for q in stored(family).values()] == [
        ("asked", None, "person", "2"),
        ("resolved", "answered", "person", "2"),
    ]
    assert [p["name"] for p in family.get_diagram_data().people] == ["Wren", "Nell"]


def test_only_the_user_dismisses_and_the_user_does_nothing_else(family):
    # R-0077
    add(box(family))
    add(box(family), LATER)

    for fields in (
        {"state": "resolved", "outcome": "declined_by_user", "text": "Something else?"},
        {"state": "resolved", "outcome": "answered"},
    ):
        with pytest.raises(record.Invalid) as refused:
            record.apply(
                family.id,
                [{"item_kind": "question", "item_id": "q1", "field": f, "after": v} for f, v in fields.items()],
                author=Author.User,
                turn_id="by-hand",
            )
        assert refused.value.plain == "Only you can dismiss a question."
    dismiss(family, "q2")
    assert stored(family)["q2"]["outcome"] == "declined_by_user"


MAP = DiagramData(
    people=[{"id": 1, "name": "Wren"}],
    questions=[
        {"id": "q1", "text": LATER, "kind": "fact", "state": "resolved", "outcome": "declined_by_user"},
        {"id": "q2", "text": ASK, "kind": "fact", "state": "held", "outcome": None,
         "item_kind": "person", "item_id": "1"},
        {"id": "q3", "text": "How does your father respond when he's anxious?", "kind": "thought",
         "state": "asked", "outcome": None},
        {"id": "q4", "text": "Where did they live?", "kind": "fact", "state": "resolved", "outcome": "answered"},
        {"id": "q10", "text": "What would your mother say?", "kind": "thought", "state": "resolved",
         "outcome": "declined_in_chat"},
    ],
)


def test_the_map_lists_open_questions_then_declined_ones(family):
    # R-0479, R-0006
    assert (
        'QUESTIONS (open, then declined: never ask a declined one again)\n'
        f'q2 held fact "{ASK}" about person 1\n'
        'q3 asked thought "How does your father respond when he\'s anxious?"\n'
        f'q1 declined fact "{LATER}"\n'
        'q10 declined thought "What would your mother say?"'
    ) in outline(MAP, 5)
    assert "Where did they live?" not in outline(MAP, 5)
    assert "QUESTIONS" not in outline(DiagramData(), 5)


def test_reading_questions_gives_open_and_declined_and_closed_on_asking(family):
    # R-0479
    toolbox = box(family)
    add(toolbox, "Where did they live?")
    add(toolbox, LATER, state="held")
    add(toolbox)
    settle(toolbox, family, "q1", state="resolved", outcome="answered")
    dismiss(family, "q3")

    text, _ = toolbox.call(ToolName.ReadQuestions, {})
    assert text == (
        f'q2 held fact "{LATER}"\n'
        f'q3 declined fact "{ASK}"\n\n'
        f"Record version {version(family)}."
    )
    text, _ = toolbox.call(ToolName.ReadQuestions, {"closed": True})
    assert text.splitlines()[0] == 'q1 resolved fact "Where did they live?" outcome=answered'


def test_a_coach_that_keeps_a_question_and_stops_silent_is_asked_once_to_reply(
    web, family, monkeypatch
):
    # R-0182
    model = coach(
        monkeypatch,
        Model(
            calling((ToolName.AddQuestion, {"text": LATER, "kind": "fact", "state": "held"})),
            said(""),
            said("What was your grandmother like?"),
        ),
    )
    body = post(web, csrf_token(web), "My grandmother raised me.").get_json()

    assert statements(web, body["discussion_id"])[1]["text"] == "What was your grandmother like?"
    assert model.histories[-1][-1]["content"][-1] == {"type": "text", "text": coachturn.SPEAK}


def asking_turn(web, monkeypatch, reply=f"Tell me about them. {ASK}"):
    coach(
        monkeypatch,
        Model(
            calling(
                (ToolName.AddQuestion, {"text": ASK, "kind": "fact", "state": "asked"}),
                (ToolName.AddQuestion, {"text": LATER, "kind": "fact", "state": "held"}),
            ),
            called(ToolName.ReadQuestions),
            said(reply),
        ),
    )
    return post(web, csrf_token(web), "My father had a big family.").get_json()


def test_a_reply_with_question_calls_names_each_and_logs_one_row_per_line(web, family, monkeypatch):
    # R-0478
    body = asking_turn(web, monkeypatch)

    reply = statements(web, body["discussion_id"])[1]
    assert [(t["name"], t["names"].get("it")) for t in reply["tools"]] == [
        ("add_question", ASK),
        ("add_question", None),
        ("read_questions", None),
    ]
    rows = Change.query.filter_by(statement_id=reply["id"]).all()
    assert len(rows) == len([t for t in reply["tools"] if t["name"] != "read_questions"])


def test_the_words_of_a_question_kept_for_later_never_reach_the_page(web, family, monkeypatch):
    # R-0006, R-0478
    read = version(family)
    coach(
        monkeypatch,
        Model(
            calling(
                (ToolName.AddQuestion, {"text": ASK, "kind": "fact", "state": "asked"}),
                (ToolName.AddQuestion, {"text": LATER, "kind": "fact", "state": "held"}),
            ),
            called(ToolName.SetQuestion, id="q2", version=read, state="resolved", outcome="let_go"),
            said(f"Tell me about them. {ASK}"),
        ),
    )
    body = post(web, csrf_token(web), "My father had a big family.").get_json()

    live = json.dumps([event for _, event in turnlog.read_from(body["turn_id"], 0)])
    thread = web.get(f"/app/sessions/{body['discussion_id']}").get_data(as_text=True)
    timeline = web.get("/app/timeline").get_data(as_text=True)
    assert [LATER in text for text in (live, thread, timeline)] == [False, False, False]
    assert [t["name"] for t in statements(web, body["discussion_id"])[1]["tools"]] == [
        "add_question",
        "add_question",
        "set_question",
    ]
    assert ASK in thread


def unsaid(family) -> list[dict]:
    return [
        o.detail
        for o in Observation.query.filter_by(
            diagram_id=family.id, kind=ObservationKind.QuestionUnsaid
        )
    ]


@pytest.mark.parametrize(
    "question,reply,observed",
    [
        (
            "How old are Ada's brothers now?",
            "Ada has two brothers. And how old are they now?",
            [],
        ),
        (ASK, "Tell me about your father's family.", [{"question": "q1", "overlap": 0.29}]),
    ],
)
def test_a_reply_that_hardly_holds_the_question_it_asked_is_observed_never_refused(
    web, family, monkeypatch, question, reply, observed
):
    # R-0482, R-0006
    coach(
        monkeypatch,
        Model(
            calling((ToolName.AddQuestion, {"text": question, "kind": "fact", "state": "asked"})),
            said(reply),
        ),
    )
    with patch.object(coachturn._log, "error") as error:
        body = post(web, csrf_token(web), "My brothers are older than me.").get_json()

    assert error.call_args_list == []
    assert statements(web, body["discussion_id"])[1]["text"] == reply
    assert unsaid(family) == observed


@pytest.mark.parametrize(
    "question,reply",
    [
        ("What's your last name?", "what's your last name"),
        ("What\u2019s your LAST name?", "Tell me: what's your last name..."),
    ],
)
def test_a_question_and_its_reply_are_compared_without_case_punctuation_or_apostrophe_kind(
    question, reply
):
    # R-0482
    assert observer.overlap(question, reply) == 1.0


def test_the_page_gets_asked_questions_only_each_with_where_it_was_asked(web, family, monkeypatch):
    # R-0006, R-0072
    body = asking_turn(web, monkeypatch)

    shown = web.get("/app/timeline").get_json()["asked_questions"]
    assert shown == [
        {
            "id": "q1",
            "text": ASK,
            "kind": "fact",
            "open": True,
            "asked_at": TODAY,
            "asked_in": {
                "discussion_id": body["discussion_id"],
                "statement_id": statements(web, body["discussion_id"])[1]["id"],
            },
            "evidence": [],
            "pushback": None,
            "case_report_card": None,
            "answer": None,
        }
    ]


def test_the_user_dismisses_a_question_and_the_coach_sees_it_declined(web, family, monkeypatch):
    # R-0077
    asking_turn(web, monkeypatch)
    token = csrf_token(web)

    answer = web.patch(
        "/app/questions/q1",
        json={"state": "resolved", "outcome": "declined_by_user"},
        headers={"X-CSRFToken": token},
    )
    assert (answer.status_code, answer.get_json()) == (
        200,
        {"id": "q1", "state": "resolved", "outcome": "declined_by_user", "pushback": None},
    )
    tap = web.post(
        "/app/interactions",
        json={"diagram_id": family.id, "kind": "dismiss", "item_kind": "question", "item_id": "q1"},
        headers={"X-CSRFToken": token},
    )
    assert tap.status_code == 201
    assert [(i.kind, i.item_kind, i.item_id) for i in recent(family.id)] == [
        (InteractionKind.Dismiss, ItemKind.Question, "q1")
    ]
    assert web.get("/app/timeline").get_json()["asked_questions"][0]["open"] is False
    assert f'q1 declined fact "{ASK}"' in outline(stored_data(family), version(family))
    refused = web.patch(
        "/app/questions/q2", json={"text": "Something else?"}, headers={"X-CSRFToken": token}
    )
    assert refused.status_code == 400


def stored_data(diagram) -> DiagramData:
    db.session.expire_all()
    return diagram.get_diagram_data()


def test_a_question_chip_survives_and_one_the_record_lacks_does_not():
    # R-0072
    text = chips.validate("[[question:q3]] and [[question:q9]]", MAP, None)
    assert text == "[[question:q3]] and this question"
    assert chips.context("[[question:q3]]", MAP, None).splitlines()[1] == (
        "question q3: \"How does your father respond when he's anxious?\""
    )


HUGH, SAM, ADA = 2, 3, 4
COUPLE, HOME = 7, 10
CHILDREN = "Do you and Sam have children?"
ALIVE = "Is your father still alive?"
HOLDS = "It was about to ask something the record already holds."


def grown(diagram):
    """Wren with her parents Ada and Hugh, and her partner Sam."""
    data = diagram.get_diagram_data()
    data.people[0]["parents"] = HOME
    data.people += [
        asdict(Person(id=HUGH, name="Hugh", gender=PersonKind.Male)),
        asdict(Person(id=SAM, name="Sam", gender=PersonKind.Male)),
        asdict(Person(id=ADA, name="Ada", gender=PersonKind.Female)),
    ]
    data.pair_bonds = [
        asdict(PairBond(id=COUPLE, person_a=1, person_b=SAM)),
        asdict(PairBond(id=HOME, person_a=ADA, person_b=HUGH, married=True)),
    ]
    data.lastItemId = HOME
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def with_record(diagram, events=(), questions_=()):
    """Events and questions written the record's way: a question only ever
    arrives through a change row."""
    record.apply(
        diagram.id,
        [
            {"item_kind": kind, "item_id": item["id"], "field": None, "after": item}
            for kind, items in (("event", events), ("question", questions_))
            for item in items
        ],
        author=Author.Coach,
        turn_id="t0",
    )


def speaking(family, user, text="What else do you want to know?"):
    """A toolbox answering the person's words, as a coach turn's is."""
    said_ = says(open_session(user, family), text, "2026-09-27T11:00")
    return Toolbox(
        family.id, "t1", user_id=user.id, session_id=said_.discussion_id, said=said_
    ), said_


def test_an_asked_fact_question_the_record_answers_is_refused_with_the_answer(family):
    # R-0760
    grown(family)
    with_record(
        family,
        events=[{"id": 20, "kind": "death", "person": HUGH, "dateTime": "2019-05-02"}],
        questions_=[
            {
                "id": "q1",
                "text": CHILDREN,
                "kind": "fact",
                "state": "resolved",
                "outcome": "answered",
                "item_kind": "pair_bond",
                "item_id": str(COUPLE),
                "fact": "children",
            }
        ],
    )
    toolbox = box(family)

    with pytest.raises(ToolError) as refused:
        add(toolbox, ALIVE, fact="alive", item_kind="person", item_id=str(HUGH))
    assert refused.value.plain == HOLDS
    assert str(refused.value) == (
        "The record already answers alive or not for 2 Hugh (father): "
        "20 2019-05-02 [death] person=2. Do not ask it; use the answer"
    )
    with pytest.raises(ToolError) as refused:
        add(toolbox, "How many children do you have?", fact="children", item_kind="pair_bond", item_id=str(COUPLE))
    assert refused.value.plain == HOLDS
    assert str(refused.value) == (
        "The record already answers how many children for couple 7, Wren and Sam "
        f'(the person and partner): q1 resolved fact "{CHILDREN}" about pair_bond 7 '
        "outcome=answered. Do not ask it; use the answer"
    )
    # a thought question, or one kept for later, is never refused this way, and
    # nor is a fact on the wrong kind of thing, which is kept as it always was
    add(toolbox, "What was your father like?", kind="thought", item_kind="person", item_id=str(HUGH))
    add(toolbox, ALIVE, state="held", fact="alive", item_kind="person", item_id=str(HUGH))
    add(toolbox, "Was Joe your mother's father, or your father's?", fact="children", item_kind="person", item_id=str(HUGH))
    add(toolbox, "Are Ada and Hugh both still living?", fact="alive", item_kind="pair_bond", item_id=str(HOME))
    assert list(stored(family)) == ["q1", "q2", "q3", "q4", "q5"]


def test_a_fact_question_can_be_added_already_answered_in_one_call(family, test_user):
    # R-0760
    grown(family)
    toolbox, said_ = speaking(family, test_user, "We can't have children.")

    text, _ = add(
        toolbox,
        CHILDREN,
        state="resolved",
        outcome="answered",
        fact="children",
        item_kind="pair_bond",
        item_id=str(COUPLE),
    )
    assert text == "Added question q1."
    kept = stored(family)["q1"]
    assert (kept["state"], kept["outcome"], kept["session_id"], kept["asked_at"]) == (
        "resolved",
        "answered",
        said_.discussion_id,
        TODAY,
    )
    assert kept["answer"] == {"kind": "statement", "id": said_.id, "label": said_label(said_)}
    assert Change.query.filter_by(diagram_id=family.id).count() == 1
    # "we can't have children" answers how many children the couple had, with
    # no number, and it is never asked again
    data = stored_data(family)
    children = (Fact.Children, ItemKind.PairBond, COUPLE)
    assert coverage.state_of(data, *children) is FactState.Known
    assert coverage.states(data)[children] is FactState.Known
    with pytest.raises(ToolError) as refused:
        add(toolbox, "How many children do you have?", fact="children", item_kind="pair_bond", item_id=str(COUPLE))
    assert refused.value.plain == HOLDS
    assert f"answer=message {said_.id}" in str(refused.value)
    # it carries its day, so it shows where closed questions show, answered
    assert [(q["id"], q["open"], q["answer"]["text"]) for q in questions.asked(family.id, data)] == [
        ("q1", False, "We can't have children.")
    ]


def test_a_fact_question_can_be_added_already_said_unknown_citing_an_older_message(family, test_user):
    # R-0760
    grown(family)
    toolbox, said_ = speaking(family, test_user)
    earlier = says(said_.discussion, "I don't know when Dad was born.", "2026-09-20T10:00")

    add(toolbox, "When was your father born?", state="resolved", outcome="unknown", fact="birth_date", item_kind="person", item_id=str(HUGH))
    add(toolbox, ALIVE, state="resolved", outcome="answered", answer=earlier.id, fact="alive", item_kind="person", item_id=str(HUGH))

    kept = stored(family)
    assert (kept["q1"]["outcome"], kept["q1"].get("answer")) == ("unknown", None)
    assert kept["q2"]["answer"]["id"] == earlier.id
    data = stored_data(family)
    assert coverage.state_of(data, Fact.BirthDate, ItemKind.Person, HUGH) is FactState.SaidUnknown
    assert coverage.state_of(data, Fact.Alive, ItemKind.Person, HUGH) is FactState.Known


BORN_CLOSED = [
    (
        {"kind": "fact", "fact": "children", "item_kind": "pair_bond", "item_id": "7", "outcome": "let_go"},
        "That is not how a question added closed ends.",
    ),
    (
        {"kind": "fact", "fact": "children", "item_kind": "pair_bond", "item_id": "7", "outcome": "answered"},
        "It kept an answer with no message behind it.",
    ),
    ({"kind": "fact", "outcome": "answered"}, "It kept an answer without saying what it answers."),
    (
        {"kind": "thought", "outcome": "answered", "fact": "children", "item_kind": "pair_bond", "item_id": "7"},
        "It kept an answer without saying what it answers.",
    ),
]


@pytest.mark.parametrize("args,plain", BORN_CLOSED)
def test_a_question_born_closed_needs_an_outcome_a_fact_and_its_item(family, args, plain):
    # R-0760
    grown(family)
    with pytest.raises(ToolError) as refused:
        box(family).call(ToolName.AddQuestion, {"text": CHILDREN, "state": "resolved", **args})
    assert refused.value.plain == plain
    assert stored(family) == {}


def test_a_second_open_fact_question_on_the_same_item_is_refused(family):
    # R-0760
    grown(family)
    toolbox = box(family)
    add(toolbox, ALIVE, fact="alive", item_kind="person", item_id=str(HUGH))

    with pytest.raises(ToolError) as refused:
        add(toolbox, "Is Hugh living?", fact="alive", item_kind="person", item_id=str(HUGH))
    assert refused.value.plain == "It asked the same thing twice."
    assert str(refused.value).startswith(
        "Question q1 already asks alive or not for 2 Hugh (father) and is open: close it "
        "with set_question first"
    )
    # the person's answer closes the open one; a new closed one is not the way
    with pytest.raises(ToolError) as refused:
        add(toolbox, "Is Hugh living?", state="resolved", outcome="unknown", fact="alive", item_kind="person", item_id=str(HUGH))
    assert refused.value.plain == "It asked the same thing twice."
    settle(toolbox, family, "q1", state="resolved", outcome="unknown")
    add(toolbox, "Is Hugh living?", fact="alive", item_kind="person", item_id=str(HUGH))
    assert [q["state"] for q in stored(family).values()] == ["resolved", "asked"]


def test_an_asked_fact_question_carries_what_the_person_said_before_about_it(family, test_user):
    # R-0760
    grown(family)
    toolbox, said_ = speaking(family, test_user)
    session = said_.discussion
    says(session, "Sam and I were never able to start a family.", "2026-09-20T10:00")
    says(session, "My dad had a stroke last year but he's still with us.", "2026-09-20T10:05")
    says(session, "Work has been busy.", "2026-09-21T10:00")
    says(session, "My neighbour's kids are loud all day.", "2026-09-21T10:05")
    says(session, "My parents are still married, fifty years this June.", "2026-09-21T10:10")

    # a paraphrase the word list catches ("start a family"); the person's own
    # couple is searched by the item's words alone, since they say "we", so
    # anyone's kids come back too, newest first, for the coach to judge
    text, _ = add(toolbox, CHILDREN, fact="children", item_kind="pair_bond", item_id=str(COUPLE))
    assert text.splitlines()[0] == "Added question q1."
    assert text.splitlines()[2] == (
        "Said before about how many children for couple 7, Wren and Sam (the person and "
        "partner); read these before you ask, and when one answers it, close q1 with "
        "set_question as answered, citing the message, instead of asking:"
    )
    assert [line.split(" ", 1)[1] for line in text.splitlines()[3:]] == [
        "2026-09-21 user: My neighbour's kids are loud all day.",
        "2026-09-20 user: Sam and I were never able to start a family.",
    ]
    # the father's words are found under what he is called, "my parents" too
    text, _ = add(toolbox, ALIVE, fact="alive", item_kind="person", item_id=str(HUGH))
    assert [line.split(" ", 1)[1] for line in text.splitlines()[3:]] == [
        "2026-09-21 user: My parents are still married, fifty years this June.",
        "2026-09-20 user: My dad had a stroke last year but he's still with us.",
    ]
    # words that name neither him nor what he is called are not his, and the
    # neighbour's kids are not the parents' children
    text, _ = add(toolbox, "What did Hugh do for work?", fact="work", item_kind="person", item_id=str(HUGH))
    assert text == "Added question q3."
    text, _ = add(toolbox, "How many children did your parents have?", fact="children", item_kind="pair_bond", item_id=str(HOME))
    assert text == "Added question q4."
    assert [q["state"] for q in stored(family).values()] == ["asked"] * 4
