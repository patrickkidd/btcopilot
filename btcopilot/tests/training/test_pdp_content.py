import pytest

from btcopilot.schema import (
    Diagram,
    PDP,
    Person,
    Event,
    Conflict,
    RelationshipKind,
)
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.async_utils import one_result
from btcopilot.personal import pdp


@pytest.fixture(autouse=True)
def e2e(request):
    if not request.config.getoption("--e2e"):
        pytest.skip("need --e2e option to run")


def test_shift_topic():

    discussion = Discussion(
        user_id=1,
        messages=[
            Statement(
                speaker=Speaker(type=SpeakerType.Subject),
                text="I had a run-in with my mother last christmas",
            ),
            Statement(
                origin=Speaker(type=SpeakerType.Expert),
                text="What specific event occurred during your run-in with your mother last Christmas?",
            ),
        ],
    )
    database = Diagram(
        pdp=PDP(
            people=[
                Person(
                    id=-1,
                    name="Mother",
                    spouses=[],
                    offspring=[],
                    birthDate=None,
                    confidence=0.9,
                ),
                Person(
                    id=-2,
                    name="Mother",
                    spouses=[],
                    offspring=[],
                    birthDate=None,
                    confidence=0.99,
                ),
            ],
            events=[
                Event(
                    id=-1,
                    description="Had a run-in with mother last christmas.",
                    dateTime="2022-12-25",
                    people=[-2],
                    symptom=None,
                    anxiety=None,
                    functioning=None,
                    relationship=Conflict(
                        shift=None,
                        kind=RelationshipKind.Conflict,
                        people=[],
                        movers=[0],
                        recipients=[-2],
                    ),
                    confidence=0.85,
                )
            ],
        )
    )

    user_message = "I went for my turn at the chinese auction and she told me which one to pick and I threw up"

    pdp_deltas = one_result(pdp.update(discussion, database, user_message))
