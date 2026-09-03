"""The coach-reference contract: what the model may write, and what the client
is handed."""

from btcopilot.personal.refs import (
    INDEX_BUDGET_TOKENS,
    Ref,
    RefKind,
    index,
    parse,
    resolve,
)
from btcopilot.schema import DateCertainty, DiagramData


def test_every_kind_parses():
    clean, refs = parse(
        "In [[chapter:c2|those years]] — [[events:10,11|two moments]], "
        "[[person:4|Nell]], [[range:1992-01-01..1998-12-31|92 to 98]]."
    )
    assert clean == "In those years — two moments, Nell, 92 to 98."
    assert [r.kind for r in refs] == list(RefKind)
    assert refs[0].cluster_id == "c2"
    assert refs[1].event_ids == [10, 11]
    assert refs[2].person_id == 4
    assert (refs[3].start, refs[3].end) == ("1992-01-01", "1998-12-31")


def test_a_reply_naming_nothing_has_no_references():
    assert parse("What did that look like from where you sat?") == (
        "What did that look like from where you sat?",
        [],
    )


def test_unparseable_target_keeps_its_words_and_makes_no_reference():
    clean, refs = parse("I mean [[events:the winter|that winter]].")
    assert clean == "I mean that winter."
    assert refs == []


def test_backwards_range_is_not_a_reference():
    assert parse("[[range:1998-01-01..1992-01-01|x]]")[1] == []


def test_resolve_drops_targets_the_diagram_does_not_have():
    data = DiagramData(people=[{"id": 1}], events=[{"id": 10}], clusters=[{"id": "c1"}])
    refs = [
        Ref(kind=RefKind.Person, label="a", person_id=2),
        Ref(kind=RefKind.Events, label="b", event_ids=[10, 99]),
        Ref(kind=RefKind.Chapter, label="c", cluster_id="c9"),
    ]
    resolved = resolve(refs, data)
    assert [r.label for r in resolved] == ["b"]
    assert resolved[0].event_ids == [10]


def _seeded() -> DiagramData:
    """Invented people. One event and one cluster are deliberately off the
    line: an Unknown date, and a cluster starting before the record."""
    return DiagramData(
        people=[
            {"id": 1, "name": "Nell"},
            {"id": 2, "name": "Ivo"},
            {"id": 3, "name": "Wren"},
        ],
        events=[
            {
                "id": 10,
                "person": 1,
                "dateTime": "1992-04-05",
                "description": "Nell moved north",
            },
            {
                "id": 11,
                "person": 2,
                "dateTime": "1995-08-01",
                "kind": "married",
                "spouse": 1,
            },
            {
                "id": 12,
                "person": 3,
                "dateTime": "1998-02-11",
                "description": "Wren started school",
            },
            {
                "id": 13,
                "person": 1,
                "dateTime": "1999-01-01",
                "dateCertainty": DateCertainty.Unknown.value,
                "description": "sometime around then",
            },
        ],
        clusters=[
            {
                "id": "c1",
                "title": "The move north",
                "startDate": "1992-04-05",
                "endDate": "1995-08-01",
            },
            {
                "id": "c9",
                "title": "Before the record",
                "startDate": "1901-01-01",
                "endDate": "1902-01-01",
            },
        ],
    )


def test_index_names_every_kind_of_id_the_markup_takes():
    out = index(_seeded())
    assert "1 Nell" in out and "3 Wren" in out
    assert "c1 1992–1995 The move north" in out
    assert "12 1998-02-11 Wren started school" in out


def test_index_leaves_out_what_the_picture_cannot_aim_at():
    out = index(_seeded())
    assert "13 " not in out
    assert "c9" not in out


def test_index_is_empty_without_a_dated_record():
    assert index(DiagramData(people=[{"id": 1, "name": "Nell"}])) == ""
    assert index(None) == ""


def test_index_is_capped():
    data = DiagramData(
        people=[{"id": 1, "name": "Nell"}],
        events=[
            {
                "id": i,
                "person": 1,
                "dateTime": f"19{50 + i // 300:02d}-01-01",
                "description": "a long enough description to spend the budget on",
            }
            for i in range(1, 900)
        ],
    )
    out = index(data)
    assert len(out) <= INDEX_BUDGET_TOKENS * 4
    assert out.count(";") < 898


def test_a_reply_citing_the_index_resolves_to_real_targets():
    data = _seeded()
    out = index(data)
    assert "c1" in out and "12 " in out and "3 Wren" in out
    clean, refs = parse(
        "[[chapter:c1|the move]] set up [[events:12|the school year]] for "
        "[[person:3|Wren]]."
    )
    assert clean == "the move set up the school year for Wren."
    resolved = resolve(refs, data)
    assert [r.kind for r in resolved] == [
        RefKind.Chapter,
        RefKind.Events,
        RefKind.Person,
    ]
    assert (resolved[0].cluster_id, resolved[1].event_ids, resolved[2].person_id) == (
        "c1",
        [12],
        3,
    )


def _wide(people_count: int) -> DiagramData:
    """A cast far larger than the chapters and events around it."""
    return DiagramData(
        people=[{"id": i, "name": f"Person Number{i}"} for i in range(1, people_count + 1)],
        events=[
            {
                "id": 1000 + i,
                "person": (i % people_count) + 1,
                "dateTime": f"{1950 + i // 12}-{(i % 12) + 1:02d}-01",
                "description": f"something happened number {i}",
            }
            for i in range(300)
        ],
        clusters=[
            {
                "id": f"c{n}",
                "title": f"a chapter titled {n}",
                "startDate": f"{1950 + n}-01-01",
                "endDate": f"{1951 + n}-01-01",
            }
            for n in range(1, 41)
        ],
    )


def _section(out: str, name: str) -> list[str]:
    line = next(l for l in out.splitlines() if l.startswith(name))
    return line.split(": ", 1)[1].split("; ")


def test_chapters_are_listed_newest_first():
    """Ids sort as text, so double digits are where a by-id sort goes wrong."""
    entries = _section(index(_wide(5)), "Chapters")
    years = [int(entry.split(" ")[1][:4]) for entry in entries]
    assert years == sorted(years, reverse=True)
    assert entries[0].split(" ")[0] == "c24"


def test_a_large_cast_cannot_crowd_out_the_events():
    out = index(_wide(300))
    assert len(out) <= INDEX_BUDGET_TOKENS * 4
    for name in ("People", "Chapters", "Events"):
        assert len(_section(out, name)) > 10
