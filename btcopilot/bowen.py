"""Bowen's own numbers from his ten taped interviews, one entry per panel of
the board "How the coach compares to Bowen" (deploy/grafana/fd-coachquality.json):
the question the panel asks, the figure, its unit, the rule in one sentence,
the word lists the rule uses, the base it was counted on and where it comes
from. Beside them, the word lists of the Bowen coding rulebook that
btcopilot.flow does not hold, and the one way a list becomes the regex a
panel pastes into its SQL, so the board cannot drift from the lists.

Every figure was computed by the job 013 and job 017 scripts over the counted
interviewer rows of the ten coded tables (471 turns, 4953 words, 340 question
marks; TOTALS.md in the private corpus, research/conversation-flow/bowen-coding),
with the same list the panel applies to the coach. No model judged a number.
"""

import dataclasses
import re

from btcopilot import flow
from btcopilot.proactive import CAUSES

TURNS, WORDS, QUESTION_MARKS = 471, 4953, 340
TEN = "all ten files: 471 counted interviewer turns, 4953 words (RULES 0.3), 340 question marks"
LEGEND = f"Bowen, {TURNS} turns on ten tapes"

# RULES.md 1.8(a), the DATE-ASK cues, with MEASURE-FIXES A3 ("when" only before
# an auxiliary or as the last word before "?") and C5 (durations and counts).
DATE_ASK = (
    "what year",
    "which year",
    "what time",
    "how old",
    "what age",
    "how long",
    "how long ago",
    "how many years",
    "before or after",
    "the year",
    "the month",
    "since when",
    "how much time",
    "how many times",
    "how many hours",
    "how many days",
    "how many weeks",
    "how many months",
)
WHEN_AUXILIARY = (
    "when did",
    "when was",
    "when were",
    "when's",
    "when do",
    "when would",
)
# "when" as the last word of a question sentence (A3 ii), on the lower-cased sentence.
WHEN_LAST_SQL = r"(?<![a-z0-9'])when[^a-z0-9]*$"

# RULES.md 3.5, the HEAVY words of a heavy disclosure, verbatim.
HEAVY = (
    tuple(
        """died death dead killed suicide cancer tumor psychotic hospitalized breakdown beat
    beats beating hit slapped violent violence abuse raped attacked knife knifepoint affair
    cheated divorce""".split()
    )
    + (
        "kill herself",
        "kill himself",
        "kill myself",
        "left him",
        "left her",
        "never spoke",
        "don't speak",
        "cut off",
        "haven't seen",
        "ran away",
    )
)
# MEASURE-FIXES A9: the words and inflections the tapes used that 3.5 lacks.
HEAVY_ADDED = (
    "adultery",
    "unfaithful",
    "deceased",
    "stroke",
    "heart attack",
    "overdose",
    "methadone",
    "institution",
    "hitting",
    "beatings",
    "beat up",
    "abused",
    "slapping",
    "slap",
    "knives",
)
# RULES.md 0.9: two words match once the endings -s, -es, -ed, -ing, -'s, -er,
# -est are stripped; "-d" is added so "divorce" meets "divorced".
STEM_SUFFIX = "(?:s|es|d|ed|ing|'s|er|est)?"
HEAVY_WORDS = 250

# RULES.md 2.18, the plain words and the euphemisms for death, verbatim.
PLAIN = (
    "died",
    "die",
    "dead",
    "death",
    "dying",
    "cancer",
    "tumor",
    "suicide",
    "killed",
    "divorce",
    "divorced",
    "heart attack",
    "stroke",
)
EUPHEMISM = (
    "passed away",
    "passed on",
    "passed",
    "lost",
    "gone",
    "no longer with us",
    "departed",
)
# MEASURE-FIXES C4: "gone" and "passed" only with a person subject within three
# words before and none of on / to / through / out / by after; "lost" only before
# a kin word or a pronoun. The three guarded words leave the plain phrase list.
GUARDED = ("passed", "lost", "gone")
EUPHEMISM_PHRASES = tuple(p for p in EUPHEMISM if p not in GUARDED)
DEATH_SUBJECTS = ("he", "she", "they", "he's", "she's", "they're", "who")
NOT_AFTER_GONE = ("on", "to", "through", "out", "by", "the", "away", "into")
DETERMINERS = ("my", "your", "his", "her", "their", "our", "the", "a", "an")
OBJECT_PRONOUNS = ("him", "her", "them")

