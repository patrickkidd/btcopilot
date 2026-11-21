"""The coach dates an event by one of three kinds and keeps adjusting an
unknown date as evidence comes in (R-0956 to R-0959): a vague time said is an
estimate marked unknown with the person's words kept; an order said places it
between its bounds; a standing pattern has no date; a later year or a
corrected birth places it again. A case passes when 2 of 3 runs leave the
stored record as the case states, read from the diagram.

Fails on the old prompt and tool: the tool kept no words about when, and the
prompt said every event needs a date and a pattern is dated today.

Invented names only.
"""

from btcopilot import record
from btcopilot.schema import DateCertainty
from btcopilot.tests.live.conftest import FATHER, ME, MOTHER
from btcopilot.tests.live.criterion import passes

GRAN = {"id": 4, "name": "June", "last_name": "Bly", "gender": "female"}
GRAN_DIED = {
    "id": 40,
    "kind": "death",
    "person": 4,
    "dateTime": "1998-03-02",
    "dateCertainty": "certain",
}
DAD_BORN = {
    "id": 41,
    "kind": "birth",
    "child": 3,
    "dateTime": "1950-01-01",
    "dateCertainty": "approximate",
    "datePrecision": "year",
}
ARMY = {
    "id": 42,
    "kind": "noted",
    "person": 3,
    "title": "Joined the army",
    "description": "Joined the army",
    "dateTime": "1968-01-01",
    "dateCertainty": "unknown",
    "datePrecision": "year",
    "dateEvidence": "when he was 18",
}
PANIC = {
    "id": 43,
    "kind": "shift",
    "person": 1,
    "anxiety": "up",
    "title": "Panic attacks started",
    "description": "Panic attacks started",
    "dateTime": "2000-01-01",
    "dateCertainty": "unknown",
    "datePrecision": "year",
    "dateEvidence": "around high school",
}


def written(coach, person: int, statement: str) -> list[dict]:
    before = {e["id"] for e in coach.events}
    coach.say(statement)
    return [e for e in coach.events if e["id"] not in before and record.involves(e, person)]


def year(event: dict) -> int | None:
    return int(event["dateTime"][:4]) if event.get("dateTime") else None


def one(coach, event_id: int) -> dict:
    return next(e for e in coach.events if e["id"] == event_id)


@passes(2, of=3)
def test_a_vague_time_is_an_estimate_marked_unknown_with_the_words_kept(coach):
    # R-0958, R-0957, R-0956
    coach.record()
    events = written(coach, ME["id"], "Around high school I started having panic attacks.")
    assert events, "the turn wrote no event about them"
    assert all(
        e.get("dateCertainty") == DateCertainty.Unknown.value
        and 1998 <= (year(e) or 0) <= 2004
        and "high school" in (e.get("dateEvidence") or "")
        for e in events
    ), events


@passes(2, of=3)
def test_an_order_said_places_the_event_after_its_bound(coach):
    # R-0958, R-0957
    coach.record(people=[GRAN], events=[GRAN_DIED])
    events = written(
        coach, MOTHER["id"], "After Gran June died, my mum stopped speaking to her brother."
    )
    assert events, "the turn wrote no event about my mother"
    assert all(
        (year(e) or 0) >= 1998 and "after" in (e.get("dateEvidence") or "").lower()
        for e in events
    ), events


@passes(2, of=3)
def test_a_standing_pattern_has_no_date(coach):
    # R-0958, R-0956
    coach.record()
    events = written(coach, FATHER["id"], "My dad was always a drinker, my whole life.")
    assert events, "the turn wrote no event about my father"
    assert all(not e.get("dateTime") for e in events), events


@passes(2, of=3)
def test_a_later_age_moves_an_unknown_date(coach):
    # R-0959
    coach.record(events=[PANIC])
    coach.say("Actually the panic attacks started the year I turned sixteen.")
    panic = one(coach, PANIC["id"])
    assert year(panic) == 2001, panic
    assert "sixteen" in (panic.get("dateEvidence") or ""), panic


@passes(2, of=3)
def test_a_corrected_birth_places_again_what_was_placed_from_it(coach):
    # R-0959
    coach.record(events=[DAD_BORN, ARMY])
    coach.say("Sorry, I got that wrong: my dad was born in 1955, not 1950.")
    assert year(one(coach, DAD_BORN["id"])) == 1955
    assert year(one(coach, ARMY["id"])) == 1973, one(coach, ARMY["id"])
