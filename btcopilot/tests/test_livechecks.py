"""The live cases' checks on made-up replies, no model: each wrong reply is
rejected and each allowed reply accepted.

Invented names only.
"""

import pytest

from btcopilot.tests.live.checks import (
    asks_children,
    asks_father_alive_or_age,
    asks_most_first,
    asks_only_waiting,
    title_retry,
)

MOST = (
    "Looking back over your life so far, what were the two or three times when the "
    "most was going on, and about what years were they?"
)


@pytest.mark.parametrize(
    "reply",
    [
        "That sounds hard. Do you and Sam have any children?",
        "Did you and Sam ever want kids?",
        "Have you and Sam thought about kids?",
        "What about kids, is that something you want?",
        "Would you like children someday?",
        "Since you can't have children, have you thought about adopting?",
    ],
)
def test_a_question_whether_the_couple_have_or_plan_children_is_rejected(reply):
    # R-0760
    assert asks_children(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "What happened between you and Sam after you learned you could not have children?",
        "How did you take learning you could not have children?",
        "What were you and Sam like as kids?",
        "How did the two of you meet?",
    ],
)
def test_a_question_after_learning_they_could_not_have_children_is_accepted(reply):
    # R-0760
    assert asks_children(reply) == []


@pytest.mark.parametrize(
    "reply",
    [
        "Is he still living?",
        "Are your parents both still alive?",
        "How old is your dad now?",
        "When was your father born?",
    ],
)
def test_a_question_whether_the_father_is_living_or_his_age_is_rejected(reply):
    # R-0760
    assert asks_father_alive_or_age(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "There's one thing still missing about your parents: when was your mom born?",
        "When was your mom born?",
        "How did your parents meet?",
    ],
)
def test_a_question_about_the_mother_is_accepted(reply):
    # R-0760
    assert asks_father_alive_or_age(reply) == []


@pytest.mark.parametrize(
    "reply",
    [
        "No worries. When were your parents married?",
        "Your mom's dad drank. When was your mother born?",
        "That's fine.",
    ],
)
def test_a_reply_that_asks_a_new_basic_data_question_fails_the_waiting_case(reply):
    # R-0771
    assert not asks_only_waiting(reply)


def test_a_reply_that_asks_the_waiting_question_passes():
    # R-0771
    assert asks_only_waiting(
        "That's fine. What has your mother told you about growing up with her father's drinking?"
    )


@pytest.mark.parametrize(
    "reply",
    [
        f"How old were you then? {MOST}",
        "That sounds like a lot. What did she get last year?",
        f"I hear you. {MOST.replace('?', '.')}",
    ],
)
def test_the_two_or_three_times_question_after_another_question_fails(reply):
    # R-0762
    assert not asks_most_first(reply)


def test_the_two_or_three_times_question_first_passes():
    # R-0762
    assert asks_most_first(f"Birthdays can be tricky. {MOST} And what did she like last year?")


def test_only_a_retried_title_refusal_is_tolerated():
    # R-0442
    refused = "event 35 is a shift event and needs a title: a complete phrase of 2 to 6 words"
    assert title_retry({"refusal": refused, "retried": True})
    assert not title_retry({"refusal": refused, "retried": False})
    assert not title_retry({"refusal": "event 31 is already in the record", "retried": True})
