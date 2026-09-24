"""The one-shot import of the old Pro accounts and diagrams into the chat app's
own database (R-0327).

The chat app starts over with its own accounts. This reads the old database once
— a restored dump or a live connection string, read-only either way — and writes
each person and each of their diagrams into the new one, converting a pickled
diagram to the stored JSON form on the way.

Run it as a dry run first: it opens every diagram, counts what would be written
and prints every failure with its reason, and writes nothing.

    python -m btcopilot.proimport --source postgresql://.../familydiagram
    python -m btcopilot.proimport --source sqlite:///dump.db --apply

The same module converts this database's own pickled diagram rows to the stored
JSON form in place. Idempotent: rows already in JSON are counted and skipped.

    python -m btcopilot.proimport --rows

Never prints a name or an address: an account is named by its old id.

Passwords do not come across. The chat app signs in by emailed code or passkey,
so the old password hashes have no reader in the new database.
"""

import argparse
import dataclasses
import logging
import pickle
import sys

from sqlalchemy import MetaData, create_engine, select

from btcopilot import diagramjson
from btcopilot.app import create_app
from btcopilot.extensions import db
from btcopilot.models import Diagram, User

_log = logging.getLogger(__name__)

BATCH = 100

USER_FIELDS = [
    "username",
    "active",
    "status",
    "roles",
    "first_name",
    "last_name",
    "birthdate",
    "stripe_id",
]

DIAGRAM_FIELDS = [
    "name",
    "alias",
    "use_real_names",
    "require_password_for_real_names",
    "version",
    "created_at",
    "updated_at",
]


@dataclasses.dataclass
class Count:
    read: int = 0
    written: int = 0
    skipped: int = 0
    failed: int = 0


@dataclasses.dataclass
class Result:
    users: Count = dataclasses.field(default_factory=Count)
    diagrams: Count = dataclasses.field(default_factory=Count)
    failures: list[str] = dataclasses.field(default_factory=list)

    def failed(self, what: str, old_id: int, why: str) -> None:
        self.failures.append(f"{what} {old_id}: {why}")


def rows(connection, table, columns: list[str]) -> list[dict]:
    """Only the columns the old schema actually carries — a dump older than a
    column is normal and the column is simply absent."""
    present = [table.c[name] for name in columns if name in table.c]
    found = connection.execute(select(table.c.id, *present)).mappings().all()
    return [dict(row) for row in found]


def convert(blob: bytes | None) -> bytes | None:
    if blob is None or diagramjson.is_json(blob):
        return blob
    return diagramjson.store(blob)


def run(source: str, apply: bool) -> Result:
    result = Result()
    engine = create_engine(source)
    metadata = MetaData()
    metadata.reflect(engine, only=["users", "diagrams"])
    users, diagrams = metadata.tables["users"], metadata.tables["diagrams"]

    with engine.connect() as connection:
        old_users = rows(connection, users, USER_FIELDS)
        result.users.read = len(old_users)
        new_user_id = {}
        for old in old_users:
            old_id = old.pop("id")
            if db.session.query(User).filter_by(username=old["username"]).count():
                result.users.skipped += 1
                continue
            user = User(**old)
            db.session.add(user)
            db.session.flush()
            new_user_id[old_id] = user.id
            result.users.written += 1

        old_diagrams = rows(connection, diagrams, DIAGRAM_FIELDS + ["user_id"])
        result.diagrams.read = len(old_diagrams)
        new_diagram_id = {}
        for old in old_diagrams:
            old_id = old.pop("id")
            owner = new_user_id.get(old.pop("user_id"))
            if owner is None:
                result.diagrams.skipped += 1
                continue
            blob = connection.execute(
                select(diagrams.c.data).where(diagrams.c.id == old_id)
            ).scalar()
            try:
                data = convert(blob)
            except (
                pickle.UnpicklingError,
                AttributeError,
                KeyError,
                TypeError,
                ValueError,
            ) as exception:
                result.diagrams.failed += 1
                result.failed("diagram", old_id, f"{type(exception).__name__}: {exception}")
                continue
            diagram = Diagram(user_id=owner, data=data, **old)
            db.session.add(diagram)
            db.session.flush()
            new_diagram_id[old_id] = diagram.id
            result.diagrams.written += 1

        _point_at_diagrams(connection, users, new_user_id, new_diagram_id)

    if apply:
        db.session.commit()
    else:
        db.session.rollback()
    return result


def _point_at_diagrams(connection, users, new_user_id, new_diagram_id) -> None:
    """The diagram a person is on and the one they hold free of charge, carried
    over as the new rows' ids."""
    for name in ("free_diagram_id", "current_diagram_id"):
        if name not in users.c:
            continue
        for old_id, pointed in connection.execute(select(users.c.id, users.c[name])):
            user_id = new_user_id.get(old_id)
            if user_id is None or pointed is None:
                continue
            setattr(db.session.get(User, user_id), name, new_diagram_id.get(pointed))


def convert_rows() -> tuple[int, int, int]:
    """Every pickled diagram row in this database, rewritten as JSON: the
    counts converted, skipped and failed."""
    ids = [row[0] for row in db.session.query(Diagram.id).order_by(Diagram.id).all()]
    converted = skipped = failed = 0
    for start in range(0, len(ids), BATCH):
        for diagram_id in ids[start : start + BATCH]:
            diagram = db.session.get(Diagram, diagram_id)
            if not diagram.data or diagramjson.is_json(diagram.data):
                skipped += 1
                continue
            try:
                diagram.data = diagramjson.store(diagram.data)
            except (TypeError, ValueError, KeyError, AttributeError):
                failed += 1
                _log.exception(f"Diagram {diagram_id} did not convert")
                db.session.rollback()
                continue
            converted += 1
        db.session.commit()
    return converted, skipped, failed


def report(result: Result, apply: bool) -> None:
    print(f"{'imported' if apply else 'dry run'}")
    for what, count in (("users", result.users), ("diagrams", result.diagrams)):
        print(
            f"{what}: read={count.read} written={count.written} "
            f"skipped={count.skipped} failed={count.failed}"
        )
    for failure in result.failures:
        print(f"  {failure}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--source", help="the old database's url")
    what.add_argument(
        "--rows", action="store_true", help="convert this database's pickled rows"
    )
    parser.add_argument(
        "--apply", action="store_true", help="write; without it nothing is written"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    with create_app().app_context():
        if args.rows:
            converted, skipped, failed = convert_rows()
            print(f"converted={converted} skipped={skipped} failed={failed}")
            return 1 if failed else 0
        result = run(args.source, args.apply)
    report(result, args.apply)
    return 1 if result.failures else 0


if __name__ == "__main__":
    sys.exit(main())
