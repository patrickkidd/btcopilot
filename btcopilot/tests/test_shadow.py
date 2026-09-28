from btcopilot.coachmodel import Spent
from btcopilot.coachturn import CoachTurn
from btcopilot.models import ModelCall, TokenMeter
from btcopilot.toolbox import ToolName
from btcopilot.tests.conftest import Model, called, said, version
from btcopilot.tests.test_profile import own_person, titles


def test_a_scratch_turn_charges_no_one_and_leaves_the_profile(discussion, test_user):
    # R-0589
    named = called(
        ToolName.EditPerson,
        id=1,
        name="Wren",
        last_name="Hale",
        version=version(discussion.diagram),
    )
    named.spent = Spent(input=1000, output=50)
    first = test_user.first_name
    CoachTurn(
        discussion,
        "I am Wren Hale",
        model=Model(named, said("Thank you, Wren.")),
        scratch=True,
    ).run()
    assert test_user.first_name == first
    assert TokenMeter.query.count() == 0
    assert ModelCall.query.count() == 2