# "You should know / see / hear" is an idiom, not advice (flow.advises).
IDIOMS = tuple(f"you should {w}" for w in flow.IDIOM)
# A statement after a heavy disclosure that comforts, advises, praises or teaches.
TEACHING_ALL = flow.TEACHING + flow.TEACHING_PHRASES
# The crisis protocol's phrases (flow.PHRASES); a message that fires one is the
# protocol's, not a heavy disclosure (R-0810).
RISK_PATTERNS = tuple(p.pattern for p in flow.PHRASES)
# flow.YEAR with Postgres word boundaries; flow.DATED (a digit or a month name).
YEAR_SQL = r"\m(" + flow.YEAR.replace(r"\b", "") + r")\M"
MONTHS_TITLE = tuple(m.title() for m in flow.MONTHS)


def _escape(phrase: str) -> str:
    return re.sub(r"[^A-Za-z0-9' -]", lambda m: "\\" + m.group(), phrase)


def regex(phrases, suffix: str = "") -> str:
    """One Postgres regex that fires where flow.has fires for any phrase of the
    list: each phrase lower-cased with its quotes folded, on word boundaries."""
    body = "|".join(_escape(flow.norm(p)) for p in phrases)
    return f"(?<![a-z0-9'])(?:{body}){suffix}(?![a-z0-9'])"


def literal(phrases, suffix: str = "") -> str:
    """The regex as a SQL string literal, quotes doubled."""
    return "'" + regex(phrases, suffix).replace("'", "''") + "'"


def values(phrases) -> str:
    """The list as the rows of a SQL values table, one phrase a row, for a rule
    that tests phrase by phrase (a phrase the person's own message carries)."""
    return ",".join(
        "('" + _escape(flow.norm(p)).replace("'", "''") + "')" for p in phrases
    )


def risk_regex() -> str:
    """The 24 crisis phrases as one regex; Python's \\b is Postgres's \\y."""
    body = "|".join(RISK_PATTERNS).replace("\\b", "\\y")
    return f"(?<![a-z0-9'])(?:{body})(?![a-z0-9'])"


def dated_regex() -> str:
    return r"\d|(?<![A-Za-z0-9])(?:" + "|".join(MONTHS_TITLE) + r")(?![A-Za-z0-9])"


def gone_regex() -> str:
    subjects = "|".join(_escape(flow.norm(p)) for p in DEATH_SUBJECTS + flow.KIN)
    after = "|".join(NOT_AFTER_GONE)
    return (
        rf"(?<![a-z0-9'])(?:{subjects})(?:\s+[a-z0-9']+){{0,2}}\s+(?:gone|passed)"
        rf"(?![a-z0-9'])(?!\s+(?:{after})(?![a-z0-9']))"
    )


def lost_regex() -> str:
    kin = "|".join(_escape(flow.norm(p)) for p in flow.KIN)
    return (
        rf"(?<![a-z0-9'])lost\s+(?:(?:{'|'.join(DETERMINERS)})\s+)?(?:{kin})(?![a-z0-9'])"
        rf"|(?<![a-z0-9'])lost\s+(?:{'|'.join(OBJECT_PRONOUNS)})(?![a-z0-9'])"
    )


def sql(pattern: str) -> str:
    return "'" + pattern.replace("'", "''") + "'"


