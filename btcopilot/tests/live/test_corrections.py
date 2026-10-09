"""Real coach turns where the person tells the coach it read something into
what they said. The coach's notes must say so, which writes the correction
down for the tuning queue; a turn with no correction writes none.

Invented names only.
"""

from btcopilot.models import Observation, ObservationKind
from btcopilot.tests.live.criterion import passes


def corrections(coach) -> int:
    return Observation.query.filter_by(
        diagram_id=coach.user.free_diagram_id, kind=ObservationKind.PersonCorrected
    ).count()


@passes(2, of=3)
def test_the_person_saying_the_coach_assumed_is_written_down_as_a_correction(coach):
    # R-0822
    coach.record()
    coach.say(
        "In fourth grade my teacher Mr. Pell let me stay in at recess to read "
        "instead of going outside."
    )
    assert corrections(coach) == 0
    coach.say(
        "I didn't say Mr. Pell understood me, that's you assuming. I never said "
        "that. Stick to what I tell you."
    )
    assert corrections(coach) == 1
