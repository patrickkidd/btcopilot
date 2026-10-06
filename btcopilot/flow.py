"""The conversational-flow measures (R-0669): fixed word rules over a thread's
messages and its stored record, so each one is proven on made-up replies and
counted on real threads with no model judging anything."""

import dataclasses
import datetime
import enum
import hashlib
import re
import statistics

from btcopilot.discussions import SITTING_GAP
from btcopilot.proactive import CAUSE, CAUSES


class Role(enum.StrEnum):
    Person = "person"
    Coach = "coach"


class FactKind(enum.StrEnum):
    Name = "name"
    Place = "place"
    Year = "year"


class Pushback(enum.StrEnum):
    RecordChanged = "record_changed"
    Reasserted = "reasserted"
    Argued = "argued"


class Dawning(enum.StrEnum):
    Exact = "exact"
    Stem = "stem"


class Return(enum.StrEnum):
    Yes = "yes"
    No = "no"
    Unknown = "unknown"


@dataclasses.dataclass(frozen=True)
class Message:
    role: Role
    text: str
    at: datetime.datetime
    turn_id: int | None = None
    model: str | None = None
    prompt_version: str | None = None


@dataclasses.dataclass(frozen=True)
class Fact:
    kind: FactKind
    value: str
    since: datetime.datetime


@dataclasses.dataclass(frozen=True)
class Edit:
    turn_id: int
    item_kind: str
    field: str | None
    before: object
    after: object


@dataclasses.dataclass(frozen=True)
class Record:
    facts: tuple[Fact, ...] = ()
    edits: tuple[Edit, ...] = ()
    todo_turns: frozenset[int] = frozenset()
    # Each event as the words that name it, in order of time.
    events: tuple[tuple[str, ...], ...] = ()


# measures.md, shared cue lists and M04, M12, M15, M32, M35, M37, M38, M49.
FEELING = (
    "feel",
    "felt",
    "feeling",
    "feelings",
    "emotion",
    "emotional",
    "how is that for you",
    "how was that for you",
    "upset",
    "hurt",
    "angry",
    "sad",
    "scared",
)
ADVICE = (
    "you should",
    "you could try",
    "i suggest",
    "i recommend",
    "it would help to",
    "try to",
    "have you thought about doing",
    "my advice",
)
TEACHING = (
    "in family systems",
    "bowen",
    "the theory",
    "a triangle is",
    "this is called",
    "research shows",
    "typically families",
    "people often",
)
TEACHING_PHRASES = (
    "what happens is",
    "in most families",
    "the way families",
    "that's the way it works",
)
OBJECTION = (
    "that's not what i said",
    "that's not right",
    "i didn't say",
    "you've got that wrong",
    "why are you asking",
    "stop asking",
    "i already told you",
    "check your information",
)
ARGUE = ("actually", "that's not right", "that's not what")
DAWNING = (
    "i never realised",
    "i never realized",
    "i hadn't thought",
    "now that you say it",
    "i guess that's when",
    "i wonder if",
    "that makes me think",
    "i just put that together",
)
DAWNING_STEMS = (
    "come to think of it",
    "i never knew",
    "i forgot about that",
    "i put that together",
    "i see it now",
)
AGREEMENT = (
    "you're right",
    "you are right",
    "that was wrong of him",
    "that was wrong of her",
    "he shouldn't have",
    "she shouldn't have",
    "they shouldn't have",
    "no wonder",
    "understandably",
)
HEDGED = ("whether", "not", "don't know", "do not know")
PRAISE = (
    "great job",
    "well done",
    "you're doing great",
    "don't worry",
    "it'll be okay",
    "you've got this",
    "i'm proud",
)
RISK = (
    "i can't go on",
    "i want to die",
    "kill myself",
    "end it all",
    "no point in living",
    "hurt myself",
    "suicidal",
    "i don't want to be here any more",
    "better off dead",
)
# The causal connectives of measures.md that proactive.CAUSES does not already hold.
CONNECTIVES = (
    "that's why",
    "which is why",
    "so that",
    "as a result",
    "linked to",
    "explains",
)
STEPS = ("i'll", "i will", "i'm going to", "i am going to", "i want to", "i plan to")
ASSIGNS = ("you could ask", "try asking", "why not ask", "you might ask", "i'd suggest")
# RULES.md 0.10, STOP and the kin words of REFERENT.
STOP = tuple(
    """about above after again against almost already although always another anybody anyone
    anything anyway around because before being better between could couldn't didn't doesn't
    don't during either enough every everybody everything except family families first getting
    going gonna guess hadn't hasn't haven't having heard isn't little maybe might mostly never
    nothing often other others people person pretty probably quite rather really right should
    shouldn't since somebody someone something sometimes still stuff sure their there these
    they're thing things think thought those through under until usually wasn't weren't where
    which while whole would wouldn't you're you've yourself""".split()
)
KIN = (
    tuple(
        """mother mom mommy ma father dad daddy pop parent parents grandmother grandma nana
    grandfather grandpa grandparents sister sisters brother brothers siblings aunt aunts uncle
    uncles cousin niece nephew wife husband spouse son daughter child children kid kids baby boy
    girl stepdaughter stepson stepmother stepfather in-law son-in-law mother-in-law father-in-law
    girlfriend boyfriend oldest youngest eldest twin""".split()
    )
    + ("only child", "an only")
)
QUESTION_WORDS = (
    "who",
    "whom",
    "whose",
    "what",
    "when",
    "where",
    "which",
    "how",
    "why",
    "did",
    "do",
    "does",
    "was",
    "were",
    "is",
    "are",
    "have",
    "has",
    "had",
    "can",
    "could",
    "would",
    "will",
)
FILLERS = (
    "well",
    "okay",
    "ok",
    "so",
    "and",
    "now",
    "then",
    "yeah",
    "oh",
    "um",
    "uh",
    "but",
)
MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
CRISIS_LINES: tuple[
    str, ...
] = ()  # Patrick's wording, per country; the app has none yet.
SHORT = 8


