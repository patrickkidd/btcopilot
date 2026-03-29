"""Restricted pickle deserialization to prevent RCE attacks.

The Pro app uses pickle as its wire format. Standard pickle.loads() will
execute arbitrary code embedded in the payload — a textbook RCE vector.

This module provides restricted unpicklers that only allow known-safe types:

- safe_loads(): For untrusted client request data (builtins only)
- safe_loads_diagram(): For diagram blobs that may contain PyQt5.QtCore types
"""

import io
import pickle
import logging

_log = logging.getLogger(__name__)

# Types that are safe to unpickle from any source
_SAFE_BUILTINS = frozenset(
    {
        "dict",
        "list",
        "set",
        "frozenset",
        "tuple",
        "bytes",
        "bytearray",
        "str",
        "int",
        "float",
        "bool",
        "complex",
        "slice",
        "range",
        "type",
    }
)

# PyQt5.QtCore types used in diagram data (QDate, QDateTime, QPointF, etc.)
# sip._unpickle_type is used internally by PyQt5 for pickle reconstruction
_PYQT5_ALLOWED_MODULES = frozenset(
    {
        "PyQt5.QtCore",
        "sip",
    }
)

# datetime types that may appear in pickled data
_DATETIME_ALLOWED = frozenset(
    {
        "date",
        "datetime",
        "time",
        "timedelta",
        "timezone",
    }
)

# collections types (e.g. OrderedDict) that may appear
_COLLECTIONS_ALLOWED = frozenset(
    {
        "OrderedDict",
    }
)


class _RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that only allows safe builtin types.

    Use for deserializing untrusted client request data where only
    basic Python types (dict, list, str, int, etc.) are expected.
    """

    def find_class(self, module: str, name: str) -> type:
        if module == "builtins" and name in _SAFE_BUILTINS:
            return getattr(__import__(module), name)
        if module == "datetime" and name in _DATETIME_ALLOWED:
            import datetime

            return getattr(datetime, name)
        if module == "collections" and name in _COLLECTIONS_ALLOWED:
            import collections

            return getattr(collections, name)
        raise pickle.UnpicklingError(
            f"Blocked unpickling of {module}.{name} — "
            f"only safe builtins are allowed in request data"
        )


class _DiagramUnpickler(pickle.Unpickler):
    """Unpickler that allows safe builtins + PyQt5.QtCore types.

    Use for deserializing diagram data blobs stored in the database,
    which may contain QDate, QDateTime, QPointF, etc.
    """

    def find_class(self, module: str, name: str) -> type:
        if module == "builtins" and name in _SAFE_BUILTINS:
            return getattr(__import__(module), name)
        if module == "datetime" and name in _DATETIME_ALLOWED:
            import datetime

            return getattr(datetime, name)
        if module == "collections" and name in _COLLECTIONS_ALLOWED:
            import collections

            return getattr(collections, name)
        if module in _PYQT5_ALLOWED_MODULES:
            import importlib

            mod = importlib.import_module(module)
            return getattr(mod, name)
        raise pickle.UnpicklingError(
            f"Blocked unpickling of {module}.{name} — "
            f"only safe builtins and PyQt5.QtCore types are allowed in diagram data"
        )


def safe_loads(data: bytes):
    """Safely deserialize pickle data from untrusted client requests.

    Only allows basic Python types (dict, list, str, int, float, bool, etc.).
    Raises pickle.UnpicklingError if the payload contains disallowed types.
    """
    return _RestrictedUnpickler(io.BytesIO(data)).load()


def safe_loads_diagram(data: bytes):
    """Safely deserialize diagram pickle blobs (database storage).

    Allows basic Python types plus PyQt5.QtCore types (QDate, QDateTime, etc.)
    that are legitimately used in diagram data.
    Raises pickle.UnpicklingError if the payload contains disallowed types.
    """
    return _DiagramUnpickler(io.BytesIO(data)).load()