# Every list a panel pastes, by the name its figure cites: the regex or values
# literal the board must carry, so a test can hold the JSON to the lists.
LISTS = {
    "flow.ADVICE": literal(flow.ADVICE),
    "flow.IDIOM": literal(IDIOMS),
    "flow.AGREEMENT": literal(flow.AGREEMENT),
    "flow.HEDGED": literal(flow.HEDGED),
    "flow.KIN": literal(flow.KIN),
    "flow.KIN rows": values(flow.KIN),
    "flow.MONTHS": sql(dated_regex()),
    "proactive.CAUSES": literal(CAUSES),
    "flow.CONNECTIVES": literal(flow.CONNECTIVES),
    "flow.YEAR": sql(YEAR_SQL),
    "flow.WHY rows": values(flow.WHY),
    "flow.FEELING rows": values(flow.FEELING),
    "flow.TEACHING": literal(flow.TEACHING),
    "flow.TEACHING + flow.TEACHING_PHRASES": literal(TEACHING_ALL),
    "flow.PRAISE": literal(flow.PRAISE),
    "flow.PHRASES": sql(risk_regex()),
    "RULES 1.8(a) DATE_ASK": literal(DATE_ASK),
    "RULES 1.8(a) WHEN_AUXILIARY": literal(WHEN_AUXILIARY),
    "RULES 1.8(a) WHEN_LAST": sql(WHEN_LAST_SQL),
    "RULES 3.5 HEAVY": literal(HEAVY + HEAVY_ADDED, STEM_SUFFIX),
    "RULES 2.18 PLAIN": literal(PLAIN),
    "RULES 2.18 EUPHEMISM": literal(EUPHEMISM_PHRASES),
    "RULES 2.18 EUPHEMISM gone": sql(gone_regex()),
    "RULES 2.18 EUPHEMISM lost": sql(lost_regex()),
}


@dataclasses.dataclass(frozen=True)
class Figure:
    key: str
    title: str
    value: float
    unit: str
    rule: str
    lists: tuple[str, ...]
    base: str
    numerator: float
    denominator: float
    source: str


