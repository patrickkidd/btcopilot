"""Every dashboard query runs on Postgres against a small hand-built dataset,
and each first-wave measure returns the value its rule gives on that dataset,
worked out by hand from the rule rather than read off the SQL."""

import calendar
import datetime
import json
import math
import re
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from btcopilot import bowen, flow
from btcopilot.extensions import db
from btcopilot.tables import TABLES
from btcopilot.tests import grafanasql
from btcopilot.tests.fixtures import make_app
from btcopilot.tests.repo import REPO

pytestmark = pytest.mark.integration

GRAFANA = REPO / "deploy" / "grafana"
TODAY = datetime.datetime.utcnow()
START, END = TODAY - datetime.timedelta(days=90), TODAY + datetime.timedelta(days=1)
FIRST_WAVE = ("fd-people", "fd-coach", "fd-return", "fd-coachquality")
WEEK = 7 * 86400


def boards() -> dict[str, dict]:
    return {
        path.stem: json.loads(path.read_text())
        for path in sorted(GRAFANA.glob("*.json"))
    }


def queries() -> list[tuple[str, str, str]]:
    """(board, title, sql) for every panel target and annotation."""
    out = []
    for name, board in boards().items():
        for panel in board["panels"]:
            for target in panel.get("targets", []):
                if target.get("rawSql"):
                    out.append((name, panel["title"], target["rawSql"]))
        for note in board.get("annotations", {}).get("list", []):
            sql = note.get("rawQuery") or note.get("target", {}).get("rawSql")
            if sql:
                out.append((name, note["name"], sql))
    return out


def on(board: str):
    return pytest.mark.skipif(
        not (GRAFANA / f"{board}.json").exists(), reason=f"{board}.json not built yet"
    )


@pytest.fixture
def flask_app(tmp_path, postgres):
    app = make_app(
        SimpleNamespace(param={"SQLALCHEMY_DATABASE_URI": postgres}), tmp_path, TABLES
    )
    yield next(app)
    db.session.remove()
    db.engine.dispose()
    app.close()


@pytest.fixture
def ids(flask_app):
    return grafanasql.build(TODAY)


def run(sql: str, variables: dict | None = None) -> list[dict]:
    expanded = grafanasql.expand(sql, START, END, variables or {})
    return [
        dict(r._mapping)
        for r in db.session.execute(sa.text(expanded.replace(":", r"\:")))
    ]


def variables(board: dict) -> dict:
    """Each variable at every value it offers, as a board opened on "All" sends it."""
    out = {}
    for v in board.get("templating", {}).get("list", []):
        if v["type"] == "textbox":
            out[v["name"]] = v["query"]
            continue
        rows = run(v["query"] if isinstance(v["query"], str) else v["query"]["rawSql"])
        values = [r.get("__value", next(iter(r.values()))) for r in rows]
        out[v["name"]] = values or ["none"]
    return out


def panel(board: str, title: str) -> list[dict]:
    found = boards()[board]
    (sql,) = [
        t["rawSql"]
        for p in found["panels"]
        if p["title"] == title
        for t in p.get("targets", [])
    ]
    return run(sql, variables(found))


def row(rows: list[dict], label: str) -> dict:
    """The one row with a text cell matching `label` (a regex, any case)."""
    (found,) = [
        r
        for r in rows
        if any(isinstance(v, str) and re.search(label, v, re.I) for v in r.values())
    ]
    return found


def numbers(r: dict) -> list[float]:
    return [
        float(v)
        for v in r.values()
        if isinstance(v, (int, float)) or hasattr(v, "is_finite")
    ]


def test_every_panel_query_runs_on_postgres(ids):
    # R-0814, R-0517
    failed = []
    for board, title, sql in queries():
        try:
            with db.session.begin_nested():
                run(sql, variables(boards()[board]))
        except sa.exc.DBAPIError as e:
            failed.append(f"{board}: {title}: {str(e.orig).splitlines()[0]}")
    assert not failed, "\n".join(failed)


