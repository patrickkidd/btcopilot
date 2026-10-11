"""The desktop file import's four model passes, on fictional families: the
coding pass reads what the file's author wrote, the merge pass judges who and
what the diagram already holds, cluster detection sees the file's tags as a
hint, and the coach writes and asks after an import. Invented names only; no
real diagram is involved.

The coding and merge passes and the grouping are side calls the app makes to
its cheap structured model. Here each goes through Claude Code (`claude -p`
with the answer's JSON schema), as the grouping cases in test_clusters.py do:
the coding and merge passes on LIVE_IMPORT_MODEL, by default Haiku, the model
the rulings name for them; the grouping on that file's own model. Each call's
cost as Claude Code reports it is printed. The coach cases run as every coach
case here does (README.md).
"""

import json
import os
import re
import subprocess
import tempfile
from decimal import Decimal

from btcopilot import fdcoding, fdimport, fdmerge, fdnotice, record
from btcopilot.clusters import ClusterError, detect_clusters
from btcopilot.fdnotice import Summary
from btcopilot.models import Author
from btcopilot.schema import (
    DiagramData,
    EventKind,
    ItemKind,
    NotedFact,
    QuestionState,
    RelationshipKind,
    VariableShift,
    from_dict,
)
from btcopilot.tests.live.checks import questions
from btcopilot.tests.live.conftest import ME
from btcopilot.tests.live.criterion import Broken, passes
from btcopilot.tests.live.test_clusters import SYSTEM, TIMEOUT, ask, spent
from btcopilot.tests.live.test_structurefirst import EARLIER, EVENTS, kept, questions_of
from btcopilot.tests.test_fdnotice import _held

MODEL = os.environ.get("LIVE_IMPORT_MODEL", "haiku")


def structured(prompt: str, response_format, schema: dict, limit: int):
    """One answer from Claude Code, in the dataclass the pass asks for, the way
    the app's side-call model gives it."""
    env = dict(os.environ, CLAUDE_CODE_MAX_OUTPUT_TOKENS=str(limit))
    with tempfile.TemporaryDirectory() as cwd:
        ran = subprocess.run(
            [
                "claude",
                "-p",
                "--output-format",
                "json",
                "--model",
                MODEL,
                "--system-prompt",
                SYSTEM,
                "--tools",
                "",
                "--max-turns",
                "3",
                "--setting-sources",
                "",
                "--strict-mcp-config",
                "--no-session-persistence",
                "--json-schema",
                json.dumps(schema),
            ],
            input=prompt,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=TIMEOUT,
        )
    if ran.returncode and not ran.stdout.strip():
        raise RuntimeError(f"claude -p failed: {ran.stderr.strip()[:500]}")
    result = json.loads(ran.stdout)
    if result.get("is_error"):
        raise RuntimeError(
            f"claude -p failed: {result.get('subtype')} {result.get('result')}"
        )
    spent.append(Decimal(str(result.get("total_cost_usd") or 0)))
    print(f"  {MODEL}: ${spent[-1]:.4f}, {sum(spent):.4f} so far")
    return from_dict(
        response_format, result.get("structured_output") or json.loads(result["result"])
    )


# The coding pass: Ruth's file. Two shifts the author described and never
# coded, one they coded by hand, and a note holding a clinician's guess beside
# a dated happening to her brother.
RUTH, LEW, IDA, ABE = 1, 2, 3, 4
DRINKING, MOVED, HEART = 20, 21, 22
MOSS = {
    "people": [
        {
            "id": RUTH,
            "name": "Ruth",
            "last_name": "Moss",
            "gender": "female",
            "parents": 10,
            "notes": (
                "Probably a cutoff from her mother's side. In March 1979 her brother "
                "Abe was hospitalized after a car accident on the Seward Highway."
            ),
        },
        {"id": LEW, "name": "Lew", "last_name": "Moss", "gender": "male"},
        {"id": IDA, "name": "Ida", "last_name": "Moss", "gender": "female"},
        {
            "id": ABE,
            "name": "Abe",
            "last_name": "Moss",
            "gender": "male",
            "parents": 10,
        },
    ],
    "pair_bonds": [{"id": 10, "person_a": LEW, "person_b": IDA, "married": True}],
    "events": [
        {
            "id": DRINKING,
            "kind": "shift",
            "person": RUTH,
            "dateTime": "1998-04-01",
            "dateCertainty": "approximate",
            "description": "Started drinking every night and missed work most Mondays",
        },
        {
            "id": MOVED,
            "kind": "shift",
            "person": RUTH,
            "dateTime": "2002-09-01",
            "dateCertainty": "approximate",
            "description": "Moved to Juneau",
        },
        {
            "id": HEART,
            "kind": "shift",
            "person": LEW,
            "dateTime": "2001-06-01",
            "dateCertainty": "certain",
            "symptom": "up",
            "description": "Heart attack; retired early from the railroad",
        },
    ],
}


