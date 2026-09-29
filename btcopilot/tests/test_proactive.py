import datetime
from unittest.mock import patch

import pytest

from btcopilot import proactive
from btcopilot.extensions import db
from btcopilot.models import (
    Discussion,
    Notification,
    NotificationChannel,
    Observation,
    ObservationKind,
    ProactiveMessage,
    ProductEvent,
    Statement,
    Trigger,
)
from btcopilot.models.preferences import PrefKey, Proactive
from btcopilot.toolbox import ToolError, ToolName, Toolbox
from btcopilot.schema import (
    DiagramData,
    Event,
    EventKind,
    Person,
    RelationshipKind,
    VariableShift,
    asdict,
)

WORDS = "In October 2010 the breakup and a hard month sat close together. What do you make of that?"
# Noon in Anchorage.
T0 = datetime.datetime(2026, 9, 1, 20)
DAY = datetime.timedelta(days=1)


def _pattern(first_id: int, first_year: int, variable: str) -> list[dict]:
    """Two cutoffs ten years apart, each followed within weeks by a variable
    turning worse."""
    events = []
    for n, year in enumerate((first_year, first_year + 10)):
        cutoff = first_id + 10 * n
        events += [
            asdict(
                Event(
                    id=cutoff,
                    kind=EventKind.Shift,
                    person=1,
                    dateTime=f"{year}-03-01",
                    relationship=RelationshipKind.Cutoff,
                    relationshipTargets=[3],
                )
            ),
            asdict(
                Event(
                    id=cutoff + 1,
                    kind=EventKind.Shift,
                    person=1,
                    dateTime=f"{year}-03-20",
                    **{variable: VariableShift.Up},
                )
            ),
        ]
    return events


@pytest.fixture
def family(test_user):
    """The test user's record holding one pattern, with the budget set weekly."""
    people = [asdict(Person(id=i, name=f"P{i}")) for i in (1, 3)]
    people[0]["primary"] = True
    diagram = test_user.free_diagram
    diagram.set_diagram_data(
        DiagramData(people=people, events=_pattern(10, 1990, "symptom"))
    )
    test_user.set_prefs(**{PrefKey.Proactive.value: Proactive.Weekly})
    db.session.commit()
    return test_user


@pytest.fixture
def sent():
    with (
        patch("btcopilot.proactive.push.send") as send,
        patch("btcopilot.proactive.response_text_sync", return_value=WORDS) as model,
    ):
        yield send, model


def _reply(user, when):
    """Into the sitting the newest message the coach wrote first opened."""
    discussion = (
        Discussion.query.filter_by(user_id=user.id)
        .order_by(Discussion.id.desc())
        .first()
    )
    db.session.add(
        Statement(
            discussion_id=discussion.id,
            speaker_id=discussion.chat_user_speaker_id,
            text="Hm, I had not seen that.",
            order=discussion.next_order(),
            created_at=when,
        )
    )
    db.session.commit()


def _counts() -> list[ObservationKind]:
    return sorted(o.kind for o in Observation.query)


def test_a_pattern_becomes_one_coach_message_then_a_notification(family, sent):
    # R-0004
    send, model = sent
    assert proactive.run(now=T0.replace(hour=11)) == []
    said = proactive.run(now=T0)
    assert said == [
        {
            "email": family.username,
            "trigger": Trigger.Correlation.value,
            "text": WORDS,
            "refused": False,
        }
    ]
    message = ProactiveMessage.query.one()
    statement = db.session.get(Statement, message.statement_id)
    assert (message.key, message.statement.created_at) == ("1:symptom", T0)
    assert statement.text == WORDS
    assert statement.speaker_id == statement.discussion.chat_ai_speaker_id
    assert send.call_args.args == (family, statement)
    assert _counts() == [ObservationKind.ProactiveSent]
    prompt = model.call_args.args[0]
    assert (
        prompt.index("EARLIER")
        < prompt.index("10 1990-03-01")
        < prompt.index("NEWEST")
        < prompt.index("20 2000-03-01")
    )

    assert proactive.run(now=T0 + 30 * DAY) == []
    assert model.call_count == 1


def test_words_out_of_shape_are_kept_unsent_and_never_asked_for_again(family, sent):
    # R-0004
    send, model = sent
    model.return_value = "The breakup came first. Then the depression. Why?"
    said = proactive.run(now=T0)
    assert [s["refused"] for s in said] == [True]
    assert send.call_count == 0
    assert _counts() == [ObservationKind.ProactiveRefused]

    assert proactive.run(now=T0 + 30 * DAY) == []
    assert model.call_count == 1


