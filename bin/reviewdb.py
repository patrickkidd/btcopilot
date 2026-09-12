#!/usr/bin/env python
"""Bring a sandbox SQLite database up to the review's schema, once.

The sandbox databases were stamped at the same migration revision as the
rename, so alembic will not touch them. This does by hand exactly what that
migration does, and only what is missing, so running it twice is harmless.

    uv run python bin/reviewdb.py /path/to/beta2.db
"""

import os
import sqlite3
import sys

RENAMES = [("changes", "diagram_changes"), ("interactions", "diagram_interactions")]
REVIEW_TABLES = [
    "review_cuts",
    "review_codings",
    "review_items",
    "review_votes",
    "review_rules",
]


def tables(db: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})")}


def rename(db: sqlite3.Connection) -> list[str]:
    done = []
    here = tables(db)
    for old, new in RENAMES:
        if old in here and new not in here:
            db.execute(f"ALTER TABLE {old} RENAME TO {new}")
            done.append(f"{old} → {new}")
    return done


def add_kind(db: sqlite3.Connection) -> list[str]:
    if "discussions" not in tables(db) or "kind" in columns(db, "discussions"):
        return []
    db.execute(
        "ALTER TABLE discussions ADD COLUMN kind VARCHAR(16) NOT NULL DEFAULT 'chat'"
    )
    return ["discussions.kind"]


def create_review(path: str) -> list[str]:
    """The five review tables, from the models themselves."""
    os.environ["FLASK_SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{path}"
    from btcopilot.app import create_app
    from btcopilot.extensions import db

    app = create_app()
    with app.app_context():
        wanted = [
            table
            for name, table in db.metadata.tables.items()
            if name in REVIEW_TABLES
        ]
        missing = [t.name for t in wanted if not _exists(db, t.name)]
        db.metadata.create_all(bind=db.engine, tables=wanted, checkfirst=True)
    return missing


def _exists(db, name: str) -> bool:
    from sqlalchemy import inspect

    return inspect(db.engine).has_table(name)


def main(path: str) -> None:
    if not os.path.exists(path):
        raise SystemExit(f"no database at {path}")
    db = sqlite3.connect(path)
    done = rename(db) + add_kind(db)
    db.commit()
    db.close()
    done += create_review(path)
    print(f"{path}: " + (", ".join(done) if done else "already up to date"))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
