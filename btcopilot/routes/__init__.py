import enum
import logging
import re
import uuid

from flask import Blueprint, abort, request
from flask_wtf.csrf import CSRFError, generate_csrf
from werkzeug.exceptions import Forbidden

import btcopilot
from btcopilot import auth
from btcopilot.auth.signin import origin
from btcopilot.extensions import csrf, db
from btcopilot import record
from btcopilot.models import Author, Discussion
from btcopilot.models import Diagram
from btcopilot.discussions import (  # noqa: F401  routes import them from here
    chats,
    create_discussion,
    family,
    last_activity,
    newest,
    sitting,
    utc_iso,
)
from btcopilot.review.freeze import frozen
from btcopilot.schema import ItemKind
from btcopilot.theorypages import TheoryPages

_log = logging.getLogger(__name__)

bp = Blueprint(
    "app",
    __name__,
    url_prefix="/app",
    template_folder="templates",
    static_folder="../static",
)


# What a browser fetches without its cookie: the service worker, the manifest,
# the icons the manifest names, and the icon iOS puts on the home screen; and
# where a report is posted, which takes no CSRF token, so the browser's word
# that the post came from this site stands in for one.
PUBLIC = {"app.service_worker", "app.manifest", "app.apple_touch_icon", "app.create_report"}
TOKENLESS = {"app.create_report"}
PUBLIC_STATIC = re.compile(r"web/icon-\w+\.png")


class Access(enum.StrEnum):
    """How the app is on a diagram: the user's own, shared with them
    read-write, or another person's that an admin opened to look at, which no
    access right grants and nothing may write to (Patrick, 2026-10-01)."""

    Own = "own"
    Shared = "shared"
    AdminView = "admin-view"


def access(dia: Diagram, user) -> Access | None:
    """None when the user may not put the app on the diagram at all."""
    if dia.user_id == user.id:
        return Access.Own
    if dia.check_write_access(user):
        return Access.Shared
    if user.has_role(btcopilot.ROLE_ADMIN):
        return Access.AdminView
    return None


def chatter(user, dia: Diagram | None = None):
    """Whose sittings the app shows on `dia`, or on the diagram the app is on:
    the user's own, or on a diagram an admin is only viewing, the sittings of
    the person it belongs to."""
    dia = dia or user.current_diagram or user.free_diagram
    if dia is not None and access(dia, user) is Access.AdminView:
        return dia.user
    return user


class ReadOnly(Forbidden):
    description = "this diagram is open read-only"


class FetchSite(enum.StrEnum):
    SameOrigin = "same-origin"
    Typed = "none"


def public() -> bool:
    if request.endpoint == "app.static":
        return bool(PUBLIC_STATIC.fullmatch(request.view_args["filename"]))
    return request.endpoint in PUBLIC


@bp.before_request
def _authenticate():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if request.endpoint in TOKENLESS:
            _same_origin()
        else:
            csrf.protect()
    if not public():
        auth.authenticate_web()


def _same_origin():
    if (
        request.headers.get("Sec-Fetch-Site") not in (FetchSite.SameOrigin, FetchSite.Typed)
        and request.headers.get("Origin") != origin()
    ):
        _log.warning(f"Cross-site post to {request.path} from {request.remote_addr}")
        abort(403)


@bp.errorhandler(CSRFError)
def _csrf_error(e):
    _log.warning(f"CSRF error: {e.description} from {request.remote_addr}")
    return e.description, 400


@bp.errorhandler(ReadOnly)
def _read_only(e):
    """Said in words, where every other refusal is a bare Forbidden."""
    return e.description, 403


@bp.errorhandler(ValueError)
def _value_error(e):
    """A rejected value is the client's fault, not a server fault: every
    endpoint here validates by raising ValueError."""
    return str(e), 400


@bp.errorhandler(record.Invalid)
def _invalid_record(e):
    """A write the record itself refuses — a bond of one person with themselves,
    say. The editor offered it, so it is told in plain words rather than shown
    a server error."""
    return e.plain, 400


@bp.context_processor
def _inject_globals():
    return {"csrf_token": generate_csrf}


def user_sessions(user, diagram_id: int | None = None) -> list[Discussion]:
    """The user's sessions on one diagram, most recently active first. Without
    a diagram it is the one the app is on."""
    return newest(chats(chatter(user), diagram_id or user.diagram_in_use()))


def current_session(user, create: bool = False) -> Discussion | None:
    """The sitting last spoken in; with `create`, the one the next words go
    into, which is a new sitting once the family has been quiet a while."""
    if create:
        return sitting(user, family(user, writable_diagram()))
    found = user_sessions(user)
    return found[0] if found else None


def owned_session(session_id: int) -> Discussion:
    """Another user's session is a 404, not a 403: the app never confirms that
    a session it will not show exists. An admin viewing another person's
    diagram reads that person's sessions; every write on one still passes
    `require_write_access`. A discussion missing either chat
    speaker id is not a session either — see `user_sessions`."""
    discussion = db.session.get(Discussion, session_id)
    if (
        discussion is None
        or discussion.user_id != chatter(auth.current_user()).id
        or discussion.chat_user_speaker_id is None
        or discussion.chat_ai_speaker_id is None
    ):
        abort(404)
    return discussion


def diagram():
    """The diagram every surface reads and writes: the one the app is
    on, which is the free one until the user switches."""
    user = auth.current_user()
    return user.current_diagram or user.free_diagram


def asked_diagram():
    """The diagram a request names with `?diagram_id=`, which is how the coding
    screen writes onto the record that coding is of rather than onto the
    coder's own family. Without one it is the diagram the app is on."""
    asked = request.args.get("diagram_id", type=int)
    if asked is None:
        return diagram()
    found = db.session.get(Diagram, asked)
    if found is None:
        abort(404)
    return found


def require_write_access(dia):
    """The write gate every mutating route shares: a diagram reached only
    through a read-only grant refuses the write outright, and so does one a
    coder has already called done in the review."""
    if dia is None:
        return dia
    if not dia.check_write_access(auth.current_user()):
        raise ReadOnly()
    if frozen(dia.id):
        abort(409, "that coding is done and its record no longer takes edits")
    return dia


def writable_diagram():
    """The diagram every writing route mutates — the one the request names, or
    the one the app is on — refused if the user may only read it."""
    return require_write_access(asked_diagram())


def delta(kind: ItemKind, item_id, field, after) -> dict:
    return {"item_kind": kind.value, "item_id": item_id, "field": field, "after": after}


def edit(deltas: list[dict]):
    """A hand edit on the page, logged as the user's own turn exactly as the
    coach's writes are, so undo and the coach's read of recent changes see it
    (R-0084)."""
    dia = writable_diagram()
    if dia is None:
        abort(404)
    return record.apply(
        dia.id,
        deltas,
        author=Author.User,
        turn_id=uuid.uuid4().hex,
        user_id=auth.current_user().id,
    )


from btcopilot.routes import (  # noqa: E402  bp must exist first
    diagrams,
    events,
    fixtures,
    interactions,
    notifications,
    pairbonds,
    productevents,
    people,
    play,
    questions,
    recordings,
    reports,
    sessions,
    settings,
    theory,
    turns,
    users,
    web,
)


def init_app(app):
    app.extensions["theory"] = TheoryPages(
        repo=app.config["THEORY_REPO"],
        ref=app.config["THEORY_REF"],
        path=app.config["THEORY_PATH"],
        token=app.config.get("THEORY_GITHUB_TOKEN"),
    )
    # the reports each sender made in the last hour
    app.extensions["reports"] = {}
    app.register_blueprint(bp)
