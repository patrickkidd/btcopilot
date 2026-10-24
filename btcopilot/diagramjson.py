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

A Qt tag decodes to a QtValue holding the tag's own value, and a stored pickle
is read with the desktop file's reader, so no Qt library is loaded
[Oracle: R-0913].
"""

import enum
import io
import json
import pickle

from btcopilot import fdfile, qtvalue, schema
from btcopilot.qtvalue import QtValue

TAG = "$"

ENUMS = {
    name: obj
    for name, obj in vars(schema).items()
    if isinstance(obj, type) and issubclass(obj, enum.Enum) and obj is not enum.Enum
}


class Reader(fdfile.Reader):
    """A stored pickle: its Qt values as the QtValue the JSON tag decodes to,
    the schema's enums as themselves."""

    qt = staticmethod(qtvalue.unpickled)
    classes = {
        **{("btcopilot.schema", name): cls for name, cls in ENUMS.items()},
        ("btcopilot.qtvalue", "QtValue"): QtValue,
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
    if isinstance(v, QtValue):
        return _tag(v.kind, list(v.v) if isinstance(v.v, tuple) else v.v)
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
    **{
        kind: lambda v, kind=kind: QtValue(kind, tuple(v) if isinstance(v, list) else v)
        for kind in qtvalue.SIP
    },
}


def loads(blob: bytes | None) -> dict:
    """Decode a stored blob: JSON for a row the chat app made, pickle for an older one."""
    if not blob:
        return {}
    if blob[:1] == b"{":
        return from_json(json.loads(blob.decode("utf-8")))
    return Reader(io.BytesIO(blob)).load()


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

