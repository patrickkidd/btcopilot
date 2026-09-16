"""The one-shot read of the old Pro database into this one (R-0327).

The reading and the writing live in btcopilot.proimport; this is only the shape
the command line prints: a line per table with counts in against counts out, and
a line per record that failed, saying why.
"""

import os

from btcopilot import proimport

COLUMNS = ["what", "read", "written", "skipped", "failed", "why"]


def source(dump: str) -> str:
    """A database file, or a connection string to read a live one."""
    if "://" in dump:
        return dump
    if not os.path.exists(dump):
        raise FileNotFoundError(dump)
    return f"sqlite:///{os.path.abspath(dump)}"


def rows(result: proimport.Result) -> tuple[list[str], list[dict]]:
    counted = [
        {
            "what": what,
            "read": count.read,
            "written": count.written,
            "skipped": count.skipped,
            "failed": count.failed,
        }
        for what, count in (("users", result.users), ("diagrams", result.diagrams))
    ]
    named = [
        {"what": failure.split(":")[0], "why": failure.split(":", 1)[1].strip()}
        for failure in result.failures
    ]
    return COLUMNS, counted + named


def dry_run(dump: str) -> tuple[list[str], list[dict]]:
    """Counts in against counts out, and every record that would fail, without
    writing anything."""
    return rows(proimport.run(source(dump), apply=False))


def run(dump: str) -> tuple[list[str], list[dict]]:
    """The same read, writing the users and the converted records."""
    return rows(proimport.run(source(dump), apply=True))
