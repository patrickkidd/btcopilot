"""A stand-in of the old Pro database, in the shape it had before the chat app's
columns: no birthdate, no preferences, no current diagram.

One person with one readable record, one record owned by nobody, and one record
that will not open. The stand-in family only; no real name is in here.
"""

import pickle
import sqlite3

WHITLOCK = {"people": [{"name": "Marcus Whitlock", "birth": 1951}]}


def build(path) -> str:
    old = sqlite3.connect(path)
    old.execute(
        "create table users (id integer primary key, username text, active boolean,"
        " status text, roles text, first_name text, last_name text, stripe_id text,"
        " free_diagram_id integer)"
    )
    old.execute(
        "create table diagrams (id integer primary key, user_id integer, name text,"
        " alias text, use_real_names boolean, require_password_for_real_names boolean,"
        " version integer, data blob, created_at datetime, updated_at datetime)"
    )
    old.execute(
        "insert into users values (7, 'marcus@fd362-fixture.invalid', 1, 'confirmed',"
        " 'subscriber', 'Marcus', 'Whitlock', null, 11)"
    )
    old.execute(
        "insert into diagrams values (11, 7, 'The Whitlocks', null, 1, 0, 1, ?,"
        " '2026-01-01 00:00:00', '2026-01-02 00:00:00')",
        (pickle.dumps(WHITLOCK),),
    )
    old.execute(
        "insert into diagrams values (12, 99, 'Nobody''s', null, 1, 0, 1, ?,"
        " '2026-01-01 00:00:00', '2026-01-02 00:00:00')",
        (pickle.dumps(WHITLOCK),),
    )
    old.execute(
        "insert into diagrams values (13, 7, 'Broken', null, 1, 0, 1, x'00ff',"
        " '2026-01-01 00:00:00', '2026-01-02 00:00:00')"
    )
    old.commit()
    old.close()
    return str(path)
