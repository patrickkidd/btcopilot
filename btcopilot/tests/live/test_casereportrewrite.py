"""A refresh of the case report writes every card the coach writes again, from
the diagram as it stands, in one coach turn (R-0825): each of the four cards
holds a new guess afterwards, none of the ones it held before, and the new
Executive Summary opens on the symptom and its person and then names the pattern (R-0850). Then the
formulation framing (R-0850): what brought the person is decided from the
opening of their first conversation, in their own words; no card gives a
cause; the part card states the other way it could have gone; a cluster with
fewer than three supporting shifts, all the speaker's, is said to be both on its
line, and the Open line asks about the others in the family.

The family is the summary eval's, plus the speaker twice stopping calling her
mother and saying she is working on calling her every week. A pass is all four
cards rewritten and the summary passing the summary eval's three checks; each
framing eval states its own pass. Two runs of three: the cards are the
coach's judgement. Written, not yet run: real spend needs Patrick's yes.

Invented names only.
"""

import re

from btcopilot import diagramjson, record
from btcopilot.extensions import db
from btcopilot.models import Observation, ObservationKind
from btcopilot.schema import CardLine, Cluster, ClusterSource, asdict
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

CARDS = ("main_guess", "coach_guess", "couple", "own_part", "work_on")
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


# Her own period, so no regrouping in a turn replaces it: Silas's death, her
# classes stopped and her calls to her mother stopped, two supporting shifts,
# both hers.
THIN = Cluster(id="c1", title="After Grandpa died", summary="", name="After Grandpa died",
               eventIds=[32, 33, 36], source=ClusterSource.User, startDate="2009-03-14", endDate="2009-10-01")


def seeded(coach, clusters=()) -> None:
    coach.record(people=[ADA, HUGH, SILAS, RUTH, WALT, IRIS, TESS], pair_bonds=BONDS, events=[*EVENTS, *MORE])
    diagram = coach.user.free_diagram
    data = diagramjson.loads(diagram.data)
    data["questions"] = list(BEFORE)
    data["clusters"] = [asdict(one) for one in clusters]
    diagram.data = diagramjson.dumps(data)
    db.session.commit()


@passes(2, of=3)
def test_a_refresh_writes_all_four_cards_again_and_the_summary_opens_on_the_symptom(coach):
    # R-0825, R-0850
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
    assert reads(held["main_guess"][-1], coach.events) == (True,) * 3, held["main_guess"]


# Said first, but not where her focus landed; the second message is.
OPENING = ("Hi. I'm not sure where to start, I've been meaning to try this for a while.",
           "My husband says I'm the anxious one, and I suppose since my mother's fall I can't stop checking on everyone.")


def refreshed(coach, *said, clusters=()) -> list[dict]:
    seeded(coach, clusters)
    for statement in said:
        coach.turn(statement)
    response = coach.web.post("/app/case-report-rewrites", headers={"X-CSRFToken": coach.token})
    assert response.status_code == 202, response.get_data(as_text=True)
    assert coach.web.get(f"/app/case-report-rewrites/{response.get_json()['id']}").get_json()["state"] == "done"
    db.session.expire_all()
    return coach.user.free_diagram.get_diagram_data().questions


def on(questions, card) -> dict:
    return [q for q in questions if q.get("case_report_card") == card][-1]


@passes(2, of=3)
def test_what_brought_is_the_persons_own_words_where_her_focus_landed(coach):
    # R-0850
    # pass: the what_brought card rests on one of her messages and quotes words of the second, not only the first
    card = on(refreshed(coach, *OPENING), "what_brought")
    assert any(one["kind"] == "statement" for one in card["evidence"]), card
    quoted = card["text"].strip("\u201c\u201d\" ").lower()
    assert any(word in quoted for word in ("anxious", "checking", "fall")), card["text"]


@passes(2, of=3)
def test_no_card_of_a_refresh_gives_a_cause_on_its_first_answer(coach):
    # R-0850, R-0569
    # pass: the refresh needed no second ask for a cause, and the coach's guess holds a pattern
    questions = refreshed(coach, *OPENING)
    refused = Observation.query.filter_by(kind=ObservationKind.ToolRefused).all()
    assert not [o for o in refused if o.detail.get("retried")], [o.detail for o in refused]
    assert on(questions, "coach_guess")["text"].splitlines()[0].strip()


# Told close together in her own first-person words: the cards must stay the
# coach's and say only what happened and when.
TOLD = ("My parents separated the spring I joined the youth orchestra.",
        "I couldn't sleep before concerts that year, and I stopped calling my mother.")


def first_answer_refused(word: str) -> list[dict]:
    return [o.detail for o in Observation.query.filter_by(kind=ObservationKind.ToolRefused)
            if o.detail.get("retried") and word in o.detail["refusal"]]


@passes(2, of=3)
def test_every_card_of_a_refresh_is_in_the_coachs_voice_on_its_first_answer(coach):
    # R-0860
    # pass: no card of the first answer is refused as speaking as the person, and no card keeps "I", "me" or "my" outside quotation marks
    questions = refreshed(coach, *TOLD)
    assert not first_answer_refused("speaks as the person"), first_answer_refused("speaks as the person")
    spoken = {q["case_report_card"]: q["text"] for q in questions if q.get("case_report_card")}
    assert {c: record.voiced(t) for c, t in spoken.items()} == dict.fromkeys(spoken), spoken


@passes(2, of=3)
def test_events_told_close_together_are_set_side_by_side_never_one_creating_another(coach):
    # R-0864, R-0569
    # pass: no card of the first answer is refused for a cause, and no card says one event created, caused or led to another
    questions = refreshed(coach, *TOLD)
    assert not first_answer_refused("gives a cause"), first_answer_refused("gives a cause")
    spoken = {q["case_report_card"]: q["text"] for q in questions if q.get("case_report_card")}
    assert {c: record.caused(t) for c, t in spoken.items()} == dict.fromkeys(spoken), spoken


@passes(2, of=3)
def test_the_part_card_states_the_other_way_it_could_have_gone(coach):
    # R-0850
    # pass: the own_part card ends on an "Other way:" line, a question
    card = on(refreshed(coach, *OPENING), "own_part")
    other = [line for line in card["text"].splitlines() if line.startswith(f"{CardLine.OtherWay.value}:")]
    assert other and other[-1].rstrip().endswith("?"), card["text"]


@passes(2, of=3)
def test_a_thin_run_of_one_persons_shifts_is_said_so_and_the_open_line_asks_about_the_others(coach):
    # R-0850
    # pass: a For or Against line on c1 gives its shortfall ("only", "two" or "fewer") and names Wren or "you",
    # and the Open line names someone else in the family or asks about the others
    card = on(refreshed(coach, *OPENING, clusters=[THIN]), "coach_guess")
    lines = card["text"].splitlines()
    held = " ".join(line for line in lines if line.startswith((f"{CardLine.For.value} c1", f"{CardLine.Against.value} c1")))
    assert re.search(r"\b(only|two|fewer)\b", held.lower()) and re.search(r"\b(Wren|yours?)\b", held), card["text"]
    opened = " ".join(line for line in lines if line.startswith(f"{CardLine.Open.value}:"))
    assert re.search(r"\b(Ada|Hugh|Tess|Silas|Ruth|others?|rest of)\b", opened), card["text"]