def test_every_first_wave_panel_returns_rows(ids):
    # R-0814
    empty = [
        f"{board}: {title}"
        for board, title, sql in queries()
        if board in FIRST_WAVE
        # a panel that holds back a prompt version under 30 people is empty here
        and not grafanasql.by_version(sql) and not run(sql, variables(boards()[board]))
    ]
    assert not empty, "\n".join(empty)


def test_the_shared_tables_run_and_leave_out_tests_and_scratch(ids):
    # R-0814
    sittings = run(
        grafanasql.fragments("select user_id, nth from sit order by started")
    )
    assert len(sittings) == 5
    msgs = run(grafanasql.fragments("select text from msg"))
    assert not [m for m in msgs if "who is Mary" in m["text"]]


def test_the_log_rebuilds_the_records_questions_people_and_events(ids):
    # R-0814
    rows = run(
        grafanasql.fragments(
            "select u.username, c.item_kind, count(distinct c.item_id) as n from cur c"
            " join diagrams dg on dg.id = c.diagram_id join users u on u.id = dg.user_id"
            " where not exists (select 1 from removed x where (x.diagram_id, x.item_kind,"
            " x.item_id) = (c.diagram_id, c.item_kind, c.item_id))"
            " group by 1, 2"
        )
    )
    held = {(r["username"], r["item_kind"]): r["n"] for r in rows}
    # Ann: Mary, Tom, Joan and herself (her parents link); Sam was removed
    assert held[(grafanasql.ANN, "person")] == 4
    assert held[(grafanasql.ANN, "event")] == 6
    assert held[(grafanasql.ANN, "pair_bond")] == 2
    assert held[(grafanasql.ANN, "question")] == 3
    assert held[(grafanasql.BO, "person")] == 1
    assert held[(grafanasql.BO, "event")] == 2
    kin = run(
        grafanasql.fragments("select person_id, link, side, gen from kin where gen > 0")
    )
    assert {(k["person_id"], k["side"]) for k in kin} == {
        ("2", "mother's line"),
        ("3", "father's line"),
    }


def test_b2_word_hits_equal_flow_objection(ids):
    # R-0814, R-0517
    hits = {
        r["statement_id"]
        for r in run(grafanasql.fragments("select statement_id from word_hit"))
    }
    msgs = run(grafanasql.fragments("select * from msg order by sitting_id, pos"))
    expected, before = set(), {}
    for m in msgs:
        if m["who"] == "coach":
            before[m["sitting_id"]] = m["text"]
        elif not m["text"].startswith("That doesn't fit: [[impression:"):
            if flow.objection(m["text"], before.get(m["sitting_id"], "")):
                expected.add(m["statement_id"])
    assert hits == expected
    assert len(hits) == 2


@on("fd-people")
def test_a1_topics_placed_count_the_sittings_each_topic_was_written_in(ids):
    # R-0814
    rows = panel(
        "fd-people", "Topics placed in the record: sittings and writes per topic"
    )
    # Partners: Ann's first sitting (bond, divorce, marriage) and third (Joan)
    assert 2 in numbers(row(rows, r"^Partners$"))
    # Deaths: Mary in Ann's second sitting, Rose in Bo's
    assert 2 in numbers(row(rows, r"^Deaths$"))
    # Health: the question on Mary's health, asked and closed in one sitting: 3 writes
    assert numbers(row(rows, r"^Health and symptoms$"))[:2] == [1, 3]
    # Who is who: a person added or removed in four sittings
    assert 4 in numbers(row(rows, r"^Who is who$"))


@on("fd-people")
def test_a3_most_named_people_count_the_sittings_naming_them(ids):
    # R-0814
    rows = panel("fd-people", "Most-named people per record")
    assert 3 in numbers(row(rows, r"^Tom$"))
    assert 2 in numbers(row(rows, r"^Mary$"))
    assert 1 in numbers(row(rows, r"^Rose$"))


@on("fd-people")
def test_b2_pushback_finds_each_objection_once(ids):
    # R-0814, R-0517
    rows = panel("fd-people", "Pushback: the objection phrases found")
    assert 1 in numbers(row(rows, r"i already told you"))
    assert 1 in numbers(row(rows, r"new date or name"))
    # the test account's "that's not right" is not counted
    assert not [r for r in rows if any(v == "that's not right" for v in r.values())]