def version(*lists) -> str:
    return hashlib.sha256(repr(lists).encode()).hexdigest()[:12]


RULES_VERSION = version(
    FEELING,
    ADVICE,
    TEACHING,
    TEACHING_PHRASES,
    OBJECTION,
    ARGUE,
    DAWNING,
    DAWNING_STEMS,
    AGREEMENT,
    HEDGED,
    PRAISE,
    RISK,
    CAUSES,
    CONNECTIVES,
    STEPS,
    ASSIGNS,
    STOP,
    KIN,
    QUESTION_WORDS,
    FILLERS,
    MONTHS,
    CRISIS_LINES,
    SHORT,
    str(SITTING_GAP),
)

YEAR = r"\b(?:1[89]|20)\d\d\b"
MONTH = rf"\b(?:{'|'.join(m.title() for m in MONTHS)})\b"
DATED = re.compile(rf"\d|{MONTH}")
LEAD = re.compile(rf"^\W*(?i:(?:{'|'.join(FILLERS)})\b[\s,]*)*(?:[A-Z][a-z]+,\s*)?")


def norm(text: str) -> str:
    return text.lower().replace("’", "'").replace("anymore", "any more")


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", norm(text))


def has(text: str, phrase: str) -> bool:
    return (
        re.search(rf"(?<![a-z0-9']){re.escape(norm(phrase))}(?![a-z0-9'])", norm(text))
        is not None
    )


def found(text: str, phrases) -> list[str]:
    return [p for p in phrases if has(text, p)]


def own(text: str, phrases, person_last: str) -> list[str]:
    """The phrases in the text that the person did not use in their last message."""
    return [p for p in found(text, phrases) if not has(person_last, p)]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+|\n+", text) if s.strip()]


