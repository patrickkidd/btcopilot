import datetime
from unittest.mock import patch

import pytest
from freezegun import freeze_time
import requests
from pywebpush import WebPushException

from btcopilot import clock, proactive, tuning
from btcopilot.proactive import Reason
from btcopilot.tests.conftest import csrf_token, wrote
from btcopilot.extensions import db
from btcopilot.models import (
    NotificationKind,
    Discussion,
    Notification,
    NotificationChannel,
    Observation,
    ModelCall,
    ObservationKind,
    ProactiveMessage,
    ProductEvent,
    Purpose,
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


def _record(user):
    """The user's record holding one pattern, with the budget set weekly."""
    people = [asdict(Person(id=i, name=f"P{i}")) for i in (1, 3)]
    people[0]["primary"] = True
    user.free_diagram.set_diagram_data(
        DiagramData(people=people, events=_pattern(10, 1990, "symptom"))
    )
    user.set_prefs(**{PrefKey.Proactive.value: Proactive.Weekly})
    user.timezone = "America/Anchorage"
    db.session.commit()
    return user


@pytest.fixture
def family(test_user):
    return _record(test_user)


@pytest.fixture
def sent():
    with (
        patch("btcopilot.proactive.push.send") as send,
        patch(
            "btcopilot.metered.response_text_sync", return_value=wrote(WORDS)
        ) as model,
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


def _why(rows: list[dict]) -> list[str | None]:
    return [row["reason"] for row in rows]


def test_a_pattern_becomes_one_coach_message_then_a_notification(family, sent):
    # R-0004
    send, model = sent
    assert _why(proactive.run(now=T0.replace(hour=11))) == [Reason.Night]
    said = proactive.run(now=T0)
    assert said == [
        {
            "email": family.username,
            "trigger": Trigger.Correlation.value,
            "text": WORDS,
            "refused": False,
            "reason": None,
        }
    ]
    message = ProactiveMessage.query.one()
    statement = db.session.get(Statement, message.statement_id)
    assert (message.key, message.sent_at) == ("1:symptom", T0)
    assert statement.text == WORDS
    assert statement.speaker_id == statement.discussion.chat_ai_speaker_id
    assert send.call_args.args == (family, statement)
    assert _counts() == [ObservationKind.ProactiveSent]
    call = ModelCall.query.one()
    assert (call.user_id, call.diagram_id, call.purpose) == (
        family.id,
        message.diagram_id,
        Purpose.Proactive,
    )
    prompt = model.call_args.args[0]
    assert (
        prompt.index("EARLIER")
        < prompt.index("10 1990-03-01")
        < prompt.index("NEWEST")
        < prompt.index("20 2000-03-01")
    )

    assert _why(proactive.run(now=T0 + 30 * DAY)) == [Reason.Quiet]
    assert model.call_count == 1


def test_words_out_of_shape_stay_unsent_and_are_tried_twice_more_then_never(
    family, sent
):
    # R-0004
    send, model = sent
    model.return_value = wrote("The breakup came first. Then the depression. Why?")
    for day in range(proactive.TRIES):
        said = proactive.run(now=T0 + day * DAY)
        assert [s["refused"] for s in said] == [True]
    assert send.call_count == 0
    assert ProactiveMessage.query.one().sent_at is None
    assert _counts() == [ObservationKind.ProactiveRefused] * proactive.TRIES

    assert _why(proactive.run(now=T0 + 30 * DAY)) == [Reason.Quiet]
    assert model.call_count == proactive.TRIES


def test_words_making_one_event_the_cause_of_the_other_stay_unsent(family, sent):
    # R-0004
    send, model = sent
    model.return_value = wrote(
        "The loss in November 1998 led to the symptoms that December. "
        "What do you notice?"
    )
    said = proactive.run(now=T0)
    assert [s["refused"] for s in said] == [True]
    assert send.call_count == 0
    assert _counts() == [ObservationKind.ProactiveRefused]


def test_a_refused_push_keeps_nothing_says_why_and_the_next_family_is_sent(
    family, test_user_2, sent
):
    # R-0004
    send, _ = sent
    test_user_2.set_free_diagram()
    other = _record(test_user_2)
    answer = requests.Response()
    answer.status_code, answer._content = 400, b'{"reason":"BadWebPushTopic"}'

    def refuse(user, statement):
        if user is family:
            raise WebPushException("Push failed: 400 Bad Request", response=answer)

    send.side_effect = refuse
    assert _why(proactive.run(now=T0)) == [
        'push failed: 400 {"reason":"BadWebPushTopic"}',
        None,
    ]
    [message] = ProactiveMessage.query.all()
    assert (message.user_id, message.sent_at) == (other.id, T0)
    assert Statement.query.filter_by(text=WORDS).count() == 1

    send.side_effect = None
    proactive.run(now=T0)
    assert ProactiveMessage.query.filter_by(user_id=family.id).one().sent_at == T0


def test_never_sends_nothing_unasked_but_a_follow_up_they_asked_for_goes(family, sent):
    # R-0004
    send, model = sent
    family.set_prefs(**{PrefKey.Proactive.value: Proactive.Never})
    db.session.commit()
    assert _why(proactive.run(now=T0)) == [Reason.Off]

    proactive.ask_later(
        family.id, family.free_diagram_id, T0.date(), "How did the talk with Ann go?"
    )
    db.session.commit()
    said = proactive.run(now=T0 + DAY)
    assert [s["text"] for s in said] == ["How did the talk with Ann go?"]
    assert model.call_count == 0
    assert send.call_count == 1


def test_a_follow_up_is_never_sent_again_after_its_sitting_is_deleted(
    family, sent, web, foreign_keys
):
    # R-0004
    send, _ = sent
    family.set_prefs(**{PrefKey.Proactive.value: Proactive.Never})
    proactive.ask_later(family.id, family.free_diagram_id, T0.date(), "And Ann?")
    db.session.commit()
    proactive.run(now=T0)
    sitting = ProactiveMessage.query.one().statement.discussion_id
    deleted = web.delete(
        f"/app/sessions/{sitting}", headers={"X-CSRFToken": csrf_token(web)}
    )
    assert deleted.status_code == 204
    assert ProactiveMessage.query.one().statement_id is None

    assert _why(proactive.run(now=T0 + 8 * DAY)) == [Reason.Off]
    assert send.call_count == 1


def test_the_coach_sets_a_question_for_later_and_it_goes_on_that_day(family, sent):
    # R-0004
    family.set_prefs(**{PrefKey.Proactive.value: Proactive.Never})
    tools = Toolbox(family.free_diagram_id, "t1", user_id=family.id)
    today = clock.today(family.timezone)
    with pytest.raises(ToolError):
        tools.call(ToolName.FollowUp.value, {"when": str(today), "question": "And?"})
    tools.call(
        ToolName.FollowUp.value,
        {"when": str(today + DAY), "question": "How did the talk with Ann go?"},
    )
    db.session.commit()
    due = ProactiveMessage.query.one().due_at

    assert _why(proactive.run(now=due - datetime.timedelta(hours=1))) == [Reason.Night]
    said = proactive.run(now=due + datetime.timedelta(hours=3))
    assert [s["text"] for s in said] == ["How did the talk with Ann go?"]


def test_a_follow_up_for_the_day_after_saturday_waits_for_sunday_where_the_person_is(
    family, sent
):
    # R-0760
    """Saturday evening in Anchorage is already Sunday in UTC: the coach may
    still set a question for Sunday, and it waits for Sunday morning there."""
    family.set_prefs(**{PrefKey.Proactive.value: Proactive.Never})
    saturday_evening = datetime.datetime(2026, 10, 4, 1, 30)
    with freeze_time(saturday_evening):
        Toolbox(family.free_diagram_id, "t1", user_id=family.id).call(
            ToolName.FollowUp.value,
            {"when": "2026-10-04", "question": "How did Sunday dinner go?"},
        )
    db.session.commit()
    assert ProactiveMessage.query.one().due_at == datetime.datetime(2026, 10, 4, 17)

    saturday_afternoon = datetime.datetime(2026, 10, 3, 23)
    assert _why(proactive.run(now=saturday_afternoon)) == [Reason.Off]
    assert _why(proactive.run(now=saturday_evening)) == [Reason.Off]
    sunday_morning = datetime.datetime(2026, 10, 4, 18)
    said = proactive.run(now=sunday_morning)
    assert [s["text"] for s in said] == ["How did Sunday dinner go?"]


def test_with_no_zone_kept_the_sending_hours_are_utcs(family, sent):
    # R-0760
    family.timezone = None
    db.session.commit()
    noon_in_anchorage = T0
    assert _why(proactive.run(now=noon_in_anchorage)) == [Reason.Night]
    assert _why(proactive.run(now=T0.replace(hour=12))) != [Reason.Night]


def test_rarely_waits_a_month_after_the_last_unasked_message(family, sent):
    # R-0004
    family.set_prefs(**{PrefKey.Proactive.value: Proactive.Rarely})
    proactive.run(now=T0)
    _reply(family, T0 + DAY)
    data = family.free_diagram.get_diagram_data()
    data.events += _pattern(110, 1991, "anxiety")
    family.free_diagram.set_diagram_data(data)
    db.session.commit()

    assert _why(proactive.run(now=T0 + 20 * DAY)) == [Reason.Budget]
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
    assert _why(proactive.run(now=T0 + 3 * DAY)) == [Reason.Waiting]
    assert [s["text"] for s in proactive.run(now=T0 + 8 * DAY)] == ["Second?"]
    assert _why(proactive.run(now=T0 + 16 * DAY)) == [Reason.Ignored]
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
                kind=NotificationKind.Coach,
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


def test_the_loop_counts_stay_out_of_the_queue_patrick_rules_on(family, sent):
    # R-0517
    proactive.run(now=T0)
    db.session.add(
        Observation(
            diagram_id=family.free_diagram_id,
            turn_id="t1",
            kind=ObservationKind.ToolRefused,
            detail={"reason": "show: No people were named."},
        )
    )
    db.session.commit()
    assert [g["kind"] for g in tuning.queue()] == [ObservationKind.ToolRefused.value]


def test_a_dry_run_keeps_and_sends_nothing(family, sent):
    # R-0004
    send, model = sent
    said = proactive.run(now=T0, dry_run=True)
    assert [s["text"] for s in said] == ["would write about 1:symptom"]
    assert model.call_count == 0
    assert ProactiveMessage.query.count() == 0
    assert Statement.query.count() == 0
    assert send.call_count == 0
