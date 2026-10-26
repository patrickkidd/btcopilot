"""The theory expert's concept pages, one per code, read beside the coding
work by coders alone; the public edition is made outside the app (R-0541)."""

import logging
import re
from enum import StrEnum

from flask import abort, current_app, render_template, url_for
from markdown_it import MarkdownIt
from markupsafe import Markup

from btcopilot.review.routes import coder
from btcopilot.routes import bp
from btcopilot.theorypages import Unavailable

_log = logging.getLogger(__name__)
_markdown = MarkdownIt("commonmark").enable("table")
GUIDE = "Auditor's Coding Guide"
LINK = re.compile(r"(?<!!)\[((?:[^\[\]\n]|\[[^\]\n]*\])*)\]\(([^)\s]+)\)")
CODE_STATUS = "Status of the code"
SENTENCE = re.compile(r"(?<=\.) (?=\S)")
LIST_ITEM = re.compile(r"\s*(?:[-*] |\d+\. )?")
INTRO = re.compile(r"\A.*?(?=^## Coder summary$)", re.M | re.S)
INTRO_ITEM = re.compile(r"^- .*\n", re.M)
CONFIDENTIAL_HEADING = re.compile(r"^(#+ .*?) \(confidential\)$", re.M)


class Mark(StrEnum):
    Public = "PUBLIC"
    Confidential = "CONFIDENTIAL"


MARK = re.compile(rf" · (?:{'|'.join(Mark)})\b")
MAINTAINER_SENTENCE = re.compile(rf"\]\(README\.md|\b(?:{'|'.join(Mark)})\b")


def links(text: str, targets: dict[str, str]) -> str:
    """Point links to the pages at `targets` (file name to URL); every other
    link becomes its plain label, since coders cannot open those files."""

    def link(m):
        label, target = m.groups()
        path, sep, anchor = target.partition("#")
        if not path:
            return m.group(0)
        if path in targets:
            return f"[{label}]({targets[path]}{sep}{anchor})"
        return label

    return LINK.sub(link, text)


def page_table(text: str) -> str:
    """The index as coders read it: its title and the table of pages, without
    the column on the state of the code (R-0939)."""
    lines = text.splitlines()
    rows = [line.strip("|").split("|") for line in lines if line.startswith("|")]
    drop = [cell.strip() for cell in rows[0]].index(CODE_STATUS)
    table = ["|" + "|".join(c for i, c in enumerate(r) if i != drop) + "|" for r in rows]
    return "\n".join([lines[0], "", *table]) + "\n"


def _without_maintainer_sentences(line: str) -> str | None:
    if not MAINTAINER_SENTENCE.search(line):
        return line
    prefix = LIST_ITEM.match(line).group(0)
    body = SENTENCE.split(line[len(prefix) :])
    kept = [s for s in body if not MAINTAINER_SENTENCE.search(s)]
    return prefix + " ".join(kept) if kept else None


def unmarked(text: str) -> str:
    """A concept page without its maintainers' lines: the notes before the
    coder summary, the PUBLIC or CONFIDENTIAL mark on entries and headings,
    and any sentence still naming a mark or pointing to README.md; every
    entry stays (R-0939)."""
    text = INTRO.sub(lambda m: INTRO_ITEM.sub("", m.group(0)), text, count=1)
    text = CONFIDENTIAL_HEADING.sub(r"\1", MARK.sub("", text))
    lines = (_without_maintainer_sentences(line) for line in text.split("\n"))
    return "\n".join(line for line in lines if line is not None)


def _render(text: str, names: list[str]):
    targets = {f"{n}.md": url_for("app.theory_page", name=n) for n in names}
    targets["INDEX.md"] = url_for("app.theory_index")
    return render_template(
        "theory.html",
        guide=GUIDE,
        title=re.match(r"# (.+)", text).group(1),
        body=Markup(_markdown.render(links(text, targets))),
    )


@bp.errorhandler(Unavailable)
def _unavailable(e):
    """Where the pages live and what to set is for the log, not the reader."""
    _log.error(str(e))
    return (
        render_template(
            "theory.html",
            guide=GUIDE,
            title=GUIDE,
            error=f"The {GUIDE} can't be loaded right now.",
        ),
        503,
    )


@bp.route("/theory")
def theory_index():
    coder()
    pages = current_app.extensions["theory"]
    return _render(page_table(pages.text("INDEX")), pages.names())


@bp.route("/theory/<name>")
def theory_page(name):
    coder()
    pages = current_app.extensions["theory"]
    names = pages.names()
    if name not in names:
        abort(404)
    return _render(unmarked(pages.text(name)), names)
