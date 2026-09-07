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

import PyQt5.sip  # noqa: F401  registers QtCore types for pickle
from PyQt5.QtCore import QDate, QDateTime, QPoint, QPointF, QSize, QSizeF, QTime, Qt
from PyQt5.QtGui import QColor

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
    if isinstance(v, QColor):
        return _tag("QColor", v.name(QColor.HexArgb) if v.isValid() else None)
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
    "QColor": lambda v: QColor(v) if v else QColor(),
}
