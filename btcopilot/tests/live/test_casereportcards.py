"""The coach puts its guesses and questions on the case report's cards: its
main guess when asked for one, what it infers the person's own part was along
with the question asking what they think it was, and the person's answer to
that question, kept as their own view (R-0708, R-0709).

Each check reads the calls the turn made, refused or not, and the record it
left. Two runs of three: the card is the coach's judgement, asked for in plain
words, so one miss in three is allowed.

Then the formulation the refresh writes (R-0850), one eval per line of the
refresh prompt: the summary is the trouble then the pattern; the coach's guess
lays the people out in time order, names a triangle only when the events mark
one, and its For lines carry the changes in the family, who was rearranged,
how the trouble came on and how things stood after; only what to work on says
what will come, with what that rests on. Written to fail on the prompt before
these lines; not yet run.

Invented names only.
"""

import re

from btcopilot import diagramjson, record
from btcopilot.casereport import FORETOLD, MARK
from btcopilot.extensions import db
from btcopilot.schema import CardLine, Cluster, ClusterSource, asdict
from btcopilot.tests.live.conftest import FATHER, MOTHER
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.live.test_casereportrewrite import first_answer_refused
from btcopilot.toolbox import ToolName
from btcopilot.turnlog import TurnEventKind

NOTES = (ToolName.AddImpression, ToolName.SetImpression)
ASKS = (ToolName.AddQuestion, ToolName.SetQuestion)


def shift(id, date, person, title, **fields):
    return {"id": id, "kind": "shift", "person": person, "dateTime": date, "title": title,
            "description": title, "dateCertainty": "approximate", **fields}


EVENTS = [
    shift(40, "2004-09-01", 1, "Stopped sleeping well", symptom="up"),
    shift(41, "2005-02-01", 1, "Stopped calling her mother", relationship="distance",
          relationshipTargets=[2]),
    shift(42, "2018-04-01", 2, "Hospitalized with pneumonia", symptom="up"),
    shift(43, "2019-01-01", 1, "Stopped visiting her mother", relationship="distance",
          relationshipTargets=[2]),
]


def guess(id, text, evidence, card=None) -> dict:
    return {"id": id, "text": text, "kind": "impression", "state": "raised",
            "outcome": None, "session_id": None, "asked_at": "2026-09-20",
            "evidence": [{"kind": "event", "id": str(e)} for e in evidence],
            "pushback": None, "case_report_card": card}


DISTANCE = guess("i1", "It looks to me as if twice you stopped being in touch with your "
                 "mother within months of a worry about her.", (41, 42, 43))
OWN = guess("i2", "My guess is that your part has been to stay away when things with "
            "your mother get tense.", (41, 43), "own_part")
ASKED = {"id": "q1", "text": "What do you think your own part was?", "kind": "thought",
         "state": "asked", "outcome": None, "session_id": None, "asked_at": "2026-09-20",
         "case_report_card": "own_part"}


def recorded(coach, *questions) -> None:
    coach.record(people=[dict(MOTHER)], events=EVENTS)
    diagram = coach.user.free_diagram
    data = diagramjson.loads(diagram.data)
    data["questions"] = list(questions)
    diagram.data = diagramjson.dumps(data)
    db.session.commit()


def carded(turn: list[dict], tools, card: str) -> list[dict]:
    return [
        e for e in turn
        if e["type"] == TurnEventKind.ToolCall
        and e["name"] in tools
        and e["args"].get("case_report_card") == card
    ]


def stored(coach) -> dict:
    db.session.expire_all()
    return {q["id"]: q for q in coach.user.free_diagram.get_diagram_data().questions}


@passes(2, of=3)
def test_asked_for_its_main_guess_the_coach_puts_one_on_the_card(coach):
    # R-0709
    recorded(coach, DISTANCE)
    turn = coach.turn("If you had to sum it up, what is your main guess about what is going on with me?")
    assert carded(turn, NOTES, "main_guess"), [e.get("name") for e in turn]


