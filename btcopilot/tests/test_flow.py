import datetime

from btcopilot import flow
from btcopilot.flow import (
    Dawning,
    Edit,
    Fact,
    FactKind,
    Message,
    Pushback,
    Record,
    Return,
    Role,
)

T0 = datetime.datetime(2026, 3, 2, 18, 0)


def at(minutes=0, days=0):
    return T0 + datetime.timedelta(minutes=minutes, days=days)


def person(text, minutes=0, days=0, turn_id=None):
    return Message(Role.Person, text, at(minutes, days), turn_id)


def coach(text, minutes=0, days=0, turn_id=None, model="opus", prompt_version="p1"):
    return Message(Role.Coach, text, at(minutes, days), turn_id, model, prompt_version)


def test_sentences_and_questions():
    # R-0669
    said = flow.sentences("Mara moved in 2011. When did Ruth follow?\nTomas stayed.")
    assert said == ["Mara moved in 2011.", "When did Ruth follow?", "Tomas stayed."]
    assert flow.is_question("Well, when did your aunt leave Leeds.")
    assert flow.is_question("Tomas, where were you living then.")
    assert not flow.is_question("He was born in 1962.")


def test_sessions_split_at_sitting_gap():
    # R-0669
    messages = [person("hi", 0), coach("Hello.", 1), person("back", 0, days=1)]
    split = flow.sessions(messages)
    assert [len(s) for s in split] == [2, 1]


def test_feeling_questions():
    # R-0669, R-0787
    assert (
        flow.feeling_questions("How did you feel when Ruth left?", "Ruth left in 2011.")
        == 1
    )
    quoted = flow.feeling_questions(
        "You said you were angry that winter; when was that?", "I was so angry."
    )
    assert quoted == 0
    assert flow.feeling_questions("What was it like for you when she left?", "") == 1
    assert flow.feeling_questions("How did that sit with you?", "") == 1


def test_subjective():
    # R-0669, R-0787
    assert flow.subjective("I was devastated. It hurt for years.") == 1
    assert flow.subjective("When Dad left in 2009 I felt lost.") == 1 / 2
    assert flow.subjective("Tomas moved to Leeds. That was in March.", ["Tomas"]) == 0
    assert flow.subjective("Nell called on Sunday.", ["Nell"]) == 0
    assert flow.subjective("He was sad. I was sadder than anyone.") is None
    assert flow.subjective("Okay.") is None


def test_rows_subjectivity_after_a_feeling_question():
    # R-0669, R-0787
    rows = flow.rows(
        [
            coach("What happened next?", 0),
            person("Ruth left in 2011.", 1),
            coach("How did you feel when Ruth left?", 2),
            person("I was scared. Mostly it hurt.", 3),
            person("She moved to Leeds.", 4),
        ],
        Record(facts=(Fact(FactKind.Name, "Ruth", at(0)),)),
    )
    row = rows[("opus", "p1")]
    assert (row["subjective_after_feeling_q"], row["subjective_other"]) == (1, 0)


def test_why_questions():
    # R-0669, R-0786
    assert flow.why_questions("Why did your brother move to Leeds?", "He moved.") == 1
    assert flow.why_questions("What year did your brother move?", "He moved.") == 0
    assert flow.why_questions("When you asked 'why me', what did she say?", "") == 1
    assert flow.why_questions("How come she stopped calling?", "") == 1
    assert flow.why_questions("What made him leave?", "") == 1


def test_quoted_words_and_contractions():
    # R-0669
    assert flow.words("I'll say 'why me' and you're 'done'.") == [
        "i'll",
        "say",
        "why",
        "me",
        "and",
        "you're",
        "done",
    ]


def test_advice():
    # R-0669
    assert flow.advice("You should call your brother this week.") == 1
    assert flow.advice("When did you last speak with your brother?") == 0
    assert flow.advice("Did you try to call her?") == 0
    assert flow.advice("You should know I keep everything you say here.") == 0
    assert flow.advice("Maybe call your brother this week.") == 1
    assert flow.advice("You might want to talk to your mother.") == 1
    assert flow.advice("You could try writing it down.") == 1


def test_teaching():
    # R-0669
    assert (
        flow.teaching(
            "In most families the oldest takes over. When did your father die?"
        )
        == 1
    )
    assert flow.teaching("Does the theory say anything about that?") == 0
    assert flow.teaching("You lived on Bowen Street then.") == 0
    assert flow.teaching("Bowen saw this in many families.") == 1


def test_objection():
    # R-0669
    assert flow.objection("No, it was August 2007.", "So Ruth moved in 2006?")
    assert flow.objection("I already told you that.", "When did Ruth move?")
    assert not flow.objection("No.", "Did your parents divorce?")


