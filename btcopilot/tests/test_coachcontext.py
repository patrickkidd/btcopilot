"""What the coach is told each turn besides the record's contents."""

from btcopilot import prompts, recordtext
from btcopilot.schema import DiagramData

PEOPLE = [{"id": 1, "name": "Sarah"}, {"id": 2, "name": "Tom"}]


def test_the_record_marks_the_person_the_coach_is_talking_with():
    # R-0438
    text = recordtext.render(DiagramData(people=PEOPLE), speaker=1)
    assert f"1 Sarah{recordtext.SPEAKER}" in text
    assert text.count(recordtext.SPEAKER) == 1


def test_the_coach_is_told_today_in_the_tail_not_the_cached_head():
    # R-0438
    fixed, tail = prompts.agent_prompt(record="1 Sarah", today="2026-09-23")
    assert "2026-09-23" in tail
    assert "2026-09-23" not in fixed
