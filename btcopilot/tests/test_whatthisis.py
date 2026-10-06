"""The coach says what this is early, asks what the person hopes for, and
touches on it now and then; made-up replies prove the live check.

Invented names only.
"""

import pytest

from btcopilot.promptdir import key_present, read
from btcopilot.tests.live.checks import asks_hope, explains
from btcopilot.tests.repo import REPO
from btcopilot.tests.test_questions import (
    add,
    clock,
    settle,
    speaking,
    stored,
)  # noqa: F401
from btcopilot.tests.test_turnhistory import family  # noqa: F401
from btcopilot.toolbox import said_label

PRIVATE = REPO / "private" / "prompts" / "fragments" / "agent_opening.md"
PUBLIC = REPO / "btcopilot" / "prompty" / "agent.prompty"
ONBOARDING = REPO / "btcopilot" / "prompty" / "onboarding.prompty"
EXAMPLE = (
    "That sounds painful. I'll ask about what's going on and the people around it, "
    "and over a few conversations a picture of your life over time builds up that "
    "you can look at. What are you hoping to get from this?"
)


def test_the_private_opening_says_what_this_is():
    # R-0802, R-0801
    if not key_present():
        pytest.skip("no key opens the private prompts")
    text = read(PRIVATE)
    assert "**What this is.**" in text
    assert "Don't lead\nwith family or relationships" in text
    assert "In the reply after they answer the two or three times\nquestion" in text


def test_the_public_prompt_says_what_this_is():
    # R-0802, R-0801
    text = PUBLIC.read_text()
    assert "What this is." in text
    assert "Don't lead with family or relationships." in text
    assert "In the reply after they answer the two or three times question" in text


def test_onboarding_lets_the_sentence_ride_with_the_request():
    # R-0802, R-0801
    text = ONBOARDING.read_text()
    assert (
        "what this is and what builds up over a few conversations may come with that request"
        in text
    )
    assert "do nothing else" in text


def test_the_example_reply_passes():
    # R-0802, R-0801
    assert explains(EXAMPLE) and asks_hope(EXAMPLE)


@pytest.mark.parametrize(
    "reply",
    [
        EXAMPLE.replace("the people around it", "your relationships"),
        EXAMPLE.replace(
            "What are you hoping to get from this?", "How long has it been?"
        ),
        EXAMPLE.replace(
            "the people around it", "your family, and over time your family"
        ),
        "What are you hoping to get from this?",
    ],
)
def test_a_reply_that_leads_with_family_or_skips_the_hope_question_fails(reply):
    # R-0802, R-0801
    assert not (explains(reply) and asks_hope(reply))


def test_a_question_closed_as_answered_keeps_the_message_it_answers(family, test_user):
    # R-0802
    toolbox, said_ = speaking(family, test_user, "I want to stop dreading holidays")
    add(toolbox, "What are you hoping to get from this?", kind="thought")

    settle(toolbox, family, "q1", state="resolved", outcome="answered")
    assert stored(family)["q1"]["answer"] == {
        "kind": "statement",
        "id": said_.id,
        "label": said_label(said_),
    }