def is_question(sentence: str) -> bool:
    """Ends in "?", or opens with a question word once leading fillers and a
    name used as an address are dropped."""
    if sentence.rstrip(" *_\"')”").endswith("?"):
        return True
    rest = words(LEAD.sub("", sentence))
    return bool(rest) and rest[0] in QUESTION_WORDS


def sessions(
    messages: list[Message], gap: datetime.timedelta = SITTING_GAP
) -> list[list[Message]]:
    out = []
    for m in messages:
        if out and m.at - out[-1][-1].at <= gap:
            out[-1].append(m)
        else:
            out.append([m])
    return out


def slope(values: list[float]) -> float | None:
    n = len(values)
    if n < 3:
        return None
    mx, my = (n - 1) / 2, sum(values) / n
    return sum((i - mx) * (v - my) for i, v in enumerate(values)) / sum(
        (i - mx) ** 2 for i in range(n)
    )


def relative(sentence: str, names) -> bool:
    return bool(found(sentence, KIN) or found(sentence, names))


def content(word: str) -> bool:
    return word not in STOP and (
        len(word) >= 5 or word in KIN or any(c.isdigit() for c in word)
    )


# F1
def feeling_questions(reply: str, person_last: str) -> int:
    return sum(
        bool(own(s, FEELING, person_last)) for s in sentences(reply) if is_question(s)
    )


# F2
def why_questions(reply: str, person_last: str) -> int:
    return sum(
        bool(own(s, ("why",), person_last)) for s in sentences(reply) if is_question(s)
    )


# F3
def advice(reply: str) -> int:
    return sum(bool(found(s, ADVICE)) for s in sentences(reply))


def teaching(reply: str) -> int:
    return sum(
        bool(found(s, TEACHING + TEACHING_PHRASES))
        for s in sentences(reply)
        if "?" not in s
    )


# F4
def marks(sentence: str) -> set[str]:
    """Years, months and capitalised words after the sentence's first word."""
    return {
        w
        for rest in sentence.split(maxsplit=1)[1:]
        for w in re.findall(rf"{YEAR}|\b[A-Z][a-z]+\b", rest)
        if w != "I"
    }


def corrected(text: str, coach_before: str) -> set[str]:
    """The years, months and names a sentence opening with "no" adds to what the
    coach last said."""
    return {
        w
        for s in sentences(text)
        if re.match(r"\W*no\b", s, re.I)
        for w in marks(s)
        if not has(coach_before, w)
    }


def objection(text: str, coach_before: str) -> bool:
    return bool(found(text, OBJECTION) or corrected(text, coach_before))


def after_pushback(
    coach_next: Message, edits, old: set[str], new: set[str]
) -> dict[Pushback, bool]:
    text = coach_next.text
    return {
        Pushback.RecordChanged: any(e.turn_id == coach_next.turn_id for e in edits),
        Pushback.Reasserted: bool(found(text, old)) and not found(text, new),
        Pushback.Argued: bool(found(text, ARGUE)),
    }


# F5
def specifics(reply: str, person_before: str, facts, at: datetime.datetime) -> bool:
    if found(reply, [f.value for f in facts if f.since < at]):
        return True
    said, line = words(person_before), f" {' '.join(words(reply))} "
    return any(
        f" {' '.join(run)} " in line and any(map(content, run))
        for run in (said[i : i + 3] for i in range(len(said) - 2))
    )


# F6
def shrinking(session: list[Message]) -> dict:
    counts = [len(words(m.text)) for m in session if m.role is Role.Person]
    latency = [
        (b.at - a.at).total_seconds()
        for a, b in zip(session, session[1:])
        if a.role is Role.Coach and b.role is Role.Person
    ]
    return {
        "slope": slope(counts),
        "latency": statistics.median(latency) if latency else None,
        "latency_slope": slope(latency),
        "short": sum(c < SHORT for c in counts),
    }


