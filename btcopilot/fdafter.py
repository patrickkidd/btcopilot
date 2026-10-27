"""A desktop file made into a new diagram from the Diagrams page
[Oracle: R-0899, R-0902]. The request reads the file, builds it as it stands
with no model call, each object on its own, saves it as one change-log turn
and puts the app on it [Oracle: R-0947]. The worker then mails the import
record the request wrote from that one build [Oracle: R-0932].

The case report needs nothing here: a report is out of date by a rule on the
change log the import's write already satisfies (R-0825), and coverage is
worked out from the diagram each time it is read.
"""

import datetime
import io
import pickle
import zipfile
import zlib
from pathlib import Path

from sqlalchemy import func
from werkzeug.exceptions import RequestEntityTooLarge

from btcopilot import (
    attachments,
    clusters,
    extensions,
    fdfile,
    fdimport,
    fdledger,
    prompts,
    recordtext,
)
from btcopilot.admin import setting
from btcopilot.admin.setting import SettingKey
from btcopilot.discussions import coach_said, sitting
from btcopilot.extensions import db
from btcopilot.llmutil import Spent, resolve_model
from btcopilot.models import Diagram, ModelCall, Purpose, User
from btcopilot.pricing import cost
from btcopilot.schema import EventKind

TASK = "fd_import_landed"
REGROUP = "clusters_regroup"
NOT_FD = "That is not a Family Diagram file."
DAMAGED = "That file is damaged and cannot be opened."
LOCKED = "That file is locked with a password and cannot be opened."
# The flag a zip sets on a file it holds encrypted.
ENCRYPTED = 0x1
# How far back, and how many calls, the coding question's cost is read from.
COST_DAYS = 30
RECENT_CALLS = 20
# The repo's rough count of characters to a token (refs.py), for a cost read
# from prices when the model has too few calls to read it from.
CHARS_PER_TOKEN = 4
# What a coach call writes, when the ledger holds no coach call to read it from.
OUTPUT_TOKENS = 800
# Measured 2026-10-24 on the third free subscription run: the coach's first
# coding pass over the clinic case cost $1.23 without prompt caching for its 78
# events that can take codes and had none.
PER_EVENT_COST = 0.016
CODABLE = (EventKind.Noted.value, EventKind.Shift.value)
CODES = ("symptom", "anxiety", "functioning", "relationship")
# The first bytes of a zip, and of a pickle the desktop writes (protocol 2 on).
ZIP = b"PK\x03\x04"
PICKLED = b"\x80"
# The folder a Mac zip keeps its file forks in, never part of the package.
MAC_FORKS = "__MACOSX"
#: The ending of a desktop file's name.
SUFFIX = ".fd"


def scene(data: bytes) -> dict:
    """The scene read from an upload's diagram.pickle, itself or inside a zip
    of the .fd folder; a file that is neither, or one that cannot be opened at
    all, is refused in one sentence, and one saved before events had a list of
    their own in the reader's words [Oracle: R-0914, R-0882, R-0947]."""
    # read by what the bytes are, never by the file's name: a browser sends
    # an .fd package as a zip under any name, or its diagram.pickle itself
    if data.startswith(ZIP):
        data = _unzipped(data)
    if not data.startswith(PICKLED):
        raise ValueError(NOT_FD)
    try:
        return fdfile.read(data)
    except fdfile.TooOld:
        raise
    except (pickle.UnpicklingError, EOFError, ValueError, TypeError, AttributeError, IndexError, KeyError):
        raise ValueError(NOT_FD)


def _unzipped(data: bytes) -> bytes:
    """The diagram.pickle inside a zip of the .fd folder."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as folder:
            found = next(
                (
                    one
                    for one in folder.infolist()
                    if Path(one.filename).name == fdfile.PICKLE
                    and MAC_FORKS not in Path(one.filename).parts
                ),
                None,
            )
            if found is None:
                raise ValueError(NOT_FD)
            if found.flag_bits & ENCRYPTED:
                raise ValueError(LOCKED)
            if found.file_size > attachments.MAX_BYTES:
                raise RequestEntityTooLarge(attachments.TOO_BIG)
            return folder.read(found)
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError):
        raise ValueError(DAMAGED)


def made(user: User, name: str, fd: dict) -> tuple[Diagram, fdimport.Imported, str]:
    """The file as a new diagram of the user's, the app put on it, and the
    import's report written into its chat as the coach's message, a note
    that stays [Oracle: R-0947]; returns the diagram, the import and the
    message's words."""
    out = fdimport.build(fd)
    diagram = fdimport.save(user.id, name, out, yes=True)
    user.current_diagram_id = diagram.id
    # the person's speaker is set from who they say they are with their own
    # first words, so nothing is added to the diagram here
    note = coach_said(sitting(user, diagram), out.said())
    db.session.commit()
    return diagram, out, note.text


