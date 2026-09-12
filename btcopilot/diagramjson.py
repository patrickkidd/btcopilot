"""Lossless JSON encoding of the Pro app's pickled scene payload.

The Pro app writes a scene as a pickled dict (familydiagram scene.py
``Scene.write``) holding Qt value types, non-str dict keys, tuples and
btcopilot.schema enums. JSON expresses none of those, so each is wrapped in a
tagged object ``{"$": <tag>, "v": <plain json>}``:

    QDateTime   ISO-8601 with milliseconds, "" when null
    QDate       "yyyy-MM-dd", "" when null
    QTime       "HH:mm:ss.zzz", "" when null
    QPoint      [x, y]              QPointF   [x, y]
    QSize       [w, h]              QSizeF    [w, h]
    QColor      "#aarrggbb", null when invalid
    tuple       [item, ...]
    dict        [[key, value], ...] -- only when a key is not a str
    enum        [class name, member name] -- classes visible in btcopilot.schema

A dict whose keys are all strings becomes a plain JSON object. One that carries
"$" as a key takes the tagged ``dict`` form instead, so a tag is never confused
with data. Anything else raises.
"""

import enum
import json
import pickle
import sys

import PyQt5.sip  # noqa: F401  registers QtCore types for pickle
from PyQt5.QtCore import QDate, QDateTime, QPoint, QPointF, QSize, QSizeF, QTime, Qt

from btcopilot import schema

TAG = "$"

ENUMS = {
    name: obj
    for name, obj in vars(schema).items()
    if isinstance(obj, type) and issubclass(obj, enum.Enum) and obj is not enum.Enum
}


def to_json(data: dict) -> dict:
    return _enc(data)


def from_json(doc: dict) -> dict:
    return _dec(doc)


def _tag(kind, v):
    return {TAG: kind, "v": v}


def _color_type():
    """QColor's class, or None when the Qt GUI module was never loaded.

    Colours are the only value here needing PyQt5.QtGui, and the server the Pro
    app talks to runs without that module's system libraries. A QColor cannot
    exist in a payload unless the module is already loaded, so looking the class
    up rather than importing it keeps the GUI module out of startup.
    """
    gui = sys.modules.get("PyQt5.QtGui")
    return getattr(gui, "QColor", None) if gui else None


def _color(v):
    """The one place that imports the Qt GUI module: a stored colour becoming a QColor."""
    from PyQt5.QtGui import QColor

    return QColor(v) if v else QColor()


def _enc(v):
    if isinstance(v, enum.Enum):
        return _tag("enum", [type(v).__name__, v.name])
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, list):
        return [_enc(x) for x in v]
    if isinstance(v, tuple):
        return _tag("tuple", [_enc(x) for x in v])
    if isinstance(v, dict):
        if all(isinstance(k, str) and k != TAG for k in v):
            return {k: _enc(x) for k, x in v.items()}
        return _tag("dict", [[_enc(k), _enc(x)] for k, x in v.items()])
    if isinstance(v, QDateTime):
        return _tag("QDateTime", v.toString(Qt.ISODateWithMs))
    if isinstance(v, QDate):
        return _tag("QDate", v.toString(Qt.ISODate))
    if isinstance(v, QTime):
        return _tag("QTime", v.toString(Qt.ISODateWithMs))
    if isinstance(v, QPointF):
        return _tag("QPointF", [v.x(), v.y()])
    if isinstance(v, QPoint):
        return _tag("QPoint", [v.x(), v.y()])
    if isinstance(v, QSizeF):
        return _tag("QSizeF", [v.width(), v.height()])
    if isinstance(v, QSize):
        return _tag("QSize", [v.width(), v.height()])
    color = _color_type()
    if color is not None and isinstance(v, color):
        return _tag("QColor", v.name(color.HexArgb) if v.isValid() else None)
    raise TypeError(f"cannot encode {type(v)}")


def _dec(v):
    if isinstance(v, list):
        return [_dec(x) for x in v]
    if not isinstance(v, dict):
        return v
    if TAG not in v:
        return {k: _dec(x) for k, x in v.items()}
    return _DEC[v[TAG]](v["v"])


_DEC = {
    "enum": lambda v: ENUMS[v[0]][v[1]],
    "tuple": lambda v: tuple(_dec(x) for x in v),
    "dict": lambda v: {_dec(k): _dec(x) for k, x in v},
    "QDateTime": lambda v: QDateTime.fromString(v, Qt.ISODateWithMs),
    "QDate": lambda v: QDate.fromString(v, Qt.ISODate),
    "QTime": lambda v: QTime.fromString(v, Qt.ISODateWithMs),
    "QPointF": lambda v: QPointF(*v),
    "QPoint": lambda v: QPoint(*v),
    "QSizeF": lambda v: QSizeF(*v),
    "QSize": lambda v: QSize(*v),
    "QColor": _color,
}


def loads(blob: bytes | None) -> dict:
    """Decode a stored blob: JSON for a row the chat app made, pickle for an older one."""
    if not blob:
        return {}
    if blob[:1] == b"{":
        return from_json(json.loads(blob.decode("utf-8")))
    return pickle.loads(blob)


def dumps(data: dict) -> bytes:
    return json.dumps(to_json(data)).encode("utf-8")


def is_json(blob: bytes | None) -> bool:
    return bool(blob) and blob[:1] == b"{"


def store(blob: bytes | None) -> bytes:
    """Convert an incoming pickled blob to the stored JSON form."""
    return dumps(loads(blob))


def encode(data: dict, stored: bytes | None) -> bytes:
    """Re-encode in the format the row already holds: JSON stays JSON, pickle stays pickle."""
    return dumps(data) if is_json(stored) else pickle.dumps(data)


def wire(blob: bytes | None) -> bytes | None:
    """The pickled form the Pro and Personal apps speak; a pickle row passes through."""
    return pickle.dumps(loads(blob)) if is_json(blob) else blob