@passes(2, of=3)
def test_asked_about_their_part_the_coach_infers_it_and_asks_what_they_think(coach):
    # R-0708
    recorded(coach, DISTANCE)
    turn = coach.turn("Looking at all this, what do you think my own part in it has been?")
    assert (bool(carded(turn, NOTES, "own_part")), bool(carded(turn, ASKS, "own_part"))) == (
        True,
        True,
    ), [(e.get("name"), e.get("args")) for e in turn if e["type"] == TurnEventKind.ToolCall]


@passes(2, of=3)
def test_their_answer_about_their_own_part_is_kept_as_their_view(coach):
    # R-0708
    recorded(coach, DISTANCE, OWN, ASKED)
    coach.turn("Honestly, I think I go quiet and stay away instead of telling her what I need.")
    answered = stored(coach)["q1"]
    assert (answered["outcome"], bool(answered.get("answer"))) == ("answered", True), answered


AIM = {"id": 44, "kind": "noted", "person": 1, "dateTime": "2026-09-01",
       "title": "Working on visiting more", "description": "Said she is working on visiting her mother more",
       "dateCertainty": "approximate"}


@passes(2, of=3)
def test_what_to_work_on_rests_first_on_where_they_said_what_they_are_working_on(coach):
    # R-0707
    coach.record(people=[dict(MOTHER)], events=[*EVENTS, AIM])
    turn = coach.turn("So what do you think I should work on, and what should I expect when I do?")
    marked = carded(turn, (ToolName.AddImpression,), "work_on")
    assert marked and marked[0]["args"]["evidence"][0] == {"kind": "event", "id": "44"}, marked


MAIN = guess("i3", "My guess is that when your mother is unwell you keep your distance from her, "
             "and your sleep goes first.", (40, 42, 43), "main_guess")
OTHERS = [
    guess("i4", "Your sleep went before you stopped calling your mother in 2005.", (40, 41)),
    guess("i5", "You stopped visiting your mother within a year of her time in hospital.", (42, 43)),
    guess("i6", "Twice the distance from your mother came in the same years as trouble of your own.", (40, 41, 43)),
    guess("i7", "Your mother was in hospital the year before you stopped visiting.", (42, 43)),
]


@passes(2, of=3)
def test_the_coachs_guess_card_holds_only_the_parts_that_matter_most(coach):
    # R-0732
    recorded(coach, DISTANCE, MAIN, *OTHERS)
    coach.turn("Of everything you have noticed about me, which parts matter most for me to look at?")
    marked = [i for i, q in stored(coach).items() if q.get("case_report_card") == "coach_guess"]
    assert 1 <= len(marked) <= 2 and "i3" not in marked, marked


OWEN = {"id": 20, "name": "Owen", "last_name": "Reyes", "gender": "male"}
WED = {"id": 21, "person_a": 1, "person_b": 20, "married": True}
PARENTS_WED = {"id": 50, "kind": "married", "person": 2, "spouse": 3, "dateTime": "1981-06-01",
               "dateCertainty": "certain"}
COUPLE = [
    {"id": 51, "kind": "bonded", "person": 1, "spouse": 20, "dateTime": "2006-05-01", "dateCertainty": "approximate"},
    {"id": 52, "kind": "married", "person": 1, "spouse": 20, "dateTime": "2009-09-12", "dateCertainty": "certain"},
    shift(53, "2010-03-01", 1, "Stopped calling her mother", relationship="distance", relationshipTargets=[2]),
    shift(54, "2010-08-01", 20, "Visited his brother every weekend", relationship="toward"),
]


def written(coach, *said) -> dict[str, dict]:
    """Each card's newest entry after the turns said and one refresh."""
    for statement in said:
        coach.turn(statement)
    response = coach.web.post("/app/case-report-rewrites", headers={"X-CSRFToken": coach.token})
    assert response.status_code == 202, response.get_data(as_text=True)
    assert coach.web.get(f"/app/case-report-rewrites/{response.get_json()['id']}").get_json()["state"] == "done"
    return {q["case_report_card"]: q for q in stored(coach).values() if q.get("case_report_card")}


