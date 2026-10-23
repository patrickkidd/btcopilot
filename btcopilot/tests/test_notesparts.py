"""Notes too long for one coach loop are cut into parts at paragraph breaks,
each after the first reminding the coach how the one before ended."""

import json
import re

from btcopilot import notesparts
from btcopilot.notesparts import PART_WORDS, REMINDER_LINES


def paragraph(i: int, lines: int = 4, words: int = 100) -> str:
    """Invented notes: one paragraph of short dated lines about Nell's family."""
    return "\n".join(
        f"Line {i}.{j}: Nell's cousin Ada moved in 19{50 + j}, "
        + " ".join(["then"] * words)
        for j in range(lines)
    )


def test_notes_that_fit_one_part_go_in_as_they_are():
    # R-0897
    text = "  Nell was born in 1950.\n\nHer brother Finn in 1953.\n"
    assert notesparts.split(text) == [text]


def test_long_notes_are_cut_at_paragraph_breaks_into_parts_of_at_most_a_part():
    # R-0897
    paragraphs = [paragraph(i) for i in range(10)]
    parts = notesparts.split("\n\n".join(paragraphs))
    assert len(parts) == 4
    assert all(len(part.split()) <= PART_WORDS for part in parts)
    assert "\n\n".join(parts) == "\n\n".join(paragraphs)
    assert all(part.startswith("Line ") for part in parts)


def test_a_paragraph_longer_than_a_part_is_cut_at_line_breaks_never_inside_a_line():
    # R-0897
    lines = paragraph(0, lines=20, words=150).splitlines()
    parts = notesparts.split("\n".join(lines))
    assert len(parts) > 1
    assert [line for part in parts for line in part.splitlines()] == lines


def test_one_paragraph_on_one_line_is_cut_at_sentence_ends_into_as_many_parts_as_the_page_says():
    # R-0897
    sentences = [
        f"Ada moved in 19{i % 90 + 10} with " + " ".join(["then"] * 11) + "."
        for i in range(250)
    ]
    text = " ".join(sentences)
    assert len(text.split()) == 4000
    parts = notesparts.split(text)
    assert len(parts) == -(-4000 // PART_WORDS) == 3
    assert " ".join(parts) == text
    assert all(part.endswith(".") for part in parts)


def test_a_part_before_the_last_is_told_to_add_no_stand_ins():
    # R-0897
    parts = notesparts.split("\n\n".join(paragraph(i) for i in range(10)))
    for k in (1, 2):
        assert "never add a stand-in" in notesparts.framed(parts, k)
    assert "stand-in" not in notesparts.framed(parts, len(parts))


def test_each_part_after_the_first_carries_the_last_lines_of_the_one_before():
    # R-0897
    parts = notesparts.split("\n\n".join(paragraph(i) for i in range(10)))
    first, second, last = (notesparts.framed(parts, k) for k in (1, 2, len(parts)))
    assert "Reminder" not in first and "part 1 of 4" in first
    lines = [line for line in parts[0].splitlines() if line.strip()]
    reminder = second.split("End of the reminder")[0]
    assert all(line in reminder for line in lines[-REMINDER_LINES:])
    assert lines[-REMINDER_LINES - 1] not in reminder
    assert second.endswith(parts[1])
    assert "Do not reply" in second
    assert "last part, 4 of 4" in last and "Do not reply" not in last


def test_the_page_is_given_the_part_size_and_the_price_and_time_of_a_part(web):
    # R-0897
    page = web.get("/app/", headers={"Sec-Fetch-Dest": "document"}).get_data(
        as_text=True
    )
    bootstrap = json.loads(re.search(r"window.BOOTSTRAP=(\{.*?\})</script>", page)[1])
    assert bootstrap["notes"] == {
        "part_words": PART_WORDS,
        "usd_per_1000_words": notesparts.USD_PER_1000_WORDS,
        "seconds_per_part": notesparts.SECONDS_PER_PART,
    }
