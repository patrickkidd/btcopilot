"""Who each user is on a case: access_rights.person_id, the person in the
diagram the user is, or empty for someone who is not in the family, such as a
human coach consulting on it (FD-387). Every user on a case has a row, the
owner included, so each diagram gets its owner's row, read-write. A user's
free diagram is theirs: its primary person, or person 1, the one the chat app
makes, when it holds no one yet; one holding people but no primary person is an
imported Pro case, on no one. Any other diagram is on its primary person, or
on no one.

The blob is read here without the app: a row the chat app made is JSON, an
older one a pickle from the Pro app whose Qt values and enums are read as
stand-ins, since only each person's id and primary mark are needed.

Revision ID: 1b00000000c5
Revises: 1b00000000c4
"""

import datetime
import io
import json
import pickle

import sqlalchemy as sa
from alembic import op

revision = "1b00000000c5"
down_revision = "1b00000000c4"
branch_labels = None
depends_on = None

READ_WRITE = "rw"
BATCH = 200


class StandIn:
    """Any value of a class the migration does not import: a Qt value, an enum
    of the app's, anything the Pro app pickled. It takes whatever it is built
    from and holds nothing."""

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return StandIn()

    def __setstate__(self, state):
        pass

    def __setitem__(self, key, value):
        pass

    def append(self, value):
        pass

    def extend(self, values):
        pass


class Reader(pickle.Unpickler):
    KEPT = {
        ("builtins", "set"),
        ("builtins", "frozenset"),
        ("collections", "OrderedDict"),
    }

    def find_class(self, module, name):
        if (module, name) in self.KEPT:
            return super().find_class(module, name)
        return StandIn


def people(blob: bytes | memoryview | None) -> list:
    if not blob:
        return []
    # Postgres hands a bytea back as a memoryview, whose first byte is an int
    blob = bytes(blob)
    if blob[:1] == b"{":
        scene = json.loads(blob.decode("utf-8"))
    else:
        scene = Reader(io.BytesIO(blob)).load()
    found = scene.get("people") if isinstance(scene, dict) else None
    return found if isinstance(found, list) else []


FIRST_PERSON_ID = 1


def primary(found: list) -> int | None:
    for person in found:
        if isinstance(person, dict) and person.get("primary") is True:
            return person.get("id") if isinstance(person.get("id"), int) else None
    return None


def owner_person(blob: bytes | memoryview | None, free: bool) -> int | None:
    found = people(blob)
    chosen = primary(found)
    if chosen is None and free and not found:
        return FIRST_PERSON_ID
    return chosen


def upgrade():
    with op.batch_alter_table("access_rights", schema=None) as batch_op:
        batch_op.add_column(sa.Column("person_id", sa.Integer(), nullable=True))
    bind = op.get_bind()
    rights = sa.table(
        "access_rights",
        sa.column("id", sa.Integer),
        sa.column("created_at", sa.DateTime),
        sa.column("diagram_id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("right", sa.String),
        sa.column("person_id", sa.Integer),
    )
    owned = {
        (diagram_id, user_id)
        for diagram_id, user_id in bind.execute(
            sa.select(rights.c.diagram_id, rights.c.user_id)
        )
    }
    free = {
        row[0]
        for row in bind.execute(
            sa.text(
                "SELECT free_diagram_id FROM users WHERE free_diagram_id IS NOT NULL"
            )
        )
    }
    last = 0
    while True:
        diagrams = bind.execute(
            sa.text(
                "SELECT id, user_id, data FROM diagrams WHERE id > :last ORDER BY id LIMIT :n"
            ),
            {"last": last, "n": BATCH},
        ).all()
        if not diagrams:
            break
        now = datetime.datetime.utcnow()
        for diagram_id, user_id, data in diagrams:
            person_id = owner_person(data, diagram_id in free)
            if (diagram_id, user_id) in owned:
                bind.execute(
                    rights.update()
                    .where(
                        rights.c.diagram_id == diagram_id, rights.c.user_id == user_id
                    )
                    .values(person_id=person_id)
                )
            else:
                bind.execute(
                    rights.insert().values(
                        created_at=now,
                        diagram_id=diagram_id,
                        user_id=user_id,
                        right=READ_WRITE,
                        person_id=person_id,
                    )
                )
        last = diagrams[-1][0]


def downgrade():
    # The owners' rows stay: an owner's access never read them.
    with op.batch_alter_table("access_rights", schema=None) as batch_op:
        batch_op.drop_column("person_id")
