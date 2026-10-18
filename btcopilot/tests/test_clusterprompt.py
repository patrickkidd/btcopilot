"""The citation guard on the cluster detection prompt (R-0858).

Every rule the private cluster prompt gives rests on a source, and every source
is a row of the prompt's inventory (btcopilot-sources,
`research/clusters/INVENTORY.md` section 1; its ids alone are copied into
`live/clusters/inventory-ids.txt` by `bin/inventoryids.py`, so CI needs no corpus).
A line names its sources in a Jinja comment, `{# P-012; S-090; R-0850 #}`, which
the render strips, so the coach's cluster detection never sees it.

What is checked, in the prompt's body (front matter left out) and in every
fragment it includes:

- Every comment is a citation: its tokens, split on `;`, `,` or spaces, are ids
  in the ids file or the word `shape`. Headings and the output shape carry
  `{# shape #}`. A citation of commit messages (GIT-n) alone is not a source.
- An instruction line is a non-blank line that still holds text once its
  comments are taken out, other than a line holding only `{% ... %}` tags or
  only a format slot such as `{existing}`. Each one carries a citation on itself
  or on a comment-only line directly above it. A comment covers one line: a
  sentence wrapped onto a second line needs a second comment.
- Rendered the way cluster detection renders it (Jinja, then the slots filled
  by `clusters._prompt`, here with empty inputs), the text holds no `{#`.
- No banned word reaches the rendered text outside a quotation. A quotation is
  text inside "..." or “...” that does not cross a blank line, or a backtick
  span holding one identifier and no space (an output key such as `eventIds`).
  The banned words take their plurals and verb endings; "ran" is not one.

Without a sops key these skip, as the other private prompt tests do; the
checker's own rules, and the script that writes the ids file, are proven on
invented text in every environment.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import bin.inventoryids as inventoryids
from btcopilot import clusters, prompts
from btcopilot.promptdir import PromptDir, key_present, read, split

PROMPT = prompts.PRIVATE / "cluster.prompty"
# Where an include resolves, in the loader's order.
DIRS = [prompts.PRIVATE, prompts.PUBLIC]

COMMENT = re.compile(r"\{#-?(.*?)-?#\}", re.DOTALL)
TAGS_ONLY = re.compile(r"\s*(?:\{%-?.*?-?%\}\s*)+")
SLOT_ONLY = re.compile(r"\s*\{[A-Za-z_]+\}\s*")
INCLUDE = re.compile(r"""\{%-?\s*include\s+["']([^"']+)["']""")
TOKEN = re.compile(r"[;,\s]+")
COMMIT = re.compile(r"GIT-\d+")
SHAPE = "shape"

BANNED = re.compile(
    r"\b(?:span(?:s|ned|ning)?|stretch(?:es|ed|ing)?|runs?|running"
    r"|group(?:s|ed|ing|ings)?|candidates?|windows?|waves?|nodal"
    r"|record(?:s|ed|ing)?|the\s+models?)\b",
    re.IGNORECASE,
)
QUOTED = re.compile(r'"(?:[^"\n]|\n(?![ \t]*\n))*"|“(?:[^”\n]|\n(?![ \t]*\n))*”')
IDENTIFIER = re.compile(r"`[A-Za-z_][A-Za-z0-9_.]*`")


def known() -> set[str]:
    return set(inventoryids.IDS_FILE.read_text().split())


@dataclass
class Line:
    number: int
    words: str
    cites: list[str] = field(default_factory=list)

    def exempt(self) -> bool:
        return not self.words.strip() or bool(
            TAGS_ONLY.fullmatch(self.words) or SLOT_ONLY.fullmatch(self.words)
        )

    def comment_only(self) -> bool:
        return bool(self.cites) and not self.words.strip()


def lines(text: str, first: int = 1) -> list[Line]:
    """Each line with its comments taken out; a comment is held on the line it
    closes on, and the lines a long comment crosses are left blank."""
    cites: dict[int, list[str]] = defaultdict(list)

    def blank(match: re.Match) -> str:
        cites[text.count("\n", 0, match.end())].append(match.group(1))
        return "\n" * match.group(0).count("\n")

    words = COMMENT.sub(blank, text).split("\n")
    return [Line(first + i, said, cites[i]) for i, said in enumerate(words)]


def citation_faults(body: str, ids: set[str]) -> list[str]:
    tokens = [t for t in TOKEN.split(body.strip()) if t]
    if not tokens:
        return ["an empty comment"]
    wrong = [t for t in tokens if t != SHAPE and t not in ids]
    if wrong:
        return [f"not inventory ids: {', '.join(wrong)}"]
    if all(COMMIT.fullmatch(t) for t in tokens):
        return ["a commit message alone is not a source"]
    return []


def faults(text: str, ids: set[str], first: int = 1) -> list[str]:
    """What breaks the citation rule in one file's body, line by line."""
    found = []
    rows = lines(text, first)
    for i, row in enumerate(rows):
        for body in row.cites:
            found += [f"{row.number}: {fault}" for fault in citation_faults(body, ids)]
        if "{#" in row.words or "#}" in row.words:
            found.append(f"{row.number}: a comment that does not close")
        if row.exempt() or row.cites or (i and rows[i - 1].comment_only()):
            continue
        found.append(f"{row.number}: no citation: {row.words.strip()[:70]}")
    return found


def banned(text: str) -> list[str]:
    """Each banned word left once the quotations are blanked, with its line."""

    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    open_text = IDENTIFIER.sub(blank, QUOTED.sub(blank, text))
    return [
        f"{open_text.count(chr(10), 0, m.start()) + 1}: {m.group(0)!r}"
        for m in BANNED.finditer(open_text)
    ]


def body_of(path: Path) -> tuple[str, int]:
    """A file's body, decrypted, and the line number the body starts on."""
    text = read(path)
    _, body = split(text)
    return body, text[: len(text) - len(body)].count("\n") + 1


def included(body: str) -> list[str]:
    return INCLUDE.findall(body)


@pytest.fixture(scope="module")
def bodies() -> dict[str, tuple[str, int]]:
    """The prompt and every fragment it includes, by path under the prompts."""
    if not PROMPT.is_file() or not key_present():
        pytest.skip("the private prompts are not installed, or no key opens them")
    found = {PROMPT.name: body_of(PROMPT)}
    waiting = included(found[PROMPT.name][0])
    while waiting:
        name = waiting.pop(0)
        if name not in found:
            found[name] = body_of(next(d / name for d in DIRS if (d / name).is_file()))
            waiting += included(found[name][0])
    return found


@pytest.fixture
def rendered(bodies, monkeypatch) -> str:
    """The prompt as cluster detection sends it: the private files through the
    app's Jinja loader, then the slots filled by `clusters._prompt`."""
    monkeypatch.setitem(
        prompts.READ,
        "CLUSTER_PROMPT",
        PromptDir(DIRS).text("cluster"),
    )
    return clusters._prompt([], [], {}, [], None)


def first_cited(rows: list[Line]) -> int:
    """The index of the first instruction line that carries a citation."""
    for i, row in enumerate(rows):
        if not row.exempt() and (row.cites or (i and rows[i - 1].comment_only())):
            return i
    raise AssertionError("no instruction line of the prompt carries a citation")


def test_every_instruction_line_of_the_cluster_prompt_names_its_sources(bodies):
    # R-0858
    ids = known()
    found = [
        f"{name}:{fault}"
        for name, (body, first) in bodies.items()
        for fault in faults(body, ids, first)
    ]
    assert not found, f"{len(found)} faults:\n" + "\n".join(found)


def test_the_cluster_prompt_includes_its_three_fragments(bodies):
    # R-0858
    assert {
        "fragments/cluster_terms.md",
        "fragments/cluster_vocabulary.md",
        "fragments/cluster_examples.md",
    } <= set(bodies)


def test_the_rendered_cluster_prompt_holds_no_comment(rendered):
    # R-0858
    assert "{#" not in rendered and "#}" not in rendered
    assert "{existing}" not in rendered and "{events}" not in rendered


def test_no_banned_word_reaches_the_rendered_cluster_prompt(rendered):
    # R-0858
    found = banned(rendered)
    assert not found, f"{len(found)} banned words:\n" + "\n".join(found)


def test_the_guard_flags_a_line_whose_citation_is_taken_out(bodies):
    # R-0858
    body, first = bodies[PROMPT.name]
    ids = known()
    rows = lines(body, first)
    i = first_cited(rows)
    source = body.split("\n")
    source[i] = COMMENT.sub("", source[i])
    if i and rows[i - 1].comment_only():
        source[i - 1] = COMMENT.sub("", source[i - 1])
    flagged = f"{rows[i].number}: no citation: {rows[i].words.strip()[:70]}"
    assert flagged not in faults(body, ids, first)
    assert flagged in faults("\n".join(source), ids, first)


def test_the_guard_flags_a_misspelled_id(bodies):
    # R-0858
    body, first = bodies[PROMPT.name]
    ids = known()
    match = next(
        (m for m in COMMENT.finditer(body) if set(TOKEN.split(m.group(1))) & ids), None
    )
    assert match, "no comment of the prompt cites an inventory id"
    good = next(t for t in TOKEN.split(match.group(1)) if t in ids)
    wrong = good.replace("-", "-0", 1)
    assert wrong not in ids
    cut = match.start(1) + match.group(1).index(good)
    mutated = body[:cut] + wrong + body[cut + len(good) :]
    after = faults(mutated, ids, first)
    assert any(f"not inventory ids: {wrong}" in fault for fault in after)


SAMPLE_IDS = {"P-001", "S-002", "R-0858", "GIT-1"}
SAMPLE = """{% include "fragments/a.md" %}{% include "fragments/b.md" %}
{# shape #}
HEADING
A rule with its source on the same line. {# P-001; S-002 #}
{# R-0858 #}
A rule with its source on the line above.
The line after that is not covered by it.

{existing}
A rule with an id that is not in the file. {# P-01 #}
A rule resting on a commit message alone. {# GIT-1 #}
A rule resting on a commit and a ruling. {# GIT-1, R-0858 #}
{# a note, not a citation #}
{#   #}

A rule with an unclosed comment {# P-001
"""


def test_the_guard_reads_lines_as_its_rule_says():
    # R-0858
    assert faults(SAMPLE, SAMPLE_IDS, first=10) == [
        "16: no citation: The line after that is not covered by it.",
        "19: not inventory ids: P-01",
        "20: a commit message alone is not a source",
        "22: not inventory ids: a, note, not, a, citation",
        "23: an empty comment",
        "25: a comment that does not close",
        "25: no citation: A rule with an unclosed comment {# P-001",
    ]


def test_the_guard_reads_a_long_comment_as_closing_on_its_last_line():
    # R-0858
    text = "{# P-001;\n   S-002 #}\nA rule under a long citation.\nAn uncited one."
    assert faults(text, SAMPLE_IDS) == ["4: no citation: An uncited one."]


def test_banned_words_are_found_outside_quotations_only():
    # R-0858
    text = (
        "The coach reads a run of events and groups them into a window.\n"
        'Records spanned years; "a run they named" stays; “a stretch” stays.\n'
        "The key `run` stays, `a run` does not; things ran higher.\n"
        '"An open quote\n\ncrosses a blank line into a candidate".\n'
        "The model's answer and the models it tried."
    )
    assert banned(text) == [
        "1: 'run'",
        "1: 'groups'",
        "1: 'window'",
        "2: 'Records'",
        "2: 'spanned'",
        "3: 'run'",
        "6: 'candidate'",
        "7: 'The model'",
        "7: 'the models'",
    ]


# The ids file itself, written by bin/inventoryids.py from the inventory.

SAMPLE_INVENTORY = """# The inventory

## 1. The inventory

### Passages from the literature

| id | kind | text |
|---|---|---|
| P-010 | passage | a passage |
| P-002 | passage | another |

### Rulings

| id | kind | text |
|---|---|---|
| R-0858 | ruling | a ruling |
| GIT-10 | commit message | a commit |
| GIT-2 | commit message | a commit |
| DR-01 | derivation rule | a rule |
| DOC-07 | doc | a doc row |
| S-201 | statement | a statement |

## 2. The current prompt, line by line

| line | text | rests on |
|---|---|---|
| P-999 | a row outside section 1 | P-002 |
"""


def test_the_ids_are_section_one_only_sorted_by_prefix_then_number():
    # R-0858
    assert inventoryids.ids(SAMPLE_INVENTORY) == [
        "DOC-07",
        "DR-01",
        "GIT-2",
        "GIT-10",
        "P-002",
        "P-010",
        "R-0858",
        "S-201",
    ]


def test_an_id_of_no_known_shape_stops_the_script():
    # R-0858
    with pytest.raises(ValueError, match="P-12 is not an inventory id shape"):
        inventoryids.ids(SAMPLE_INVENTORY.replace("| P-010 |", "| P-12 |"))


def test_an_id_given_twice_stops_the_script():
    # R-0858
    with pytest.raises(ValueError, match="P-002 is given twice"):
        inventoryids.ids(SAMPLE_INVENTORY.replace("| P-010 |", "| P-002 |"))


def test_an_inventory_with_no_section_one_stops_the_script():
    # R-0858
    with pytest.raises(ValueError, match="no ids found"):
        inventoryids.ids(SAMPLE_INVENTORY.replace("## 1.", "## One"))


def test_check_says_stale_and_writes_nothing(tmp_path, monkeypatch):
    # R-0858
    inventory = tmp_path / "INVENTORY.md"
    inventory.write_text(SAMPLE_INVENTORY)
    ids_file = tmp_path / "inventory-ids.txt"
    monkeypatch.setattr(inventoryids, "IDS_FILE", ids_file)
    assert inventoryids.main([str(inventory), "--check"]) == 1
    assert not ids_file.exists()
    assert inventoryids.main([str(inventory)]) == 0
    assert ids_file.read_text() == inventoryids.listing(SAMPLE_INVENTORY)
    assert inventoryids.main([str(inventory), "--check"]) == 0


def test_with_no_path_the_inventory_is_read_under_the_corpus_setting(
    tmp_path, monkeypatch
):
    # R-0858
    monkeypatch.setenv(inventoryids.SOURCES, str(tmp_path))
    assert (
        inventoryids.inventory_path([]) == tmp_path / "research/clusters/INVENTORY.md"
    )
    monkeypatch.delenv(inventoryids.SOURCES)
    with pytest.raises(SystemExit):
        inventoryids.inventory_path([])


def test_the_committed_ids_file_is_sorted_unique_and_of_the_known_shapes():
    # R-0858
    listed = inventoryids.IDS_FILE.read_text().splitlines()
    assert listed
    assert all(inventoryids.SHAPES.fullmatch(one) for one in listed)
    assert listed == sorted(set(listed), key=inventoryids._order)