@passes(2, of=3)
def test_the_coding_pass_codes_plain_words_keeps_hand_coding_and_reads_no_guess_as_fact():
    # R-0860, R-0868, R-0859, R-0364
    data, decisions = fdcoding.code(MOSS, structured)
    for decision in decisions:
        print(
            f"  {decision.item} {decision.field} {decision.after!r}: {decision.reason}"
        )
    events = {e["id"]: e for e in data["events"]}
    assert (events[DRINKING]["kind"], events[DRINKING].get("symptom")) == (
        EventKind.Shift.value,
        VariableShift.Up,
    ), events[DRINKING]
    assert (events[MOVED]["kind"], events[MOVED].get("item")) == (
        EventKind.Noted.value,
        NotedFact.Places,
    ), events[MOVED]
    assert (events[HEART]["kind"], events[HEART]["symptom"]) == (
        EventKind.Shift.value,
        VariableShift.Up,
    ), events[HEART]
    added = [e for eid, e in events.items() if eid not in (DRINKING, MOVED, HEART)]
    assert added and all(
        e["person"] == ABE and (e.get("dateTime") or "").startswith("1979-03")
        for e in added
    ), added
    assert not [
        e
        for e in data["events"]
        if e.get("relationship") == RelationshipKind.Cutoff.value
    ]


# The merge pass: Wren's diagram from conversation, and her old desktop file.
# Her brother is Kit in the diagram, born about 1982, and Christopher in the
# file, born 1982. The file holds two sisters named Nell: one who died at four
# months in 1979, and the Nell born 1988 whose son the diagram knows. One day
# in 2019 the diagram holds her panic attacks and the file holds them in other
# words, beside a car accident the same day.
KIT, NELL = 4, 5
CHRISTOPHER, INFANT = 4, 5


def born(id, child, day, certainty="certain", **parents) -> dict:
    return {
        "id": id,
        "kind": EventKind.Birth.value,
        "child": child,
        "dateTime": day,
        "dateCertainty": certainty,
        **parents,
    }


def shift(id, day, **more) -> dict:
    return {
        "id": id,
        "kind": EventKind.Shift.value,
        "person": 1,
        "dateTime": day,
        "dateCertainty": "certain",
        **more,
    }


HALES = {"person": 2, "spouse": 3}
DIAGRAM = {
    "people": [
        {
            "id": 1,
            "name": "Wren",
            "last_name": "Hale",
            "gender": "female",
            "parents": 10,
            "primary": True,
        },
        {"id": 2, "name": "Ada", "gender": "female"},
        {"id": 3, "name": "Hugh", "gender": "male"},
        {"id": KIT, "name": "Kit", "gender": "male", "parents": 10},
        {"id": NELL, "name": "Nell", "gender": "female", "parents": 10},
        {"id": 6, "name": "Theo", "gender": "male"},
    ],
    "pair_bonds": [{"id": 10, "person_a": 2, "person_b": 3, "married": True}],
    "events": [
        born(30, 1, "1985-04-12", **HALES),
        born(31, KIT, "1982-01-01", "approximate", **HALES),
        born(32, 6, "2015-01-01", "approximate", person=NELL),
        shift(
            33,
            "2019-03-01",
            symptom="up",
            title="Panic attacks",
            description="Panic attacks started at work",
        ),
    ],
    "questions": [],
    "lastItemId": 33,
}
FILE = {
    "people": [
        {
            "id": 1,
            "name": "Wren",
            "last_name": "Hale",
            "gender": "female",
            "parents": 10,
            "primary": True,
        },
        {"id": 2, "name": "Ada", "last_name": "Hale", "gender": "female"},
        {"id": 3, "name": "Hugh", "last_name": "Hale", "gender": "male"},
        {
            "id": CHRISTOPHER,
            "name": "Christopher",
            "last_name": "Hale",
            "gender": "male",
            "parents": 10,
        },
        {
            "id": INFANT,
            "name": "Nell",
            "last_name": "Hale",
            "gender": "female",
            "parents": 10,
        },
        {
            "id": 6,
            "name": "Nell",
            "last_name": "Hale",
            "gender": "female",
            "parents": 10,
        },
    ],
    "pair_bonds": [{"id": 10, "person_a": 2, "person_b": 3, "married": True}],
    "events": [
        born(20, 1, "1985-04-12", **HALES),
        born(21, CHRISTOPHER, "1982-07-09", **HALES),
        born(22, INFANT, "1979-02-01", **HALES),
        {
            "id": 23,
            "kind": EventKind.Death.value,
            "person": INFANT,
            "dateTime": "1979-06-20",
            "dateCertainty": "certain",
        },
        born(24, 6, "1988-05-05", **HALES),
        shift(
            25,
            "2019-03-01",
            anxiety="up",
            title="Anxious at the office",
            description="Began having panic attacks at the office",
        ),
        shift(
            26,
            "2019-03-01",
            functioning="down",
            title="Wrecked her car",
            description="Totaled her car on the Glenn Highway",
        ),
    ],
}