# F7
def dawning(text: str) -> dict[Dawning, bool]:
    stem = any(
        not re.search(r"\b(not|never)\b|n't\b", s[: m.start()][-30:])
        for s in map(norm, sentences(text))
        for m in re.finditer(r"\breali[sz]", s)
        if re.search(r"\bi\b[\w' ]{0,20}$", s[: m.start()])
    )
    return {
        Dawning.Exact: bool(found(text, DAWNING)),
        Dawning.Stem: stem or bool(found(text, DAWNING_STEMS)),
    }


# F8
def agreement(reply: str, names) -> int:
    n = 0
    for s in sentences(reply):
        hit = re.search(
            rf"(?<![a-z'])({'|'.join(map(re.escape, AGREEMENT))})(?![a-z'])", norm(s)
        )
        if hit is None or DATED.search(s) or found(norm(s)[: hit.start()], HEDGED):
            continue
        n += relative(s, names)
    return n


# F9
def own_step(last3: list[Message], names, todo_turns) -> tuple[bool, bool]:
    """Whether the person's last three messages state their own next step with a
    relative, and whether a todo was stored from that message (R-0783)."""
    said = [
        m
        for m in last3
        for s in sentences(m.text)
        if re.search(rf"\b({'|'.join(map(re.escape, STEPS))})\s+[a-z]+", norm(s))
        and relative(s, names)
    ]
    return bool(said), any(m.turn_id in todo_turns for m in said)


def coach_assigns(replies: list[str], names) -> bool:
    return any(
        found(s, ASSIGNS) and relative(s, names) for r in replies for s in sentences(r)
    )


# F10
def returned(starts: list[datetime.datetime], now: datetime.datetime) -> dict:
    first = starts[0]

    def within(days: int) -> Return:
        span = datetime.timedelta(days=days)
        if len(starts) > 1 and starts[1] - first <= span:
            return Return.Yes
        return Return.No if now - first >= span else Return.Unknown

    return {
        "week": within(7),
        "month": within(30),
        "fourth": len(starts) >= 4,
        "days": (starts[-1] - first).total_seconds() / 86400,
    }


# F11
def risk(text: str) -> bool:
    return bool(found(text, RISK))


def protocol(reply: str, lines) -> bool:
    return bool(found(reply, lines))


# F12
def paired_with_cause(reply: str, years, events) -> int:
    """Coach sentences setting two stored years or two record events side by
    side with a cause word (R-0784)."""
    n = 0
    for s in sentences(reply):
        if not (CAUSE.search(s) or found(s, CONNECTIVES)):
            continue
        both = sum(bool(re.search(rf"\b{y}\b", s)) for y in set(map(str, years))) >= 2
        n += both or sum(bool(found(s, e)) for e in events) >= 2
    return n


# F13
def praise(reply: str) -> int:
    return sum(bool(found(s, PRAISE)) for s in sentences(reply))


# F14
def talk_shape(messages: list[Message]) -> dict:
    """The person's share of words, the coach's words per message and against
    the person's last message, and coach messages ending in a question (R-0436)."""
    person = sum(len(words(m.text)) for m in messages if m.role is Role.Person)
    coach = [m for m in messages if m.role is Role.Coach]
    said = [len(words(m.text)) for m in coach]
    ratios, last = [], 0
    for m in messages:
        if m.role is Role.Person:
            last = len(words(m.text))
        elif last:
            ratios.append(len(words(m.text)) / last)
    total = person + sum(said)
    return {
        "person_share": person / total if total else None,
        "coach_words": statistics.mean(said) if said else None,
        "coach_ratio": statistics.mean(ratios) if ratios else None,
        "ends_question": sum(m.text.rstrip(" *_\"')”\n").endswith("?") for m in coach),
    }


COUNTS = (
    "coach_messages",
    "person_messages",
    "feeling_questions",
    "why_questions",
    "advice",
    "teaching",
    "specifics",
    "agreement",
    "praise",
    "paired_with_cause",
    "objections",
    "record_changed",
    "reasserted",
    "argued",
    "dawning_exact",
    "dawning_stem",
    "risk",
    "protocol",
    "short",
    "sessions",
    "sessions_scored",
    "sessions_falling",
    "own_steps",
    "own_steps_stored",
    "coach_assigned",
)