def test_after_pushback():
    # R-0669
    edits = (Edit(7, "event", "dateTime", "2006", "2007"),)
    fixed = flow.after_pushback(
        coach("Got it, 2007.", turn_id=7), edits, {"2006"}, {"2007"}
    )
    assert fixed == {
        Pushback.RecordChanged: True,
        Pushback.Reasserted: False,
        Pushback.Argued: False,
    }
    argued = flow.after_pushback(
        coach("Actually it was 2006.", turn_id=8), edits, {"2006"}, {"2007"}
    )
    assert argued == {
        Pushback.RecordChanged: False,
        Pushback.Reasserted: True,
        Pushback.Argued: True,
    }


def test_specifics():
    # R-0669
    facts = (Fact(FactKind.Place, "Leeds", at(0)),)
    assert flow.specifics("What took Ruth to Leeds?", "", facts, at(5))
    assert flow.specifics(
        "You said the old farmhouse burned. When?",
        "the old farmhouse burned down",
        (),
        at(5),
    )
    assert not flow.specifics(
        "Tell me more about that.", "it was a hard year", facts, at(-5)
    )
    rose = (Fact(FactKind.Name, "Rose", at(0)),)
    assert flow.specifics("When did Rose start school?", "", rose, at(5))
    assert not flow.specifics("Prices rose that year; then what?", "", rose, at(5))


def test_shrinking():
    # R-0669
    lengths = [40, 35, 12, 6, 4]
    session = []
    for i, n in enumerate(lengths):
        session += [
            coach("And then?", i * 10),
            person(" ".join(["word"] * n), i * 10 + 2),
        ]
    found = flow.shrinking(session)
    assert found["slope"] < 0
    assert found["short"] == 2
    assert found["latency"] == 120
    steady = flow.shrinking([person("one two"), person("one two", 1)])
    assert steady["slope"] is None


def test_dawning():
    # R-0669
    assert flow.dawning("I never realised she moved the year he died.")[Dawning.Exact]
    assert flow.dawning("Oh, I just realized that was the same winter.")[Dawning.Stem]
    assert flow.dawning("Oh. I never saw it that way.")[Dawning.Exact]
    neither = flow.dawning("I don't realize what you mean.")
    assert neither == {Dawning.Exact: False, Dawning.Stem: False}


def test_agreement():
    # R-0669
    assert flow.agreement("No wonder your sister stopped calling.", []) == 1
    assert flow.agreement("You're right, 2011, not 2010.", []) == 0
    assert (
        flow.agreement(
            "I don't know whether Priya shouldn't have gone; she shouldn't have, perhaps.",
            ["Priya"],
        )
        == 0
    )
    assert flow.agreement("That was unfair of your mother.", []) == 1
    assert flow.agreement("Your father shouldn't have done that.", []) == 1
    assert flow.agreement("You're right, Will was there.", ["Will"]) == 1
    assert flow.agreement("You're right, it will be hard.", ["Will"]) == 0


def test_own_step():
    # R-0669, R-0783
    said = [
        person("Thanks."),
        person("I'll ask Aunt Ruth on Sunday when they moved.", 1, turn_id=4),
    ]
    assert flow.own_step(said, ["Ruth"], frozenset({4})) == (True, True)
    assert flow.own_step(said, ["Ruth"], frozenset()) == (True, False)
    assert flow.own_step([person("I'll think about it.")], ["Ruth"], frozenset()) == (
        False,
        False,
    )
    assert flow.own_step([person("I'll call my sister.")], [], frozenset())[0]
    assert flow.own_step([person("I'll probably visit Mark.")], ["Mark"], frozenset())[
        0
    ]
    for text in (
        "I'm going to bed, my husband is asleep.",
        "I want to mark the date down.",
        "I'll call it a night, then see my sister.",
    ):
        assert flow.own_step([person(text)], ["Mark"], frozenset()) == (False, False)


def test_coach_assigns():
    # R-0669, R-0783
    assert flow.coach_assigns(["You could ask your uncle when he left."], [])
    assert flow.coach_assigns(["Maybe ask your aunt."], [])
    assert not flow.coach_assigns(["What would you want to find out next?"], [])


def test_returned():
    # R-0669, R-0788
    starts = [at(0), at(days=3), at(days=9), at(days=20)]
    assert flow.returned(starts, at(days=40)) == {
        "week": Return.Yes,
        "month": Return.Yes,
        "fourth": True,
        "days": 20.0,
    }
    once = flow.returned([at(0)], at(days=10))
    assert (once["week"], once["month"], once["fourth"]) == (
        Return.No,
        Return.Unknown,
        False,
    )


def test_risk():
    # R-0669, R-0790, R-0797
    assert flow.risk("I can't go on like this.")
    assert not flow.risk("My father couldn't go on, he died by suicide in 2015.")
    assert flow.risk("Sometimes I think everyone would be better off without me.")


