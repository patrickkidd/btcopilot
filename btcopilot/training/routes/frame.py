import re

from flask import Blueprint, abort, current_app, render_template, url_for

import btcopilot
from btcopilot import auth
from btcopilot.training import frameedition
from btcopilot.training.utils import get_breadcrumbs

bp = Blueprint("frame", __name__, url_prefix="/frame")


def _render(text, title, full, names):
    targets = {f"{n}.md": url_for("training.frame.page", name=n) for n in names}
    targets["INDEX.md"] = url_for("training.frame.index")
    targets["README.md"] = (
        url_for("training.frame.page", name="README")
        if full
        else url_for("training.frame.index")
    )
    breadcrumbs = get_breadcrumbs("frame")
    if title:
        breadcrumbs.append({"title": title, "url": None})
    return render_template(
        "frame.html",
        text=frameedition.links(text, targets),
        current_user=auth.current_user(),
        breadcrumbs=breadcrumbs,
    )


def _full():
    return auth.current_user().has_role(btcopilot.ROLE_AUDITOR)


@bp.route("/")
def index():
    pages = current_app.extensions["frame"]
    names = pages.names()
    full = _full()
    if full:
        text = pages.text("INDEX")
    else:
        text = frameedition.index(
            pages.text("INDEX"),
            pages.text("README"),
            {n: frameedition.public(n, pages.text(n), names) for n in names},
        )
    return _render(text, None, full, names)


@bp.route("/<name>")
def page(name):
    pages = current_app.extensions["frame"]
    names = pages.names()
    full = _full()
    if name not in names and not (full and name == "README"):
        abort(404)
    text = pages.text(name)
    if not full:
        text = frameedition.public(name, text, names)
    return _render(text, re.match(r"# (.+)", text).group(1), full, names)
