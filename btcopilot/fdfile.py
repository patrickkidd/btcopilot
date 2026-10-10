"""A Family Diagram desktop file read with plain Python: the pickled scene in
an .fd bundle, its five Qt value types turned into plain values, and no Qt
loaded [Oracle: R-0854]."""

import datetime
import io
import pickle
from pathlib import Path

PICKLE = "diagram.pickle"
SIP = {("sip", "_unpickle_type"), ("PyQt5.sip", "_unpickle_type")}
# Files saved before desktop 2.1.16 hold the app's own enums; each loads as
# its plain value.
ENUMS = {
    ("btcopilot.schema", name)
    for name in (
        "EventKind",
        "VariableShift",
        "RelationshipKind",
        "DateCertainty",
        "PersonKind",
    )
}
# The desktop's 2.0.12b1 upgrade moved events out of people and pair-bonds;
# it upgrades every file saved at or before it (compat.UP_TO) [Oracle: R-0855].
OLDEST = (2, 0, 12, 1)
TOO_OLD = (
    "This file was saved by Family Diagram {}, before events had a list of "
    "their own. Open it in Family Diagram and save it, then import it again."
)


def _date(y, m, d) -> str | None:
    return datetime.date(y, m, d).isoformat() if y > 0 else None


def _datetime(y, m, d, h=0, mi=0, s=0, *rest) -> str | None:
    """The day alone at midnight; a time of day is kept so the import can say
    it was dropped."""
    if y <= 0 or (h, mi, s) == (0, 0, 0):
        return _date(y, m, d)
    return datetime.datetime(y, m, d, h, mi, s).isoformat(sep=" ", timespec="minutes")


QT = {
    "QDateTime": _datetime,
    "QDate": _date,
    "QPointF": lambda *xy: xy,
    "QSize": lambda *wh: wh,
    "QColor": lambda *rgba: rgba,
}


def _qt(module: str, name: str, args: tuple):
    if name not in QT:
        raise ValueError(
            f"the file holds a Qt type this reader does not know: {module}.{name}"
        )
    return QT[name](*args)


class Reader(pickle.Unpickler):
    """Loads only Qt values through sip and the app's own enums; any other
    class in the file is refused, since unpickling one could run code."""

    def find_class(self, module, name):
        if (module, name) in SIP:
            return _qt
        if (module, name) in ENUMS:
            return str
        raise ValueError(
            f"the file holds a type this reader does not know: {module}.{name}"
        )


def version(text: str | None) -> tuple:
    """(major, minor, micro, beta), beta 0 for a release, as the desktop
    compares them: a release ties with its own betas."""
    if not text:
        return ()
    major, minor, micro = text.strip().split(".")
    for mark in ("b", "a"):
        if mark in micro:
            micro, beta = micro.split(mark)
            return int(major), int(minor), int(micro), int(beta)
    return int(major), int(minor), int(micro), 0


def read(source: Path | bytes) -> dict:
    """The scene dict of an .fd bundle, or of its diagram.pickle bytes."""
    if isinstance(source, Path):
        source = (source / PICKLE if source.is_dir() else source).read_bytes()
    data = Reader(io.BytesIO(source)).load()
    if version(data.get("version")) <= OLDEST:
        raise ValueError(TOO_OLD.format(data.get("version") or "before 1.0"))
    return data