def cells(messages: list[Message]) -> list[tuple]:
    """Each message keyed by the model and prompt of the coach reply it sits
    with: a person message goes with the coach reply before it, or the first
    one after when none came before."""
    out, waiting, key = [], [], None
    for m in messages:
        if m.role is Role.Coach:
            key = (m.model, m.prompt_version)
            out += [(key, w) for w in waiting]
            waiting = []
        if key is None:
            waiting.append(m)
        else:
            out.append((key, m))
    return out


def rows(messages: list[Message], record: Record) -> dict[tuple, dict]:
    """Counts per (model, prompt version); no text."""
    keyed = cells(messages)
    out = {key: dict.fromkeys(COUNTS, 0) for key, _ in keyed}

    def names(at):
        return [
            f.value for f in record.facts if f.kind is FactKind.Name and f.since < at
        ]

    years = [f.value for f in record.facts if f.kind is FactKind.Year]
    seen, coach_before = [], ""
    for i, (key, m) in enumerate(keyed):
        row = out[key]
        if m.role is Role.Coach:
            last = seen[-1] if seen else ""
            row["coach_messages"] += 1
            row["feeling_questions"] += feeling_questions(m.text, last)
            row["why_questions"] += why_questions(m.text, last)
            row["advice"] += advice(m.text)
            row["teaching"] += teaching(m.text)
            row["specifics"] += specifics(m.text, " ".join(seen), record.facts, m.at)
            row["agreement"] += agreement(m.text, names(m.at))
            row["praise"] += praise(m.text)
            row["paired_with_cause"] += paired_with_cause(m.text, years, record.events)
            coach_before = m.text
            continue
        row["person_messages"] += 1
        row["short"] += len(words(m.text)) < SHORT
        found_dawning = dawning(m.text)
        row["dawning_exact"] += found_dawning[Dawning.Exact]
        row["dawning_stem"] += found_dawning[Dawning.Stem]
        nxt = next((n for _, n in keyed[i + 1 :] if n.role is Role.Coach), None)
        if risk(m.text):
            row["risk"] += 1
            row["protocol"] += bool(nxt) and protocol(nxt.text, CRISIS_LINES)
        if objection(m.text, coach_before):
            row["objections"] += 1
            if nxt:
                new = corrected(m.text, coach_before)
                old = {
                    w
                    for s in sentences(coach_before)
                    for w in marks(s)
                    if not has(m.text, w)
                }
                for kind, hit in after_pushback(nxt, record.edits, old, new).items():
                    row[kind.value] += hit
        seen.append(m.text)

    where = {id(m): key for key, m in keyed}
    for session in sessions([m for _, m in keyed]):
        coach = [m for m in session if m.role is Role.Coach]
        if not coach:
            continue
        row = out[where[id(coach[-1])]]
        row["sessions"] += 1
        found_slope = shrinking(session)["slope"]
        row["sessions_scored"] += found_slope is not None
        row["sessions_falling"] += found_slope is not None and found_slope < 0
        last3 = [m for m in session if m.role is Role.Person][-3:]
        step, stored = own_step(last3, names(session[-1].at), record.todo_turns)
        row["own_steps"] += step
        row["own_steps_stored"] += stored
        row["coach_assigned"] += coach_assigns(
            [m.text for m in coach[-3:]], names(session[-1].at)
        )

    for key in out:
        out[key] |= talk_shape([m for k, m in keyed if k == key])
        out[key]["rules_version"] = RULES_VERSION
    return out


def account_row(messages: list[Message], now: datetime.datetime) -> dict:
    """F10 for one account, over all its threads, at the sitting gap."""
    starts = [
        s[0].at for s in sessions(messages) if any(m.role is Role.Person for m in s)
    ]
    return returned(starts, now) | {"rules_version": RULES_VERSION}