@on("fd-people")
def test_d1_fact_questions_by_item_show_what_was_recorded_and_tapped(ids):
    # R-0814
    rows = panel(
        "fd-people",
        "Fact questions by item: what the coach recorded and what people tapped",
    )
    # Mary's health: asked once, said unknown
    assert numbers(row(rows, r"health"))[:1] == [1]
    assert numbers(row(rows, r"health")).count(1) >= 2
    # how Tom and Joan met: asked once, dismissed by Ann
    assert numbers(row(rows, r"^met$|when .* met|\bmet\b")).count(1) >= 2


@on("fd-people")
def test_d3_hand_corrections_count_a_removal_and_a_date(ids):
    # R-0814, R-0517
    rows = panel("fd-people", "What people correct, per 100 coach writes, by field")
    assert 1 in numbers(row(rows, r"^removed$"))
    assert 1 in numbers(row(rows, r"^dateTime$|date"))


@on("fd-people")
def test_e1_coverage_at_the_last_sitting(ids):
    # R-0814
    rows = panel("fd-people", "How far each record got, at the last sitting")
    # Ann's last turn: (4 known + 1 said unknown + 0 declined) of 10; Bo's: (2 + 0 + 1) of 4
    assert {0.5, 50.0} & set(numbers(row(rows, grafanasql.ANN)))
    assert {0.75, 75.0} & set(numbers(row(rows, grafanasql.BO)))


@on("fd-people")
def test_e4_a_look_then_talk_about_the_same_person_counts(ids):
    # R-0814
    rows = panel("fd-people", "Picture taps by name and by item kind")
    assert 1 in numbers(row(rows, r"^person_open$"))
    assert 1 in numbers(row(rows, r"^look$"))


@on("fd-coach")
def test_f1_fact_questions_the_coach_asked_by_item(ids):
    # R-0814
    rows = panel("fd-coach", "Fact questions the coach asked, by item")
    assert numbers(row(rows, r"health"))[:1] == [1]
    assert numbers(row(rows, r"\bmet\b"))[:1] == [1]


@on("fd-coach")
def test_f4_the_guess_that_did_not_fit(ids):
    # R-0814, R-0517
    rows = panel("fd-coach", "How the coach's guesses fared")
    assert 1 in numbers(row(rows, r"doesn.t fit"))


@on("fd-coach")
def test_g1_record_tools_count_committed_calls(ids):
    # R-0814, R-0517
    rows = panel("fd-coach", "Record tools per 100 coach turns, by tool")
    # edit_person: Mary, Tom, Ann's parents, Sam, Joan, Rose; one edit_event refused
    assert 6 in numbers(row(rows, r"^edit_person$"))
    assert 1 in numbers(row(rows, r"^edit_event$"))


@on("fd-coach")
def test_g3_a_failed_turn_is_followed_by_silence(ids):
    # R-0814, R-0517
    rows = panel(
        "fd-coach", "Faults ranked by the share of people who sent nothing more"
    )
    # Ann's last turn failed and she sent nothing more: 1 of 1
    assert {1.0, 100.0} & set(numbers(row(rows, r"turn_failed|failed")))


@on("fd-coach")
def test_h1_a_week_with_one_reply_has_its_words_as_median_and_90th(ids):
    # R-0814
    rows = panel("fd-coach", "Words per coach reply, weekly median and 90th percentile")
    # Cy's week holds one reply, "Hi, what brings you here?": 5 words
    assert [r for r in rows if numbers(r).count(5.0) >= 2]


@on("fd-return")
def test_c1_how_sittings_end(ids):
    # R-0814
    rows = panel("fd-return", "How sittings end")
    # Ann's three: asked, neither, a failed turn; Bo's wrote; Cy's asked
    assert 2 in numbers(row(rows, r"^asked"))
    assert 1 in numbers(row(rows, r"^wrote"))
    assert 1 in numbers(row(rows, r"^neither"))
    assert 1 in numbers(row(rows, r"^fault"))


@on("fd-return")
def test_c3_active_silent_left(ids):
    # R-0814
    rows = panel("fd-return", "Active, silent, left")
    # Bo spoke 3 days ago; Ann last spoke 35 days ago; Cy is no longer active
    for state in ("active", "silent", "left"):
        assert 1 in numbers(row(rows, rf"^{state}$"))


