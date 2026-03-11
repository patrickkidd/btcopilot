"""Tests for the restricted pickle deserialization module.

Verifies that:
1. Safe builtin types are allowed
2. Malicious payloads (arbitrary code execution) are blocked
3. Diagram unpickler additionally allows PyQt5.QtCore types
"""

import os
import pickle
import io
import datetime
import collections
import subprocess

import pytest

from btcopilot.pro.safe_pickle import safe_loads, safe_loads_diagram


def _make_exploit_payload(func, args_tuple):
    """Build a pickle payload that calls func(*args_tuple) on deserialization.

    Uses pickle protocol to craft a __reduce__-based exploit payload.
    """

    class _Exploit:
        def __reduce__(self):
            return (func, args_tuple)

    return pickle.dumps(_Exploit())


class TestSafeLoads:
    """Tests for safe_loads (untrusted request data)."""

    def test_allows_dict(self):
        data = pickle.dumps({"key": "value", "num": 42})
        result = safe_loads(data)
        assert result == {"key": "value", "num": 42}

    def test_allows_list(self):
        data = pickle.dumps([1, 2, 3])
        result = safe_loads(data)
        assert result == [1, 2, 3]

    def test_allows_nested_structures(self):
        payload = {
            "username": "test@example.com",
            "password": "secret",
            "licenses": [{"key": "abc-123"}],
            "nested": {"a": [1, 2.0, True, None]},
        }
        data = pickle.dumps(payload)
        result = safe_loads(data)
        assert result == payload

    def test_allows_str(self):
        assert safe_loads(pickle.dumps("hello")) == "hello"

    def test_allows_int(self):
        assert safe_loads(pickle.dumps(42)) == 42

    def test_allows_float(self):
        assert safe_loads(pickle.dumps(3.14)) == 3.14

    def test_allows_bool(self):
        assert safe_loads(pickle.dumps(True)) is True

    def test_allows_none(self):
        assert safe_loads(pickle.dumps(None)) is None

    def test_allows_bytes(self):
        assert safe_loads(pickle.dumps(b"raw")) == b"raw"

    def test_allows_tuple(self):
        assert safe_loads(pickle.dumps((1, 2, 3))) == (1, 2, 3)

    def test_allows_datetime(self):
        dt = datetime.datetime(2026, 3, 11, 12, 0, 0)
        assert safe_loads(pickle.dumps(dt)) == dt

    def test_allows_date(self):
        d = datetime.date(2026, 3, 11)
        assert safe_loads(pickle.dumps(d)) == d

    def test_allows_ordered_dict(self):
        od = collections.OrderedDict([("a", 1), ("b", 2)])
        assert safe_loads(pickle.dumps(od)) == od

    def test_blocks_os_system(self):
        """Verify that os.system() RCE payload is blocked."""
        payload = _make_exploit_payload(os.system, ("echo pwned",))
        with pytest.raises(pickle.UnpicklingError, match="Blocked"):
            safe_loads(payload)

    def test_blocks_subprocess(self):
        """Verify that subprocess.check_output RCE payload is blocked."""
        payload = _make_exploit_payload(subprocess.check_output, (["id"],))
        with pytest.raises(pickle.UnpicklingError, match="Blocked"):
            safe_loads(payload)

    def test_blocks_eval(self):
        """Verify that builtins.eval is blocked (not in safe set)."""
        payload = _make_exploit_payload(eval, ("__import__('os').system('id')",))
        with pytest.raises(pickle.UnpicklingError, match="Blocked"):
            safe_loads(payload)

    def test_blocks_exec(self):
        """Verify that builtins.exec is blocked."""
        payload = _make_exploit_payload(exec, ("import os; os.system('id')",))
        with pytest.raises(pickle.UnpicklingError, match="Blocked"):
            safe_loads(payload)

    def test_blocks_arbitrary_class(self):
        """Verify that arbitrary module classes cannot be instantiated."""
        payload = _make_exploit_payload(os.listdir, (".",))
        with pytest.raises(pickle.UnpicklingError, match="Blocked"):
            safe_loads(payload)

    def test_blocks_pyqt5_in_request_data(self):
        """PyQt5 types should NOT be allowed in untrusted request data."""
        pytest.importorskip("PyQt5.QtCore")
        from PyQt5.QtCore import QDate

        payload = pickle.dumps(QDate(2026, 1, 1))
        with pytest.raises(pickle.UnpicklingError, match="Blocked"):
            safe_loads(payload)

    def test_typical_pro_app_request(self):
        """Simulate a typical Pro app request payload."""
        payload = {
            "username": "patrick@example.com",
            "password": "test123",
            "session": "abc-def-ghi",
            "data": b"\x80\x04\x95...",  # binary diagram data
            "updated_at": datetime.datetime(2026, 3, 11, 10, 0, 0),
            "expected_version": 5,
        }
        data = pickle.dumps(payload)
        result = safe_loads(data)
        assert result["username"] == "patrick@example.com"
        assert result["expected_version"] == 5


class TestSafeLoadsDiagram:
    """Tests for safe_loads_diagram (database diagram blobs)."""

    def test_allows_builtins(self):
        data = pickle.dumps({"items": [1, 2, 3], "name": "test"})
        result = safe_loads_diagram(data)
        assert result == {"items": [1, 2, 3], "name": "test"}

    def test_allows_datetime(self):
        dt = datetime.datetime(2026, 1, 1)
        assert safe_loads_diagram(pickle.dumps(dt)) == dt

    def test_blocks_os_system(self):
        """Verify that os.system() RCE is blocked even for diagram data."""
        payload = _make_exploit_payload(os.system, ("echo pwned",))
        with pytest.raises(pickle.UnpicklingError, match="Blocked"):
            safe_loads_diagram(payload)

    def test_blocks_subprocess(self):
        payload = _make_exploit_payload(subprocess.check_output, (["id"],))
        with pytest.raises(pickle.UnpicklingError, match="Blocked"):
            safe_loads_diagram(payload)

    def test_allows_pyqt5_qtcore(self):
        """PyQt5.QtCore types should be allowed in diagram data."""
        pytest.importorskip("PyQt5.QtCore")
        from PyQt5.QtCore import QDate

        d = QDate(2026, 3, 11)
        data = pickle.dumps(d)
        result = safe_loads_diagram(data)
        assert result == d

    def test_allows_pyqt5_qdatetime(self):
        """PyQt5.QtCore.QDateTime should be allowed in diagram data."""
        pytest.importorskip("PyQt5.QtCore")
        from PyQt5.QtCore import QDateTime

        dt = QDateTime(2026, 3, 11, 12, 0, 0)
        data = pickle.dumps(dt)
        result = safe_loads_diagram(data)
        assert result == dt

    def test_typical_diagram_blob(self):
        """Simulate a typical diagram data blob."""
        blob = {
            "items": [
                {"kind": "Person", "id": 1, "name": "Alice"},
                {"kind": "Person", "id": 2, "name": "Bob"},
            ],
            "lastItemId": 2,
            "pdp": {"people": [], "events": []},
            "people": [],
            "events": [],
            "pair_bonds": [],
        }
        data = pickle.dumps(blob)
        result = safe_loads_diagram(data)
        assert result["lastItemId"] == 2
        assert len(result["items"]) == 2