@passes(2, of=3)
def test_the_merge_joins_a_nickname_keeps_a_namesake_apart_and_joins_one_happening_told_twice():
    # R-0851, R-0853, R-0877
    data, decisions, held = fdmerge.merge(DIAGRAM, FILE, structured)
    for decision in decisions:
        print(
            f"  {decision.item} {decision.field} {decision.after!r}: {decision.reason}"
        )
    became = {
        d.item: d.after
        for d in decisions
        if d.item.startswith("person ") and not d.field
    }
    if became[f"person {INFANT}"] == f"person {NELL}":
        raise Broken("the Nell who died in 1979 was joined to the living Nell")
    assert became[f"person {CHRISTOPHER}"] == f"person {KIT}", became
    infant = became[f"person {INFANT}"].removeprefix("person ")
    assert not [q for q in held if q["item_id"] == infant], held
    that_day = sorted(
        e["description"]
        for e in data["events"]
        if e["kind"] == EventKind.Shift.value and e["dateTime"] == "2019-03-01"
    )
    assert that_day == [
        "Panic attacks started at work",
        "Totaled her car on the Glenn Highway",
    ], that_day


# The grouping: Hugh's first stroke in 2003, then a quiet stretch the app's
# rules do not bridge, then his second stroke, a son pulling away and his death
# in 2005 and 2006, all tagged by the person for the stroke. A second tag names
# his brother Ray on three ordinary events.
STROKE = "Dad's stroke"
RAY = "Uncle Ray"
FIRST_STROKE = {41, 42, 43}
SECOND_STROKE = {44, 45, 46}
RAYS = {51, 52, 53}


def tagged(id, day, person, kind, tag, **more) -> dict:
    return {
        "id": id,
        "kind": kind.value,
        "person": person,
        "dateTime": day,
        "dateCertainty": "certain",
        "tags": [tag],
        **more,
    }


SHIFT, NOTED = EventKind.Shift, EventKind.Noted
TAGGED = DiagramData(
    people=[
        {
            "id": 1,
            "name": "Wren",
            "last_name": "Hale",
            "gender": "female",
            "parents": 10,
            "primary": True,
        },
        {"id": 2, "name": "Ada", "last_name": "Hale", "gender": "female"},
        {"id": 3, "name": "Hugh", "last_name": "Hale", "gender": "male"},
        {"id": 4, "name": "Kit", "last_name": "Hale", "gender": "male", "parents": 10},
        {"id": 5, "name": "Ray", "last_name": "Hale", "gender": "male"},
    ],
    pair_bonds=[{"id": 10, "person_a": 2, "person_b": 3, "married": True}],
    events=[
        born(30, 1, "1985-04-12", **HALES),
        born(31, 4, "1982-07-09", **HALES),
        tagged(
            41,
            "2003-04-10",
            3,
            SHIFT,
            STROKE,
            symptom="up",
            title="Had a stroke",
            description="Had a stroke at work",
        ),
        tagged(
            42,
            "2003-08-01",
            2,
            SHIFT,
            STROKE,
            relationship="overfunctioning",
            relationshipTargets=[3],
            title="Took over everything",
            description="Quit her job",
        ),
        tagged(
            43,
            "2003-12-01",
            1,
            SHIFT,
            STROKE,
            anxiety="up",
            title="Could not sleep",
            description="Could not sleep for months",
        ),
        tagged(
            44,
            "2005-09-01",
            3,
            SHIFT,
            STROKE,
            symptom="up",
            title="Second stroke",
            description="A second stroke; moved to a nursing home",
        ),
        tagged(
            45,
            "2006-01-15",
            4,
            SHIFT,
            STROKE,
            relationship="distance",
            relationshipTargets=[2],
            title="Stopped visiting",
            description="Stopped coming home",
        ),
        tagged(46, "2006-06-01", 3, EventKind.Death, STROKE),
        tagged(
            51,
            "1998-12-24",
            5,
            NOTED,
            RAY,
            title="Came for Christmas",
            description="Came up for Christmas",
        ),
        tagged(
            52,
            "1999-07-01",
            5,
            NOTED,
            RAY,
            title="Lent money for a truck",
            description="Lent the family money for a truck",
        ),
        tagged(
            53,
            "2001-05-01",
            5,
            NOTED,
            RAY,
            item="work",
            title="Retired from the railroad",
            description="Retired from the railroad",
        ),
    ],
)


