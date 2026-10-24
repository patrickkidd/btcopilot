"""A Qt value of a Pro diagram held as the plain value its stored JSON tag
carries, read and written with no Qt library loaded [Oracle: R-0913]."""

from dataclasses import dataclass

DATES = {"QDateTime", "QDate", "QTime"}
# Qt's own truth: an empty date, a point at the origin, a size below zero and
# an invalid colour are false.
TRUTH = {
    "QDateTime": bool,
    "QDate": bool,
    "QTime": bool,
    "QPointF": any,
    "QPoint": any,
    "QSizeF": lambda v: min(v) >= 0,
    "QSize": lambda v: min(v) >= 0,
    "QColor": lambda v: v is not None,
}
# The Qt formats the app reads a date with, as the length of the ISO text.
FORMATS = {"yyyy-MM-dd": 10, "yyyy-MM-ddTHH:mm:ss": 19}
# Qt.TimeSpec: local time, UTC, an offset from UTC, a named time zone (read
# as local time, since the file does not carry the zone's rules).
LOCAL, UTC, OFFSET, ZONE = 0, 1, 2, 3


@dataclass(frozen=True)
class QtValue:
    """kind is the Qt class name; v is ISO text for a date, an (x, y) or
    (w, h) tuple, or "#aarrggbb" text for a colour."""

    kind: str
    v: str | tuple | None

    def __bool__(self) -> bool:
        return TRUTH[self.kind](self.v)

    def __reduce__(self):
        return QtValue, (self.kind, self.v)

    def toString(self, fmt: str) -> str:
        if self.kind not in DATES:
            raise TypeError(f"a {self.kind} has no text form")
        return self.v[: FORMATS[fmt]]


def _date(y, m, d) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}" if y else ""


def _time(h, mi, s, ms) -> str:
    return f"{h:02d}:{mi:02d}:{s:02d}.{ms:03d}" if h >= 0 else ""


def _zone(spec: int, offset: int | None) -> str:
    """The ISO suffix for a Qt time spec. PyQt pickles no offset, so an offset
    spec without one keeps its wall-clock time, as local time does."""
    if spec in (LOCAL, ZONE) or (spec == OFFSET and offset is None):
        return ""
    if spec == UTC:
        return "Z"
    if spec == OFFSET:
        sign, minutes = "-" if offset < 0 else "+", abs(offset) // 60
        return f"{sign}{minutes // 60:02d}:{minutes % 60:02d}"
    raise ValueError(f"Qt time spec {spec} is not one Qt has")


def _datetime(y, m, d, h, mi, s, ms, spec, offset=None) -> str:
    return f"{_date(y, m, d)}T{_time(h, mi, s, ms)}{_zone(spec, offset)}" if y else ""


SIP = {
    "QDateTime": _datetime,
    "QDate": _date,
    "QTime": _time,
    "QPointF": lambda *xy: xy,
    "QPoint": lambda *xy: xy,
    "QSizeF": lambda *wh: wh,
    "QSize": lambda *wh: wh,
    "QColor": lambda r, g, b, a: f"#{a:02x}{r:02x}{g:02x}{b:02x}",
}


def unpickled(module: str, name: str, args: tuple) -> QtValue:
    """The value a pickled Qt object holds, from the arguments sip pickled it
    with, as the text Qt itself writes."""
    if name not in SIP:
        raise ValueError(
            f"the diagram holds a Qt type this reader does not know: {module}.{name}"
        )
    return QtValue(name, SIP[name](*args))
