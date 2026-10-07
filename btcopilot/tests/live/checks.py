"""What the live cases look for in a coach reply, as plain functions so made-up
replies prove each one rejects the wrong reply and accepts the allowed one."""

import re

from btcopilot.proactive import CAUSE

KIDS = r"\b(children|child|kids?|sons?|daughters?|bab(y|ies)|adopt\w*|foster\w*|start(ing)? a family|family of (your|their) own)\b"
# What the couple already said, or the person's own childhood: naming children
# inside these is not asking whether they have, had or plan any.
SAID_KIDS = (
    r"\b(could not|couldn't|can't|cannot|can not|were never able to|weren't able to|"
    r"not able to|unable to)\s+(\w+\s+){0,2}(have|had|start)\s+(any\s+)?"
    r"(children|kids|a child|a baby|a family)"
    r"|\b(as|when you were)\s+(kids|children|a child|little)\b|\bgrowing up\b"
)
FATHER = r"\b(dad|father|Hugh|he|him|his|parents|both)\b"
ALIVE_OR_AGE = (
    r"\bstill (living|alive|with us|around|here)\b|\balive\b|\bpassed( away)?\b|\bdied\b"
    r"|\bdeath\b|\bhow old\b|\bage\b|\baged\b|\bborn\b|\bbirthday\b|\bbirth ?date\b"
)
WAITING = r"\b(drink\w*|drank|drunk|alcohol\w*|grow(ing)? up|grew up|childhood)\b"
DRINKING = r"\b(drink\w*|drank|drunk|alcohol\w*)\b"
MOST = "two or three times when the most was going on"
NUMBERS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty"
).split()
COUNT = r"(\d{1,2}|" + "|".join(NUMBERS) + ")"
# A time marker: a four-digit year, an age, or a step from the marker before.
MARKER = (
    r"\b(?P<year>1[89]\d\d|20\d\d)\b"
    rf"|\b(?:at|aged|at age|by|by age|when (?:i|you|she|he|they) (?:was|were)) (?P<age>{COUNT})\b"
    rf"|\b(?:(?P<steps>a|an|{COUNT}) years? (?P<way>later|after|before|earlier)"
    r"|the (?:year (?P<next>after|before)|(?:next|following) year))\b"
)


def questions(reply: str) -> list[str]:
    """Each question in the reply, cut at the sentence, colon or semicolon
    before it."""
    return [q.strip() for q in re.findall(r"[^.?!:;]*\?", reply)]


def asks_children(reply: str) -> list[str]:
    """The questions whether the couple have, had or plan children (R-0760)."""
    return [q for q in questions(reply) if re.search(KIDS, re.sub(SAID_KIDS, "", q, flags=re.I), re.I)]


def asks_father_alive_or_age(reply: str) -> list[str]:
    """The questions whether the father is living, or his age or birth (R-0760)."""
    return [q for q in questions(reply) if re.search(FATHER, q, re.I) and re.search(ALIVE_OR_AGE, q, re.I)]


def asks_only_waiting(reply: str) -> bool:
    """The reply asks the waiting question about the mother's father's
    drinking, and no other (R-0771)."""
    asked = questions(reply)
    return bool(asked) and all(re.search(WAITING, q, re.I) for q in asked)


def asks_passed_over(reply: str) -> list[str]:
    """The questions about the mother's father's drinking, which the person
    has passed over twice (R-0774)."""
    return [q for q in questions(reply) if re.search(DRINKING, q, re.I)]


def asks_most_first(reply: str) -> bool:
    """The two or three times question comes before any other (R-0762)."""
    asked = questions(reply)
    return bool(asked) and MOST in asked[0]


def title_retry(detail: dict) -> bool:
    """A refused event the coach then wrote with a title in the same turn."""
    return "needs a title" in (detail.get("refusal") or "") and bool(detail.get("retried"))


BUILDS = r"\bpicture\b|\bover a few conversations\b|\bover time\b"
HOPE = r"\bhop(e|ing)\b|\bwant\b|\bget out of\b"


def explains(reply: str) -> bool:
    """One sentence says what the coach does or what builds up, without leading
    with family or relationships (R-0802, R-0801)."""
    said = [s for s in re.findall(r"[^.?!]+[.?!]?", reply) if re.search(BUILDS, s, re.I)]
    return bool(said) and all(
        len(re.findall(r"\bfamily\b", s, re.I)) <= 1 and not re.search("relationship", s, re.I)
        for s in said
    )


def asks_hope(reply: str) -> bool:
    """A question asks what the person is hoping to get from this (R-0802)."""
    return any(re.search(HOPE, q, re.I) for q in questions(reply))


def number(word: str) -> int:
    word = word.lower()
    return int(word) if word.isdigit() else 1 if word in ("a", "an") else NUMBERS.index(word)


def told_in_order(sentence: str, events: list[list[str]]) -> bool:
    """Three or more of the events, each found by any of its words, named in
    the order the list gives them."""
    found = []
    for words in events:
        at = [m.start() for w in words for m in re.finditer(rf"\b{re.escape(w)}", sentence, re.I)]
        if at:
            found.append(min(at))
    return len(found) >= 3 and found == sorted(found)


def places_in_time(
    reply: str, years: list[int], born: int | None = None, events: list[list[str]] = ()
) -> bool:
    """One sentence with no cause word puts the person's material in order of
    time (R-0804): three or more distinct times in order, each one of the given
    years, an age ("at five", "when I was twelve", "aged 9") counted from
    `born`, or a step ("a year later", "the next year", "two years after", "the
    year before") from the marker before it; or three or more of `events`,
    given in the record's order as words for each, named in that order with
    at least one such time marker."""
    for sentence in re.split(r"(?<=[.?!])\s+", reply):
        if CAUSE.search(sentence):
            continue
        said = []
        for m in re.finditer(MARKER, sentence, re.I):
            if m["year"]:
                if int(m["year"]) in years:
                    said.append(int(m["year"]))
            elif m["age"]:
                said.append((born or 0) + number(m["age"]))
            elif said:
                back = (m["way"] or m["next"] or "").lower() in ("before", "earlier")
                step = number(m["steps"]) if m["steps"] else 1
                said.append(said[-1] + (-step if back else step))
        if len(set(said)) >= 3 and said == sorted(said):
            return True
        if re.search(MARKER, sentence, re.I) and told_in_order(sentence, events):
            return True
    return False


# Words of a todo that say nothing of what it is about.
PLAIN = r"\b(i'll|i'm|i|will|going|to|my|the|a|an|and|of|when|they|them|it|out|find|go|get|some|about)\b"


def mentions_todo(text: str, todo_words: str) -> bool:
    """The text carries at least two of the todo's own words, each matched at
    the start of a word."""
    words = set(re.sub(PLAIN, " ", todo_words.lower()).split())
    return sum(bool(re.search(rf"\b{re.escape(w[:4])}", text.lower())) for w in words) >= 2


def leads_with_todo(reply: str, todo_words: str) -> bool:
    """The reply's first question, with the sentence leading into it, is about
    the person's todo (R-0803, R-0815)."""
    led = re.search(r"([^.?!]*[.!]\s*)?[^.?!]*\?", reply)
    return led is not None and mentions_todo(led.group(0), todo_words)


def offers_todo(reply: str, todo_words: str) -> bool:
    """The reply mentions the todo and leaves another door open: a second
    question, or an "or ..." in the question about it (R-0815)."""
    if not mentions_todo(reply, todo_words):
        return False
    asked = questions(reply)
    return len(asked) >= 2 or any(re.search(r"\bor\b", q.lower()) for q in asked)