@passes(2, of=3)
def test_a_tag_on_a_period_of_difficulty_is_taken_up_and_a_tag_naming_a_person_is_not():
    # R-0858, R-0857
    try:
        result = detect_clusters(TAGGED, ask)
    except ClusterError as refused:
        raise AssertionError(f"refused twice: {refused}") from refused
    for cluster in result.clusters:
        print(f"  {cluster.eventIds} {cluster.name!r}: {cluster.reason}")
    assert [
        c
        for c in result.clusters
        if FIRST_STROKE & set(c.eventIds) and SECOND_STROKE & set(c.eventIds)
    ], "no period holds both strokes"
    assert not [
        c.name
        for c in result.clusters
        if len(RAYS & set(c.eventIds)) >= 2 or "Ray" in c.name
    ], "a period was made of the tag naming Ray"


# The coach after an import. Who-is-you: a new diagram from a file that marked
# both sisters as the one it is about. Own topic: Wren's diagram from earlier
# sittings, with two questions the merge left.
NELL_HALE = {
    "id": 4,
    "name": "Nell",
    "last_name": "Hale",
    "gender": "female",
    "parents": 10,
}
UNMARKED = {key: value for key, value in ME.items() if key != "primary"}
WHO = r"\b(which|who)\b[^?]*\byou\b|\bare you\b|\bis you\b"
NOT_SURE = "Hi. There's a lot in that file and I'm not sure where to begin."
BOSS = "My boss called me into her office today and I froze again. I couldn't get a word out."
BOSS_WORDS = r"\b(boss|office|froze|freez\w*|word|work|meeting|today)\b"
LEFT = r"\b(Christopher|Kit|Nell)\b"


def brought_in(coach, monkeypatch, *held) -> None:
    """The file written into the diagram as the import's own turn, with what
    it left to ask, and the coach's first message about it."""
    monkeypatch.setattr("btcopilot.push.send", lambda *args, **kwargs: None)
    diagram = coach.user.free_diagram
    turn = fdimport.TURN.format(diagram.id)
    if held:
        record.apply(
            diagram.id,
            [
                {
                    "item_kind": ItemKind.Question.value,
                    "item_id": q["id"],
                    "field": None,
                    "after": q,
                }
                for q in held
            ],
            author=Author.Pro,
            turn_id=turn,
            user_id=coach.user.id,
        )
    data = diagram.get_diagram_data()
    primaries = () if data.primary_person() else (ME["id"], NELL_HALE["id"])
    fdnotice.after_import(
        diagram.id,
        coach.user.id,
        Summary(
            turn,
            people=len(data.people),
            events=len(data.events),
            pair_bonds=len(data.pair_bonds),
            primaries=primaries,
        ),
    )


@passes(2, of=3)
def test_given_the_floor_after_an_import_the_coach_asks_which_person_is_them(
    coach, monkeypatch
):
    # R-0871, R-0878
    coach.record(people=[UNMARKED, NELL_HALE], events=EVENTS)
    brought_in(coach, monkeypatch)

    reply = coach.say(NOT_SURE)

    asked = questions(reply)
    assert asked and re.search(WHO, asked[0], re.I), reply
    who = [q for q in questions_of(coach) if re.search(WHO, q["text"], re.I)]
    assert [q["state"] for q in who] == [QuestionState.Asked], who


@passes(2, of=3)
def test_a_topic_the_person_brings_after_an_import_comes_before_its_questions(
    coach, monkeypatch
):
    # R-0815, R-0878, R-0852
    coach.record(
        people=[
            {"id": 4, "name": "Kit", "gender": "male", "parents": 10},
            {
                "id": 5,
                "name": "Christopher",
                "last_name": "Hale",
                "gender": "male",
                "parents": 10,
            },
            {"id": 6, "name": "Nell", "gender": "female", "parents": 10},
            {
                "id": 7,
                "name": "Nell",
                "last_name": "Hale",
                "gender": "female",
                "parents": 10,
            },
        ],
        events=EVENTS,
    )
    kept(coach, EARLIER)
    held = [
        _held("q-kit", 5, "Is Christopher Hale, born 1982, the Kit you've mentioned?"),
        _held("q-nell", 7, "Is Nell Hale, born 1979, the Nell you've mentioned?"),
    ]
    brought_in(coach, monkeypatch, *held)

    reply = coach.say(BOSS)

    asked = questions(reply)
    assert asked and re.search(BOSS_WORDS, asked[0], re.I), reply
    assert not [
        q for q in asked if re.search(LEFT, q) or re.search(WHO, q, re.I)
    ], reply
    states = {
        q["id"]: q["state"]
        for q in questions_of(coach)
        if q["id"] in ("q-kit", "q-nell")
    }
    assert states == {"q-kit": QuestionState.Held, "q-nell": QuestionState.Held}, states
