import collections
import json
import pickle
import subprocess
import sys

import pytest

from btcopilot import diagramjson
from btcopilot.qtvalue import QtValue
from btcopilot.schema import EventKind, VariableShift
from btcopilot.tests.fdfixtures import Qt, dumps

PICKLED = {
    "dates": [
        Qt("QDateTime", 1998, 3, 1, 0, 0, 0, 0, 0),
        Qt("QDateTime", 1983, 4, 9, 10, 30, 5, 7, 0),
        Qt("QDateTime", 0, 0, 0, -1, -1, -1, -1, 0),
        Qt("QDateTime", 2020, 1, 1, 0, 0, 0, 0, 1),
        Qt("QDate", 999, 1, 2),
        Qt("QDate", 0, 0, 0),
        Qt("QTime", 10, 3, 4, 5),
        Qt("QTime", -1, -1, -1, -1),
    ],
    "geometry": [
        Qt("QPointF", 12.5, -7.25),
        Qt("QPoint", 1, 2),
        Qt("QSize", -1, -1),
        Qt("QSizeF", 1.5, 2.5),
    ],
    "color": Qt("QColor", 1, 2, 3, 4, module="PyQt5.QtGui"),
    "kind": EventKind.Birth,
    "keys": {1: "x", (1, 2): Qt("QDate", 2000, 1, 1)},
}
# What the PyQt5 converter wrote for the same pickle, taken from it before it
# was removed.
STORED = {
    "dates": [
        {"$": "QDateTime", "v": "1998-03-01T00:00:00.000"},
        {"$": "QDateTime", "v": "1983-04-09T10:30:05.007"},
        {"$": "QDateTime", "v": ""},
        {"$": "QDateTime", "v": "2020-01-01T00:00:00.000Z"},
        {"$": "QDate", "v": "0999-01-02"},
        {"$": "QDate", "v": ""},
        {"$": "QTime", "v": "10:03:04.005"},
        {"$": "QTime", "v": ""},
    ],
    "geometry": [
        {"$": "QPointF", "v": [12.5, -7.25]},
        {"$": "QPoint", "v": [1, 2]},
        {"$": "QSize", "v": [-1, -1]},
        {"$": "QSizeF", "v": [1.5, 2.5]},
    ],
    "color": {"$": "QColor", "v": "#04010203"},
    "kind": {"$": "enum", "v": ["EventKind", "Birth"]},
    "keys": {
        "$": "dict",
        "v": [
            [1, "x"],
            [{"$": "tuple", "v": [1, 2]}, {"$": "QDate", "v": "2000-01-01"}],
        ],
    },
}


def test_encode_rejects_unknown_type():
    # R-0453
    with pytest.raises(TypeError):
        diagramjson.to_json({"x": object()})


def test_dict_carrying_the_tag_key_survives():
    # R-0083
    data = {"a": {diagramjson.TAG: 1, "b": 2}, "c": {3: "x"}}
    assert diagramjson.from_json(diagramjson.to_json(data)) == data


def test_a_stored_pickle_becomes_the_json_the_qt_converter_wrote():
    # R-0854, R-0083
    stored = json.loads(diagramjson.store(dumps(PICKLED)))
    assert stored == STORED


def test_stored_json_reads_back_unchanged():
    # R-0854, R-0083
    blob = json.dumps(STORED).encode()
    data = diagramjson.loads(blob)
    assert diagramjson.dumps(data) == blob
    assert data["dates"][0] == QtValue("QDateTime", "1998-03-01T00:00:00.000")


def test_a_qt_date_reads_as_qt_did():
    # R-0854
    data = diagramjson.loads(json.dumps(STORED).encode())
    born, timed, empty = data["dates"][:3]
    assert (born.toString("yyyy-MM-dd"), timed.toString("yyyy-MM-ddTHH:mm:ss")) == (
        "1998-03-01",
        "1983-04-09T10:30:05",
    )
    assert [bool(v) for v in (born, empty, *data["geometry"], data["color"])] == [
        True, False, True, True, False, True, True,
    ]


def test_a_pickled_row_written_again_reads_back():
    # R-0854, R-0422
    data = diagramjson.loads(dumps(PICKLED))
    data["symptom"] = VariableShift.Up
    blob = diagramjson.encode(data, dumps(PICKLED))
    assert not diagramjson.is_json(blob)
    assert diagramjson.loads(blob) == data


def test_a_pickle_holding_any_other_class_is_refused():
    # R-0854, R-0453
    with pytest.raises(ValueError, match="collections.OrderedDict"):
        diagramjson.loads(pickle.dumps({"x": collections.OrderedDict()}))


def test_reading_a_diagram_loads_no_qt():
    # R-0854
    code = "import sys, btcopilot.diagramjson, btcopilot.schema; sys.exit('PyQt5' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
