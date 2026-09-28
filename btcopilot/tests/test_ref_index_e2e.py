"""The whole chip loop without a model: the index tells the coach which ids
exist, a reply cites them, and every chip the client is handed aims at
something the picture can actually show."""

from btcopilot.seed import seed_diagram_data
from btcopilot.timeline import aimable, build_timeline
from btcopilot import prompts
from btcopilot.refs import RefKind, index, parse, resolve


def _cited(out: str, section: str) -> list[str]:
    line = next(l for l in out.splitlines() if l.startswith(section))
    return [entry.split(" ")[0] for entry in line.split(": ", 1)[1].split("; ")]


def test_every_id_the_index_offers_survives_the_whole_loop():
    # R-0072
    data = seed_diagram_data()
    out = index(data)
    person = _cited(out, "People")[0]
    cluster = _cited(out, "Clusters")[0]
    event = _cited(out, "Events")[0]

    clean, refs = parse(
        f"[[cluster:{cluster}|that cluster]] holds "
        f"[[events:{event}|what you just told me]] for "
        f"[[person:{person}|him]]."
    )
    assert clean == "that cluster holds what you just told me for him."
    chips = aimable(resolve(refs, data), data)
    assert [c.kind for c in chips] == [RefKind.Cluster, RefKind.Events, RefKind.Person]

    timeline = build_timeline(data)
    assert any(cluster in c["cluster_ids"] for c in timeline["clusters"])
    # the moment is on the line, whether or not a cluster claims it
    assert any(int(event) == e["id"] for e in timeline["events"])


def test_an_id_the_index_withholds_is_thrown_away():
    # R-0085
    data = seed_diagram_data()
    out = index(data)
    unknown = max(int(i) for i in _cited(out, "Events")) + 1000
    _, refs = parse(f"[[events:{unknown}|a moment I made up]]")
    assert aimable(resolve(refs, data), data) == []