def test_paired_with_cause():
    # R-0669, R-0784
    events = (("moved", "Leeds"), ("grandmother", "died"))
    caused = flow.paired_with_cause(
        "Your move to Leeds happened because your grandmother died.", [], events
    )
    assert caused == 1
    assert (
        flow.paired_with_cause(
            "You moved to Leeds in 2011 and your grandmother died in 2012.",
            [2011, 2012],
            events,
        )
        == 0
    )
    assert (
        flow.paired_with_cause("That's why 2011 and 2012 matter.", [2011, 2012], ())
        == 1
    )
    set_off = flow.paired_with_cause(
        "The 1979 layoff set off the 1980 move.", [1979, 1980], ()
    )
    assert set_off == 1


def test_praise():
    # R-0669
    assert flow.praise("Well done getting that year from your aunt.") == 1
    assert flow.praise("You got the year from your aunt.") == 0
    assert flow.praise("You're doing so well with this.") == 1
    assert flow.praise("That's a brave thing to share.") == 1
    assert flow.praise("Don't worry about the exact year; roughly when?") == 0


def test_ends_question():
    # R-0669, R-0436
    assert flow.ends_question("Who was there?\n\n_(saved)_")
    assert flow.ends_question("Who was there?\n*Noted: Ruth, 2011.*")
    assert not flow.ends_question("Who was there? Tell me.")


def test_talk_shape():
    # R-0669, R-0436
    shape = flow.talk_shape(
        [
            person("one two three four five six"),
            coach("When was that?", 1),
            coach("Okay.", 2),
        ]
    )
    assert shape["person_share"] == 6 / 10
    assert shape["coach_words"] == 2
    assert shape["coach_ratio"] == (3 / 6 + 1 / 6) / 2
    assert shape["ends_question"] == 1
    assert flow.talk_shape([])["person_share"] is None


def thread():
    return [
        coach("Hello. What brings you here?", 0, turn_id=1),
        person(
            "My brother Tomas moved to Leeds in 2011 and stopped calling.", 2, turn_id=2
        ),
        coach(
            "How did you feel about Tomas leaving? You should call him.",
            3,
            turn_id=2,
            prompt_version="p2",
        ),
        person("No, it was 2012.", 5, turn_id=3),
        coach(
            "Got it, 2012. Who else was in Leeds then?",
            6,
            turn_id=3,
            prompt_version="p2",
        ),
        person("I'll ask my mother about it on Sunday.", 8, turn_id=4),
        coach(
            "When you do, what would you want to know?",
            9,
            turn_id=4,
            prompt_version="p2",
        ),
    ]


def record():
    return Record(
        facts=(
            Fact(FactKind.Name, "Tomas", at(2)),
            Fact(FactKind.Place, "Leeds", at(2)),
        ),
        edits=(Edit(3, "event", "dateTime", "2011", "2012"),),
        todo_turns=frozenset({4}),
    )


def test_rows_counts_only():
    # R-0669
    rows = flow.rows(thread(), record())
    assert all(
        not isinstance(v, str) or len(v) <= len(flow.RULES_VERSION)
        for r in rows.values()
        for v in r.values()
    )
    assert {r["rules_version"] for r in rows.values()} == {flow.RULES_VERSION}


def test_rows_split_by_model_and_prompt():
    # R-0669
    rows = flow.rows(thread(), record())
    first, second = rows[("opus", "p1")], rows[("opus", "p2")]
    assert (first["coach_messages"], first["person_messages"]) == (1, 1)
    assert (second["coach_messages"], second["person_messages"]) == (3, 2)
    assert (second["feeling_questions"], second["advice"]) == (1, 1)
    assert (second["objections"], second["record_changed"], second["reasserted"]) == (
        1,
        1,
        0,
    )
    assert (second["own_steps"], second["own_steps_stored"]) == (1, 1)
    assert first["feeling_questions"] == 0
    assert (first["subjective_after_feeling_q"], first["subjective_other"]) == (None, 0)
    assert (second["subjective_after_feeling_q"], second["subjective_other"]) == (0, None)


def test_account_row():
    # R-0669, R-0788
    messages = [coach("Hello.", 0), person("Hi.", 1), person("Back again.", 0, days=2)]
    row = flow.account_row(messages, at(days=40))
    assert (row["week"], row["month"], row["fourth"]) == (Return.Yes, Return.Yes, False)
    assert row["rules_version"] == flow.RULES_VERSION


def test_rules_version():
    # R-0669
    assert len(flow.RULES_VERSION) == 12
    assert flow.version(flow.FEELING) != flow.version(flow.FEELING + ("lonely",))