def refreshed(coach, said: str) -> dict | None:
    return written(coach, said).get("couple")


@passes(2, of=3)
def test_a_refresh_writes_the_couple_card_on_the_persons_own_couple_not_their_parents(coach):
    # R-0850
    # pass: the couple card rests on Wren and Owen's own events and never on her parents' wedding
    coach.record(people=[OWEN], pair_bonds=[WED], events=[PARENTS_WED, *COUPLE])
    card = refreshed(coach, "Owen and I met in 2006 and married three years later; after that I called my mother less.")
    rests = {str(e["id"]) for e in (card or {}).get("evidence", []) if e["kind"] == "event"}
    assert card and rests & {"51", "52", "53", "54"} and "50" not in rests, card


@passes(2, of=3)
def test_with_no_partner_on_the_diagram_the_couple_card_says_what_it_still_needs(coach):
    # R-0850
    # pass: the couple card is the one line saying there is not enough in the diagram yet
    coach.record(events=[PARENTS_WED])
    card = refreshed(coach, "I've been thinking about my family a lot lately.")
    assert card and card["text"].startswith("Not enough in the diagram yet"), card


# The formulation family: Wren's mother Ada and Ada's sister Ivy, their parents
# Ruth and Walt; Ruth's illness and death with Ada taking her in, Wren's sleep
# going and her calls to Ada stopping; Walt's death with Wren cutting off from
# Ada and her sleep going again; Ada and Ivy close with Wren outside in 2010.
ADA = dict(MOTHER, parents=11)
HUGH = dict(FATHER, parents=12)
RUTH = {"id": 5, "name": "Ruth", "last_name": "Marsh", "gender": "female"}
WALT = {"id": 6, "name": "Walt", "last_name": "Marsh", "gender": "male"}
IVY = {"id": 7, "name": "Ivy", "last_name": "Marsh", "gender": "female", "parents": 11}
NAN = {"id": 8, "name": "Nan", "last_name": "Hale", "gender": "female"}
GRAND = [{"id": 11, "person_a": 5, "person_b": 6, "married": True}, {"id": 12, "person_a": 8, "person_b": None}]


def told(id, kind, date, person, title="", **fields) -> dict:
    return {"id": id, "kind": kind, "person": person, "dateTime": date, "title": title,
            "description": title, "dateCertainty": "approximate", **fields}


IVY_BORN = {"id": 59, "kind": "birth", "person": 5, "spouse": 6, "child": 7, "dateTime": "1955-03-01"}
ILLNESS = [
    told(60, "noted", "1997-11-01", 5, "Diagnosed with cancer"),
    told(61, "noted", "1998-03-01", 2, "Took her mother into her home"),
    told(62, "shift", "1998-06-01", 1, "Stopped sleeping well", symptom="up"),
    told(63, "shift", "1998-09-01", 1, "Stopped calling her mother", relationship="distance", relationshipTargets=[2]),
    told(64, "death", "1999-02-01", 5),
]
SIDED = told(65, "shift", "2010-03-01", 2, "Sided with her sister", relationship="inside",
             relationshipTargets=[7], relationshipTriangles=[1])
LOSS = [
    told(66, "death", "2014-10-01", 6),
    told(67, "shift", "2015-01-01", 1, "Cut off from her mother", relationship="cutoff", relationshipTargets=[2]),
    told(68, "shift", "2015-03-01", 1, "Could not sleep again", symptom="up"),
]
CLUSTERS = [
    Cluster(id="c1", title="Ruth's illness and death", summary="", name="Ruth's illness and death",
            eventIds=[60, 61, 62, 63, 64], source=ClusterSource.User, startDate="1997-11-01", endDate="1999-02-01"),
    Cluster(id="c2", title="Walt's death", summary="", name="Walt's death",
            eventIds=[66, 67, 68], source=ClusterSource.User, startDate="2014-10-01", endDate="2015-03-01"),
]
WORKING = told(69, "noted", "2026-09-01", 1, "Working on visiting her mother every month")
SLEEP = "I haven't slept well for years. It comes and goes."