@on("fd-return")
def test_c3_days_between_sittings(ids):
    # R-0814
    rows = panel("fd-return", "Days between sittings")
    # Ann: 2 days, then 23
    assert 1 in numbers(row(rows, r"^1.3"))
    assert 1 in numbers(row(rows, r"^14.28"))


def week_of(days_ago: int) -> float:
    """The 7-day bucket $__timeGroup puts a message of that day at 10:00 in."""
    at = TODAY.replace(hour=10, minute=0, second=0, microsecond=0) - datetime.timedelta(
        days=days_ago
    )
    return math.floor(calendar.timegm(at.timetuple()) / WEEK) * WEEK


def coach_week(key: str, days_ago: int = 3) -> dict:
    """The all-versions row of a Bowen-board panel for the week of Bo's sitting."""
    board = boards()["fd-coachquality"]
    (p,) = [p for p in board["panels"] if p["title"] == bowen.BY_KEY[key].title]
    (coach,) = [t["rawSql"] for t in p["targets"] if t["refId"] == "A"]
    rows = run(coach, variables(board))
    (found,) = [
        r
        for r in rows
        if r["metric"] == "the coach, all versions" and r["time"] == week_of(days_ago)
    ]
    return found


def value(found: dict, key: str) -> float:
    return float(found[bowen.BY_KEY[key].unit])


# Bo's sitting, 158 coach words in 8 replies with 8 question sentences, the
# person's 47 words; every count below is worked by hand from the rule.


@on("fd-coachquality")
def test_q1_advice_counts_the_advice_sentence_and_not_the_idiom(ids):
    # R-0812
    found = coach_week("advice")
    # "You might want to ask your aunt" is advice; "You should know that" is not
    assert value(found, "advice") == pytest.approx(1000 * 1 / 158, abs=0.005)
    assert found["coach words"] == 158


@on("fd-coachquality")
def test_q2_agreement_counts_the_sentences_siding_about_a_relative(ids):
    # R-0809
    # "That was wrong of him ... your mother" and "no wonder ... your aunt"
    assert value(coach_week("agreement"), "agreement") == pytest.approx(
        1000 * 2 / 158, abs=0.005
    )


@on("fd-coachquality")
def test_q3_cause_words_are_counted_as_tokens(ids):
    # R-0804, R-0805
    # "so that is", "which is why", "it explains"
    assert value(coach_week("cause"), "cause") == pytest.approx(
        1000 * 3 / 158, abs=0.005
    )


@on("fd-coachquality")
def test_q4_two_years_side_by_side_asked_or_told(ids):
    # R-0805
    found = coach_week("side_by_side_asked")
    # 1999 and 2001 followed by a question; 1999 and 2001 followed by a lesson
    assert value(found, "side_by_side_asked") == pytest.approx(0.5, abs=0.0005)
    assert found["side-by-side sentences"] == 2


@on("fd-coachquality")
def test_q5_the_person_share_of_words(ids):
    # R-0003, R-0801
    found = coach_week("person_share")
    assert value(found, "person_share") == pytest.approx(47 / (47 + 158), abs=0.0005)
    assert found["coach replies"] == 8


@on("fd-coachquality")
def test_q6_question_marks_per_100_coach_words(ids):
    # R-0436
    assert value(coach_week("question_marks"), "question_marks") == pytest.approx(
        100 * 8 / 158, abs=0.005
    )


@on("fd-coachquality")
def test_q7_why_questions_per_100_question_sentences(ids):
    # R-0806
    found = coach_week("why")
    # "Why do you think she kept quiet?"; "which is why I ask" is a statement
    assert value(found, "why") == pytest.approx(100 * 1 / 8, abs=0.005)
    assert found["coach question sentences"] == 8


@on("fd-coachquality")
def test_q8_feeling_questions_per_100_question_sentences(ids):
    # R-0807
    # "How did that feel for you?"; "no wonder you felt alone" is a statement
    assert value(coach_week("feeling"), "feeling") == pytest.approx(
        100 * 1 / 8, abs=0.005
    )