FIGURES = (
    Figure(
        "advice",
        "Does it give advice?",
        0.2,
        "per 1000 words",
        "Coach statement sentences carrying an advice phrase (you should know, see or "
        "hear is an idiom, not advice), per 1000 coach words.",
        ("flow.ADVICE", "flow.IDIOM"),
        TEN,
        1,
        WORDS,
        "TOTALS.md section 11, column adv (0 under RULES 1.7); scripts/job-020: one try to in a "
        "statement under flow.ADVICE",
    ),
    Figure(
        "agreement",
        "Does it side with the person about a relative?",
        0.0,
        "per 1000 words",
        "Coach sentences carrying an agreement phrase that also name a relative (a kin "
        "word or a name from the record), with no digit, month or hedge before it, "
        "per 1000 coach words.",
        ("flow.AGREEMENT", "flow.HEDGED", "flow.KIN", "flow.MONTHS"),
        TEN,
        0,
        WORDS,
        "TOTALS.md section 11, column agree; scripts/job-020 under flow.AGREEMENT (0)",
    ),
    Figure(
        "cause",
        "Does it say because?",
        1.21,
        "per 1000 words",
        "Cause words (because, led to, due to, that's why and the rest) in coach "
        "sentences, per 1000 coach words.",
        ("proactive.CAUSES", "flow.CONNECTIVES"),
        TEN,
        6,
        WORDS,
        "TOTALS.md section 11, column caus (6 under RULES 1.12); scripts/job-020: 6 under "
        "proactive.CAUSES + flow.CONNECTIVES (because 3, that's why, caused, triggered)",
    ),
    Figure(
        "side_by_side_asked",
        "When it puts two events side by side, does it ask or tell?",
        0.75,
        "share",
        "Of coach sentences naming two different years, the share that is a question "
        "or is followed at once by one.",
        ("flow.YEAR",),
        TEN,
        9,
        12,
        "TOTALS.md section 11, column sbs with q; COMPARE-KERR.md row M10; scripts/job-020: "
        "the same 9 of 12 under flow.is_question",
    ),
    Figure(
        "person_share",
        "Who does the talking?",
        0.82,
        "share",
        "The person's words over the person's and the coach's words together, chips "
        "reduced to their words and the taps left out.",
        (),
        TEN,
        23505,
        28552,
        "TOTALS.md section 4, family share (third-party words in the base); the two-party "
        "share, the coach rule's shape, is 0.826",
    ),
    Figure(
        "question_marks",
        "Does it mostly ask or tell?",
        6.86,
        "per 100 words",
        "Question marks in coach replies per 100 coach words.",
        (),
        TEN,
        QUESTION_MARKS,
        WORDS,
        "TOTALS.md sections 3 and 4; scripts/job-020: the literal ? count equals the q column",
    ),
    Figure(
        "why",
        "Does it ask why?",
        2.65,
        "per 100 questions",
        "Coach question sentences carrying why, how come or what made that the "
        "person's last message did not, per 100 coach question sentences.",
        ("flow.WHY rows",),
        TEN,
        9,
        QUESTION_MARKS,
        "TOTALS.md section 3, column why (10); scripts/job-020: 9 under flow.why_questions, "
        "which drops the one why handed back from the father's own",
    ),
    Figure(
        "feeling",
        "Does it ask how people felt?",
        0.59,
        "per 100 questions",
        "Coach question sentences carrying a feeling word the person's last message "
        "did not, per 100 coach question sentences.",
        ("flow.FEELING rows",),
        TEN,
        2,
        QUESTION_MARKS,
        "TOTALS.md section 3, question kinds, feel; scripts/job-020: 2 under flow.feeling_questions",
    ),
    Figure(
        "teaching",
        "Does it explain or teach?",
        0.0,
        "per 1000 words",
        "Coach sentences with no question mark carrying a teaching phrase not followed "
        "by a capitalised word, per 1000 coach words.",
        ("flow.TEACHING + flow.TEACHING_PHRASES",),
        TEN,
        0,
        WORDS,
        "TOTALS.md section 11, column teach (3 under RULES 1.7, none on flow.TEACHING); "
        "scripts/job-020: 0 under flow.teaching",
    ),
    Figure(
        "widening",
        "Does it keep other family members in the picture?",
        15.59,
        "per 100 questions",
        "Coach question sentences naming a kin word or a record person none of the "
        "person's last three messages named, per 100 coach question sentences.",
        ("flow.KIN rows",),
        TEN,
        53,
        QUESTION_MARKS,
        "TOTALS.md section 11, column widen q (RULES 2.19, with the synonym rows and no "
        "vocatives); scripts/job-020: 72 of 340 under the coach's literal matching",
    ),
    Figure(
        "date_asked",
        "Does it ask when things happened?",
        6.18,
        "per 100 questions",
        "Coach question sentences with a date cue (when did, what year, how old, how "
        "long, how many years and the rest), per 100 coach question sentences.",
        (
            "RULES 1.8(a) DATE_ASK",
            "RULES 1.8(a) WHEN_AUXILIARY",
            "RULES 1.8(a) WHEN_LAST",
        ),
        TEN,
        21,
        QUESTION_MARKS,
        "TOTALS.md section 3, question kinds, date; scripts/job-020: the same 21 under the "
        "DATE_ASK list with MEASURE-FIXES A3 and C5",
    ),
    Figure(
        "comfort_after_blow",
        "When the person tells of a death or a blow, does it ask or comfort?",
        0.0,
        "share",
        "Of person messages with a heavy word (a death, violence, an affair, a cutoff) "
        "or over 250 words that fire no crisis phrase, the share whose reply carries a "
        "feeling, advice, praise or teaching phrase.",
        (
            "RULES 3.5 HEAVY",
            "flow.PHRASES",
            "flow.FEELING rows",
            "flow.ADVICE",
            "flow.PRAISE",
            "flow.TEACHING",
        ),
        TEN,
        0,
        45,
        "TOTALS.md section 12, M13; scripts/job-020: 0 of 45 under the flow lists (44 once the "
        "one disclosure that fires a crisis phrase is left out)",
    ),
    Figure(
        "praise",
        "Does it praise or reassure?",
        0.0,
        "per 1000 words",
        "Coach sentences carrying a praise or reassurance phrase, per 1000 coach words.",
        ("flow.PRAISE",),
        TEN,
        0,
        WORDS,
        "TOTALS.md section 11, column praise; scripts/job-020: 0 under flow.PRAISE and under its "
        "union with RULES 2.17",
    ),
    Figure(
        "plain_words",
        "Does it use plain words for death?",
        1.0,
        "share",
        "Plain words for death and illness (died, dead, cancer, stroke) over plain "
        "words plus euphemisms (passed away, lost her, she is gone) in coach sentences.",
        (
            "RULES 2.18 PLAIN",
            "RULES 2.18 EUPHEMISM",
            "RULES 2.18 EUPHEMISM gone",
            "RULES 2.18 EUPHEMISM lost",
        ),
        TEN,
        13,
        13,
        "TOTALS.md section 11, column death p / e (13 turns); scripts/job-020: 14 of 14 words",
    ),
)
BY_KEY = {f.key: f for f in FIGURES}