def test_never_sends_nothing_unasked_but_a_follow_up_they_asked_for_goes(family, sent):
    # R-0004
    send, model = sent
    family.set_prefs(**{PrefKey.Proactive.value: Proactive.Never})
    db.session.commit()
    assert proactive.run(now=T0) == []

    proactive.ask_later(
        family.id, family.free_diagram_id, T0.date(), "How did the talk with Ann go?"
    )
    db.session.commit()
    said = proactive.run(now=T0 + DAY)
    assert [s["text"] for s in said] == ["How did the talk with Ann go?"]
    assert model.call_count == 0
    assert send.call_count == 1


def test_the_coach_sets_a_question_for_later_and_it_goes_on_that_day(family, sent):
    # R-0004
    family.set_prefs(**{PrefKey.Proactive.value: Proactive.Never})
    tools = Toolbox(family.free_diagram_id, "t1", user_id=family.id)
    today = datetime.date.today()
    with pytest.raises(ToolError):
        tools.call(ToolName.FollowUp.value, {"when": str(today), "question": "And?"})
    tools.call(
        ToolName.FollowUp.value,
        {"when": str(today + DAY), "question": "How did the talk with Ann go?"},
    )
    db.session.commit()
    due = ProactiveMessage.query.one().due_at

    assert proactive.run(now=due - datetime.timedelta(hours=1)) == []
    said = proactive.run(now=due + datetime.timedelta(hours=3))
    assert [s["text"] for s in said] == ["How did the talk with Ann go?"]


def test_rarely_waits_a_month_after_the_last_unasked_message(family, sent):
    # R-0004
    family.set_prefs(**{PrefKey.Proactive.value: Proactive.Rarely})
    proactive.run(now=T0)
    _reply(family, T0 + DAY)
    data = family.free_diagram.get_diagram_data()
    data.events += _pattern(110, 1991, "anxiety")
    family.free_diagram.set_diagram_data(data)
    db.session.commit()

    assert proactive.run(now=T0 + 20 * DAY) == []
    said = proactive.run(now=T0 + 31 * DAY)
    assert [m.key for m in ProactiveMessage.query] == ["1:symptom", "1:anxiety"]
    assert len(said) == 1


def test_two_ignored_in_a_row_stop_their_kind_until_a_reply(family, sent):
    # R-0004
    family.set_prefs(**{PrefKey.Proactive.value: Proactive.Never})
    for question in ("First?", "Second?", "Third?"):
        proactive.ask_later(family.id, family.free_diagram_id, T0.date(), question)
    db.session.commit()

    assert [s["text"] for s in proactive.run(now=T0)] == ["First?"]
    assert proactive.run(now=T0 + 3 * DAY) == []
    assert [s["text"] for s in proactive.run(now=T0 + 8 * DAY)] == ["Second?"]
    assert proactive.run(now=T0 + 16 * DAY) == []
    _reply(family, T0 + 17 * DAY)
    assert [s["text"] for s in proactive.run(now=T0 + 18 * DAY)] == ["Third?"]


def test_the_loop_counts_are_written_once_each(family, sent):
    # R-0004
    proactive.run(now=T0)
    message = ProactiveMessage.query.one()
    db.session.add_all(
        [
            Notification(
                user_id=family.id,
                statement_id=message.statement_id,
                channel=NotificationChannel.Push,
                opened_at=T0 + DAY,
            ),
            ProductEvent(
                user_id=family.id,
                session_id="s",
                screen="chat",
                name="open",
                client_at=T0 + DAY,
                created_at=T0 + DAY,
            ),
        ]
    )
    db.session.commit()
    _reply(family, T0 + DAY)

    proactive.run(now=T0 + 2 * DAY)
    proactive.run(now=T0 + 3 * DAY)
    assert _counts() == sorted(
        [
            ObservationKind.ProactiveSent,
            ObservationKind.ProactiveOpened,
            ObservationKind.ProactiveReplied,
            ObservationKind.ProactiveReturned,
        ]
    )


def test_a_dry_run_keeps_and_sends_nothing(family, sent):
    # R-0004
    send, _ = sent
    assert [s["text"] for s in proactive.run(now=T0, dry_run=True)] == [WORDS]
    assert ProactiveMessage.query.count() == 0
    assert Statement.query.count() == 0
    assert send.call_count == 0
