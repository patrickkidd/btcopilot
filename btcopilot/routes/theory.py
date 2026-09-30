"""The theory expert's concept pages, one per code, read beside the coding
work by coders alone; the public edition is made outside the app (R-0541)."""

import logging
import re

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


def _render(text: str, names: list[str]):
    targets = {f"{n}.md": url_for("app.theory_page", name=n) for n in names}
    targets["INDEX.md"] = url_for("app.theory_index")
    targets["README.md"] = url_for("app.theory_page", name="README")
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
    return _render(pages.text("INDEX"), pages.names())


@bp.route("/theory/<name>")
def theory_page(name):
    coder()
    pages = current_app.extensions["theory"]
    names = pages.names()
    if name not in names and name != "README":
        abort(404)
    return _render(pages.text(name), names)
