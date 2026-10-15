"""Each date the coach writes is marked as sure as what the person said and no
surer: certain for a day, approximate for a year, an age or a range of about two
years, unknown only for a guess with nothing to anchor it (R-0855). A case
passes when 8 of 10 runs mark every event the turn writes about that person as
expected, read from the stored record.

Not yet run: the old prompt marked a hedge or a range unknown, so the range and
age cases are the ones expected to fail on it.

Invented names only.
"""

from btcopilot import record
from btcopilot.schema import DateCertainty
from btcopilot.tests.live.conftest import FATHER, MOTHER
from btcopilot.tests.live.criterion import passes


def marked(coach, person: int, statement: str) -> list[str]:
    """The certainty of each event about `person` the turn wrote."""
    coach.record()
    before = {e["id"] for e in coach.events}
    coach.say(statement)
    written = [
        e for e in coach.events if e["id"] not in before and record.involves(e, person)
    ]
    assert written, "the turn wrote no event about them"
    return sorted({e.get("dateCertainty") for e in written})


@passes(8, of=10)
def test_a_day_given_is_certain(coach):
    # R-0855
    said = "My dad had a heart attack on the 3rd of March 2011."
    assert marked(coach, FATHER["id"], said) == [DateCertainty.Certain.value]


@passes(8, of=10)
def test_a_year_given_is_approximate(coach):
    # R-0855
    said = "My mum had her hip replaced in 2014."
    assert marked(coach, MOTHER["id"], said) == [DateCertainty.Approximate.value]


@passes(8, of=10)
def test_one_year_or_the_next_is_approximate(coach):
    # R-0855
    said = "My dad was diagnosed with diabetes in 2008 or 2009."
    assert marked(coach, FATHER["id"], said) == [DateCertainty.Approximate.value]


@passes(8, of=10)
def test_an_age_given_is_approximate(coach):
    # R-0855
    said = "When I was eleven my dad lost his job at the mill."
    assert marked(coach, FATHER["id"], said) == [DateCertainty.Approximate.value]


@passes(8, of=10)
def test_sometime_in_childhood_is_unknown(coach):
    # R-0855
    said = "My mum went back to work sometime when I was a kid."
    assert marked(coach, MOTHER["id"], said) == [DateCertainty.Unknown.value]


@passes(8, of=10)
def test_a_decade_guessed_is_unknown(coach):
    # R-0855
    said = "My dad left the navy, I don't know, maybe the 70s."
    assert marked(coach, FATHER["id"], said) == [DateCertainty.Unknown.value]
