"""The questions the coach keeps: stored whole, never removed, closed once,
dismissed only by the user, on the map, and shown on the page only once asked.

Invented names only.
"""

import datetime

import pytest
from mock import patch

from btcopilot import chips, coachturn, record
from btcopilot.extensions import db
from btcopilot.interactions import recent
from btcopilot.models import Author, Change, InteractionKind
from btcopilot.recordtext import outline
from btcopilot.schema import DiagramData, ItemKind
from btcopilot.tests.conftest import Model, called, calling, csrf_token, said, version
from btcopilot.tests.test_turnhistory import coach, family, post, statements, titles  # noqa: F401
from btcopilot.toolbox import ToolError, ToolName, Toolbox

ASK = "Who were your father's brothers and sisters?"
LATER = "When did your grandmother die?"
TODAY = datetime.date.today().isoformat()


def box(diagram, turn="t1", author=Author.Coach) -> Toolbox:
    return Toolbox(diagram.id, turn, session_id="7", author=author)


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
        "session_id": 7,
        "asked_at": TODAY,
    }


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


def test_the_same_words_are_one_question_even_once_it_is_closed(family):
    # R-0479
    toolbox = box(family)
    add(toolbox, LATER, state="held")
    settle(toolbox, family, "q1", state="resolved", outcome="unknown")

    with pytest.raises(ToolError) as refused:
        add(toolbox, "  when did your GRANDMOTHER   die?")
    assert refused.value.plain == "That question is already there."
    assert "q1" in str(refused.value)


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
        ("add_question", LATER),
        ("read_questions", None),
    ]
    rows = Change.query.filter_by(statement_id=reply["id"]).all()
    assert len(rows) == len([t for t in reply["tools"] if t["name"] != "read_questions"])


def test_a_reply_that_drops_the_words_it_asked_is_logged(web, family, monkeypatch):
    # R-0006
    with patch.object(coachturn._log, "error") as error:
        asking_turn(web, monkeypatch, reply="Tell me about your father's family.")
    assert "asked question q1" in error.call_args.args[0]


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
        {"id": "q1", "state": "resolved", "outcome": "declined_by_user"},
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
    text = chips.validate("[[question:q3]] and [[question:q9]]", MAP)
    assert text == "[[question:q3]] and this question"
    assert chips.context("[[question:q3]]", MAP).splitlines()[1] == (
        "question q3: \"How does your father respond when he's anxious?\""
    )
