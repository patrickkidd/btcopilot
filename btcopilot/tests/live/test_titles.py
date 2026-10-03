"""Every noted event and shift a real turn writes carries its own title: a
complete phrase of 2 to 4 words, readable alone beside the person in the
picture (R-0681).

The old prompt fails this: the old event tool had no title field, so no event
it wrote carries one; and the description it was told to keep to about three
words, never more than five, is what the picture cut to its first three
("Stayed out of").

Invented names only.
"""

from btcopilot import record
from btcopilot.schema import LOOSE_ENDS, TITLE_WORDS, EventKind
from btcopilot.tests.live.criterion import passes

WORDED = (EventKind.Noted.value, EventKind.Shift.value)


def untitled(coach, before: set[int]) -> list[str]:
    """What is wrong with each title the turn wrote; empty when all are good."""
    data = {"people": coach.people}
    wrong = []
    written = [e for e in coach.events if e["id"] not in before and e.get("kind") in WORDED]
    assert written, "the turn wrote no noted event and no shift"
    for event in written:
        title = (event.get("title") or "").strip()
        words = title.lower().rstrip(".").split()
        if not TITLE_WORDS[0] <= len(words) <= TITLE_WORDS[1]:
            wrong.append(f"{event['id']}: {title!r} is not 2 to 4 words")
        elif words[-1].strip(",;:") in LOOSE_ENDS:
            wrong.append(f"{event['id']}: {title!r} ends mid-phrase")
        elif record.linked_name(data, event, title):
            wrong.append(f"{event['id']}: {title!r} names a person the event links")
    return wrong


@passes(3, of=3)
def test_a_job_lost_and_drinking_again_each_get_a_title(coach):
    # R-0681
    coach.record()
    before = {e["id"] for e in coach.events}
    coach.say(
        "My dad lost his job at the plant in the spring of 1998, and by that summer "
        "he was drinking again."
    )
    assert untitled(coach, before) == []


@passes(3, of=3)
def test_a_brother_stepping_back_from_the_caring_gets_a_title(coach):
    # R-0681
    coach.record(people=[{"id": 4, "name": "Callum", "last_name": "Hale", "gender": "male"}])
    before = {e["id"] for e in coach.events}
    coach.say(
        "Since Mum was diagnosed in 2019 my brother Callum has stepped right back. "
        "He stays out of it and leaves all the caring to me."
    )
    assert untitled(coach, before) == []


@passes(3, of=3)
def test_a_move_across_the_country_gets_a_title(coach):
    # R-0681
    coach.record()
    before = {e["id"] for e in coach.events}
    coach.say(
        "In early 2004 I packed everything into my car and moved from Ohio to Tucson "
        "to start over after the divorce."
    )
    assert untitled(coach, before) == []