@on("fd-coachquality")
def test_q9_teaching_sentences_per_1000_words(ids):
    # R-0810
    # "In family systems, this is called a cutoff"
    assert value(coach_week("teaching"), "teaching") == pytest.approx(
        1000 * 1 / 158, abs=0.005
    )


@on("fd-coachquality")
def test_q10_widening_questions_name_someone_the_last_three_messages_did_not(ids):
    # R-0801, R-0618
    # the aunt, Rose by her record name, the mother; Rose in the first reply was just named
    assert value(coach_week("widening"), "widening") == pytest.approx(
        100 * 3 / 8, abs=0.005
    )


@on("fd-coachquality")
def test_q11_date_questions_per_100_question_sentences(ids):
    # R-0686, R-0618
    # how old, how long after, when did, how many years
    assert value(coach_week("date_asked"), "date_asked") == pytest.approx(
        100 * 4 / 8, abs=0.005
    )


@on("fd-coachquality")
def test_q12_heavy_disclosures_met_with_comfort_or_advice(ids):
    # R-0807, R-0812, R-0810
    found = coach_week("comfort_after_blow")
    # four deaths told; the praise after "Hal killed himself" and the advice after the date
    assert value(found, "comfort_after_blow") == pytest.approx(0.5, abs=0.0005)
    assert found["heavy disclosures"] == 4


@on("fd-coachquality")
def test_q13_praise_sentences_per_1000_words(ids):
    # R-0810
    # "you're doing great" and "Well done"
    assert value(coach_week("praise"), "praise") == pytest.approx(
        1000 * 2 / 158, abs=0.005
    )


@on("fd-coachquality")
def test_q14_plain_words_for_death_over_euphemisms(ids):
    # R-0810, R-0737
    found = coach_week("plain_words")
    # died, died; "after she was gone"; "lost both of them" is not a euphemism by the rule
    assert value(found, "plain_words") == pytest.approx(2 / 3, abs=0.0005)
    assert found["death words"] == 3


@on("fd-coachquality")
def test_bowen_constant_lines_span_the_range_at_the_module_value(ids):
    # R-0810, R-0814
    board = boards()["fd-coachquality"]
    for figure in bowen.FIGURES:
        (p,) = [p for p in board["panels"] if p["title"] == figure.title]
        (constant,) = [t["rawSql"] for t in p["targets"] if t["refId"] == "B"]
        rows = run(constant, variables(board))
        assert [float(r[figure.unit]) for r in rows] == [figure.value, figure.value]
        assert {r["metric"] for r in rows} == {bowen.LEGEND}


@on("fd-coachquality")
def test_never_panels_read_zero_in_the_weeks_without_the_fault(ids):
    # R-0812, R-0809
    for key in ("advice", "agreement", "praise"):
        found = coach_week(key, days_ago=20)  # Cy's week: "Hi, what brings you here?"
        assert value(found, key) == 0


@on("fd-return")
def test_i1_from_invitation_to_second_sitting(ids):
    # R-0814
    rows = panel("fd-return", "From invitation to second sitting")
    # used 3 (Ann, Bo, Cy; the unused and the test invitation left out),
    # a first message 3, a first write 2 (Ann, Bo), a second sitting 1 (Ann)
    found = sorted((n for r in rows for n in numbers(r)), reverse=True)
    assert found[:4] == [3, 3, 2, 1]


SAMPLES = (
    "you’re doing great",
    "I don’t know 'why' anymore.",
    "How did that feel for you",
    "Well, so Rose, was she there",
    "That was hard.",
    "Okay. What happened next?",
)


def test_the_bowen_sql_counts_words_and_questions_the_way_flow_does(ids):
    # R-0810, R-0814
    for text in SAMPLES:
        literal = bowen.sql(text)
        (r,) = run(
            f"select {bowen.words(literal)} as words, {bowen.is_question(literal)} as q"
        )
        assert (r["words"], r["q"]) == (
            len(flow.words(text)),
            flow.is_question(text),
        ), text
    (r,) = run(
        f"select {bowen.words(bowen.unchip(bowen.sql('[[person:2|Rose]] left')))} as n"
    )
    assert r["n"] == 2
