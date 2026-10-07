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
    asks_passed_over,
    leads_with_todo,
    offers_todo,
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


@pytest.mark.parametrize(
    "reply",
    [
        "What has your mother told you about growing up with her father's drinking?",
        "That's fine. Did your grandfather's drinking ever come up at home?",
        "No worries. How much did Walt drink when your mom was small?",
    ],
)
def test_asking_the_question_passed_over_twice_fails(reply):
    # R-0774
    assert asks_passed_over(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "That's fine. When was your father born?",
        "No worries. What did Theo say when you texted him?",
        "It sounds like being left out of the trip hurt.",
    ],
)
def test_following_the_person_or_asking_something_else_passes(reply):
    # R-0774
    assert asks_passed_over(reply) == []


ASK_MOM = "ask my mom when they moved"


@pytest.mark.parametrize(
    "reply",
    [
        "Last time you were going to ask your mom when they moved. Did that happen, "
        "or is something else on your mind?",
        "Welcome back. Did you get to ask your mom when they moved? What has been "
        "on your mind since we talked?",
    ],
)
def test_a_reply_that_offers_the_todo_as_one_of_two_doors_passes(reply):
    # R-0815
    assert offers_todo(reply, ASK_MOM)


@pytest.mark.parametrize(
    "reply",
    [
        "Welcome back. Did you get to ask your mom when they moved?",
        "Welcome back. How have things been with your sister, or with work?",
        "Welcome back. I hope your mom is well.",
    ],
)
def test_a_reply_that_presses_the_todo_or_never_mentions_it_does_not_offer_it(reply):
    # R-0815
    assert not offers_todo(reply, ASK_MOM)


@pytest.mark.parametrize(
    "reply",
    [
        "Good to see you again. Did you get to ask your mom when they moved?",
        "Welcome back. Did your mom say when the move was?",
        "Last time you were going to ask your mom when they moved. Did that happen, "
        "or is something else on your mind?",
    ],
)
def test_a_reply_whose_first_question_is_the_todo_leads_with_it(reply):
    # R-0815, R-0803
    assert leads_with_todo(reply, ASK_MOM)


@pytest.mark.parametrize(
    "reply",
    [
        "That call sounds like it shook you. What did he say?",
        "Welcome back. How was your week? Did you get to ask your mom when they moved?",
        "Did you ask her?",
        "Welcome back. Your mom sounds busy. How is your sister?",
    ],
)
def test_a_reply_that_asks_something_else_first_does_not_lead_with_the_todo(reply):
    # R-0815, R-0803
    assert not leads_with_todo(reply, ASK_MOM)
