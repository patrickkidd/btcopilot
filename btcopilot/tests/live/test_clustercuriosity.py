"""A cluster is a hypothesis of a broader family process: when the person talks
about their own hard years, the coach asks what was going on in the wider
family around then, expecting them not to have linked the two.

Fictionalized from Patrick's own example: a run of a person's own problems
from 2008 to 2011 and, elsewhere in the diagram, a grandmother's cancer and
death in 2010 and 2011 the person never connected to it. Invented names only.
"""

import re

from btcopilot.extensions import db
from btcopilot.tests.live.criterion import passes

GRANDMOTHER = {"id": 5, "name": "Edna", "last_name": "Pike", "gender": "female"}
GRANDFATHER = {"id": 6, "name": "Carl", "last_name": "Pike", "gender": "male"}
MOTHER = {"id": 2, "name": "Ada", "last_name": "Hale", "gender": "female", "parents": 11}
HER_PARENTS = {"id": 11, "person_a": 5, "person_b": 6, "married": True}
EVENTS = [
    {"id": 40, "kind": "shift", "person": 1, "dateTime": "2008-11-01", "dateCertainty": "approximate", "anxiety": "up", "title": "Couldn't sleep", "description": "Stopped sleeping well"},
    {"id": 41, "kind": "shift", "person": 1, "dateTime": "2009-01-15", "dateCertainty": "certain", "functioning": "down", "title": "Burnout", "description": "Burned out at work and took leave"},
    {"id": 42, "kind": "shift", "person": 1, "dateTime": "2009-09-01", "dateCertainty": "approximate", "symptom": "up", "title": "Back trouble", "description": "Back pain most days"},
    {"id": 43, "kind": "shift", "person": 1, "dateTime": "2010-06-01", "dateCertainty": "approximate", "relationship": "conflict", "title": "Fights with Sam", "description": "Fighting with her partner"},
    {"id": 44, "kind": "shift", "person": 1, "dateTime": "2011-03-01", "dateCertainty": "approximate", "functioning": "down", "title": "Quit the job", "description": "Left the job"},
    {"id": 45, "kind": "shift", "person": 5, "dateTime": "2010-02-01", "dateCertainty": "approximate", "symptom": "up", "title": "Lung cancer", "description": "Edna diagnosed with lung cancer"},
    {"id": 46, "kind": "death", "person": 5, "dateTime": "2011-01-20", "dateCertainty": "certain"},
]
CLUSTERS = [
    {
        "id": "c1",
        "title": "Burnout and what came after",
        "name": "Burnout and what came after",
        "summary": "",
        "reason": "Her sleep, work, back and partnership went wrong one after another.",
        "eventIds": [40, 41, 42, 43, 44],
        "source": "model",
    }
]
SAID = (
    "I keep coming back to 2009 to 2011. It started with the burnout and then "
    "everything kept going wrong for me, one thing after another."
)
FAMILY = re.compile(
    r"\b(famil\w*|grand\w*|mother|mom|father|dad|parents?|aunts?|uncles?|"
    r"sister|brother|siblings?|relatives?|died|death|ill\w*|sick\w*|born|moved?)\b",
    re.IGNORECASE,
)


def question(reply: str) -> str:
    """The reply's last sentence that asks something."""
    asks = [s for s in re.split(r"(?<=[.?!])\s+", reply) if s.endswith("?")]
    return asks[-1] if asks else ""


@passes(2, of=3)
def test_the_coach_asks_about_the_wider_family_around_the_persons_hard_years(coach):
    # R-0841
    """Pass: the reply's question asks about the family around those years."""
    coach.record([MOTHER, GRANDMOTHER, GRANDFATHER], [HER_PARENTS], EVENTS)
    data = coach.user.free_diagram.get_diagram_data()
    data.clusters = CLUSTERS
    coach.user.free_diagram.set_diagram_data(data)
    db.session.commit()

    reply = coach.say(SAID)
    print(f"  {reply}")
    assert FAMILY.search(question(reply)), reply
