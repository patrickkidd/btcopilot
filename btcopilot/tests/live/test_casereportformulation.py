"""The parts of the formulation the refresh writes that an audit of FD-381
found missing (R-0850): each parent's family gives who on that side has died,
the person's contact with that side now or that it is not known, and the
parent's place among their brothers and sisters; the family card gives the
person's own place; no card calls a cluster "chronic anxiety"; and the coach's
guess names the periods its pattern does not fit. Each was run on the prompt
before its line and after.

Invented names only.
"""

import re

from btcopilot.schema import CardLine, Cluster, ClusterSource
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.live.test_casereportcards import (
    CLUSTERS,
    ILLNESS,
    IVY_BORN,
    LOSS,
    SIDED,
    chips,
    formulated,
    marked,
    notes,
    statement,
    told,
    words,
)

# Wren's place among her brothers and sisters and Ada's among hers: Ada the
# younger of two sisters, Wren the elder of two with her brother Finn.
FINN = {"id": 9, "name": "Finn", "last_name": "Hale", "gender": "male", "parents": 10}
ADA_BORN = {"id": 58, "kind": "birth", "person": 5, "spouse": 6, "child": 2, "dateTime": "1958-07-01"}
FINN_BORN = {"id": 57, "kind": "birth", "person": 2, "spouse": 3, "child": 9, "dateTime": "1988-02-01"}
PLACED = [IVY_BORN, ADA_BORN, FINN_BORN, *ILLNESS, SIDED, *LOSS]


def sided(coach) -> tuple[str, str]:
    """Her mother's side note and her father's, told apart by the people each rests on."""
    sides = notes(coach, "sides")
    on = lambda people: " ".join(words(s) for s in sides if chips(s, "person") & people)
    return on({"5", "6", "7"}), on({"3", "8"})


@passes(2, of=3)
def test_each_sides_card_gives_who_died_the_contact_now_and_the_parents_place(coach):
    # R-0850
    # pass: her mother's side note gives Ada's place as the younger sister, a death on that side and Wren's cutoff from Ada; her father's side note speaks of her contact with that side
    formulated(coach, events=PLACED, people=[FINN])
    mother, father = sided(coach)
    assert re.search(r"younger|youngest|second", mother, re.I) and re.search(r"died|death", mother, re.I), mother
    assert re.search(r"cut ?off|cut off|no contact", mother, re.I), mother
    assert re.search(r"contact|in touch", father, re.I), father


@passes(2, of=3)
def test_the_family_card_gives_the_persons_own_place_among_her_brothers_and_sisters(coach):
    # R-0850
    # pass: the family card says Wren is the elder or first of the two children
    formulated(coach, events=PLACED, people=[FINN])
    family = " ".join(words(n) for n in notes(coach, "family"))
    assert re.search(r"\b(eldest|oldest|elder|older of|first of|first-born|firstborn|first child)\b", family, re.I), family
