"""The coach writing first after a desktop file is brought in, the reminders
while what the import left to check stays open, and the block each coach turn
sees meanwhile. Invented names only; no model is called."""

import datetime
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from btcopilot import fdimport, fdnotice, proactive, record
from btcopilot.extensions import db
from btcopilot.fdnotice import Summary
from btcopilot.models import (
    Author,
    Change,
    Discussion,
    Observation,
    ObservationKind,
    ProactiveMessage,
    Statement,
    Trigger,
)
from btcopilot.models.preferences import PrefKey, Proactive
from btcopilot.proactive import Reason
from btcopilot.schema import ItemKind, Person, QuestionOutcome, QuestionState, asdict
from btcopilot.tests.conftest import Model, said
from btcopilot.tests.test_coverage import data_of
from btcopilot.tests.test_turnhistory import coach, post
from btcopilot.tests.test_turns import token  # noqa: F401
from btcopilot.toolbox import ToolError, ToolName, Toolbox

TURN = fdimport.TURN.format("f00d")
# Noon in Anchorage.
T0 = datetime.datetime(2026, 9, 1, 20)
DAY = datetime.timedelta(days=1)
ANN, BOB, CAL = 11, 12, 13


def _held(qid: str, person: int, text: str) -> dict:
    return {
        "id": qid,
        "text": text,
        "kind": "thought",
        "item_kind": ItemKind.Person.value,
        "item_id": str(person),
        "fact": None,
        "state": QuestionState.Held.value,
        "outcome": None,
        "session_id": None,
        "asked_at": None,
    }


def _add(kind: ItemKind, item: dict) -> dict:
    return {
        "item_kind": kind.value,
        "item_id": item["id"],
        "field": None,
        "after": item,
    }


def _summary(primaries=(), **counts) -> Summary:
    return Summary(
        **{"turn_id": TURN, "people": 3, "events": 0, "pair_bonds": 0, **counts},
        primaries=primaries,
    )


@pytest.fixture
def imported(test_user):
    """A file brought in as one turn: three people, two of them marked as the
    one it is about, and one held question the merge could not settle."""
    diagram = test_user.free_diagram
    test_user.timezone = "America/Anchorage"
    test_user.set_prefs(**{PrefKey.Proactive.value: Proactive.Weekly})
    db.session.commit()
    people = [
        asdict(Person(id=ANN, name="Ann", last_name="Lark")),
        asdict(Person(id=BOB, name="Bob", last_name="Lark")),
        asdict(Person(id=CAL, name="Cal")),
    ]
    record.apply(
        diagram.id,
        [
            *(_add(ItemKind.Person, p) for p in people),
            _add(
                ItemKind.Question,
                _held("q1", CAL, "Is Cal, born 1950, your uncle Cal?"),
            ),
        ],
        author=Author.Pro,
        turn_id=TURN,
        user_id=test_user.id,
    )
    return diagram


def _brought_in(test_user, imported, primaries=()):
    """The import's message at T0, its turn dated T0 too: a column default
    reads the real clock, not the frozen one."""
    with freeze_time(T0):
        fdnotice.after_import(imported.id, test_user.id, _summary(primaries))
    Change.query.update({"created_at": T0})
    db.session.commit()


@pytest.fixture
def push():
    with patch("btcopilot.proactive.push.send") as send:
        yield send


def _close(diagram, qid: str):
    record.apply(
        diagram.id,
        [
            {
                "item_kind": ItemKind.Question.value,
                "item_id": qid,
                "field": f,
                "after": v,
            }
            for f, v in (
                ("state", QuestionState.Resolved.value),
                ("outcome", QuestionOutcome.LetGo.value),
            )
        ],
        author=Author.Coach,
        turn_id="t-close",
    )


def _reply(user, when):
    discussion = (
        Discussion.query.filter_by(user_id=user.id)
        .order_by(Discussion.id.desc())
        .first()
    )
    db.session.add(
        Statement(
            discussion_id=discussion.id,
            speaker_id=discussion.chat_user_speaker_id,
            text="I'm Ann.",
            order=discussion.next_order(),
            created_at=when,
        )
    )
    db.session.commit()


def _texts(rows: list[dict]) -> list[str | None]:
    return [row["text"] or row["reason"] for row in rows]


