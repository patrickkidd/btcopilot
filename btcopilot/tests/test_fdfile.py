import collections
import subprocess
import sys

import pytest

from btcopilot import fdfile
from btcopilot.schema import VariableShift
from btcopilot.tests.fdfixtures import Qt, bundle, dumps, event, scene


def test_qt_values_read_as_plain_values(tmp_path):
    # R-0854
    data = fdfile.read(bundle(tmp_path, scene()))
    assert data["events"][0]["dateTime"] == "1990-05-11"
    assert data["loggedDate"] == "2020-01-01"
    assert data["search_dateStart"] is None
    assert data["centerPoint"] == (0.0, 0.0)
    assert data["pencilColor"] == (0, 0, 0, 255)
    assert data["legendSize"] == (100, 50)


def test_reads_the_pickle_bytes_and_old_enums_as_values():
    # R-0854
    data = fdfile.read(dumps(scene(events=[event(20, "shift", symptom=VariableShift.Up)])))
    assert data["events"][0]["symptom"] == "up"


def test_reader_loads_no_qt():
    # R-0854
    code = "import sys, btcopilot.fdfile; sys.exit('PyQt5' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


def test_unknown_qt_type_fails():
    # R-0854
    with pytest.raises(ValueError, match="PyQt5.QtCore.QRectF"):
        fdfile.read(dumps(scene(rect=Qt("QRectF", 0, 0, 1, 1))))


def test_any_other_class_refused():
    # R-0854
    blob = dumps(scene(order=collections.OrderedDict()))
    with pytest.raises(ValueError, match="collections.OrderedDict"):
        fdfile.read(blob)


@pytest.mark.parametrize("version", ["2.0.12b1", "2.0.12", "1.5.0", None])
def test_file_before_events_moved_out_refused(version):
    # R-0855
    with pytest.raises(ValueError, match="Open it in Family Diagram and save it"):
        fdfile.read(dumps(scene(version=version)))


def test_file_after_events_moved_out_read():
    # R-0855
    assert fdfile.read(dumps(scene(version="2.0.12b2")))["version"] == "2.0.12b2"
