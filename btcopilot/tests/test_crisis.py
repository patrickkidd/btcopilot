"""The crisis protocol: the words that fire it, which reply, the line for the
person's country, whether a reply met it, and the blocks the coach reads.

Invented people only.
"""

import datetime

import pytest

from btcopilot import flow
from btcopilot.extensions import db
from btcopilot.flow import Message, Record, RiskGroup, RiskReply, Role
from btcopilot.tests.test_searchchat import says
from btcopilot.tests.test_todo import BACK, ago, session, titles, turn  # noqa: F401

CRISIS = "This message says the person may be thinking"
STAY = "The person's last message said they may be thinking"
EXPLICIT = (
    "You said you want to die, and I'm taking that seriously. You can call or text"
    " 988 at any hour and talk with a person there; it's free. I'm here too, so"
    " what's happening for you right now?"
)
LESS = (
    "When you say you can't go on, I want to understand what you mean. If it ever"
    " means thinking about ending your life, you can call or text 988 at any hour"
    " and talk with a person there. What's it like for you right now?"
)
US = flow.line("America/New_York")


@pytest.mark.parametrize(
    "text",
    [
        "My mother wanted to die after Dad left.",
        "My father said he'd kill himself if she went.",
        'She wrote "I want to die" in her diary.',
        "I didn't hurt myself, I slipped on the stairs.",
        "I would never kill myself.",
        "I was dying to know what she said.",
        "This job is killing me.",
        "I could kill him for that.",
        "I nearly killed myself laughing.",
        "I nearly died of embarrassment.",
        "I want to end it with him.",
        "I want to end it all and start over at a new job.",
        "My brother cut himself as a teenager.",
        "How do you know if someone is suicidal?",
        "I cut myself off from my family for years.",
    ],
)
def test_the_cases_a_rule_must_not_match_do_not_fire(text):
    # R-0790, R-0797
    assert flow.risk(text) is None


def test_each_group_fires_its_reply():
    # R-0790, R-0797
    found = flow.risk("Honestly I just want to die.")
    assert (found.group, found.reply, found.emergency) == (
        RiskGroup.Explicit,
        RiskReply.Explicit,
        False,
    )
    assert found.said == "you just want to die"

    found = flow.risk("I've been hurting myself again.")
    assert (found.group, found.reply) == (RiskGroup.SelfHarm, RiskReply.Explicit)

    found = flow.risk("I have a plan to end it.")
    assert (found.group, found.reply, found.emergency) == (
        RiskGroup.Plan,
        RiskReply.Explicit,
        True,
    )

    found = flow.risk("I can't go on like this.")
    assert (found.reply, found.said) == (RiskReply.Less, "you can't go on")


def test_a_means_counts_only_beside_a_phrase_about_dying():
    # R-0790, R-0797
    assert flow.risk("We drove over the bridge to Grandma's.") is None
    found = flow.risk("I want to die. I keep thinking about the bridge.")
    assert (found.group, found.emergency) == (RiskGroup.Plan, True)


def test_the_persons_own_past_fires_the_less_explicit_reply():
    # R-0790, R-0797
    assert flow.risk("I tried to kill myself in 2010.").reply is RiskReply.Less
    assert flow.risk("I was suicidal in college.").reply is RiskReply.Less


def test_the_line_follows_the_time_zone():
    # R-0790, R-0797
    assert flow.line("America/Toronto").country == "CA"
    assert flow.line("Europe/Dublin").say.startswith("call Samaritans on 116 123")
    unknown = flow.line(None)
    assert unknown.marks == ("988", "findahelpline.com")
    assert flow.line("Europe/Berlin") == unknown


def test_protocol_passes_the_approved_replies_and_fails_the_rest():
    # R-0790, R-0797
    assert flow.protocol(EXPLICIT, US)
    assert flow.protocol(LESS, US)
    unknown = flow.line(None)
    assert flow.protocol(LESS.replace("call or text 988", unknown.say), unknown)
    assert not flow.protocol(LESS, unknown)

    dated = EXPLICIT.replace(
        "what's happening for you right now?", "when did it start?"
    )
    assert not flow.protocol(dated, US)
    assert not flow.protocol(f"{EXPLICIT} Is your mother still alive?", US)
    assert not flow.protocol(
        EXPLICIT.replace("call or text 988", "talk to someone"), US
    )


def test_tracked_rows_count_the_group_and_whether_the_reply_met_it():
    # R-0790, R-0797
    t0 = datetime.datetime(2026, 3, 2, 18, 0)
    messages = [
        Message(Role.Person, "I want to die and I have a gun.", t0),
        Message(Role.Coach, EXPLICIT, t0 + datetime.timedelta(minutes=1), 1, "m", "p"),
        Message(
            Role.Person, "I keep punishing myself.", t0 + datetime.timedelta(minutes=2)
        ),
        Message(
            Role.Coach,
            "When did that start?",
            t0 + datetime.timedelta(minutes=3),
            2,
            "m",
            "p",
        ),
    ]
    row = flow.rows(messages, Record(), "America/Chicago")[("m", "p")]
    assert (row["risk"], row["risk_plan"], row["risk_self_harm"], row["protocol"]) == (
        2,
        1,
        1,
        1,
    )


def test_the_coach_reads_the_crisis_block_then_the_stay_block(session, test_user):
    # R-0790, R-0797
    test_user.timezone = "Europe/Dublin"
    db.session.commit()
    assert CRISIS not in turn(session, "We moved to Leeds in 1998.")

    read = turn(session, "Honestly I just want to die.")
    assert CRISIS in read and "You said you just want to die" in read
    assert "116 123" in read and STAY not in read

    read = turn(session, "I don't know. It's been bad since the divorce.")
    assert STAY in read and CRISIS not in read

    assert STAY not in turn(session, "My dad was born in Cork.")


def test_the_crisis_block_comes_before_the_todo_block(session):
    # R-0790, R-0797
    says(session, "We talked about my dad.", ago(days=3))

    read = turn(session, "I can't go on like this.")
    assert -1 < read.index(CRISIS) < read.index(BACK)
