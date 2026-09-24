"""Restores a production dump into a throwaway Postgres, runs the chain from the
turn events revision to the newest, and prints expected against seen for what
it must keep true.

  PYTHONPATH=<worktree> uv run python bin/migrationgate.py <pg_dump -Fc file>

Exits non-zero when any check fails. The container is removed either way.
"""
import contextlib
import re
import subprocess
import sys
import time
from pathlib import Path

import sqlalchemy as sa
import yaml
from alembic import command
from alembic.script import ScriptDirectory

from btcopilot.admin.database import config, current
from btcopilot.app import create_app
from btcopilot.models.change import Author
from btcopilot.schema import ItemKind

COMPOSE = Path(__file__).parents[1] / "deploy" / "docker-compose.yml"
REVISION = "1b00000000ab"
USER = "familydiagram"
PASSWORD = "gate"
TOOLED = [ItemKind.Person, ItemKind.PairBond, ItemKind.Event, ItemKind.Cluster]

TURNS = sa.text(
    """
    SELECT s.id,
           s.speaker_id = d.chat_ai_speaker_id AS reply,
           (SELECT count(*) FROM diagram_changes c
             WHERE c.statement_id = s.id AND c.author = :coach
               AND c.turn_id NOT LIKE 'undo:%') AS changes,
           (SELECT count(DISTINCT (c.id, e->>'item_kind', e->>'item_id'))
              FROM diagram_changes c, jsonb_array_elements(c.deltas) e
             WHERE c.statement_id = s.id AND c.author = :coach
               AND c.turn_id NOT LIKE 'undo:%'
               AND e->>'item_kind' = ANY(:tooled)) AS items,
           (SELECT count(*) FROM turn_events t
             WHERE t.turn_id = s.turn_id AND t.kind = 'tool_call') AS lines,
           (SELECT count(*) FROM turn_events t
             WHERE t.turn_id = s.turn_id AND t.kind = 'failed') AS failed
      FROM statements s JOIN discussions d ON d.id = s.discussion_id
    """
)
ORPHANS = {
    "turn events no statement carries": """
        SELECT count(*) FROM turn_events t
         WHERE NOT EXISTS (SELECT 1 FROM statements s WHERE s.turn_id = t.turn_id)""",
    "turn events whose session is missing": """
        SELECT count(*) FROM turn_events t
         WHERE NOT EXISTS (SELECT 1 FROM discussions d WHERE d.id = t.discussion_id)""",
    "turn events in another session than their statement": """
        SELECT count(*) FROM turn_events t JOIN statements s ON s.turn_id = t.turn_id
         WHERE s.discussion_id != t.discussion_id""",
    "statements carrying a turn with no turn events": """
        SELECT count(*) FROM statements s
         WHERE s.turn_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM turn_events t WHERE t.turn_id = s.turn_id)""",
    "change rows pointing at a missing statement": """
        SELECT count(*) FROM diagram_changes c
         WHERE c.statement_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM statements s WHERE s.id = c.statement_id)""",
    "coach change rows no statement claims": """
        SELECT count(*) FROM diagram_changes c
         WHERE c.statement_id IS NULL AND c.author = 'coach'
           AND c.turn_id NOT LIKE 'undo:%'""",
}
DELETABLE = sa.text(
    """
    SELECT d.id, d.user_id FROM discussions d
     WHERE d.chat_user_speaker_id IS NOT NULL
       AND EXISTS (SELECT 1 FROM diagram_changes c JOIN statements s
                     ON s.id = c.statement_id WHERE s.discussion_id = d.id)
     ORDER BY d.id LIMIT 1
    """
)


def docker(*args: str) -> str:
    return subprocess.run(
        ["docker", *args], check=True, stdout=subprocess.PIPE, text=True
    ).stdout.strip()