def test_after_an_import_the_coach_writes_first_and_asks_which_person_is_you(
    test_user, imported, push
):
    # R-0878, R-0871, R-0852, R-0493
    with freeze_time(T0):
        message = fdnotice.after_import(imported.id, test_user.id, _summary((ANN, BOB)))
    assert message.statement.text == (
        "Your file is in: 3 people, 0 events and 0 pair-bonds. There are 2 things in "
        "it I'd like to check with you, a few at a time as we go. First, which of Ann "
        "Lark and Bob Lark is you?"
    )
    assert (
        message.statement.speaker_id == message.statement.discussion.chat_ai_speaker_id
    )
    assert (message.trigger, message.key, message.sent_at) == (Trigger.Import, TURN, T0)
    assert push.call_args.args == (test_user, message.statement)

    data = data_of(imported)
    assert [
        (q["id"], q["text"], q["state"]) for q in fdnotice.opened(imported.id, data)
    ] == [
        ("q1", "Is Cal, born 1950, your uncle Cal?", "held"),
        ("q2", "Which of Ann Lark and Bob Lark is you?", "held"),
    ]


def test_with_nobody_marked_the_message_asks_which_of_the_people_is_you(
    test_user, imported, push
):
    # R-0871, R-0878
    message = fdnotice.after_import(imported.id, test_user.id, _summary())
    assert message.question.endswith("First, which of the people in your file is you?")
    (row,) = Observation.query.filter_by(kind=ObservationKind.ProactiveSent).all()
    assert row.detail == {"reason": Trigger.Import.value, "message": message.id}


def test_with_one_person_marked_the_message_asks_nothing_of_who_they_are(
    test_user, imported, push
):
    # R-0878, R-0871
    record.apply(
        imported.id,
        [{"item_kind": "person", "item_id": ANN, "field": "primary", "after": True}],
        author=Author.Pro,
        turn_id=TURN,
    )
    message = fdnotice.after_import(imported.id, test_user.id, _summary())
    assert message.question == (
        "Your file is in: 3 people, 0 events and 0 pair-bonds. There is 1 thing in it "
        "I'd like to check with you. Shall we start with the first one?"
    )
    assert [q["id"] for q in data_of(imported).questions] == ["q1"]


def test_reminders_come_while_the_import_questions_stay_open_and_stop(
    test_user, imported, push
):
    # R-0878, R-0608
    _brought_in(test_user, imported, (ANN, BOB))
    remind = "2 things from the file you brought in are still to check with you. Shall we look at one now?"
    # the import's message waits for an answer
    assert _texts(proactive.run(now=T0 + 3 * DAY)) == [Reason.Waiting.value]
    _reply(test_user, T0 + DAY)
    # two days after the person last wrote, the first reminder; before that
    # the import's message holds back a pattern like any other
    assert _texts(proactive.run(now=T0 + 2 * DAY)) == [Reason.Budget.value]
    assert _texts(proactive.run(now=T0 + 3 * DAY)) == [remind]
    # it waits a week unanswered, then a second a week after the first
    assert _texts(proactive.run(now=T0 + 10 * DAY)) == [Reason.Waiting.value]
    assert _texts(proactive.run(now=T0 + 11 * DAY)) == [remind]
    # two ignored in a row stop them, as they stop every kind
    assert _texts(proactive.run(now=T0 + 19 * DAY)) == [Reason.Quiet.value]
    keys = [m.key for m in ProactiveMessage.query.order_by(ProactiveMessage.id)]
    assert keys == [TURN, f"{TURN}:1", f"{TURN}:2"]


def test_no_reminder_once_the_import_questions_are_closed_nor_past_four(
    test_user, imported, push
):
    # R-0878, R-0608
    _brought_in(test_user, imported)
    for n in range(1, fdnotice.REMINDERS + 1):
        when = T0 + n * 10 * DAY
        _reply(test_user, when - 8 * DAY)
        assert _texts(proactive.run(now=when))[0].startswith("2 things")
    _reply(test_user, T0 + 60 * DAY)
    assert _texts(proactive.run(now=T0 + 90 * DAY)) == [Reason.Quiet.value]

    ProactiveMessage.query.filter(ProactiveMessage.key != TURN).delete()
    _close(imported, "q1")
    _close(imported, "q2")
    assert _texts(proactive.run(now=T0 + 120 * DAY)) == [Reason.Quiet.value]


