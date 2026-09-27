import pytest

from btcopilot.training import frameedition
from btcopilot.tests.training.conftest import FRAME_PAGES


def test_public_drops_confidential_and_private_paths():
    out = frameedition.public("anxiety", FRAME_PAGES["anxiety.md"], ["anxiety", "conflict"])
    assert "anxiety is the response to a threat" in out
    assert "lighthouse" not in out
    assert "ferry" not in out
    assert "<!-- v" not in out
    assert "../REFERENCE.md" not in out
    assert "[`conflict.md`](conflict.md#C1)" in out


def test_public_refuses_a_leak():
    text = "- <a id=\"A9\"></a>**A9** “q” see private/rulings.md · PUBLIC.\n"
    with pytest.raises(ValueError):
        frameedition.public("anxiety", text, ["anxiety"])


def test_index_counts_public_entries_only():
    names = ["anxiety", "conflict"]
    pages = {n: frameedition.public(n, FRAME_PAGES[f"{n}.md"], names) for n in names}
    out = frameedition.index(FRAME_PAGES["INDEX.md"], FRAME_PAGES["README.md"], pages)
    assert "| [anxiety](anxiety.md) (A) | What anxiety is | 1 | Own evidence ruled |" in out
    assert "| FE*n* L*x* | Kerr and Bowen, *Family Evaluation* |" in out
    assert "App Seminar" not in out


def test_links_point_to_routes_and_flatten_the_rest():
    out = frameedition.links(
        "[`conflict.md`](conflict.md#C1) [`../REFERENCE.md`](../REFERENCE.md) [A1](#A1)",
        {"conflict.md": "/training/frame/conflict"},
    )
    assert out == "[`conflict.md`](/training/frame/conflict#C1) `../REFERENCE.md` [A1](#A1)"
