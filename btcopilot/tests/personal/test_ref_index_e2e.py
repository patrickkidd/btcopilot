"""The whole chip loop without a model: the index tells the coach which ids
exist, a reply cites them, and every chip the client is handed aims at
something the picture can actually show."""

from btcopilot.companion.seed import seed_diagram_data
from btcopilot.companion.timeline import aimable, build_timeline
from btcopilot.personal.chat import summarize_committed_state
from btcopilot.personal.prompts import COACH_REFERENCE_INSTRUCTION
from btcopilot.personal.refs import RefKind, index, parse, resolve


def _cited(out: str, section: str) -> list[str]:
    line = next(l for l in out.splitlines() if l.startswith(section))
    return [entry.split(" ")[0] for entry in line.split(": ", 1)[1].split("; ")]


def test_the_state_handed_to_the_coach_carries_the_index():
    state = summarize_committed_state(seed_diagram_data())
    assert "Reference index" in state
    assert "People on file" in state


def test_every_id_the_index_offers_survives_the_whole_loop():
    data = seed_diagram_data()
    out = index(data)
    person = _cited(out, "People")[0]
    chapter = _cited(out, "Chapters")[0]
    event = _cited(out, "Events")[0]

    clean, refs = parse(
        f"[[chapter:{chapter}|that stretch]] holds "
        f"[[events:{event}|what you just told me]] for "
        f"[[person:{person}|him]]."
    )
    assert clean == "that stretch holds what you just told me for him."
    chips = aimable(resolve(refs, data), data)
    assert [c.kind for c in chips] == [RefKind.Chapter, RefKind.Events, RefKind.Person]

    timeline = build_timeline(data)
    chapters = timeline["chapters"]
    assert any(chapter in c["cluster_ids"] for c in chapters)
    assert any(int(event) in c["event_ids"] for c in chapters)


def test_an_id_the_index_withholds_is_thrown_away():
    data = seed_diagram_data()
    out = index(data)
    unknown = max(int(i) for i in _cited(out, "Events")) + 1000
    _, refs = parse(f"[[events:{unknown}|a moment I made up]]")
    assert aimable(resolve(refs, data), data) == []


def test_the_instruction_teaches_the_markup_the_parser_reads():
    """Guards the one thing that silently breaks chips: the instruction and
    the parser drifting apart on the markup."""
    for kind in RefKind:
        assert f"[[{kind.value}:" in COACH_REFERENCE_INSTRUCTION
    _, refs = parse(
        "[[chapter:cl1|a]] [[events:10,11|b]] [[person:1|c]] "
        "[[range:1988-04-02..1999-11-05|d]]"
    )
    assert [r.kind for r in refs] == list(RefKind)