def test_each_coach_turn_sees_the_open_import_questions_until_closed(
    web, token, test_user, imported, monkeypatch
):
    # R-0878, R-0852, R-0493
    model = coach(monkeypatch, Model(said("Hello."), said("Hello again.")))
    post(web, token, "Hi.")
    block = (
        f"{fdnotice.HEAD}\n1 question the desktop file import kept is still open: q1."
    )
    assert block in model.systems[0]

    _close(imported, "q1")
    record.apply(
        imported.id,
        [_add(ItemKind.Question, _held("q2", CAL, "Was Cal close to your father?"))],
        author=Author.Coach,
        turn_id="t-coach",
    )
    assert fdnotice.block(imported.id, data_of(imported)) == ""


def test_the_files_own_events_are_counted_apart_from_those_found_in_its_notes(
    test_user, imported, push
):
    # R-0878
    message = fdnotice.after_import(
        imported.id,
        test_user.id,
        _summary((ANN, BOB), events=7, drawn=2, filed=5, pair_bonds=1, people=1),
    )
    assert message.question.startswith(
        "Your file is in: 1 person, 5 events and 1 pair-bond. "
        "I also found 2 more events in your notes."
    )


def test_a_stand_in_for_the_user_still_has_the_file_ask_which_person_is_them(
    test_user, imported, push
):
    # R-0871, R-0878
    record.apply(
        imported.id,
        [_add(ItemKind.Person, {**asdict(Person(id=1, name="User")), "primary": True})],
        author=Author.Pro,
        turn_id="t-first",
    )
    message = fdnotice.after_import(imported.id, test_user.id, _summary((ANN, BOB)))
    assert message.question.endswith("First, which of Ann Lark and Bob Lark is you?")
    [who] = [q for q in data_of(imported).questions if q["text"].startswith("Which")]
    assert (who["item_kind"], who["item_id"]) == (ItemKind.Person.value, "1")


def test_the_stand_in_is_never_renamed_while_the_file_asks_who_is_them(
    test_user, imported, push
):
    # R-0871
    record.apply(
        imported.id,
        [_add(ItemKind.Person, {**asdict(Person(id=1, name="User")), "primary": True})],
        author=Author.Pro,
        turn_id="t-first",
    )
    fdnotice.after_import(imported.id, test_user.id, _summary((ANN, BOB)))
    tools = Toolbox(imported.id, "t-answer", author=Author.Coach)
    with pytest.raises(ToolError, match="primary true on the person they named"):
        tools.call(
            ToolName.EditPerson,
            {"id": 1, "version": imported.version, "name": "Ann", "last_name": "Lark"},
        )

    tools.call(
        ToolName.EditPerson, {"id": ANN, "version": imported.version, "primary": True}
    )
    people = {p["id"]: p for p in data_of(imported).people}
    assert (1 in people, people[ANN]["primary"]) == (False, True)


def test_undoing_the_answer_then_the_import_leaves_the_stand_in_alone(
    test_user, push
):
    # R-0850, R-0871, R-0084
    diagram = test_user.free_diagram
    stand_in = {**asdict(Person(id=1, name="User")), "primary": True}
    record.apply(
        diagram.id,
        [_add(ItemKind.Person, stand_in)],
        author=Author.User,
        turn_id="t-first",
    )
    people = [
        asdict(Person(id=ANN, name="Ann", last_name="Lark")),
        asdict(Person(id=BOB, name="Bob", last_name="Lark")),
    ]
    record.apply(
        diagram.id,
        [_add(ItemKind.Person, p) for p in people],
        author=Author.Pro,
        turn_id=TURN,
        user_id=test_user.id,
    )
    fdnotice.after_import(diagram.id, test_user.id, _summary((ANN, BOB)))
    before = data_of(diagram).people
    Toolbox(diagram.id, "t-answer", author=Author.Coach).call(
        ToolName.EditPerson, {"id": ANN, "version": diagram.version, "primary": True}
    )

    Toolbox(diagram.id, "t-undo", author=Author.Coach).call(ToolName.Undo, {})
    assert sorted(data_of(diagram).people, key=lambda p: p["id"]) == before

    Toolbox(diagram.id, "t-undo-again", author=Author.Coach).call(ToolName.Undo, {})
    assert data_of(diagram).people == [stand_in]
