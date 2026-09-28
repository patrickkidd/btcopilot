"""The coach's play-by-play reply. Invented names only: the Whitlock stand-in
family."""

from btcopilot.case import Tool
from btcopilot.chips import ChipKind, token
from btcopilot.extensions import db
from btcopilot.models import Statement
from btcopilot.playturn import PlayTurn
from btcopilot.tests.conftest import Model, called
from btcopilot.tests.test_case import record, told


def test_a_new_play_carries_the_teal_chip_of_its_cluster(discussion):
    # R-0590, R-0545, R-0563
    data = record()
    model = Model(called(Tool.PlayByPlay, **told()))
    reply = PlayTurn.stored(data, "apart", discussion=discussion, model=model).run()
    stored = db.session.get(Statement, reply["statement_id"])

    assert token(ChipKind.Cluster, "apart", "Apart") in stored.text
    assert reply["statement"] == stored.text
    assert told()["point"] in stored.text
