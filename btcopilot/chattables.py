"""The tables the chat app's own database holds.

The chat app runs on its own database and its own migration chain from empty,
separate from the Pro app's production schema (R-0322), and starts over with its
own accounts — old Pro users are imported once, never shared live (R-0327). So
the Pro tables the chat app used to join against are either its own from here
(users, diagrams, licences) or gone (desktop sessions, machines, activations),
and the Training tables are gone with them.

`alembic-chat` creates exactly this set from empty. A test asserts the chain's
output matches what the models declare, so a new column with no revision fails
rather than silently missing from a fresh database.
"""

from sqlalchemy import MetaData, Table

from btcopilot.extensions import db

# Importing the model modules is what registers their tables on db.metadata.
import btcopilot.admin.setting  # noqa: F401
import btcopilot.auth.invitation  # noqa: F401
import btcopilot.auth.logincode  # noqa: F401
import btcopilot.auth.passkey  # noqa: F401
import btcopilot.auth.websession  # noqa: F401
import btcopilot.personal.models  # noqa: F401
import btcopilot.pro.models  # noqa: F401
import btcopilot.review.models  # noqa: F401


TABLES = frozenset(
    {
        "access_rights",
        "admin_settings",
        "diagram_changes",
        "diagram_interactions",
        "diagrams",
        "discussions",
        "invitations",
        "licenses",
        "login_codes",
        "passkeys",
        "policies",
        "review_codings",
        "review_cuts",
        "review_items",
        "review_rules",
        "review_votes",
        "speakers",
        "statements",
        "synthetic_personas",
        "token_meters",
        "users",
        "web_sessions",
    }
)


def tables() -> list[Table]:
    missing = TABLES - set(db.metadata.tables)
    if missing:
        raise KeyError(f"no model declares {sorted(missing)}")
    return [db.metadata.tables[name] for name in sorted(TABLES)]


def metadata() -> MetaData:
    """Only the chat app's tables, so a schema comparison sees what a fresh
    chat database is meant to hold and nothing the Pro app kept."""
    subset = MetaData()
    for table in tables():
        table.to_metadata(subset)
    return subset


def create_all(engine) -> None:
    db.metadata.create_all(engine, tables=tables())
