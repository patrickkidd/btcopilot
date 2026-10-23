"""Notes too long for one coach loop, cut into parts the coach enters one after
another within the same turn [Oracle: R-0897].

A part ends at a paragraph break, else at a line break; only a line longer
than a part is cut, at its sentence ends. Each part after the first
carries the last lines of the one before it, so the coach can join a story that
runs across the cut.
"""

import re

# About as much as the coach enters well within one loop of MAX_STEPS rounds.
PART_WORDS = 1500
REMINDER_LINES = 5

# What a paste costs and one part takes on the coach's model, priced at its
# rates on the app's own cache split, from one 9,000-word, seven-part run on
# the subscription (2026-10-22); the Gemini calls for clusters and titles are
# not in the price.
USD_PER_1000_WORDS = 0.29
SECONDS_PER_PART = 96

BREAK = re.compile(r"\n\s*\n")
SENTENCE = re.compile(r"(?<=[.!?])\s+")

PART = (
    "These are part {k} of {n} of the same notes. Enter every person and event "
    "in this part that you can, even if the person this diagram is about is not "
    "named yet, and ask nothing: hold every question for your one reply after "
    "the last part. Enter only people and events this text names; never add a "
    "stand-in for someone or something not yet named, and leave anything only "
    "half known for a later part. Do not reply to the person yet."
)
LAST = (
    "This is the last part, {n} of {n}, of the same notes; the parts before it "
    "are already in the diagram. Enter everything in this part, then reply to "
    "the person about the whole of the notes, with any questions you held."
)
REMINDER = (
    "Reminder only, already entered: the last lines of the part before.\n"
    "{lines}\n"
    "End of the reminder. This part's notes:"
)


def _words(text: str) -> int:
    return len(text.split())


def _packed(pieces: list[str], glue: str) -> list[str]:
    """The pieces joined back in order into runs of at most PART_WORDS, a run
    never cut inside a piece."""
    runs, run, count = [], [], 0
    for piece in pieces:
        size = _words(piece)
        if run and count + size > PART_WORDS:
            runs.append(glue.join(run))
            run, count = [], 0
        run.append(piece)
        count += size
    if run:
        runs.append(glue.join(run))
    return runs


def split(text: str) -> list[str]:
    """The text as it is when it fits one part, else its parts in order."""
    if _words(text) <= PART_WORDS:
        return [text]
    pieces = []
    for paragraph in BREAK.split(text.strip()):
        if _words(paragraph) > PART_WORDS:
            pieces.extend(_packed(_lines(paragraph), "\n"))
        else:
            pieces.append(paragraph)
    return _packed(pieces, "\n\n")


def _lines(paragraph: str) -> list[str]:
    """A paragraph's lines, a line longer than a part cut at its sentence ends."""
    lines = []
    for line in paragraph.splitlines():
        if _words(line) > PART_WORDS:
            lines.extend(_packed(SENTENCE.split(line), " "))
        else:
            lines.append(line)
    return lines


def framed(parts: list[str], k: int) -> str:
    """Part k, counted from 1, as the coach reads it: which part it is, what it
    must do with it, and the reminder from the part before."""
    n = len(parts)
    head = (LAST if k == n else PART).format(k=k, n=n)
    if k == 1:
        return f"{head}\n\n{parts[0]}"
    before = [line for line in parts[k - 2].splitlines() if line.strip()]
    reminder = REMINDER.format(lines="\n".join(before[-REMINDER_LINES:]))
    return f"{head}\n\n{reminder}\n\n{parts[k - 1]}"


def projection() -> dict:
    """What the page needs to show a paste's cost and time before it is sent."""
    return {
        "part_words": PART_WORDS,
        "usd_per_1000_words": USD_PER_1000_WORDS,
        "seconds_per_part": SECONDS_PER_PART,
    }
