"""The catch-up rereads the conversation for each event at a stand-in date and
dates it by the three kinds (R-0960, R-0958): a time said gives an estimate
marked unknown with the words kept, an order said places it after its bound,
a standing pattern is left with no date. One call per case, as the plan makes
it, the plan's entry read back. A case passes when 2 of 3 runs plan as stated.

Fails on the old prompt and tool: the tool kept no words about when, and the
prompt said every event needs a date.

Invented names only.
"""

import datetime

from btcopilot.tests.live.criterion import passes
from btcopilot.tests.test_redate import REDATE, STANDIN, family

BORN = {"id": 3, "kind": "birth", "child": 1, "dateTime": "1985-04-12", "dateCertainty": "certain", "datePrecision": "day"}
GRAN = {"id": 4, "name": "June", "gender": "female"}
GRAN_DIED = {"id": 5, "kind": "death", "person": 4, "dateTime": "1998-03-02", "dateCertainty": "certain"}
WREN = {"people": [{"id": 1, "name": "Wren", "primary": True}, GRAN], "events": [BORN, GRAN_DIED], "lastItemId": 5}
DAD = {"id": 6, "name": "Hugh", "gender": "male"}
DRINKER = dict(
    STANDIN, id=7, kind="noted", person=6, symptom=None, title="A drinker", description="A drinker"
)
STAMP = datetime.datetime(2026, 11, 16).strftime("%Y%m%dT%H%M%S")


def planned(user, said: str, data: dict = WREN, event: dict = STANDIN) -> dict:
    diagram, _ = family(user, said, data, {k: v for k, v in event.items() if v is not None})
    (standin,) = [e for e in diagram.get_diagram_data().events if e["id"] == event["id"]]
    return REDATE.planned(diagram, standin, STAMP)


@passes(2, of=3)
def test_a_time_said_is_an_estimate_with_the_words_kept(test_user):
    # R-0960, R-0958, R-0957
    entry = planned(test_user, "Things got bad for me around high school, I stopped sleeping.")
    assert entry["left"] is None, entry
    assert (entry["kind"], entry["certainty"]) == ("a", "unknown"), entry
    assert 1998 <= int(entry["new"][:4]) <= 2004, entry
    assert "high school" in (entry["evidence"] or ""), entry


@passes(2, of=3)
def test_an_order_said_places_it_after_its_bound(test_user):
    # R-0960, R-0958
    entry = planned(test_user, "After Gran June died I stopped sleeping.")
    assert entry["left"] is None, entry
    assert entry["kind"] == "b", entry
    assert int(entry["new"][:4]) >= 1998, entry


@passes(2, of=3)
def test_a_standing_pattern_is_left_with_no_date(test_user):
    # R-0960, R-0958
    data = dict(WREN, people=[*WREN["people"], DAD], lastItemId=6)
    entry = planned(test_user, "My dad Hugh was always a drinker, my whole life.", data, DRINKER)
    assert entry["left"] is None, entry
    assert (entry["kind"], entry["new"]) == ("c", None), entry