@contextlib.contextmanager
def postgres():
    image = yaml.safe_load(COMPOSE.read_text())["services"]["fd-postgres"]["image"]
    name = docker(
        "run", "-d",
        "-e", f"POSTGRES_USER={USER}",
        "-e", f"POSTGRES_PASSWORD={PASSWORD}",
        "-e", f"POSTGRES_DB={USER}",
        "-p", "127.0.0.1::5432",
        image,
    )
    try:
        ready = ["docker", "exec", name, "pg_isready", "-q", "-h", "127.0.0.1", "-U", USER]
        for _ in range(60):
            if subprocess.run(ready).returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError(f"{image} did not accept connections in 60s")
        port = docker("port", name, "5432").rsplit(":", 1)[1]
        yield name, f"postgresql://{USER}:{PASSWORD}@127.0.0.1:{port}/{USER}"
    finally:
        docker("rm", "-f", name)


def restore(name: str, dump: Path):
    docker("cp", str(dump), f"{name}:/gate.dump")
    docker(
        "exec", name, "pg_restore", "-U", USER, "-d", USER,
        "--no-owner", "--no-privileges", "--exit-on-error", "/gate.dump",
    )


def counts(conn) -> dict[str, int]:
    return {
        table: conn.execute(sa.text(f'SELECT count(*) FROM "{table}"')).scalar_one()
        for table in sa.inspect(conn).get_table_names()
    }


def turn_checks(conn) -> list[tuple]:
    turns = conn.execute(
        TURNS, {"coach": Author.Coach.value, "tooled": [k.value for k in TOOLED]}
    ).all()
    replies = [t for t in turns if t.reply]
    words = [t for t in turns if not t.reply and t.changes]
    rest = [t for t in turns if not t.reply and not t.changes]
    print(
        f"note: {len(replies)} coach replies hold {sum(t.changes for t in replies)} "
        f"change rows touching {sum(t.items for t in replies)} items; the revision "
        "writes one tool line per item touched, so lines can exceed change rows"
    )
    return [
        ("tool lines on coach replies", sum(t.items for t in replies),
         sum(t.lines for t in replies)),
        ("coach replies whose tool lines equal the items their change rows touched",
         len(replies), sum(t.lines == t.items for t in replies)),
        ("coach replies marked unfinished", 0, sum(t.failed for t in replies)),
        ("failed turns whose words hold their tool lines and one unfinished mark",
         len(words), sum(t.lines == t.items and t.failed == 1 for t in words)),
        ("other statements with tool lines or an unfinished mark", 0,
         sum(t.lines + t.failed for t in rest)),
    ]


def delete_check(app, conn) -> tuple:
    session_id, user_id = conn.execute(DELETABLE).one()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    page = client.get("/app/").get_data(as_text=True)
    token = re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)
    status = client.delete(
        f"/app/sessions/{session_id}", headers={"X-CSRFToken": token}
    ).status_code
    return (f"deleting session {session_id}, which holds change rows (HTTP status)",
            204, status)


def main(dump: Path) -> int:
    with postgres() as (name, uri):
        restore(name, dump)
        app = create_app({"SQLALCHEMY_DATABASE_URI": uri})
        engine = sa.create_engine(uri)
        with app.app_context():
            start = ScriptDirectory.from_config(config()).get_revision(REVISION).down_revision
            if current() != start:
                raise SystemExit(f"dump is at {current()}, not {start}")
            with engine.connect() as conn:
                before = counts(conn)
            command.upgrade(config(), "head")
            with engine.connect() as conn:
                after = counts(conn)
                checks = [(f"rows in {t}", n, after[t]) for t, n in before.items()]
                checks += [(label, 0, conn.execute(sa.text(q)).scalar_one())
                           for label, q in ORPHANS.items()]
                checks += turn_checks(conn)
            with engine.connect() as conn:
                checks.append(delete_check(app, conn))
    for label, expected, seen in checks:
        print(f"{'PASS' if expected == seen else 'FAIL'}  {label}: expected {expected}, seen {seen}")
    return int(any(expected != seen for _, expected, seen in checks))


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
