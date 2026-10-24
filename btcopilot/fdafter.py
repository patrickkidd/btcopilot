"""A desktop file made into a new diagram from the Diagrams page
[Oracle: R-0899, R-0902]. The request reads the file, builds it as it stands
with no model call, saves it as one change-log turn and puts the app on it.
The worker then mails the import record and groups the clusters
[Oracle: R-0932].

The case report needs nothing here: a report is out of date by a rule on the
change log the import's write already satisfies (R-0825), and coverage is
worked out from the diagram each time it is read.
"""

import datetime
import io
import pickle
import uuid
import zipfile
from pathlib import Path

from werkzeug.exceptions import RequestEntityTooLarge

from btcopilot import (
    attachments,
    clusters,
    extensions,
    fdfile,
    fdimport,
    fdledger,
)
from btcopilot.extensions import db
from btcopilot.models import Diagram, User

TASK = "fd_import_landed"
REGROUP = "clusters_regroup"
NOT_FD = "That is not a Family Diagram file."
#: The ending of a desktop file's name.
SUFFIX = ".fd"


def scene(data: bytes) -> tuple[bytes, dict]:
    """The diagram.pickle of an upload, itself or inside a zip of the .fd
    folder, and the scene read from it; a file that is neither is refused in
    one sentence, and one saved before events had a list of their own in the
    reader's words [Oracle: R-0914, R-0882]."""
    if zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as folder:
            found = [
                one
                for one in folder.infolist()
                if Path(one.filename).name == fdfile.PICKLE
            ]
            if len(found) != 1:
                raise ValueError(NOT_FD)
            if found[0].file_size > attachments.MAX_BYTES:
                raise RequestEntityTooLarge(attachments.TOO_BIG)
            data = folder.read(found[0])
    try:
        return data, fdfile.read(data)
    except fdfile.TooOld:
        raise
    except (pickle.UnpicklingError, EOFError, ValueError):
        raise ValueError(NOT_FD)


def made(user: User, name: str, fd: dict) -> tuple[Diagram, str, fdimport.Imported]:
    """The file as a new diagram of the user's, the app put on it; returns
    the diagram, the turn that wrote it and the import."""
    turn = fdimport.TURN.format(uuid.uuid4().hex)
    out = fdimport.build(fd)
    diagram = fdimport.save(user.id, name, out, yes=True, turn=turn)
    user.current_diagram_id = diagram.id
    db.session.commit()
    return diagram, turn, out


def enqueue(diagram: Diagram, user_id: int, turn: str, data: bytes) -> None:
    """The file held for the worker under the turn that wrote it, then the
    worker told to mail its record and group its clusters."""
    attachments.hold(turn, data)
    send(diagram.id, user_id, turn)


def send(diagram_id: int, user_id: int, turn: str) -> None:
    extensions.celery.send_task(TASK, args=[diagram_id, user_id, turn])


def run(diagram_id: int, user_id: int, turn: str) -> None:
    """The task: the import record mailed, and the diagram's clusters grouped."""
    data = attachments.held(turn)
    if data is None:
        raise attachments.Gone(attachments.GONE)
    fd = fdfile.read(data)
    diagram = db.session.get(Diagram, diagram_id)
    out = fdimport.build(fd)
    land(diagram, db.session.get(User, user_id), f"{diagram.name}{SUFFIX}", fd, out)
    attachments.drop(turn)


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
        file, fd, fdimport.became(imported), imported.decisions, datetime.date.today()
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