def mail(user: User, diagram: Diagram, fd: dict, imported: fdimport.Imported) -> None:
    """The import record written from the request's own build, and the worker
    told to mail it: the file is never read or built a second time
    [Oracle: R-0932, R-0947]."""
    file = f"{diagram.name}{SUFFIX}"
    send(user.id, file, diagram.name, ledger(file, fd, imported))


def send(user_id: int, file: str, name: str, text: str) -> None:
    extensions.celery.send_task(TASK, args=[user_id, file, name, text])


def run(user_id: int, file: str, name: str, text: str) -> None:
    """The task: the import record mailed."""
    fdledger.send(db.session.get(User, user_id).username, file, name, text)


def land(
    diagram: Diagram,
    user: User,
    file: str,
    fd: dict,
    imported: fdimport.Imported,
) -> None:
    """What follows once the diagram is saved, on the worker: the import record
    mailed. Its clusters are grouped once the person says who the case is
    about, which the sheet after an import always asks, so they are named for
    the right person (R-0935)."""
    fdledger.send(user.username, file, diagram.name, ledger(file, fd, imported))


def ledger(file: str, fd: dict, imported: fdimport.Imported) -> str:
    return fdledger.text(
        file,
        fdimport.listed(fd),
        fdimport.became(imported),
        imported.decisions,
        datetime.date.today(),
    )


def regroup(diagram_id: int, turn_id: str, user_id: int) -> None:
    """The diagram's clusters grouped again on the worker, under `turn_id`, as
    after an import: picking who the case is about changes how its periods are
    written [Oracle: R-0935]."""
    extensions.celery.send_task(
        REGROUP, args=[diagram_id], kwargs={"turn_id": turn_id, "user_id": user_id}
    )


def regrouped(diagram_id: int, *, turn_id: str, user_id: int) -> None:
    """The worker's regroup task; it returns nothing, since the queue keeps a
    task's answer as JSON and the regroup is in the diagram itself."""
    catch_up(diagram_id, turn_id=turn_id, user_id=user_id)


def catch_up(diagram_id: int, *, turn_id: str, user_id: int) -> clusters.Regroup | None:
    """Regroup under the import's own turn; None when the events left nothing
    to regroup."""
    regrouped = clusters.sync(diagram_id, turn_id=turn_id, user_id=user_id)
    db.session.commit()
    return regrouped


def coding_cost(user_id: int, diagram: Diagram) -> dict:
    """What the one coach turn the coding question's Yes starts would cost,
    in dollars, low to high, read from what the user's coach model has cost
    [Oracle: R-0902]. With RECENT_CALLS or more of its calls in the last
    COST_DAYS days the low end is the median call times the median calls a
    turn made; with fewer, the model's prices on this diagram's coach prompt
    and the median a coach call of any model wrote in those days
    (OUTPUT_TOKENS with none), once per such turn. The high end is what coding each of the diagram's
    events that can take codes and have none costs, at PER_EVENT_COST, since
    the coach codes in turns that end on their own (R-0936)."""
    model = resolve_model(setting.read(SettingKey.CoachModel, user_id))
    since = datetime.datetime.utcnow() - datetime.timedelta(days=COST_DAYS)
    recent = (ModelCall.purpose == Purpose.Coach, ModelCall.created_at >= since)
    calls = ModelCall.query.filter(*recent, ModelCall.model == model)
    per_turn = (
        db.session.query(func.count().label("calls"))
        .filter(*recent, ModelCall.model == model)
        .group_by(ModelCall.turn_id)
        .subquery()
    )
    steps = _median(db.session.query(per_turn.c.calls), per_turn.c.calls) or 1
    if calls.count() >= RECENT_CALLS:
        low = float(_median(calls, ModelCall.cost_usd)) * steps
    else:
        words = prompts.get_agent_prompt(
            record=recordtext.outline(diagram.get_diagram_data(), diagram.version, None)
        )
        said = _median(ModelCall.query.filter(*recent), ModelCall.output_tokens)
        output = OUTPUT_TOKENS if said is None else int(said)
        call = float(
            cost(model, Spent(input=len(words) // CHARS_PER_TOKEN, output=output))
        )
        low = call * steps
    high = uncoded(diagram.get_diagram_data()) * PER_EVENT_COST
    return {"low": round(min(low, high), 2), "high": round(high, 2)}


def _median(query, column):
    """The median of one column over a query, read as its one or two middle
    rows rather than every row; None when there are none."""
    count = query.count()
    if not count:
        return None
    middle = [
        value
        for (value,) in query.with_entities(column)
        .order_by(column)
        .offset((count - 1) // 2)
        .limit(2 - count % 2)
    ]
    return sum(middle) / len(middle)


def uncoded(data) -> int:
    """The events the coach could code: noted events and shifts with no code
    for what moved."""
    return sum(
        1
        for event in data.events
        if event.get("kind") in CODABLE and not any(event.get(name) for name in CODES)
    )