def formulated(coach, *said, events=(), people=(), bonds=GRAND, clusters=CLUSTERS) -> dict[str, dict]:
    events = events or [IVY_BORN, *ILLNESS, SIDED, *LOSS]
    coach.record(people=[ADA, HUGH, RUTH, WALT, IVY, NAN, *people], pair_bonds=bonds, events=events)
    diagram = coach.user.free_diagram
    data = diagramjson.loads(diagram.data)
    data["clusters"] = [asdict(one) for one in clusters]
    diagram.data = diagramjson.dumps(data)
    db.session.commit()
    return written(coach, *(said or (SLEEP,)))


def words(card: dict | None) -> str:
    """A card's words outside the person's quoted ones."""
    return record.QUOTED.sub("", (card or {}).get("text") or "")


def statement(card: dict | None) -> str:
    """The card's own statement, its lines that open with no mark."""
    return " ".join(line for line in words(card).splitlines() if not MARK.match(line.lstrip()))


def marked(card: dict | None, mark: CardLine) -> list[str]:
    return [
        line for line in words(card).splitlines()
        if MARK.match(line.lstrip()) and line.lstrip().startswith(mark.value)
    ]


@passes(2, of=3)
def test_a_refresh_names_each_person_by_what_they_are_to_the_person(coach):
    # R-0850
    # pass: some card calls Ruth or Walt by what they are to Wren ("grandmother", "grandfather", "your mother's mother")
    cards = formulated(coach)
    said = " ".join(words(c) for c in cards.values()).lower()
    assert re.search(r"grand(mother|father)|mother's (mother|father)", said), said


@passes(2, of=3)
def test_the_executive_summary_is_the_trouble_then_the_pattern_on_its_first_answer(coach):
    # R-0850
    # pass: no first answer refused for its length, and the summary is three sentences at most, the first naming the sleep trouble
    main = formulated(coach)["main_guess"]
    assert not first_answer_refused("Executive Summary"), first_answer_refused("Executive Summary")
    sentences = [s for s in record.SENTENCE.split(" ".join(words(main).split())) if s]
    assert len(sentences) <= 3 and "sleep" in sentences[0].lower(), main["text"]


@passes(2, of=3)
def test_only_what_to_work_on_says_what_will_come(coach):
    # R-0850
    # pass: no first answer refused for a prediction, no other card predicts, and what to work on has a Prognosis line
    cards = formulated(coach)
    assert not first_answer_refused("says what will come"), first_answer_refused("says what will come")
    others = {c: FORETOLD.search(words(q)) for c, q in cards.items() if c != "work_on"}
    assert not any(others.values()) and marked(cards.get("work_on"), CardLine.Prognosis), cards


@passes(2, of=3)
def test_the_prognosis_says_in_plain_words_what_it_rests_on(coach):
    # R-0850
    # pass: the Prognosis line names its basis: the pile-up against how the family held up, one way or several, or fast or slow onset
    work = formulated(coach)["work_on"]
    basis = re.compile(r"piled|held up|holding up|one way|several|came on|built|slowly|quickly|fast|across the years", re.I)
    assert any(basis.search(line) for line in marked(work, CardLine.Prognosis)), work["text"]


