"""The coach gives the person's own dated facts back early, in order of time,
with no cause word: the prompt says so, and the live check tells a placing
sentence from one that is not.

Invented names only.
"""

import pytest

from btcopilot.promptdir import key_present, read
from btcopilot.tests.live.checks import places_in_time
from btcopilot.tests.repo import REPO

YEARS = [1988, 1990, 1991]
PLACED = (
    "So your parents married in 1988, your sister was born in 1990, and you "
    "moved the next year."
)


def test_the_private_flow_rules_carry_the_placing_paragraph():
    # R-0804
    path = REPO / "private" / "prompts" / "fragments" / "flow_core.md"
    if not key_present():
        pytest.skip("no key opens the private prompts")
    text = " ".join(read(path).split())
    assert "**Placing what they told you**" in text
    assert "within the first ten or so exchanges" in text
    assert 'never "because", "led to" or any other cause word' in text


def test_the_private_flow_rules_keep_the_observations_pairing_two_dated_facts():
    # R-0805
    if not key_present():
        pytest.skip("no key opens the private prompts")
    fragments = REPO / "private" / "prompts" / "fragments"
    core = " ".join(read(fragments / "flow_core.md").split())
    claude = " ".join(read(fragments / "flow_claude.md").split())
    assert "your dad left the same year the headaches started" in core
    assert (
        "your mom moved cross-country the same year your grandfather got sick" in claude
    )
    assert (
        "your dad moved out the same year your mom started having the headaches"
        in claude
    )


def test_a_sentence_placing_three_years_in_order_passes():
    # R-0804
    assert places_in_time(
        f"That's a lot in a few years. {PLACED} How old were you?", YEARS
    )
    assert places_in_time(
        "Ada and Hugh married in 1988, Ivy was born in 1990, and the next year Hugh "
        "moved you all to Tacoma.",
        YEARS,
    )


@pytest.mark.parametrize(
    "reply",
    [
        "When you were three they married, at five Ivy came, and a year later you were in Tacoma.",
        "When I was twelve we moved, aged 14 I left school, and two years after that I left home.",
        "Ivy came in 1990, the move was the next year, and at eight you started school.",
    ],
)
def test_ages_and_steps_place_in_time_too(reply):
    # R-0804
    assert places_in_time(reply, YEARS, born=1985)


EVENTS = [["wedding", "married"], ["Ivy"], ["move", "moved", "Tacoma"]]


def test_three_events_in_record_order_with_a_time_marker_place_in_time():
    # R-0804
    reply = "So by age six you'd been through the wedding, Ivy's arrival, and the move to Tacoma."
    assert places_in_time(reply, YEARS, born=1985, events=EVENTS)
    assert not places_in_time(
        reply.replace("by age six", "already"), YEARS, born=1985, events=EVENTS
    )
    assert not places_in_time(
        "By age six you'd been through the move, the wedding and Ivy's arrival.",
        YEARS,
        born=1985,
        events=EVENTS,
    )
    assert not places_in_time(
        "By age six the wedding and Ivy's arrival led to the move.",
        YEARS,
        born=1985,
        events=EVENTS,
    )


def test_ages_out_of_order_fail():
    # R-0804
    assert not places_in_time(
        "At six you moved to Tacoma, at three your parents married, and at five Ivy came.",
        YEARS,
        born=1985,
    )


def test_a_cause_word_fails_the_sentence():
    # R-0804
    assert not places_in_time(
        "Your parents married in 1988 and your sister came in 1990, and the move in "
        "1991 happened because of your dad's job.",
        YEARS,
    )


def test_two_years_are_not_a_placing():
    # R-0804
    assert not places_in_time(
        "Your parents married in 1988 and your sister came in 1990.", YEARS
    )


def test_years_out_of_order_fail():
    # R-0804
    assert not places_in_time(
        "The move was in 1991, your parents married in 1988, and your sister came in 1990.",
        YEARS,
    )
