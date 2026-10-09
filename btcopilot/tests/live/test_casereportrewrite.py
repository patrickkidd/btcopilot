"""A refresh of the case report writes every card the coach writes again, from
the diagram as it stands, in one coach turn (R-0825): each of the five cards
holds a new guess afterwards, none of the ones it held before, and the new
Executive Summary reads the family as the summary eval asks (R-0820).

The family is the summary eval's, plus the speaker twice stopping calling her
mother and saying she is working on calling her every week. A pass is all five
cards rewritten and the summary passing the summary eval's four checks. Two
runs of three: the cards are the coach's judgement.

Invented names only.
"""

from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.live.test_executivesummary import (
    ADA,
    BONDS,
    EVENTS,
    HUGH,
    IRIS,
    RUTH,
    SILAS,
    TESS,
    WALT,
    event,
    reads,
)

CARDS = ("main_guess", "coach_guess", "own_part", "choice", "work_on")
MORE = [
    event(36, "shift", "2009-10-01", 1, "Stopped calling her mother", relationship="distance", relationshipTargets=[2]),
    event(37, "shift", "2016-06-01", 1, "Stopped calling her mother", relationship="distance", relationshipTargets=[2]),
    event(38, "noted", "2026-09-01", 1, "Working on weekly calls"),
]


def old(id, text, card) -> dict:
    return {"id": id, "text": text, "kind": "impression", "state": "raised", "outcome": None,
            "session_id": None, "asked_at": "2026-09-20", "pushback": None,
            "evidence": [{"kind": "event", "id": "33"}], "case_report_card": card}


BEFORE = [old(f"i{n}", f"An earlier guess for {card}.", card) for n, card in enumerate(CARDS, start=1)]


def seeded(coach) -> None:
    coach.record(people=[ADA, HUGH, SILAS, RUTH, WALT, IRIS, TESS], pair_bonds=BONDS, events=[*EVENTS, *MORE])
    diagram = coach.user.free_diagram
    data = diagramjson.loads(diagram.data)
    data["questions"] = list(BEFORE)
    diagram.data = diagramjson.dumps(data)
    db.session.commit()


@passes(2, of=3)
def test_a_refresh_writes_all_five_cards_again_and_the_summary_reads_the_family(coach):
    # R-0825, R-0820
    seeded(coach)
    coach.turn("I'm trying to call my mother every week now, even when things are tense.")
    response = coach.web.post("/app/case-report-rewrites", headers={"X-CSRFToken": coach.token})
    assert response.status_code == 202, response.get_data(as_text=True)
    rewrite = response.get_json()["id"]
    assert coach.web.get(f"/app/case-report-rewrites/{rewrite}").get_json()["state"] == "done"
    db.session.expire_all()
    now = coach.user.free_diagram.get_diagram_data().questions
    held = {card: [q for q in now if q.get("case_report_card") == card] for card in CARDS}
    stale = {q["id"] for q in BEFORE}
    assert {c: bool(qs) and not {q["id"] for q in qs} & stale for c, qs in held.items()} == dict.fromkeys(CARDS, True), held
    assert reads(held["main_guess"][-1], coach.events) == (True,) * 4, held["main_guess"]