@passes(2, of=3)
def test_the_coachs_guess_lays_the_people_out_in_time_order_with_the_time_between_them(coach):
    # R-0850, R-0864
    # pass: the statement gives two or more years in order and never says anything passed, flowed or was transmitted
    guess = statement(formulated(coach)["coach_guess"])
    years = [int(y) for y in re.findall(r"\b(?:19|20)\d\d\b", guess)]
    assert len(years) >= 2 and years == sorted(years), guess
    assert not re.search(r"\b(pass(ed|es)?|flow(ed|s)?|transmit(ted|s)?)\b", guess, re.I), guess


@passes(2, of=3)
def test_the_coachs_guess_names_the_nuclear_family_and_the_way_the_strain_was_held(coach):
    # R-0850
    # pass: the statement names Wren's mother and distance or cutoff
    guess = statement(formulated(coach)["coach_guess"]).lower()
    assert "mother" in guess and re.search(r"distance|cut ?off|cut off|pulled back|stopped calling", guess), guess


@passes(2, of=3)
def test_the_coachs_guess_names_the_triangle_the_events_mark(coach):
    # R-0850
    # pass: the coach's guess names Ivy, the third of the triangle the 2010 event marks
    guess = formulated(coach)["coach_guess"]
    assert "Ivy" in words(guess), guess["text"]


@passes(2, of=3)
def test_with_no_triangle_marked_the_coachs_guess_asks_about_one_on_its_open_line(coach):
    # R-0850
    # pass: with no inside or outside event, the statement names no triangle and the Open line asks who else was close to Ada or Wren
    guess = formulated(coach, events=[IVY_BORN, *ILLNESS, *LOSS])["coach_guess"]
    assert "triangle" not in statement(guess).lower(), guess["text"]
    asks = " ".join(marked(guess, CardLine.Open)).lower()
    assert re.search(r"ivy|close|side|between|your father|hugh", asks), guess["text"]


@passes(2, of=3)
def test_each_for_line_gives_the_changes_in_the_family_in_its_clusters_years(coach):
    # R-0850
    # pass: the For line on c1 names Ruth's illness or death and the For line on c2 Walt's death
    lines = marked(formulated(coach)["coach_guess"], CardLine.For)
    first = " ".join(line for line in lines if "c1" in line).lower()
    second = " ".join(line for line in lines if "c2" in line).lower()
    assert re.search(r"cancer|diagnos|ill|died|death", first) and re.search(r"died|death", second), lines


@passes(2, of=3)
def test_a_for_line_names_who_was_rearranged_around_the_opening(coach):
    # R-0850
    # pass: the For line on c1 says Ada took her mother in
    lines = marked(formulated(coach)["coach_guess"], CardLine.For)
    first = " ".join(line for line in lines if "c1" in line).lower()
    assert re.search(r"took .* in|into her home|moved in|lived with|care", first), lines


@passes(2, of=3)
def test_the_coachs_guess_says_whether_the_trouble_came_on_near_events_or_built_slowly(coach):
    # R-0850
    # pass: a line of the coach's guess says how the trouble came on
    guess = words(formulated(coach)["coach_guess"]).lower()
    assert re.search(r"came on|built|slowly|gradual|sudden|abrupt|quickly|within months", guess), guess


@passes(2, of=3)
def test_a_for_line_says_how_things_stood_after_its_cluster_never_what_the_trouble_did_for_anyone(coach):
    # R-0850, R-0864
    # pass: a For line says how things stood after (still, stayed, went on, from then), and no line gives the trouble a purpose
    guess = formulated(coach)["coach_guess"]
    after = " ".join(marked(guess, CardLine.For)).lower()
    assert re.search(r"still|stayed|went on|from then|after that|since|remained|continued", after), guess["text"]
    purpose = r"relie(f|ved)|pressure off|kept the peace|served|so that|to avoid|to cope"
    assert not re.search(purpose, words(guess), re.I), guess["text"]


@passes(2, of=3)
def test_when_the_person_says_when_the_trouble_is_worst_that_is_a_for_or_against_fact(coach):
    # R-0850, R-0864
    # pass: a For or Against line of the coach's guess speaks of the family gatherings
    guess = formulated(coach, SLEEP, "It's always worst after family gatherings at my mother's.")["coach_guess"]
    lines = marked(guess, CardLine.For) + marked(guess, CardLine.Against)
    assert any("gathering" in line.lower() for line in lines), guess["text"]


