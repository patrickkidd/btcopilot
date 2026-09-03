"""The coach-reference contract: what the model may write, and what the client
is handed."""

from btcopilot.personal.refs import Ref, RefKind, parse, resolve
from btcopilot.schema import DiagramData


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