@passes(2, of=3)
def test_what_to_work_on_says_whether_its_focus_agrees_with_the_persons_aim(coach):
    # R-0850
    # pass: the statement of what to work on says whether it agrees with her aim of visiting her mother monthly
    work = formulated(coach, events=[IVY_BORN, *ILLNESS, SIDED, *LOSS, WORKING])["work_on"]
    assert re.search(r"agree|fits|in line|matches|same as|differ|goes beyond|alongside", statement(work), re.I), work["text"]


@passes(2, of=3)
def test_with_no_aim_said_what_to_work_on_has_no_aim_line(coach):
    # R-0850
    # pass: with nothing said about what she is working on, what to work on has no Aim line
    work = formulated(coach)["work_on"]
    assert not marked(work, CardLine.Aim), work["text"]


@passes(2, of=3)
def test_a_side_of_the_family_the_diagram_holds_little_of_reads_toward_cutoff(coach):
    # R-0850
    # pass: with every event on her father's side, a card says her mother's side is little known or cut off, as the app's guess
    hale = [
        told(70, "death", "1996-05-01", 8),
        told(71, "shift", "1997-01-01", 3, "Stopped going to work", functioning="down"),
        told(72, "shift", "1997-04-01", 1, "Stopped sleeping well", symptom="up"),
        told(73, "noted", "1999-08-01", 3, "Moved to the coast"),
    ]
    cards = formulated(coach, events=hale, clusters=())
    said = " ".join(words(c) for c in cards.values()).lower()
    assert re.search(r"mother's side|mother's family", said) and re.search(r"cut ?off|little|contact|nothing", said), said


@passes(2, of=3)
def test_no_card_explains_a_connection_beyond_its_dates(coach):
    # R-0850, R-0864
    # pass: no card says what one fact meant for, or did to, another
    cards = formulated(coach)
    beyond = r"which is why|so that|in order to|as a way to|meant that|to cope|to avoid|in response to"
    found = {c: re.search(beyond, words(q), re.I) for c, q in cards.items()}
    assert not any(found.values()), {c: q["text"] for c, q in cards.items()}


# Wren and Owen's couple with her mother staying away from the wedding, and
# Wren taking over as Owen stopped working.
STAYED_AWAY = told(55, "noted", "2009-09-12", 2, "Did not come to the wedding")
OVER = [
    told(56, "shift", "2011-02-01", 1, "Took over all the bills", relationship="overfunctioning", relationshipTargets=[20]),
    told(57, "shift", "2011-03-01", 20, "Stopped working", relationship="underfunctioning", relationshipTargets=[1]),
]


@passes(2, of=3)
def test_the_couple_card_says_who_stayed_away_from_the_wedding_when_the_events_show_it(coach):
    # R-0850
    # pass: the couple card speaks of the wedding and her mother not coming
    coach.record(people=[OWEN], pair_bonds=[WED], events=[*COUPLE, STAYED_AWAY])
    card = refreshed(coach, "Owen and I married in 2009.")
    assert re.search(r"wedding", words(card), re.I) and re.search(r"not come|didn't come|stayed away|was not there|wasn't there|absent", words(card), re.I), card


@passes(2, of=3)
def test_the_couple_card_says_one_partner_did_more_as_the_other_did_less_when_the_events_show_it(coach):
    # R-0850
    # pass: the couple card sets her taking over the bills beside Owen stopping work
    coach.record(people=[OWEN], pair_bonds=[WED], events=[*COUPLE, *OVER])
    card = refreshed(coach, "Owen and I married in 2009.")
    assert re.search(r"bills|took over", words(card), re.I) and re.search(r"stopped working|work", words(card), re.I), card
